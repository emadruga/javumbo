# Day 14: Manual Frontend Integration Testing

**Date**: 2025-11-21
**Objective**: Validate complete deployed stack (S3 Static Website + API Gateway + Lambda + DynamoDB + S3)

---

## Test Environment

**Frontend URL**: http://javumbo-frontend-1763744826.s3-website-us-east-1.amazonaws.com
**API Gateway URL**: https://leap8plbm6.execute-api.us-east-1.amazonaws.com
**CORS Configuration**: ✅ Verified (allows all origins, X-Session-ID header, Authorization header)

---

## Manual Testing Checklist

### Pre-Test Setup
- [ ] Open Chrome/Firefox in Incognito/Private mode (clean slate)
- [ ] Open DevTools (F12):
  - **Console Tab**: Watch for errors
  - **Network Tab**: Monitor API calls and headers
  - **Application Tab → Local Storage**: Watch JWT storage

### Test Flow (Step-by-Step)

#### 1. Navigation & App Load
- [ ] Navigate to: http://javumbo-frontend-1763744826.s3-website-us-east-1.amazonaws.com
- [ ] **Verify**: Page loads without errors
- [ ] **Verify**: No console errors
- [ ] **Verify**: Login/Register form visible

**Expected Result**: React app loads, shows authentication page

---

#### 2. User Registration
- [ ] Click "Register" (or navigate to registration page)
- [ ] Enter test credentials:
  - **Username**: `day14_manual_<timestamp>` (e.g., `day14_manual_1763740000`)
  - **Name**: `Day 14 Test User`
  - **Password**: `testpass123`
- [ ] Click "Register" button
- [ ] **Monitor Network Tab**:
  - Request to `/register` endpoint
  - Response status: `200` or `201`
- [ ] **Verify**: Registration succeeds
- [ ] **Verify**: Redirected to dashboard or login page

**Expected Result**: User account created, success message displayed

---

#### 3. User Login
- [ ] Enter credentials:
  - **Username**: `day14_manual_<timestamp>`
  - **Password**: `testpass123`
- [ ] Click "Login" button
- [ ] **Monitor Network Tab**:
  - Request to `/login` endpoint
  - Response contains `access_token`
- [ ] **Monitor Application Tab → Local Storage**:
  - Key: `jwt_token` or `access_token`
  - Value: Long JWT string (e.g., `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`)
- [ ] **Verify**: JWT token stored in localStorage
- [ ] **Verify**: Redirected to dashboard/decks page

**Expected Result**: Login successful, JWT persisted, dashboard visible

---

#### 4. Create Deck
- [ ] Navigate to "Decks" page (if not already there)
- [ ] Click "Create Deck" or "Add Deck" button
- [ ] Enter deck name: **"Day 14 Test Deck"**
- [ ] Click "Save" or "Create"
- [ ] **Monitor Network Tab**:
  - Request to `POST /api/decks`
  - Headers include: `Authorization: Bearer <token>`, `X-Session-ID: sess_...` (if session created)
  - Response: `{"id": 1763740123456, "name": "Day 14 Test Deck", ...}`
- [ ] **Verify**: Deck appears in deck list
- [ ] **Verify**: No console errors

**Expected Result**: Deck created, visible in list

---

#### 5. Add Cards (3 cards)
- [ ] Select "Day 14 Test Deck" (set as current or navigate to "Add Card" page)
- [ ] **Card 1**:
  - Front: `Test Front 1`
  - Back: `Test Back 1`
  - Click "Save" or "Add Card"
- [ ] **Card 2**:
  - Front: `Test Front 2`
  - Back: `Test Back 2`
  - Click "Save"
- [ ] **Card 3**:
  - Front: `Test Front 3`
  - Back: `Test Back 3`
  - Click "Save"
- [ ] **Monitor Network Tab**:
  - 3 requests to `POST /api/cards`
  - **CRITICAL**: Check if `X-Session-ID` header is present and **same across all 3 requests** (session reuse)
  - Response for each: `{"note_id": ..., "card_id": ..., "session_id": "sess_..."}`
