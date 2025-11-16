# Lost Cards Issue - Reproduction Plan

## Summary of Issue (from Gabrielle, User ID 50)

**Symptom**: User reported that flashcards she created were "lost" or invisible.

**Evidence from logs/database analysis**:
- User created 45 cards total (all successfully saved to database)
- Started creating duplicate cards 25 minutes after initial session
- Created the same card up to 4 times (e.g., "Algorithms" card)
- Cards were in the database the whole time - never deleted
- User re-logged in during the session (possibly trying to fix the issue)

**Root cause hypothesis**: Cards were NOT visible in the UI card list, even though they existed in the database. This is likely a frontend caching, state management, or API response issue - NOT a database or session problem.

---

## Key Observations from Log Analysis

### Timeline of Gabrielle's Session (July 4, 2025):

```
16:48-16:58  Created 30 cards in default deck (ID: 1)
17:00-17:04  Switched between decks multiple times (6+ switches)
17:03        Created 2 cards in "The IA" deck (1751658410042)
[25 min gap]
17:29-17:36  Created 7 DUPLICATE cards (same content as 16:55-16:57 cards)
[gap]
18:31-18:45  Created 6 more DUPLICATES
18:41-18:42  User RE-LOGGED IN (trying to fix issue?)
18:45        Created ANOTHER duplicate
```

### Critical Patterns:
1. **Deck switching**: Heavy deck switching activity before issue appeared
2. **Time gap**: 25-minute inactivity period
3. **Multi-worker environment**: Different Gunicorn workers (491316, 491318, 491319)
4. **Duplicates from END of session**: She recreated cards from 16:55-16:57 (last few she created)
5. **Re-login didn't fix it**: Even after logging in again, issue persisted

---

## Reproduction Scenarios

### **SCENARIO A: Deck Switching Race Condition (HIGHEST PRIORITY)**

**Hypothesis**: When switching decks rapidly or creating cards while switching, the frontend loses track of which deck's cards to display.

**Steps**:
1. Login as test user
2. Open browser DevTools (Network tab)
3. Create 10-15 cards in default deck
4. Click "View Cards" to confirm they appear
5. Create a new deck ("Test Deck A")
6. Switch to "Test Deck A"
7. Switch back to default deck immediately
8. Create 2-3 more cards in default deck
9. Switch to "Test Deck A" again
10. Switch back to default deck
11. Refresh the card list OR navigate away and back

**Expected**: All cards should be visible
**Bug if**: Some or all cards disappear from the list

**Monitoring**:
- Check Network tab for `/decks/<id>/cards` requests
- Check browser console for errors
- Check if pagination shows correct total
- Verify `localStorage` currentDeckName value

---

### **SCENARIO B: Add Card Navigation + Deck Context Loss**

**Hypothesis**: When adding a card after switching decks, the UI might lose context of which deck to display.

**Steps**:
1. Create 5 cards in default deck
2. View the cards (confirm they appear)
3. Create a new deck "Test Deck B"
4. Click "Add Card" from the default deck dropdown
5. Add a card (should go to default deck)
6. Navigate back to Decks page
7. Click "View Cards" on default deck

**Expected**: All 6 cards visible
**Bug if**: Only see 1 card or none

**Check**:
- What deck ID is set in backend's `col.conf.curDeck`?
- Does frontend have the right `selectedDeck` state?
- Does `localStorage.currentDeckName` match?

---

### **SCENARIO C: Session/Cache Timeout**

**Hypothesis**: After inactivity, the frontend cache becomes stale or API responses change.

**Steps**:
1. Create 10 cards in default deck
2. View cards (confirm all 10 appear)
3. Leave browser tab open but idle for 30 minutes
4. Return to tab and click "View Cards" or refresh card list

**Expected**: All 10 cards still visible
**Bug if**: Card list empty or shows fewer cards

**Monitoring**:
- Check if session cookie expired
- Check Network tab for 401 responses
- Check if card count in pagination is correct but cards array is empty

---

### **SCENARIO D: Multi-Tab State Desync**

