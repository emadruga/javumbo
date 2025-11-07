#!/usr/bin/env python3
"""
Quick race condition test - blasts the server with concurrent card creation.
Usage: python test_race_quick.py
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://54.226.2.146"
PASSWORD = "password123test"
CARDS_PER_USER = 100  # Increased from 50
DELAY_MS = 1  # Reduced from 10ms - VERY aggressive!
NUM_USERS = 15  # Number of concurrent users to test

def spam_cards(username, worker_id):
    """
    Create cards rapidly for a single user.
    Each card has embedded markers for forensic analysis.
    """
    session = requests.Session()

    # Login
    try:
        response = session.post(
            f"{BASE_URL}/login",
            json={"username": username, "password": PASSWORD},
            timeout=10
        )

        if response.status_code != 200:
            print(f"❌ Worker {worker_id} ({username}): Login failed - {response.status_code}")
            return {"username": username, "success": 0, "errors": CARDS_PER_USER}

        print(f"✅ Worker {worker_id} ({username}): Logged in")

    except Exception as e:
        print(f"❌ Worker {worker_id} ({username}): Login exception - {e}")
        return {"username": username, "success": 0, "errors": CARDS_PER_USER}

    # Add cards rapidly
    success_count = 0
    error_count = 0
    card_ids = []

    for i in range(CARDS_PER_USER):
        timestamp = int(time.time() * 1000)

        # Embedded markers for validation
        front = f"[USER:{username}][WORKER:{worker_id}][SEQ:{i}][TIME:{timestamp}] Test Question {i}"
        back = f"Test Answer {i} [MARKER:{username}_{i}]"

        try:
            response = session.post(
                f"{BASE_URL}/add_card",
                json={"front": front, "back": back},
                timeout=10
            )

            if response.status_code in [200, 201]:
                success_count += 1
                data = response.json()
                card_id = data.get('card_id')
                if card_id:
                    card_ids.append(card_id)

                # Progress update every 10 cards
                if i % 10 == 0 and i > 0:
                    print(f"  Worker {worker_id}: {i}/{CARDS_PER_USER} cards added")
            else:
                error_count += 1
                if error_count <= 5:  # Show first 5 errors with details
                    try:
                        error_detail = response.json().get('error', 'Unknown error')
                        print(f"  ⚠️  Worker {worker_id} - Card {i}: Status {response.status_code} - {error_detail}")
                    except:
                        print(f"  ⚠️  Worker {worker_id} - Card {i}: Status {response.status_code} - {response.text[:100]}")

        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print(f"  ❌ Worker {worker_id} - Card {i}: Exception - {e}")

        # Small delay to simulate realistic timing while maintaining high concurrency
        time.sleep(DELAY_MS / 1000.0)

    result = {
        "username": username,
        "worker_id": worker_id,
        "success": success_count,
        "errors": error_count,
        "card_ids": card_ids
    }

    print(f"✅ Worker {worker_id} ({username}): Completed - {success_count} success, {error_count} errors")
    return result

def main():
    print("=" * 70)
    print("  JAVUMBO Race Condition Quick Test")
    print("=" * 70)
    print(f"Target: {BASE_URL}")
    print(f"Users: {NUM_USERS}")
    print(f"Cards per user: {CARDS_PER_USER}")
    print(f"Delay between cards: {DELAY_MS}ms")
    print(f"Total cards: {NUM_USERS * CARDS_PER_USER}")
    print()

    # Generate test users dynamically
    users = [(f"race{i}", i) for i in range(NUM_USERS)]

    print("🚀 Starting concurrent card creation...")
    print()

    start_time = time.time()

    # Launch all workers concurrently
    with ThreadPoolExecutor(max_workers=NUM_USERS) as executor:
        futures = {
            executor.submit(spam_cards, username, worker_id): username
            for username, worker_id in users
        }

        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)

    duration = time.time() - start_time

    # Calculate statistics
    total_success = sum(r["success"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    cards_per_sec = total_success / duration if duration > 0 else 0

    print()
    print("=" * 70)
    print("  Test Completed!")
    print("=" * 70)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Throughput: {cards_per_sec:.1f} cards/second")
    print(f"Total cards created: {total_success}")
    print(f"Total errors: {total_errors}")
    print()
    print("Results by user:")
    for result in results:
        print(f"  {result['username']}: {result['success']} cards, {result['errors']} errors")

    print()
    print("=" * 70)
    print("  Next Steps:")
    print("=" * 70)
    print("1. SSH to your server:")
    print(f"   ssh user@54.87.11.69")
    print()
    print("2. Copy the validation script to the server:")
    print("   cd /opt/flashcard-app-teste/javumbo/server")
    print()
    print("3. Run validation:")
    print("   python3 validate_race_condition.py")
    print()
    print("The validation script will scan all databases for misrouted cards.")
    print("=" * 70)

if __name__ == "__main__":
    main()
