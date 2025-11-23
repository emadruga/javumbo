# Day 14 Hour 1: Hybrid Frontend Integration Testing Guide

**Objective**: Test deployed stack (S3 + CORS + API Gateway + Lambda) using minimal UI + browser console API calls

---

## Test User Credentials

**Username**: `d14_61467`
**Password**: `testpass123`
**Frontend URL**: http://javumbo-frontend-1763744826.s3-website-us-east-1.amazonaws.com

---

## Part A: Frontend UI Testing (10 minutes)

### Step 1: Login via UI

1. Open frontend URL in browser (incognito/private mode recommended)
2. You should see a login page
3. Enter credentials:
   - Username: `d14_61467`
   - Password: `testpass123`
4. Click "Login"

**Verify:**
- ✅ Login succeeds (no errors)
- ✅ Redirected to `/review` route
- ✅ No console errors in DevTools

---

### Step 2: Check JWT Storage

1. Open DevTools (F12)
2. Go to **Application** tab → **Local Storage** → `http://javumbo-frontend-1763744826.s3-website-us-east-1.amazonaws.com`
3. Find key: `jwt_token`

**Verify:**
- ✅ JWT token exists
- ✅ Value is a long string with 3 parts separated by `.` (e.g., `eyJhbGci...`)

---

### Step 3: Verify CORS (No Console Errors)

1. Go to **Console** tab in DevTools
2. Look for any errors

**Verify:**
- ✅ No CORS errors (no `Access-Control-Allow-Origin` messages)
- ✅ No 404 errors
- ✅ No "Missing Authorization Header" errors

---

### Step 4: Page Refresh Test (JWT Persistence)

1. With DevTools still open, refresh the page (F5 or Ctrl+R)
2. Check **Application** tab → **Local Storage** again

**Verify:**
- ✅ JWT token still exists after refresh
- ✅ Page loads directly to `/review` (no redirect to login)
- ✅ User remains authenticated

---

## Part B: API Testing via Browser Console (30 minutes)

Now we'll test the backend APIs directly from the browser console. This validates CORS, JWT authentication, and session management from a browser origin.

### Setup: Open Console

1. Stay on the frontend page (logged in)
2. Open DevTools → **Console** tab
3. Copy/paste the following code snippets

---

### Test 1: Get Current Decks

```javascript
// Get API URL and token
const API_URL = "https://leap8plbm6.execute-api.us-east-1.amazonaws.com";
const token = localStorage.getItem('jwt_token');

// Fetch decks
const decksResponse = await fetch(`${API_URL}/api/decks`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const decksData = await decksResponse.json();
console.log('Decks:', decksData);
```

**Expected Output:**
```javascript
Decks: [
  { id: 1, name: "Default" },
  { id: 2, name: "Verbal Tenses" }
]
```

**Verify:**
- ✅ Response status: 200
- ✅ Decks array returned
- ✅ No CORS errors

---

### Test 2: Create New Deck

```javascript
const createDeckResponse = await fetch(`${API_URL}/api/decks`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ name: 'Browser Console Test Deck' })
});

const newDeck = await createDeckResponse.json();
console.log('Created Deck:', newDeck);

// Save deck ID for later tests
window.testDeckId = newDeck.id;
window.testSessionId = createDeckResponse.headers.get('X-Session-ID');
console.log('Session ID:', window.testSessionId);
```

**Expected Output:**
```javascript
Created Deck: { id: 1763761500000, name: "Browser Console Test Deck", session_id: "sess_..." }
Session ID: sess_abc123...
```

**Verify:**
- ✅ Response status: 200 or 201
- ✅ Deck created with unique ID
- ✅ `X-Session-ID` header present in response
- ✅ No CORS errors

---

### Test 3: Set Current Deck

```javascript
const setCurrentResponse = await fetch(`${API_URL}/api/decks/current`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Session-ID': window.testSessionId  // Reuse session!
  },
  body: JSON.stringify({ deck_id: window.testDeckId })
});

const currentDeck = await setCurrentResponse.json();
console.log('Current Deck Set:', currentDeck);

// Check if session was reused
const newSessionId = setCurrentResponse.headers.get('X-Session-ID');
console.log('Session Reused?', newSessionId === window.testSessionId ? '✓ YES' : '✗ NO');
```

**Expected Output:**
```javascript
Current Deck Set: { deck_id: 1763761500000, deck_name: "Browser Console Test Deck" }
Session Reused? ✓ YES
```

**Verify:**
- ✅ Response status: 200
- ✅ Current deck updated
- ✅ **CRITICAL**: `X-Session-ID` in response matches previous call (session reuse!)

---

### Test 4: Add Card to Deck

```javascript
const addCardResponse = await fetch(`${API_URL}/api/cards`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-Session-ID': window.testSessionId  // Reuse session
  },
  body: JSON.stringify({
    front: 'Browser Test Front',
    back: 'Browser Test Back'
  })
});

const newCard = await addCardResponse.json();
console.log('Created Card:', newCard);
window.testCardId = newCard.card_id;

// Check session reuse
const cardSessionId = addCardResponse.headers.get('X-Session-ID');
console.log('Session Reused?', cardSessionId === window.testSessionId ? '✓ YES' : '✗ NO');
```

**Expected Output:**
```javascript
Created Card: { note_id: 1763761500001, card_id: 1763761500002, session_id: "sess_..." }
Session Reused? ✓ YES
```