**Hypothesis**: Having multiple tabs open causes state desynchronization.

**Steps**:
1. Open app in Tab 1, login
2. Create 5 cards in default deck (Tab 1)
3. Open app in Tab 2 (same browser, same user)
4. In Tab 2, create a new deck and switch to it
5. In Tab 2, create 3 cards in new deck
6. Go back to Tab 1
7. Try to view cards in default deck

**Expected**: Default deck shows 5 cards
**Bug if**: Shows 0 cards or wrong cards

---

### **SCENARIO E: Rapid Deck Operations + Page Navigation**

**Hypothesis**: Rapid operations cause race conditions in state updates.

**Steps**:
1. Create 8 cards in default deck
2. Create new deck "Deck X"
3. Quickly do these actions (< 2 seconds between each):
   - Switch to Deck X
   - Switch back to default
   - Click "View Cards" on default
   - Click back
   - Switch to Deck X again
   - Switch to default again
4. Click "View Cards" on default deck

**Expected**: All 8 cards visible
**Bug if**: Cards missing or list empty

---

## Code Areas to Investigate

### Backend (`server/app.py`):
1. **`set_current_deck()` (line 2008)**: Updates `col.conf.curDeck`
2. **`get_deck_cards()` (line 2497)**: Fetches cards for a deck with pagination
   - Relies on `deckId` parameter from URL
   - Does NOT use `session` state or `col.conf.curDeck`
   - Could there be a mismatch?

### Frontend (`client/src/pages/DecksPage.jsx`):
1. **`handleSelectDeck()` (line 396)**: Calls backend to set current deck
2. **`handleAddCard()` (line 274)**: Sets current deck before navigating to add page
3. **`fetchCards()` (line 343)**: Fetches cards for display
   - Uses `getDeckCards(deckId, page)` API call
   - Updates `selectedDeck` state from response
   - Stores `currentDeckName` in `localStorage`

### Potential Issues:
1. **State desync**: `selectedDeck` state vs backend `curDeck` vs `localStorage`
2. **Race condition**: Multiple `setCurrentDeck` calls in quick succession
3. **Cache**: Frontend caching old card list
4. **Pagination bug**: Page number persisting across deck switches
5. **No refresh trigger**: After adding card, list doesn't auto-refresh

---

## Automated Test Script

Create a test script in `server/test_race_condition/` that:
1. Registers a test user
2. Creates 10 cards via API
3. Creates a new deck
4. Rapidly switches current deck 10 times
5. Fetches card list
6. Asserts all 10 cards are returned
7. Adds 5 more cards
8. Switches decks again
9. Fetches card list
10. Asserts all 15 cards are returned

---

## Logging Improvements

Add these log statements to help diagnose:

### Backend:
```python
# In get_deck_cards()
app.logger.info(f"Fetching cards for deck {deckId}, page {page}, user {user_id}")
app.logger.info(f"Found {total_cards} total cards in deck {deckId}")
app.logger.info(f"Returning {len(cards_data)} cards for page {page}")

# In set_current_deck()
app.logger.info(f"Switching deck: user {user_id}, old deck: {conf_dict.get('curDeck')}, new deck: {deck_id}")
```

### Frontend:
```javascript
// In fetchCards()
console.log(`[fetchCards] Requesting deck ${deckId}, page ${page}`);
console.log(`[fetchCards] Response:`, response);

// In handleSelectDeck()
console.log(`[handleSelectDeck] Switching to deck ${deckId} (${deckName})`);
```

---

## Success Criteria

The issue is **RESOLVED** when:
1. All reproduction scenarios pass without losing cards
2. Duplicate cards are not created
3. Card list always shows correct count matching database
4. Rapid deck switching doesn't cause state issues
5. Multi-tab usage doesn't cause desyncs

---

## Next Steps

1. **Manual testing**: Start with Scenario A (highest priority)
2. **Add instrumentation**: Add logging to backend and frontend
3. **Create automated test**: Build test script for continuous testing
4. **Deploy to test environment**: Test with multiple concurrent users
5. **Monitor production**: After fix, monitor for duplicate card creation patterns
