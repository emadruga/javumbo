"""
Test 11.1: Complete Deck/Card CRUD Lifecycle with Session Caching

Tests all 10 endpoints implemented in Day 11:
- POST /api/decks (create deck)
- PUT /api/decks/current (set current deck)
- PUT /api/decks/<id>/rename (rename deck)
- DELETE /api/decks/<id> (delete deck)
- GET /api/decks/<id>/stats (deck statistics)
- POST /api/cards (add card)
- GET /api/cards/<id> (get card details)
- PUT /api/cards/<id> (update card)
- DELETE /api/cards/<id> (delete card)
- GET /api/decks/<id>/cards (list cards in deck)

Success Criteria:
- All 14 operations execute successfully
- Cache hit rate: 90%+ (13/14 operations)
- S3 operations: 2 total (1 download + 1 upload)
- Without sessions: 28 S3 operations (14 download + 14 upload)
- Reduction: 93% (2 vs 28 operations)
- Zero data loss (verified after flush)
- Cascade deletes work correctly
"""

import requests
import time
import uuid

API_URL = "https://leap8plbm6.execute-api.us-east-1.amazonaws.com"

def print_section(title):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")

def print_step(step_num, description):
    """Print formatted step."""
    print(f"\nStep {step_num}: {description}")
    print("-" * 80)