**Verify:**
- ✅ Response status: 200 or 201
- ✅ Card created with note_id and card_id
- ✅ **CRITICAL**: Same session_id (session reused across 3 operations!)

---

### Test 5: Get Card Details

```javascript
const cardResponse = await fetch(`${API_URL}/api/cards/${window.testCardId}`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Session-ID': window.testSessionId  // Reuse session
  }
});

const cardDetails = await cardResponse.json();
console.log('Card Details:', cardDetails);

// Check session reuse
const getSessionId = cardResponse.headers.get('X-Session-ID');
console.log('Session Reused?', getSessionId === window.testSessionId ? '✓ YES' : '✗ NO');
```

**Expected Output:**
```javascript
Card Details: {
  card_id: 1763761500002,
  note_id: 1763761500001,
  front: "Browser Test Front",
  back: "Browser Test Back",
  deck_id: 1763761500000,
  queue: 0,
  due: 1763761500001
}
Session Reused? ✓ YES
```

**Verify:**
- ✅ Response status: 200
- ✅ Card details match what we created
- ✅ **CRITICAL**: Same session_id (4 operations, 1 session!)

---

### Test 6: Get Deck Statistics

```javascript
const statsResponse = await fetch(`${API_URL}/api/decks/${window.testDeckId}/stats`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-Session-ID': window.testSessionId  // Reuse session
  }
});

const stats = await statsResponse.json();
console.log('Deck Stats:', stats);

// Check session reuse
const statsSessionId = statsResponse.headers.get('X-Session-ID');
console.log('Session Reused?', statsSessionId === window.testSessionId ? '✓ YES' : '✗ NO');
```

**Expected Output:**
```javascript
Deck Stats: {
  deck_id: 1763761500000,
  deck_name: "Browser Console Test Deck",
  total_cards: 1,
  new_cards: 1,
  learning_cards: 0,
  due_cards: 0
}
Session Reused? ✓ YES
```

**Verify:**
- ✅ Response status: 200
- ✅ Stats show 1 total card, 1 new card
- ✅ **CRITICAL**: Same session_id (5 operations, 1 session!)

---

### Test 7: Session Flush (Force S3 Upload)

```javascript
const flushResponse = await fetch(`${API_URL}/api/session/flush`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ session_id: window.testSessionId })
});

const flushResult = await flushResponse.json();
console.log('Session Flush:', flushResult);
```

**Expected Output:**
```javascript
Session Flush: { message: "Session flushed successfully", username: "d14_61467" }
```

**Verify:**
- ✅ Response status: 200
- ✅ Session flushed (DB uploaded to S3)

---

### Test 8: Export Collection

```javascript
const exportResponse = await fetch(`${API_URL}/api/export`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// This will download a binary .apkg file
const blob = await exportResponse.blob();
console.log('Export Size:', blob.size, 'bytes');

// Create download link
const url = window.URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'd14_61467_export.apkg';
document.body.appendChild(a);
a.click();
a.remove();

console.log('✓ Export file downloaded!');
```

**Expected Output:**
```javascript
Export Size: 15000 bytes (approx 15 KB)
✓ Export file downloaded!
```

**Verify:**
- ✅ Response status: 200
- ✅ File downloads to browser
- ✅ File size: 10-20 KB (reasonable for small collection)

---

## Test Summary & Metrics

After completing all tests, fill in this table:

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| **Login via UI** | Success | _____ | ⬜ |
| **JWT Storage** | Token exists | _____ | ⬜ |
| **CORS Errors** | 0 errors | _____ | ⬜ |
| **JWT Persistence** | Token persists | _____ | ⬜ |
| **Get Decks** | 200, decks array | _____ | ⬜ |
| **Create Deck** | 201, session_id | _____ | ⬜ |
| **Set Current Deck** | 200, session reused | _____ | ⬜ |
| **Add Card** | 201, session reused | _____ | ⬜ |
| **Get Card Details** | 200, session reused | _____ | ⬜ |
| **Deck Stats** | 200, session reused | _____ | ⬜ |
| **Session Flush** | 200, flushed | _____ | ⬜ |
| **Export** | 200, file downloads | _____ | ⬜ |

---

## Critical Metrics

**Session Reuse Validation** (THE KEY METRIC):
- Total operations: 6 (create deck → set current → add card → get card → get stats → flush)
- Expected session_id: **Same across all 5 operations** (before flush)
- Actual session_id count: _____ (fill this in)

**Expected:** All 5 operations use the same `X-Session-ID` header (proves session caching works from browser)

---

## Hour 1 Success Criteria

✅ **ALL must be TRUE:**

1. ✅ Login via UI successful (JWT stored)
2. ✅ JWT persists across page refresh
3. ✅ Zero CORS errors in console
4. ✅ All 8 console tests passed (200 responses)
5. ✅ **Session reused across 5 operations** (same session_id)
6. ✅ Export file downloads successfully
7. ✅ No authentication errors (JWT working)

**If all criteria met:** Hour 1 PASSED ✅
**If any fail:** Document issue and investigate

---

## Next Steps

After Hour 1 completion:
- **Hour 2**: Automated E2E testing (Python script simulating browser behavior)
- **Hour 3**: Production readiness assessment (monitoring, security, cost)
- **Hour 4**: Week 3 retrospective documentation
