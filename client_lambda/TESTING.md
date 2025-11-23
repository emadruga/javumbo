# Day 8 Testing Guide: Frontend Session Management

## Prerequisites

1. **Backend running**: Ensure `server_lambda` backend is deployed and accessible
   - Local: `http://localhost:3000` (via SAM local)
   - AWS: `https://m2y2z7nv3b.execute-api.us-east-1.amazonaws.com`

2. **Test user exists**: Register a test user via backend (or use existing)
   - Username: `test_user`
   - Password: `password123`

3. **Test deck exists**: User should have at least 1 deck with 5+ cards due for review

## Setup

```bash
cd /Users/emadruga/proj/javumbo/client_lambda

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend should start at `http://localhost:5173`

---

## Manual Test Checklist

### Test 1: Basic Session Flow ✅

**Steps:**
1. Open browser DevTools → Network tab
2. Navigate to `http://localhost:5173`
3. Login with test credentials
4. Verify redirect to ReviewPage

**Expected:**
- POST `/login` returns `{ token: "...", user: {...} }`
- JWT stored in localStorage
- Redirect to `/review`

---

### Test 2: Session Creation on ReviewPage Mount ✅

**Steps:**
1. After login, observe ReviewPage load
2. Check Network tab for:
   - POST `/api/session/start` → returns `{ session_id: "sess_..." }`
   - GET `/review` with headers:
     - `Authorization: Bearer <token>`
     - `X-Session-ID: sess_...`

**Expected:**
- ✅ Session indicator appears (green dot + "Session active")
- ✅ First card loads
- ✅ Timer shows "5:00 remaining"
- ✅ Console logs: `[useDBSession] ✓ Session started: sess_...`

---

### Test 3: Session Reuse Across Multiple Cards ✅

**Steps:**
1. Review 5 cards in a row:
   - Click "Show Answer"
   - Click "Good (3)"
   - Repeat for next card
2. Monitor Network tab

**Expected:**
- ✅ POST `/answer` requests include `X-Session-ID` header (SAME session ID)
- ✅ GET `/review` requests include `X-Session-ID` header (SAME session ID)
- ✅ NO new POST `/api/session/start` calls (session is reused)
- ✅ Session indicator timer resets on each request (activity tracking works)

**KEY METRIC:**
- **5 cards reviewed = 1 session start + 10 API calls (5 GET /review + 5 POST /answer)**
- **NO session restart between cards** (this is the optimization!)

---

### Test 4: CloudWatch Verification (S3 Operations) ✅

**Steps:**
1. Complete Test 3 (review 5 cards)
2. Navigate back to Decks page (this ends session)
3. Check AWS CloudWatch Logs for Lambda function

**Expected S3 Operations:**
- ✅ **1 S3 GET** (on session start) - download DB from S3
- ✅ **1 S3 PUT** (on session end) - upload DB to S3
- ✅ **Total: 2 S3 operations** (not 10)

**Without sessions (original behavior):**
- Would be: 5 GET + 5 PUT = **10 S3 operations**
- **Reduction: 80%**

---

### Test 5: Session Timeout (Idle 5 Minutes) ✅

**Steps:**
1. Start review session
2. Review 1 card
3. Wait 5 minutes (do NOT click anything)
4. Observe session indicator timer count down to 0:00

**Expected:**
- ✅ Timer shows countdown: 5:00 → 4:59 → ... → 0:00
- ✅ At 0:00, session auto-flushes (check console logs)
- ✅ POST `/api/session/flush` called automatically
- ✅ Session indicator disappears
- ✅ Next card fetch creates NEW session

---

### Test 6: Manual Flush ("Save Now" Button) ✅

**Steps:**
1. Start review session
2. Review 2 cards
3. Click "Save Now" button in session indicator
4. Monitor Network tab

**Expected:**
- ✅ POST `/api/session/flush` called immediately
- ✅ Console logs: `[useDBSession] Flushing session ...`
- ✅ New session created automatically after flush
- ✅ User can continue reviewing cards without interruption