- [ ] **Verify**: All 3 cards added successfully
- [ ] **Verify**: Cards visible in deck (navigate to card list page)

**Expected Result**: 3 cards created, session reused (same session_id)

---

#### 6. Review Session (5 cards)
- [ ] Navigate to "Review" page or click "Study Deck" for "Day 14 Test Deck"
- [ ] **Verify**: Session indicator appears (if implemented in frontend)
  - Green dot with "Session Active" or countdown timer
- [ ] **Review Flow** (repeat 5 times):
  - **Card Display**: Front shown first
  - Click "Show Answer" or flip card
  - **Card Back**: Back content displayed
  - Click rating button: **"Good" (3)** or **"Easy" (4)**
  - Next card loads
- [ ] **Monitor Network Tab** (CRITICAL):
  - **First card**: `GET /api/review` - May trigger S3 download (cold start) or session creation
  - **Subsequent cards**: `GET /api/review` - Should show **same `X-Session-ID` header** (session reuse)
  - **Card submissions**: `POST /api/review` - Should show **same `X-Session-ID`** across all 5 reviews
- [ ] **Monitor Session Indicator**:
  - Timer resets after each review (activity tracking)
  - Session remains active throughout
- [ ] **Verify**: All 5 cards reviewed successfully
- [ ] **Verify**: No console errors

**Expected Result**: 5 cards reviewed, session reused (10 API calls = 1 session_id)

---

#### 7. Check Deck Statistics
- [ ] Navigate to "Statistics" page or "Deck Stats" for "Day 14 Test Deck"
- [ ] **Monitor Network Tab**:
  - Request to `GET /api/decks/<deck_id>/stats`
  - Response includes card counts: `{"new_cards": X, "learning_cards": 5, "total_cards": ...}`
- [ ] **Verify**:
  - Total cards: Should reflect 3 added cards + any default cards (e.g., Verbal Tenses = 108 total if included)
  - Learning cards: Should show 5 (just reviewed)
  - New cards: Should decrease by 5 (e.g., 108 → 103)
- [ ] **Verify**: Stats update correctly after reviews

**Expected Result**: Stats accurate, reflect reviewed cards

---

#### 8. Export Collection
- [ ] Navigate to "Export" page or click "Export Collection" button
- [ ] Click "Download .apkg" or "Export" button
- [ ] **Monitor Network Tab**:
  - Request to `GET /api/export`
  - Response: Binary data (Content-Type: `application/zip`)
  - **Response Headers**: Check for `X-Session-ID` (session reuse)
- [ ] **Verify**: Browser downloads file
- [ ] **File Name**: Should be `day14_manual_<timestamp>_export_<timestamp>.apkg`
- [ ] **File Size**: Should be 10-20 KB (small collection)
- [ ] **Verify**: No console errors during export

**Expected Result**: .apkg file downloaded successfully

---

#### 9. Validate Exported File (Optional - Desktop Anki)
- [ ] Open Anki desktop application
- [ ] File → Import
- [ ] Select downloaded `.apkg` file
- [ ] **Verify**: Import succeeds
- [ ] **Verify**: "Day 14 Test Deck" appears in Anki deck list
- [ ] **Verify**: 3 cards visible in Anki (or total cards if Verbal Tenses included)
- [ ] **Verify**: Card front/back content matches

**Expected Result**: .apkg file is valid Anki format, imports correctly

---

#### 10. JWT Persistence (Page Refresh)
- [ ] **Without logging out**, refresh the page (F5 or Ctrl+R)
- [ ] **Monitor Application Tab → Local Storage**:
  - `jwt_token` should still be present
- [ ] **Verify**: Page loads directly to dashboard (no redirect to login)
- [ ] **Verify**: User remains authenticated
- [ ] Click around (decks, cards, stats) - all pages should work without re-login

