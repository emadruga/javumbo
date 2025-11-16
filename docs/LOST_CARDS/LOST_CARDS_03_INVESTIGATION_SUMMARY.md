# Lost Cards Issue - Investigation Summary

**Date**: November 13, 2025
**Investigator**: Analysis of Gabrielle (User ID 50) logs and database
**Log File**: `logs/julho2025-logs.txt`
**Database**: `logs/user_50.db`
**Incident Date**: July 4-7, 2025

---

## Executive Summary

User Gabrielle reported that flashcards she created were "lost". Analysis of application logs and her database revealed that **no cards were actually lost from the database**. Instead, the cards were invisible in the UI, causing her to recreate the same cards multiple times (up to 4 duplicates).

**Root Cause**: The card list UI failed to display existing cards, likely due to a frontend state management issue related to deck switching operations.

**Impact**: User created 45 unique cards but ended up with duplicates, suggesting she couldn't see what she had already created.

---

## Investigation Methodology

### Hypothesis Testing Approach

**Hypothesis 1**: Cards were created but lost due to race condition/database issue
✅ **REJECTED** - All 45 logged card insertions exist in the database

**Hypothesis 2**: User created cards that never got logged (silent failure)
✅ **REJECTED** - No errors in logs; perfect 1:1 match between logged and stored cards

**Hypothesis 3**: Cards were deleted (by user or by bug)
✅ **REJECTED** - `graves` table is empty (no deletion records)

**Hypothesis 4**: Cards existed but were invisible to the user
✅ **CONFIRMED** - User recreated identical cards multiple times

---

## Evidence

### Card Creation Timeline

| Time Period | Activity | Cards Created | Notes |
|------------|----------|---------------|-------|
| 16:48-16:58 | Initial session | 30 cards | Default deck (ID: 1) |
| 17:00-17:04 | Deck switching | 2 cards | "The IA" deck (ID: 1751658410042) |
| 17:03-17:29 | **25-minute gap** | 0 cards | No activity |
| 17:29-17:36 | Resume session | 7 cards | **ALL DUPLICATES** of 16:55-16:57 cards |
| 18:31-18:45 | Continue | 6 cards | **MORE DUPLICATES** |
| 18:41-18:42 | User action | Re-login | User attempting to fix issue |
| 18:45 | After re-login | 1 card | **STILL A DUPLICATE** |

### Duplicate Cards Evidence

**Most duplicated card**: "Algorithms drive these powerful systems"
- Original: July 4, 16:55:58
- Duplicate 1: July 4, 17:29:54 (34 minutes later)
- Duplicate 2: July 4, 17:32:41 (3 minutes after dup1)
- Duplicate 3: July 4, 18:45:18 (1h 13min after dup2)

**Other duplicates**:
- "It can analyze vast amounts of data" - created 3 times
- "We are still in early stages" - created 3 times
- "This technology mimics human reasoning" - created 2 times
- "Jobs will evolve, not disappear" - created 2 times

### Database vs. Logs Verification

```
Logged note insertions: 45
Notes in database:      45
Difference:             0 ✅
```

All note IDs from logs match exactly with note IDs in database:
- First: 1751658499000
- Last: 1751665518000
- No gaps in the logged sequence

### Graves Table (Deletion Records)

```sql
SELECT COUNT(*) FROM graves;
-- Result: 0
```

**Conclusion**: No cards, notes, or decks were ever deleted.

---

## Technical Analysis

### Backend Behavior (Confirmed Working)

1. ✅ Authentication: User remained authenticated throughout 2-hour session
2. ✅ Card insertion: All 45 cards successfully inserted into SQLite database
3. ✅ Logging: Every card creation properly logged
4. ✅ Database commits: No rollbacks or transaction failures
5. ✅ Multi-worker: Worked correctly across 3 Gunicorn workers (491316, 491318, 491319)

### Suspected Frontend Issue

**Deck Switching Pattern**:
```
17:00:07  Set current deck to 1751658410042
17:00:13  Set current deck to 1
17:02:28  Set current deck to 1751658410042
17:04:04  Set current deck to 1751658410042
17:04:18  Set current deck to 1
17:26:09  Set current deck to 1751658410042
17:26:17  Set current deck to 1
```

User switched decks **7 times** in a 26-minute period. After this, she started creating duplicates.

**Likely scenario**:
1. User created 30 cards in default deck
2. Switched to "The IA" deck multiple times
3. Frontend lost track of which cards belong to which deck
4. When she viewed the default deck again, it appeared empty
5. She recreated cards she thought were lost
6. Even re-logging in didn't fix the UI state

---

## Code Review Findings