---

### Test 7: Session Cleanup on Page Navigation ✅

**Steps:**
1. Start review session
2. Review 2 cards
3. Click "Back to Decks" button
4. Monitor Network tab

**Expected:**
- ✅ POST `/api/session/flush` called on unmount
- ✅ Session cleaned up (sessionStorage cleared)
- ✅ Console logs: `[ReviewPage] Component unmounting, ending session...`

---

### Test 8: Multi-Tab Conflict Detection 🚨

**Steps:**
1. Open browser tab 1 → login → start review session
2. Open browser tab 2 → login (same user) → navigate to review page
3. Tab 2 should detect existing session

**Expected:**
- ✅ Tab 2 shows alert: "Active session detected on another tab/device"
- ✅ Tab 2 does NOT create new session (409 Conflict)
- ✅ User must close Tab 1 or wait for session timeout

**CRITICAL:** This prevents data corruption from concurrent writes.

---

### Test 9: Session Persistence Across Page Refresh ✅

**Steps:**
1. Start review session
2. Review 2 cards
3. Press F5 (refresh page)
4. Check sessionStorage in DevTools

**Expected:**
- ✅ Session ID persists in sessionStorage
- ✅ ReviewPage attempts to resume session
- ✅ If session expired, creates new session
- ✅ If session valid, continues with existing session

**DESIGN DECISION:** We use `sessionStorage` (not `localStorage`) so session dies when tab closes.

---

### Test 10: Error Handling - JWT Expiration ⚠️

**Steps:**
1. Login and start review session
2. Wait for JWT to expire (or manually delete JWT from localStorage)
3. Try to review a card

**Expected:**
- ✅ Backend returns 401 Unauthorized
- ✅ Axios interceptor catches 401
- ✅ User redirected to login page
- ✅ Console logs: `[axios] 401 Unauthorized - JWT expired`

---

## Success Criteria (All Must Pass)

- [ ] Test 1: Login works, JWT stored
- [ ] Test 2: Session created on ReviewPage mount
- [ ] Test 3: Same session used for multiple cards (no restart)
- [ ] Test 4: CloudWatch shows 1 download + 1 upload (not 5 + 5)
- [ ] Test 5: Session auto-flushes after 5min idle
- [ ] Test 6: "Save Now" button works
- [ ] Test 7: Session ends on page navigation
- [ ] Test 8: Multi-tab conflict detected and prevented
- [ ] Test 9: Session survives page refresh (if within TTL)
- [ ] Test 10: JWT expiration handled gracefully

---

## Key Metrics to Record

After running all tests, document:

1. **S3 Operations Reduction:**
   - Before: X downloads + X uploads (per session)
   - After: 1 download + 1 upload (per session)
   - Reduction: Y%

2. **Average Review Latency:**
   - First card: ~500ms (cold start + session creation)
   - Subsequent cards: ~100ms (warm, no S3 download)

3. **Session Hit Rate:**
   - Total operations: N
   - Session reuses: M
   - Hit rate: (M / N) × 100%

---

## Troubleshooting

### Issue: "No JWT token found"
**Fix:** Ensure `/login` endpoint returns `{ token: "..." }` in response body.

### Issue: "Session conflict (409)"
**Fix:** Clear all sessionStorage/localStorage and try again. Or wait 5min for old session to expire.

### Issue: "CORS error"
**Fix:** Backend must have CORS enabled for frontend origin:
```python
# In server_lambda/src/app.py
from flask_cors import CORS
CORS(app, origins=['http://localhost:5173'])
```

### Issue: Session indicator not showing
**Fix:** Check console for errors. Verify `useDBSession` hook is called correctly.

---

## Next Steps After Testing

If all tests pass, update `REFACTOR_WEEK_2.md` with:
- Day 8 completion status ✅
- Test results and metrics
- Screenshots (optional)
- Any issues encountered and how they were resolved