**Expected Result**: JWT persists, user stays logged in after refresh

---

#### 11. Session Cleanup (Close Tab Warning)
- [ ] Attempt to close the browser tab (click X on tab)
- [ ] **Verify**: Browser shows `beforeunload` warning (if implemented):
  - "You have an active session. Changes will be saved when you close this tab."
- [ ] **Option 1**: Cancel close, verify session still active
- [ ] **Option 2**: Confirm close, re-open tab, verify data persisted

**Expected Result**: Warning shown for active sessions (UX improvement)

---

## Critical Checks (DevTools Analysis)

### Console Tab
- ✅ **No CORS errors**: No `Access-Control-Allow-Origin` errors
- ✅ **No 404 errors**: All API endpoints resolve correctly
- ✅ **No JWT errors**: No "Missing Authorization Header" or "Token expired" messages
- ✅ **No session errors**: No "Session conflict" or "Session expired" warnings

### Network Tab
- ✅ **API Gateway URL**: All requests go to `https://leap8plbm6.execute-api.us-east-1.amazonaws.com`
- ✅ **Authorization Header**: Present on all authenticated requests (`Bearer <token>`)
- ✅ **X-Session-ID Header**:
  - **First operation**: Missing or new session_id created
  - **Subsequent operations**: Same session_id reused (THIS IS THE KEY METRIC)
- ✅ **Response Status Codes**:
  - Registration: `200` or `201`
  - Login: `200`
  - CRUD operations: `200` or `201`
  - Export: `200`
  - Errors: `400` (bad request), `401` (unauthorized), `404` (not found)

### Application Tab (Local Storage)
- ✅ **JWT Token**:
  - Key: `jwt_token` or `access_token`
  - Value: Valid JWT string (3 parts separated by `.`)
  - Persists after page refresh
- ✅ **Session ID** (if stored):
  - Key: `session_id` or stored in sessionStorage
  - Value: `sess_<hex_string>`

---

## Success Criteria

**All must be TRUE to declare Hour 1 PASSED:**

1. ✅ Frontend loads without errors (React app renders)
2. ✅ User registration works (account created in DynamoDB)
3. ✅ User login works (JWT returned and stored)
4. ✅ JWT persists across page refresh (localStorage working)
5. ✅ Deck creation works (deck appears in list)
6. ✅ Card addition works (3 cards created)
7. ✅ Review session works (5 cards reviewed)
8. ✅ **Session reuse validated**: Same `X-Session-ID` across multiple operations (network tab proof)
9. ✅ Stats update correctly (card counts reflect reviews)
10. ✅ Export works (.apkg file downloads)
11. ✅ No CORS errors in console
12. ✅ No 404 errors (all endpoints exist)
13. ✅ No JWT authentication errors

---

## Metrics to Record

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| **Page Load Time** | <2s | ___ | ⬜ |
| **Registration Time** | <3s | ___ | ⬜ |
| **Login Time** | <2s | ___ | ⬜ |
| **Deck Creation Time** | <1s | ___ | ⬜ |
| **Card Addition (avg)** | <1s | ___ | ⬜ |
| **Review Latency (first)** | <2s | ___ | ⬜ |
| **Review Latency (avg)** | <1s | ___ | ⬜ |
| **Export Time** | <2s | ___ | ⬜ |
| **Session Reuse Count** | 10+ ops | ___ | ⬜ |
| **Console Errors** | 0 | ___ | ⬜ |
| **CORS Errors** | 0 | ___ | ⬜ |

---

## Issues Found (To Be Documented)

| Issue | Severity | Description | Impact | Fix Required |
|-------|----------|-------------|--------|--------------|
| | | | | |
| | | | | |

---

## Next Steps

After completing manual testing:
1. Document any issues found in table above
2. Take screenshots of:
   - Network tab showing session_id reuse
   - Local Storage showing JWT token
   - Console tab (should be error-free)
3. Proceed to **Hour 2**: Automated browser testing (Selenium/Playwright)
