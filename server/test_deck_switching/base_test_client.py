#!/usr/bin/env python3
"""
Base Test Client for Deck Switching Tests

This module provides a reusable test client that mimics the frontend behavior
for testing deck switching and card management functionality. It maintains
session state and provides methods for all common user operations.

The client is designed to:
1. Simulate real user interactions (login, deck switching, card creation)
2. Maintain session state (cookies, current deck)
3. Provide detailed logging of API calls and responses
4. Handle errors gracefully with clear error messages
5. Verify expected behaviors (card counts, deck states)

Usage:
    from base_test_client import TestClient

    client = TestClient("http://localhost:5000", "testuser", "password123")
    client.login()

    # Create cards
    card = client.add_card("Question", "Answer")

    # Switch decks
    new_deck = client.create_deck("New Deck")
    client.set_current_deck(new_deck['id'])

    # Verify cards
    cards = client.get_deck_cards(1)
    assert len(cards) == 10

    client.logout()
"""

import requests
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class APICallError(Exception):
    """Raised when an API call fails with an unexpected status code"""
    pass


class TestClient:
    """
    Test client that simulates frontend user behavior for testing the flashcard API.

    This client maintains session state and provides methods for all common operations
    needed in deck switching tests. It logs all API calls for debugging purposes.

    Attributes:
        base_url: The base URL of the API server (e.g., "http://localhost:5000")
        username: The username for authentication
        password: The password for authentication
        session: The requests.Session object for maintaining cookies
        verbose: Whether to print detailed logs of API calls
        current_deck_id: The ID of the currently selected deck (tracked client-side)
        api_calls: List of all API calls made (for debugging)
    """

    def __init__(self, base_url: str, username: str, password: str, verbose: bool = True):
        """
        Initialize the test client.

        Args:
            base_url: The base URL of the API (e.g., "http://localhost:5000")
            username: Username for authentication
            password: Password for authentication
            verbose: If True, print detailed logs of API calls (default: True)
        """
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.verbose = verbose
        self.current_deck_id: Optional[int] = None
        self.api_calls: List[Dict] = []
        self.logged_in = False

        if self.verbose:
            print(f"TestClient initialized for {self.base_url}")
            print(f"Username: {self.username}")

    def _log_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> None:
        """Log an API request (internal method)"""
        if self.verbose:
            print(f"\n  → {method} {endpoint}")
            if data:
                print(f"    Data: {json.dumps(data, indent=6)}")

    def _log_response(self, response: requests.Response, endpoint: str) -> None:
        """Log an API response (internal method)"""
        call_record = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "status_code": response.status_code,
            "response_time_ms": response.elapsed.total_seconds() * 1000
        }

        try:
            call_record["response_data"] = response.json()
        except:
            call_record["response_data"] = response.text[:200]

        self.api_calls.append(call_record)

        if self.verbose:
            status_icon = "✓" if 200 <= response.status_code < 300 else "✗"
            print(f"  ← {status_icon} {response.status_code} ({response.elapsed.total_seconds()*1000:.0f}ms)")

            try:
                data = response.json()
                # Truncate long responses
                data_str = json.dumps(data, indent=6)
                if len(data_str) > 300:
                    data_str = data_str[:300] + "..."
                print(f"    Response: {data_str}")
            except:
                print(f"    Response: {response.text[:200]}")

    def _make_request(self, method: str, endpoint: str,
                     json_data: Optional[Dict] = None,
                     params: Optional[Dict] = None,
                     expected_status: int = 200,
                     timeout: int = 10) -> requests.Response:
        """
        Make an HTTP request with logging and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/decks")
            json_data: JSON data to send in request body
            params: Query parameters
            expected_status: Expected HTTP status code
            timeout: Request timeout in seconds

        Returns:
            The response object

        Raises:
            APICallError: If response status doesn't match expected_status
        """
        url = f"{self.base_url}{endpoint}"

        self._log_request(method, endpoint, json_data)

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                timeout=timeout
            )

            self._log_response(response, endpoint)

            if response.status_code != expected_status:
                error_msg = f"Expected status {expected_status}, got {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f"\nError: {error_data.get('error', error_data)}"
                except:
                    error_msg += f"\nResponse: {response.text[:200]}"

                raise APICallError(error_msg)

            return response

        except requests.exceptions.RequestException as e:
            print(f"  ✗ Request failed: {e}")
            raise

    # ==================== Authentication Methods ====================

    def login(self) -> bool:
        """
        Login to the application.

        This mimics the LoginPage.jsx behavior.

        Returns:
            True if login successful, False otherwise

        Raises:
            APICallError: If login fails
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"LOGIN: {self.username}")
            print(f"{'='*60}")

        response = self._make_request(
            method="POST",
            endpoint="/login",
            json_data={
                "username": self.username,
                "password": self.password
            },
            expected_status=200
        )

        data = response.json()
        self.logged_in = True

        if self.verbose:
            print(f"  ✓ Logged in as: {data.get('user', {}).get('username')}")

        return True

    def logout(self) -> bool:
        """
        Logout from the application.

        This mimics the Navbar.jsx handleLogout behavior.

        Returns:
            True if logout successful
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"LOGOUT: {self.username}")
            print(f"{'='*60}")

        response = self._make_request(
            method="POST",
            endpoint="/logout",
            expected_status=200
        )

        self.logged_in = False
        self.current_deck_id = None

        if self.verbose:
            print(f"  ✓ Logged out successfully")

        return True

    def register(self, name: str) -> Dict:
        """
        Register a new user.

        Args:
            name: The display name for the user

        Returns:
            Dictionary with user_id and message

        Raises:
            APICallError: If registration fails
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"REGISTER: {self.username}")
            print(f"{'='*60}")

        response = self._make_request(
            method="POST",
            endpoint="/register",
            json_data={
                "username": self.username,
                "name": name,
                "password": self.password
            },
            expected_status=201
        )

        return response.json()

    # ==================== Deck Management Methods ====================

    def get_decks(self) -> List[Dict]:
        """
        Get list of all decks for the logged-in user.

        This mimics the DecksPage.jsx useEffect behavior.

        Returns:
            List of deck dictionaries with 'id', 'name', 'card_count', etc.

        Raises:
            APICallError: If request fails
        """
        response = self._make_request(
            method="GET",
            endpoint="/decks",
            expected_status=200
        )

        decks = response.json()

        if self.verbose:
            print(f"  → Found {len(decks)} deck(s)")
            for deck in decks:
                print(f"     - {deck.get('name')} (ID: {deck.get('id')})")

        return decks

    def create_deck(self, name: str) -> Dict:
        """
        Create a new deck.

        This mimics the DecksPage.jsx handleCreateDeck behavior.

        Args:
            name: Name of the new deck

        Returns:
            Dictionary with deck info ('id', 'name')

        Raises:
            APICallError: If deck creation fails
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"CREATE DECK: {name}")
            print(f"{'='*60}")

        response = self._make_request(
            method="POST",
            endpoint="/decks",
            json_data={"name": name},
            expected_status=201
        )

        deck = response.json()

        if self.verbose:
            print(f"  ✓ Deck created with ID: {deck.get('id')}")

        return deck

    def set_current_deck(self, deck_id: int) -> bool:
        """
        Set the current active deck in the backend.

        This mimics the DecksPage.jsx handleSelectDeck behavior.
        This is a CRITICAL operation for testing deck switching!

        Args:
            deck_id: ID of the deck to set as current

        Returns:
            True if successful

        Raises:
            APICallError: If request fails
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"SWITCH TO DECK: {deck_id}")
            print(f"{'='*60}")

        response = self._make_request(
            method="PUT",
            endpoint="/decks/current",
            json_data={"deckId": deck_id},
            expected_status=200
        )

        self.current_deck_id = deck_id

        if self.verbose:
            print(f"  ✓ Current deck set to: {deck_id}")

        return True

    def delete_deck(self, deck_id: int) -> bool:
        """
        Delete a deck.

        Args:
            deck_id: ID of the deck to delete

        Returns:
            True if successful

        Raises:
            APICallError: If deletion fails
        """
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"DELETE DECK: {deck_id}")
            print(f"{'='*60}")

        response = self._make_request(
            method="DELETE",
            endpoint=f"/decks/{deck_id}",
            expected_status=200
        )

        if self.current_deck_id == deck_id:
            self.current_deck_id = None

        if self.verbose:
            print(f"  ✓ Deck {deck_id} deleted")

        return True

    def rename_deck(self, deck_id: int, new_name: str) -> Dict:
        """
        Rename a deck.

        Args:
            deck_id: ID of the deck to rename
            new_name: New name for the deck

        Returns:
            Dictionary with updated deck info

        Raises:
            APICallError: If rename fails
        """
        response = self._make_request(
            method="PUT",
            endpoint=f"/decks/{deck_id}/rename",
            json_data={"name": new_name},
            expected_status=200
        )

        return response.json()

    # ==================== Card Management Methods ====================

    def add_card(self, front: str, back: str, delay: float = 1.5) -> Dict:
        """
        Add a new card to the current deck.

        This mimics the AddCardPage.jsx handleSubmit behavior.

        Args:
            front: Front text of the card (question)
            back: Back text of the card (answer)
            delay: Delay in seconds after creating card (to avoid timestamp collisions)

        Returns:
            Dictionary with 'card_id', 'note_id', 'message'

        Raises:
            APICallError: If card creation fails
        """
        response = self._make_request(
            method="POST",
            endpoint="/add_card",
            json_data={
                "front": front,
                "back": back
            },
            expected_status=201
        )

        card_info = response.json()

        if self.verbose:
            print(f"  ✓ Card created (ID: {card_info.get('card_id')})")
            print(f"    Front: {front[:50]}{'...' if len(front) > 50 else ''}")

        # Small delay to avoid timestamp collisions
        if delay > 0:
            time.sleep(delay)

        return card_info

    def get_deck_cards(self, deck_id: int, page: int = 1, per_page: int = 100) -> List[Dict]:
        """
        Get all cards in a specific deck.

        This is THE CRITICAL METHOD for verifying if cards are visible after deck switching!

        Args:
            deck_id: ID of the deck
            page: Page number for pagination (default: 1)
            per_page: Cards per page (default: 100)

        Returns:
            List of card dictionaries with 'cardId', 'front', 'back', etc.

        Raises:
            APICallError: If request fails
        """
        response = self._make_request(
            method="GET",
            endpoint=f"/decks/{deck_id}/cards",
            params={"page": page, "perPage": per_page},
            expected_status=200
        )

        data = response.json()
        cards = data.get('cards', [])

        if self.verbose:
            print(f"  → Found {len(cards)} card(s) in deck {deck_id}")
            pagination = data.get('pagination', {})
            print(f"    Pagination: page {pagination.get('page')}/{pagination.get('totalPages')}, "
                  f"total: {pagination.get('total')}")

        return cards

    def get_card_details(self, card_id: int) -> Dict:
        """
        Get details of a specific card.

        Args:
            card_id: ID of the card

        Returns:
            Dictionary with card details

        Raises:
            APICallError: If card not found
        """
        response = self._make_request(
            method="GET",
            endpoint=f"/cards/{card_id}",
            expected_status=200
        )

        return response.json()

    def update_card(self, card_id: int, front: str, back: str) -> bool:
        """
        Update a card's content.

        Args:
            card_id: ID of the card to update
            front: New front text
            back: New back text

        Returns:
            True if successful

        Raises:
            APICallError: If update fails
        """
        response = self._make_request(
            method="PUT",
            endpoint=f"/cards/{card_id}",
            json_data={"front": front, "back": back},
            expected_status=200
        )

        return response.json().get('success', False)

    def delete_card(self, card_id: int) -> bool:
        """
        Delete a card.

        Args:
            card_id: ID of the card to delete

        Returns:
            True if successful

        Raises:
            APICallError: If deletion fails
        """
        response = self._make_request(
            method="DELETE",
            endpoint=f"/cards/{card_id}",
            expected_status=200
        )

        return response.json().get('success', False)

    # ==================== Verification Helper Methods ====================

    def verify_card_exists(self, deck_id: int, front: str) -> bool:
        """
        Verify that a card with specific front text exists in a deck.

        Args:
            deck_id: ID of the deck
            front: Front text to search for

        Returns:
            True if card exists, False otherwise
        """
        cards = self.get_deck_cards(deck_id)
        return any(card.get('front') == front for card in cards)

    def verify_card_count(self, deck_id: int, expected_count: int) -> Tuple[bool, int]:
        """
        Verify that a deck has the expected number of cards.

        This is a CRITICAL verification method for deck switching tests!

        Args:
            deck_id: ID of the deck
            expected_count: Expected number of cards

        Returns:
            Tuple of (match: bool, actual_count: int)
        """
        cards = self.get_deck_cards(deck_id)
        actual_count = len(cards)
        match = actual_count == expected_count

        if self.verbose:
            icon = "✓" if match else "✗"
            print(f"  {icon} Card count verification: expected {expected_count}, found {actual_count}")

        return match, actual_count

    def get_api_call_summary(self) -> str:
        """
        Get a summary of all API calls made by this client.

        Returns:
            Formatted string with API call statistics
        """
        if not self.api_calls:
            return "No API calls made yet"

        total_calls = len(self.api_calls)
        total_time = sum(call['response_time_ms'] for call in self.api_calls)
        avg_time = total_time / total_calls

        status_counts = {}
        for call in self.api_calls:
            status = call['status_code']
            status_counts[status] = status_counts.get(status, 0) + 1

        summary = f"\nAPI Call Summary:\n"
        summary += f"  Total calls: {total_calls}\n"
        summary += f"  Total time: {total_time:.0f}ms\n"
        summary += f"  Average time: {avg_time:.0f}ms\n"
        summary += f"  Status codes: {status_counts}\n"

        return summary


# ==================== Helper Function for Test Registration ====================

def register_test_user(base_url: str, username: str, password: str, name: str) -> TestClient:
    """
    Register a new test user and return a logged-in client.

    This is a convenience function for test setup.

    Args:
        base_url: Base URL of the API
        username: Username to register
        password: Password for the user
        name: Display name for the user

    Returns:
        TestClient instance that is already logged in

    Raises:
        APICallError: If registration or login fails
    """
    client = TestClient(base_url, username, password)

    try:
        client.register(name)
        client.login()
        return client
    except APICallError as e:
        # If registration fails because user exists, just try to login
        if "already exists" in str(e).lower():
            client.login()
            return client
        raise


if __name__ == "__main__":
    """
    Simple test/demo of the TestClient.
    Run this to verify the client works correctly.
    """
    print("=" * 70)
    print("TestClient Demo")
    print("=" * 70)

    # Configure your test server here
    BASE_URL = "http://localhost:8000"
    USERNAME = f"test{int(time.time()) % 10000}"  # Keep it short (max 10 chars)
    PASSWORD = "test_password_123"
    NAME = "Test Client Demo User"

    print(f"\nRegistering test user: {USERNAME}")

    try:
        # Register and login
        client = register_test_user(BASE_URL, USERNAME, PASSWORD, NAME)

        # Get initial decks
        print("\n" + "=" * 70)
        print("Getting initial decks...")
        decks = client.get_decks()
        default_deck = decks[0]

        # Add some cards
        print("\n" + "=" * 70)
        print("Adding 3 cards to default deck...")
        client.set_current_deck(default_deck['id'])

        # Wait 2 seconds to avoid timestamp collision with sample cards
        print("  (Waiting 2 seconds to avoid timestamp collisions...)")
        time.sleep(2)

        client.add_card("Question 1", "Answer 1")
        client.add_card("Question 2", "Answer 2")
        client.add_card("Question 3", "Answer 3")

        # Verify cards
        print("\n" + "=" * 70)
        print("Verifying cards...")
        match, count = client.verify_card_count(default_deck['id'], 3)
        print(f"Expected 3 cards, found {count}: {'PASS' if match else 'FAIL'}")

        # Create new deck and switch
        print("\n" + "=" * 70)
        print("Creating new deck and switching...")
        new_deck = client.create_deck("Test Deck B")
        client.set_current_deck(new_deck['id'])

        # Switch back and verify cards still exist
        print("\n" + "=" * 70)
        print("Switching back to default deck...")
        client.set_current_deck(default_deck['id'])

        print("\n" + "=" * 70)
        print("Verifying cards after deck switch...")
        match, count = client.verify_card_count(default_deck['id'], 3)
        print(f"Expected 3 cards, found {count}: {'PASS' if match else 'FAIL'}")

        if not match:
            print("\n⚠️  BUG DETECTED: Cards missing after deck switch!")

        # Logout
        client.logout()

        # Print summary
        print(client.get_api_call_summary())

        print("\n" + "=" * 70)
        print("Demo completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        raise
