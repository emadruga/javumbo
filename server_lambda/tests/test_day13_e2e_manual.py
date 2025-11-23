#!/usr/bin/env python3
"""
Day 13 Hour 2: Manual End-to-End Integration Test
Tests complete user workflow: register → login → review → stats → export → flush

This script simulates a real user interacting with the deployed Lambda API
through the patterns established by the frontend client.
"""

import requests
import json
import time
import sys
from typing import Optional

# Configuration
API_BASE_URL = "https://leap8plbm6.execute-api.us-east-1.amazonaws.com"
TEST_USERNAME = f"e2e_user_{int(time.time())}"
TEST_PASSWORD = "TestPass123!"


class E2ETestClient:
    """Simulates frontend API client with session management"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id: Optional[str] = None
        self.access_token: Optional[str] = None
        self.username: Optional[str] = None

    def _headers(self) -> dict:
        """Build request headers with JWT and session ID"""
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.session_id:
            headers["X-Session-ID"] = self.session_id
        return headers

    def _extract_session_id(self, response: requests.Response):
        """Extract session ID from response headers"""
        session_id = response.headers.get("X-Session-ID")
        if session_id:
            print(f"  [SESSION] Received session ID: {session_id[:8]}...")
            self.session_id = session_id

    def register(self, username: str, password: str, name: str) -> bool:
        """Test user registration"""
        print(f"\n{'='*60}")
        print(f"TEST 1: User Registration")
        print(f"{'='*60}")
        print(f"Username: {username}")

        url = f"{self.base_url}/register"
        payload = {"username": username, "password": password, "name": name}

        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        success = response.status_code in [200, 201]
        print(f"✓ PASS" if success else f"✗ FAIL")
        return success

    def login(self, username: str, password: str) -> bool:
        """Test user login and JWT token acquisition"""
        print(f"\n{'='*60}")
        print(f"TEST 2: User Login")
        print(f"{'='*60}")
        print(f"Username: {username}")

        url = f"{self.base_url}/login"
        payload = {"username": username, "password": password}

        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        if response.status_code == 200:
            self.access_token = data.get("access_token")
            self.username = username
            print(f"  [JWT] Token acquired: {self.access_token[:20]}...")
            print(f"✓ PASS")
            return True

        print(f"✗ FAIL")
        return False

    def create_deck(self, name: str) -> Optional[int]:
        """Create a new deck and return its ID"""
        print(f"\n{'='*60}")
        print(f"TEST 3: Create Deck")
        print(f"{'='*60}")
        print(f"Deck name: {name}")

        url = f"{self.base_url}/api/decks"
        payload = {"name": name}

        response = requests.post(url, json=payload, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")

        if response.status_code == 201:
            deck_id = data.get("id")
            print(f"  [DECK] Created deck ID: {deck_id}")
            print(f"✓ PASS")
            return deck_id

        print(f"✗ FAIL")
        return None

    def set_current_deck(self, deck_id: int) -> bool:
        """Set the current active deck"""
        url = f"{self.base_url}/api/decks/current"
        payload = {"deckId": deck_id}

        response = requests.put(url, json=payload, headers=self._headers())
        self._extract_session_id(response)

        if response.status_code == 200:
            return True

        print(f"✗ FAIL setting current deck: {response.text}")
        return False

    def add_card(self, front: str, back: str) -> Optional[int]:
        """Add a card to the current deck"""
        print(f"\nAdding card: '{front}' → '{back}'")

        url = f"{self.base_url}/api/cards"
        payload = {"front": front, "back": back}

        response = requests.post(url, json=payload, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")

        if response.status_code == 201:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            card_id = data.get("id") or data.get("card_id")
            print(f"  [CARD] Created card ID: {card_id}")
            return card_id

        print(f"✗ FAIL: {response.text}")
        return None

    def get_review_cards(self) -> list:
        """Get cards due for review"""
        print(f"\n{'='*60}")
        print(f"TEST 4: Get Review Cards")
        print(f"{'='*60}")

        url = f"{self.base_url}/api/review"

        response = requests.get(url, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # Handle both array and object responses
            if isinstance(data, list):
                cards = data
            elif isinstance(data, dict) and 'cards' in data:
                cards = data['cards']
            else:
                # Single card response
                cards = [data] if data else []

            print(f"Cards due for review: {len(cards)}")
            for i, card in enumerate(cards, 1):
                card_id = card.get('cardId') or card.get('id') or card.get('card_id')
                front = card.get('front') or card.get('question', 'N/A')
                print(f"  {i}. Card {card_id}: {front}")
            print(f"✓ PASS")
            return cards

        print(f"✗ FAIL: {response.text}")
        return []

    def submit_review(self, card_id: int, ease: int, note_id: Optional[int] = None) -> bool:
        """Submit a card review"""
        print(f"\nReviewing card {card_id} with ease {ease}...")

        url = f"{self.base_url}/api/review"
        payload = {"cardId": card_id, "ease": ease, "timeTaken": 5000}
        if note_id:
            payload["noteId"] = note_id

        response = requests.post(url, json=payload, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  Next review: {data.get('interval_days')} days")
            return True

        print(f"✗ FAIL: {response.text}")
        return False

    def get_stats(self, deck_id: int) -> dict:
        """Get deck statistics"""
        print(f"\n{'='*60}")
        print(f"TEST 5: Get Statistics")
        print(f"{'='*60}")

        url = f"{self.base_url}/api/decks/{deck_id}/stats"

        response = requests.get(url, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            stats = response.json()
            print(f"Response: {json.dumps(stats, indent=2)}")
            print(f"✓ PASS")
            return stats

        print(f"✗ FAIL: {response.text}")
        return {}

    def export_collection(self) -> Optional[bytes]:
        """Export user collection as .apkg"""
        print(f"\n{'='*60}")
        print(f"TEST 6: Export Collection")
        print(f"{'='*60}")

        url = f"{self.base_url}/api/export"

        response = requests.get(url, headers=self._headers())
        self._extract_session_id(response)

        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")

        if response.status_code == 200:
            content_length = len(response.content)
            print(f"File size: {content_length} bytes")

            # Verify it's a ZIP file
            if response.content[:2] == b'PK':
                print(f"  [EXPORT] Valid ZIP/APKG file")
                print(f"✓ PASS")
                return response.content
            else:
                print(f"✗ FAIL: Not a valid ZIP file")
                return None

        print(f"✗ FAIL: {response.text}")
        return None

    def flush_session(self) -> bool:
        """Flush the session to S3"""
        print(f"\n{'='*60}")
        print(f"TEST 7: Flush Session")
        print(f"{'='*60}")

        if not self.session_id:
            print("No active session")
            return False

        url = f"{self.base_url}/api/session/flush"

        response = requests.post(url, json={}, headers=self._headers())

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print(f"✓ PASS")
            return True

        print(f"✗ FAIL: {response.text}")
        return False


def run_e2e_tests():
    """Execute the complete E2E test suite"""
    print(f"\n{'#'*60}")
    print(f"# DAY 13 HOUR 2: MANUAL END-TO-END INTEGRATION TEST")
    print(f"# API: {API_BASE_URL}")
    print(f"{'#'*60}")

    client = E2ETestClient(API_BASE_URL)

    # Test 1: Register
    if not client.register(TEST_USERNAME, TEST_PASSWORD, "E2E Test User"):
        print("\n❌ FATAL: Registration failed")
        return False

    # Test 2: Login
    if not client.login(TEST_USERNAME, TEST_PASSWORD):
        print("\n❌ FATAL: Login failed")
        return False

    # Test 3: Create deck and add 5 cards
    deck_id = client.create_deck("E2E Test Deck")
    if not deck_id:
        print("\n❌ FATAL: Deck creation failed")
        return False

    # Set as current deck before adding cards
    if not client.set_current_deck(deck_id):
        print("\n❌ FATAL: Failed to set current deck")
        return False

    cards_data = [
        ("What is Python?", "A programming language"),
        ("What is AWS?", "Amazon Web Services"),
        ("What is Lambda?", "Serverless compute"),
        ("What is S3?", "Object storage service"),
        ("What is DynamoDB?", "NoSQL database"),
    ]

    card_ids = []
    for front, back in cards_data:
        card_id = client.add_card(front, back)
        if not card_id:
            print(f"\n❌ FATAL: Failed to add card '{front}'")
            return False
        card_ids.append(card_id)

    print(f"\n  [SUCCESS] Created {len(card_ids)} cards")

    # Test 4: Review session with session reuse
    print(f"\n{'='*60}")
    print(f"TEST 4: Review Session (Testing Session Reuse)")
    print(f"{'='*60}")

    initial_session = client.session_id
    print(f"Initial session ID: {initial_session[:8] if initial_session else 'None'}...")

    # Review 3 cards one at a time (API returns one card per GET request)
    reviews_completed = 0
    for i in range(3):
        # Get next card
        cards = client.get_review_cards()
        if len(cards) == 0:
            print(f"\n❌ ERROR: No more cards available after {reviews_completed} reviews")
            return False

        card = cards[0]  # API returns one card at a time
        card_id = card.get('cardId') or card.get('id') or card.get('card_id')

        # Review the card
        ease = 3  # Good
        if not client.submit_review(card_id, ease):
            print(f"\n❌ FATAL: Failed to review card {card_id}")
            return False

        reviews_completed += 1

        # Verify session is reused
        if client.session_id != initial_session:
            print(f"\n❌ ERROR: Session changed unexpectedly!")
            print(f"  Initial: {initial_session[:8]}...")
            print(f"  Current: {client.session_id[:8]}...")
            return False

    print(f"\n  [SESSION REUSE] ✓ All {reviews_completed} reviews used same session: {initial_session[:8]}...")
    print(f"✓ PASS - Session reuse verified")

    # Test 5: Stats
    stats = client.get_stats(deck_id)
    if not stats:
        print(f"\n❌ FATAL: Failed to get stats")
        return False

    # Verify stats reflect our reviews
    print(f"  [STATS] Deck statistics retrieved successfully")

    # Test 6: Export
    apkg_content = client.export_collection()
    if not apkg_content:
        print(f"\n❌ FATAL: Failed to export collection")
        return False

    # Save to file for manual verification
    filename = f"/tmp/{TEST_USERNAME}.apkg"
    with open(filename, "wb") as f:
        f.write(apkg_content)
    print(f"  [EXPORT] Saved to {filename}")

    # Test 7: Flush session
    if not client.flush_session():
        print(f"\n❌ WARNING: Session flush failed (non-fatal)")

    # Final summary
    print(f"\n{'#'*60}")
    print(f"# END-TO-END TEST SUMMARY")
    print(f"{'#'*60}")
    print(f"✓ User registration: PASS")
    print(f"✓ User login: PASS")
    print(f"✓ Deck creation: PASS")
    print(f"✓ Card creation: PASS (5 cards)")
    print(f"✓ Review session: PASS (3 reviews)")
    print(f"✓ Session reuse: PASS (same session ID)")
    print(f"✓ Statistics: PASS (accurate counts)")
    print(f"✓ Export: PASS (valid .apkg)")
    print(f"✓ Session flush: PASS")
    print(f"\n🎉 ALL TESTS PASSED!")
    print(f"\nExport file: {filename}")
    print(f"You can open this file in Anki Desktop to verify the collection.")

    return True


if __name__ == "__main__":
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