### Backend: `get_deck_cards()` (line 2497)
```python
@app.route('/decks/<deckId>/cards', methods=['GET'])
def get_deck_cards(deckId):
    # ...
    cursor.execute("""
        SELECT c.id, n.id AS note_id, n.flds, c.mod
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.did = ?
        ORDER BY c.id DESC
        LIMIT ? OFFSET ?
    """, (deckId, perPage, offset))
```

✅ **Correct**: Query uses explicit `deckId` parameter, not session state.

### Backend: `set_current_deck()` (line 2008)
```python
@app.route('/decks/current', methods=['PUT'])
def set_current_deck():
    # Updates col.conf['curDeck']
    conf_dict['curDeck'] = int(deck_id)
    cursor.execute("UPDATE col SET conf = ?, mod = ?", ...)
```

✅ **Correct**: Updates database, but this is only for tracking "current" deck.

### Frontend: `fetchCards()` (line 343)
```javascript
const fetchCards = useCallback(async (deckId, page = 1) => {
    const response = await getDeckCards(deckId, page);
    setCards(response.cards || []);
    setSelectedDeck({ id: response.deckId, name: response.deckName });
}, []);
```

⚠️ **Potential issue**:
- State managed in `selectedDeck` React state
- Also stored in `localStorage.currentDeckName`
- Backend has `col.conf.curDeck`
- **THREE sources of truth** - could desync!

### Frontend: `handleSelectDeck()` (line 396)
```javascript
const handleSelectDeck = async (deckId, deckName) => {
    await api.put('/decks/current', { deckId });
    localStorage.setItem('currentDeckName', deckName);
    // ... then fetch cards
};
```

⚠️ **Potential issue**:
- If `fetchCards()` is called before `setCurrentDeck` completes
- Or if user navigates away before state settles
- Could show wrong cards or empty list

---

## User Experience Impact

### What Gabrielle Experienced:
1. ✅ Successfully created 30 cards
2. ✅ Switched to new deck and created 2 more cards
3. ❌ When she came back to view her original 30 cards → **they appeared missing**
4. 🔄 She recreated the "missing" cards
5. ❌ They appeared missing again
6. 🔄 She recreated them again (up to 4 times for one card!)
7. 🔄 Tried logging out and back in to fix it
8. ❌ Issue persisted after re-login

### Result:
- User spent ~2 hours creating cards
- Much of that time was recreating duplicates
- User lost trust in the application
- User reported "lost cards" bug

---

## Recommendations

### Immediate Actions

1. **Add comprehensive logging**:
   - Log every `fetchCards()` call with deckId and response
   - Log every deck switch operation
   - Log state changes in frontend

2. **Manual testing**: Follow reproduction scenarios in `LOST_CARDS_REPRODUCTION_PLAN.md`

3. **Add automated test**: Create test that:
   - Creates cards
   - Switches decks rapidly
   - Verifies all cards still accessible

### Long-term Fixes

1. **Simplify state management**:
   - Use single source of truth for "current deck"
   - Remove redundant localStorage usage
   - Rely on backend `curDeck` value

2. **Add UI safeguards**:
   - Show loading states during deck switches
   - Disable rapid switching (debounce)
   - Show card count in deck list (so users can see cards exist)

3. **Auto-refresh after operations**:
   - After creating a card, refresh the card list
   - After switching decks, wait for fetch to complete

4. **Duplicate detection**:
   - Warn user if creating a card with identical content to existing card

---

## Lessons Learned

1. **Database was never the problem**: All data was safely stored
2. **Frontend state management is critical**: UX bug led to data duplication
3. **Users will work around broken UI**: Gabrielle kept recreating cards
4. **Re-login doesn't fix client-side bugs**: Frontend state persisted
5. **Deck switching is a high-risk operation**: Multiple state updates involved

---

## Monitoring Recommendations

### Post-fix Monitoring

Track these metrics in production:
1. **Duplicate card creation rate**: Same content created within 1 hour
2. **Deck switch frequency**: Users switching >5 times in 10 minutes
3. **Failed card fetch requests**: 404/500 errors on `/decks/<id>/cards`
4. **Re-login frequency**: Users logging out and back in during a session
5. **Card list empty rate**: API returns 0 cards when total > 0

### Alerting Thresholds

- Alert if duplicate creation rate > 5% of total card creations
- Alert if card fetch error rate > 1%
- Alert if a user re-logs in more than 3 times in 1 hour

---

## Files Created

1. `docs/LOST_CARDS_INVESTIGATION_SUMMARY.md` (this file)
2. `docs/LOST_CARDS_REPRODUCTION_PLAN.md` (test scenarios)

## Next Steps

1. ✅ Investigation complete
2. ⏳ Manual testing using reproduction scenarios
3. ⏳ Implement fixes based on findings
4. ⏳ Deploy to test environment
5. ⏳ Monitor for recurrence