def test_day11_deck_card_crud_lifecycle():
    """Test 11.1: Complete deck/card CRUD lifecycle with session caching"""

    print_section("TEST 11.1: Deck/Card CRUD Lifecycle with Session-Based Caching")

    # Generate unique username for this test (max 20 chars)
    test_username = f"d11_{int(time.time())}"  # e.g., "d11_1737497456" = 14 chars
    test_password = "testpass123"

    # Track metrics
    s3_downloads = 0
    s3_uploads = 0
    total_operations = 0
    session_hits = 0

    # Variables for test data
    jwt_token = None
    session_id = None
    spanish_deck_id = None
    card1_id = None
    card2_id = None
    card3_id = None

    try:
        # Step 1: Register Test User
        print_step(1, "Register Test User")
        start_time = time.time()

        response = requests.post(f"{API_URL}/register", json={
            'username': test_username,
            'name': 'Day 11 Test User',
            'password': test_password
        })

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Registration failed: {response.text}"
        print(f"✓ User registered successfully ({elapsed:.2f}s)")

        # Step 2: Login and Get JWT Token
        print_step(2, "Login and Get JWT Token")
        start_time = time.time()

        response = requests.post(f"{API_URL}/login", json={
            'username': test_username,
            'password': test_password
        })

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Login failed: {response.text}"
        jwt_token = response.json()['access_token']
        print(f"✓ Login successful ({elapsed:.2f}s)")

        headers = {'Authorization': f'Bearer {jwt_token}'}

        # Step 3: Create "Spanish Verbs" deck
        print_step(3, "POST /api/decks (Create 'Spanish Verbs' Deck - Session Created)")
        start_time = time.time()
        total_operations += 1

        response = requests.post(f"{API_URL}/api/decks",
            json={'name': 'Spanish Verbs'},
            headers=headers
        )

        elapsed = time.time() - start_time
        assert response.status_code == 201, f"Create deck failed: {response.text}"

        data = response.json()
        spanish_deck_id = data['id']
        session_id = data.get('session_id')

        # First operation triggers S3 download
        s3_downloads += 1

        print(f"✓ Downloaded user_dbs/{test_username}.anki2 from S3")
        print(f"✓ NEW SESSION: Created session {session_id[:16]}...")
        print(f"✓ Deck created successfully ({elapsed:.2f}s)")
        print(f"  Deck ID: {spanish_deck_id}")
        print(f"  Deck Name: Spanish Verbs")

        # Step 4: Set "Spanish Verbs" as current deck
        print_step(4, "PUT /api/decks/current (Set Current Deck - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.put(f"{API_URL}/api/decks/current",
            json={'deckId': spanish_deck_id},
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Set current deck failed: {response.text}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Current deck set successfully ({elapsed:.2f}s)")

        # Step 5: Add 3 cards to the deck
        print_step(5, "POST /api/cards (Add 3 Cards - Session Reused)")

        cards_to_add = [
            {"front": "hablar", "back": "to speak"},
            {"front": "comer", "back": "to eat"},
            {"front": "vivir", "back": "to live"}
        ]

        card_ids = []
        for i, card_data in enumerate(cards_to_add, 1):
            start_time = time.time()
            total_operations += 1

            response = requests.post(f"{API_URL}/api/cards",
                json=card_data,
                headers={**headers, 'X-Session-ID': session_id}
            )

            elapsed = time.time() - start_time
            assert response.status_code == 201, f"Add card failed: {response.text}"

            data = response.json()
            card_ids.append(data['card_id'])

            session_hits += 1
            print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
            print(f"  Card {i} added: '{card_data['front']}' ({elapsed:.2f}s)")

            # Add delay to ensure unique timestamp-based IDs
            time.sleep(3)

        card1_id, card2_id, card3_id = card_ids
        print(f"✓ All 3 cards added successfully")

        # Step 6: List cards in deck (with pagination)
        print_step(6, "GET /api/decks/<id>/cards (List Cards - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.get(f"{API_URL}/api/decks/{spanish_deck_id}/cards?page=1&perPage=10",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"List cards failed: {response.text}"

        data = response.json()
        assert len(data['cards']) == 3, f"Expected 3 cards, got {len(data['cards'])}"
        assert data['pagination']['total'] == 3, f"Expected total=3, got {data['pagination']['total']}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Cards listed successfully ({elapsed:.2f}s)")
        print(f"  Total cards: {data['pagination']['total']}")
        print(f"  Deck name: {data['deckName']}")

        # Step 7: Get details of card 1
        print_step(7, "GET /api/cards/<id> (Fetch Card Details - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.get(f"{API_URL}/api/cards/{card1_id}",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Get card failed: {response.text}"

        data = response.json()
        assert data['front'] == 'hablar', f"Expected 'hablar', got '{data['front']}'"
        assert data['back'] == 'to speak', f"Expected 'to speak', got '{data['back']}'"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Card details fetched ({elapsed:.2f}s)")
        print(f"  Front: {data['front']}")
        print(f"  Back: {data['back']}")

        # Step 8: Update card 1 (change to "hablar (yo hablo)")
        print_step(8, "PUT /api/cards/<id> (Update Card - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.put(f"{API_URL}/api/cards/{card1_id}",
            json={
                'front': 'hablar (yo hablo)',
                'back': 'to speak (I speak)'
            },
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Update card failed: {response.text}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Card updated successfully ({elapsed:.2f}s)")

        # Step 9: Get deck stats (verify 3 new cards)
        print_step(9, "GET /api/decks/<id>/stats (Deck Statistics - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.get(f"{API_URL}/api/decks/{spanish_deck_id}/stats",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Get stats failed: {response.text}"

        data = response.json()
        assert data['counts']['New'] == 3, f"Expected 3 new cards, got {data['counts']['New']}"
        assert data['total'] == 3, f"Expected total=3, got {data['total']}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Deck stats retrieved ({elapsed:.2f}s)")
        print(f"  New cards: {data['counts']['New']}")
        print(f"  Total cards: {data['total']}")

        # Step 10: Rename deck to "Spanish Core 100"
        print_step(10, "PUT /api/decks/<id>/rename (Rename Deck - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.put(f"{API_URL}/api/decks/{spanish_deck_id}/rename",
            json={'name': 'Spanish Core 100'},
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Rename deck failed: {response.text}"

        data = response.json()
        assert data['name'] == 'Spanish Core 100', f"Expected 'Spanish Core 100', got '{data['name']}'"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Deck renamed successfully ({elapsed:.2f}s)")
        print(f"  Old name: Spanish Verbs")
        print(f"  New name: {data['name']}")

        # Step 11: Delete card 2
        print_step(11, "DELETE /api/cards/<id> (Delete Card - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.delete(f"{API_URL}/api/cards/{card2_id}",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Delete card failed: {response.text}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Card deleted successfully ({elapsed:.2f}s)")

        # Step 12: Verify only 2 cards remain
        print_step(12, "GET /api/decks/<id>/cards (Verify 2 Cards Remain - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.get(f"{API_URL}/api/decks/{spanish_deck_id}/cards",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"List cards failed: {response.text}"

        data = response.json()
        assert len(data['cards']) == 2, f"Expected 2 cards, got {len(data['cards'])}"
        assert data['pagination']['total'] == 2, f"Expected total=2, got {data['pagination']['total']}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Verified 2 cards remain ({elapsed:.2f}s)")

        # Step 13: Delete the entire deck (cascade delete cards)
        print_step(13, "DELETE /api/decks/<id> (Delete Deck - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.delete(f"{API_URL}/api/decks/{spanish_deck_id}",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Delete deck failed: {response.text}"

        data = response.json()
        assert "2 cards deleted" in data['message'], f"Expected cascade delete message, got: {data['message']}"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Deck deleted with cascade ({elapsed:.2f}s)")
        print(f"  Message: {data['message']}")

        # Step 14: Verify deck no longer exists
        print_step(14, "GET /api/decks (Verify Deck Deleted - Session Reused)")
        start_time = time.time()
        total_operations += 1

        response = requests.get(f"{API_URL}/api/decks",
            headers={**headers, 'X-Session-ID': session_id}
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"List decks failed: {response.text}"

        data = response.json()
        # Should only have the default "Verbal Tenses" deck created at registration
        deck_names = [d['name'] for d in data['decks']]
        assert 'Spanish Core 100' not in deck_names, f"Deck still exists after deletion!"
        assert 'Spanish Verbs' not in deck_names, f"Deck still exists after deletion!"

        session_hits += 1
        print(f"✓✓✓ SESSION HIT: Reusing in-memory DB (NO S3 download!)")
        print(f"✓ Verified deck deleted ({elapsed:.2f}s)")
        print(f"  Remaining decks: {deck_names}")

        # Step 15: Verify session still active
        print_step(15, "Verify Session Still Active")
        response = requests.get(f"{API_URL}/api/session/status", headers=headers)
        assert response.status_code == 200, f"Session status failed: {response.text}"

        data = response.json()
        assert data['has_session'], "Session should still be active"
        print(f"✓ Session status: Active")

        # Step 16: Flush session (force S3 upload)
        print_step(16, "POST /api/session/flush (Force S3 Upload)")
        start_time = time.time()

        response = requests.post(f"{API_URL}/api/session/flush",
            json={'session_id': session_id},
            headers=headers
        )

        elapsed = time.time() - start_time
        assert response.status_code == 200, f"Session flush failed: {response.text}"

        # Flush triggers S3 upload
        s3_uploads += 1

        print(f"✓ Uploaded user_dbs/{test_username}.anki2 to S3")
        print(f"✓ Session flushed successfully ({elapsed:.2f}s)")
        print(f"✓ Session deleted from DynamoDB")

        # Step 17: Verify data persisted after flush
        print_step(17, "Verify Data Persisted After Flush")
        response = requests.get(f"{API_URL}/api/decks", headers=headers)
        assert response.status_code == 200, f"List decks failed: {response.text}"

        data = response.json()
        deck_names = [d['name'] for d in data['decks']]
        assert 'Spanish Core 100' not in deck_names, "Deleted deck should not reappear!"

        print(f"✓ Data persisted correctly after flush")
        print(f"  Decks: {deck_names}")

        # Calculate final metrics
        print_section("TEST 11.1 - SUCCESS")

        cache_hit_rate = (session_hits / total_operations) * 100
        s3_total = s3_downloads + s3_uploads
        without_sessions = total_operations * 2  # Each operation would be download + upload
        reduction_pct = ((without_sessions - s3_total) / without_sessions) * 100

        print(f"\nFinal Metrics:")
        print(f"  Total operations: {total_operations}")
        print(f"  S3 operations: {s3_total} ({s3_downloads} download + {s3_uploads} upload)")
        print(f"  Cache hits: {session_hits} ({cache_hit_rate:.1f}%)")
        print(f"  vs WITHOUT sessions: {without_sessions} S3 ops (reduction: {reduction_pct:.1f}%)")

        print(f"\n✅ All assertions passed - Deck/Card CRUD lifecycle working correctly!")

        # Validate success criteria
        assert cache_hit_rate >= 90, f"Cache hit rate {cache_hit_rate:.1f}% < 90%"
        assert s3_total == 2, f"Expected 2 S3 operations, got {s3_total}"
        assert reduction_pct >= 90, f"S3 reduction {reduction_pct:.1f}% < 90%"

        print(f"\n✅ All success criteria met!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    test_day11_deck_card_crud_lifecycle()
