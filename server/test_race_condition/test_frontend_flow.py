#!/usr/bin/env python3
"""
Frontend Flow Race Condition Test

Simulates the exact API call sequence that the React frontend makes,
including deck selection and state updates.

This tests for issues like:
- Cards reported as created but not actually saved
- Deck switching causing misrouted cards
- Frontend state management bugs
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

BASE_URL = "http://54.226.152.231"
PASSWORD = "password123test"
NUM_USERS = 15  # Start small for frontend flow testing
CARDS_PER_USER = 20

def frontend_flow_worker(username, worker_id):
    """
    Simulates the complete frontend user flow:
    1. Login
    2. View decks
    3. Select a deck
    4. Add multiple cards
    5. Verify cards appear in deck list
    """
    session = requests.Session()
    results = {
        "username": username,
        "worker_id": worker_id,
        "cards_created": [],
        "cards_verified": [],
        "errors": []
    }

    try:
        # STEP 1: LOGIN (like LoginPage.jsx)
        print(f"  Worker {worker_id} ({username}): Logging in...")
        response = session.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": PASSWORD},
            timeout=10
        )

        if response.status_code != 200:
            error_msg = f"Login failed: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text[:100]}"
            results["errors"].append(error_msg)
            print(f"  ❌ Worker {worker_id} ({username}): {error_msg}")
            return results

        # STEP 2: GET DECKS (like DecksPage.jsx useEffect)
        print(f"  Worker {worker_id} ({username}): Fetching decks...")
        response = session.get(f"{BASE_URL}/decks", timeout=10)

        if response.status_code != 200:
            error_msg = f"Get decks failed: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text[:100]}"
            results["errors"].append(error_msg)
            print(f"  ❌ Worker {worker_id} ({username}): {error_msg}")
            return results

        decks = response.json()
        if not decks:
            results["errors"].append("No decks found")
            return results

        # Use first deck
        deck_id = decks[0]['id']
        deck_name = decks[0]['name']
        print(f"  Worker {worker_id} ({username}): Using deck '{deck_name}' (ID: {deck_id})")

        # STEP 3: SET CURRENT DECK (like DecksPage.jsx handleAddCard)
        response = session.put(
            f"{BASE_URL}/decks/current",
            json={"deckId": deck_id},  # API expects camelCase
            timeout=10
        )

        if response.status_code != 200:
            error_msg = f"Set current deck failed: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text[:100]}"
            results["errors"].append(error_msg)
            print(f"  ❌ Worker {worker_id} ({username}): {error_msg}")
            return results

        # STEP 4: ADD CARDS (like AddCardPage.jsx handleSubmit)
        print(f"  Worker {worker_id} ({username}): Creating {CARDS_PER_USER} cards...")

        for i in range(CARDS_PER_USER):
            timestamp = int(time.time() * 1000)
            front = f"[USER:{username}][WORKER:{worker_id}][SEQ:{i}][TIME:{timestamp}] Frontend Test Q{i}"
            back = f"Frontend Test Answer {i} [MARKER:{username}_{worker_id}_{i}]"

            response = session.post(
                f"{BASE_URL}/add_card",
                json={"front": front, "back": back},
                timeout=10
            )

            if response.status_code in [200, 201]:
                data = response.json()
                card_id = data.get('card_id')
                results["cards_created"].append({
                    "card_id": card_id,
                    "front": front,
                    "back": back,
                    "sequence": i
                })

                if i % 5 == 0 and i > 0:
                    print(f"    Worker {worker_id}: {i}/{CARDS_PER_USER} cards created")
            else:
                error_msg = f"Card {i} failed: {response.status_code}"
                results["errors"].append(error_msg)
                if len(results["errors"]) <= 3:
                    print(f"    ⚠️  Worker {worker_id}: {error_msg}")

            # Small delay (simulates user typing/thinking)
            time.sleep(2.05)  # 50ms

        # STEP 5: VERIFY CARDS APPEAR (like DecksPage.jsx refresh)
        print(f"  Worker {worker_id} ({username}): Verifying cards in deck...")
        response = session.get(f"{BASE_URL}/decks", timeout=10)

        if response.status_code == 200:
            decks = response.json()
            # Find our deck and check card count
            for deck in decks:
                if deck['id'] == deck_id:
                    reported_count = len(results["cards_created"])
                    # Note: API might not return card count, would need to fetch cards
                    print(f"  Worker {worker_id} ({username}): Reported {reported_count} cards created")

        # STEP 6: LOGOUT (like Navbar.jsx handleLogout)
        session.post(f"{BASE_URL}/logout", timeout=5)

    except Exception as e:
        results["errors"].append(f"Exception: {str(e)}")
        print(f"  ❌ Worker {worker_id} ({username}): Exception - {e}")

    success_count = len(results["cards_created"])
    error_count = len(results["errors"])

    print(f"  ✅ Worker {worker_id} ({username}): {success_count} cards created, {error_count} errors")

    return results

def main():
    print("=" * 70)
    print("  Frontend Flow Race Condition Test")
    print("=" * 70)
    print(f"Target: {BASE_URL}")
    print(f"Users: {NUM_USERS}")
    print(f"Cards per user: {CARDS_PER_USER}")
    print()
    print("Simulating the complete frontend user flow:")
    print("  1. Login → 2. Get Decks → 3. Select Deck → 4. Add Cards → 5. Verify")
    print()

    start_time = time.time()

    # Generate test users
    users = [(f"race{i}", i) for i in range(NUM_USERS)]

    # Launch workers
    with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
        futures = {
            executor.submit(frontend_flow_worker, username, worker_id): username
            for username, worker_id in users
        }

        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    duration = time.time() - start_time

    # Calculate statistics
    total_created = sum(len(r["cards_created"]) for r in results)
    total_errors = sum(len(r["errors"]) for r in results)

    print()
    print("=" * 70)
    print("  Test Complete")
    print("=" * 70)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total cards created: {total_created}")
    print(f"Total errors: {total_errors}")
    print()

    # Show per-user results
    print("Results by user:")
    for result in results:
        username = result["username"]
        created = len(result["cards_created"])
        errors = len(result["errors"])
        print(f"  {username}: {created} cards, {errors} errors")

    # Show error details if any
    if total_errors > 0:
        print()
        print("Error details:")
        for result in results:
            if result["errors"]:
                username = result["username"]
                for error in result["errors"]:
                    print(f"  {username}: {error}")

    # Check for specific issues
    print()
    print("=" * 70)
    print("  Issue Detection")
    print("=" * 70)

    # Check for "phantom" cards (API said success but card missing)
    print()
    print("Checking for phantom cards (API success but card missing)...")
    print("  → Run validate_race_condition.py on server to verify")

    # Check for misrouted cards
    print()
    print("Checking for misrouted cards...")
    print("  → Run validate_race_condition.py on server to verify")

    print()
    print("=" * 70)
    print("  Next Steps")
    print("=" * 70)
    print("1. SSH to server:")
    print("   ssh ubuntu@54.226.2.146")
    print("   cd ~/javumbo/server")
    print()
    print("2. Validate card integrity:")
    print("   python3 validate_race_condition.py")
    print()
    print("3. Check for phantom cards (API said success but card missing):")
    print(f"   Expected total: {total_created} cards")
    print("   Compare with actual count from validation")
    print()

if __name__ == "__main__":
    main()
