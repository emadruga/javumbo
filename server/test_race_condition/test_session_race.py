#!/usr/bin/env python3
"""
Session race condition test - simulates rapid session switching.
This test specifically targets session corruption by having workers
rapidly login as different users and then create cards.

If session corruption occurs, a worker might create a card while
"thinking" it's logged in as user A, but the card goes to user B's database.
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://54.226.2.146"
PASSWORD = "password123test"
CARDS_PER_CYCLE = 10
CYCLES = 5  # Each worker will login/create/logout 5 times
NUM_USERS = 15  # Number of test users

# Generate users dynamically
USERS = [(f"race{i}", i) for i in range(NUM_USERS)]

def session_thrash_worker(worker_id):
    """
    Rapidly login as different users and create cards.
    This maximizes the chance of session corruption.
    """
    results = {
        "worker_id": worker_id,
        "cards_created": 0,
        "errors": 0,
        "cycles_completed": 0
    }

    for cycle in range(CYCLES):
        # Pick a user for this cycle (rotate through users)
        username, user_num = USERS[cycle % len(USERS)]

        session = requests.Session()

        try:
            # LOGIN
            response = session.post(
                f"{BASE_URL}/login",
                json={"username": username, "password": PASSWORD},
                timeout=10
            )

            if response.status_code != 200:
                print(f"  ⚠️  Worker {worker_id}, Cycle {cycle}: Login failed as {username}")
                results["errors"] += 1
                continue

            print(f"  Worker {worker_id}, Cycle {cycle}: Logged in as {username}")

            # RAPIDLY CREATE CARDS
            for i in range(CARDS_PER_CYCLE):
                timestamp = int(time.time() * 1000)
                front = f"[USER:{username}][WORKER:{worker_id}][CYCLE:{cycle}][SEQ:{i}][TIME:{timestamp}] Session Test {i}"
                back = f"Answer {i} [MARKER:{username}_{worker_id}_{cycle}_{i}]"

                try:
                    response = session.post(
                        f"{BASE_URL}/add_card",
                        json={"front": front, "back": back},
                        timeout=10
                    )

                    if response.status_code in [200, 201]:
                        results["cards_created"] += 1
                    else:
                        results["errors"] += 1
                        if results["errors"] <= 3:
                            try:
                                error = response.json().get('error', 'Unknown')
                                print(f"    ⚠️  Worker {worker_id}, Cycle {cycle}, Card {i}: {response.status_code} - {error}")
                            except:
                                print(f"    ⚠️  Worker {worker_id}, Cycle {cycle}, Card {i}: {response.status_code}")

                except Exception as e:
                    results["errors"] += 1
                    if results["errors"] <= 3:
                        print(f"    ❌ Worker {worker_id}, Cycle {cycle}, Card {i}: {e}")

                # Very short delay to maximize concurrency
                time.sleep(0.001)  # 1ms

            # LOGOUT (to force session cleanup)
            try:
                session.post(f"{BASE_URL}/logout", timeout=5)
            except:
                pass

            results["cycles_completed"] += 1

        except Exception as e:
            print(f"  ❌ Worker {worker_id}, Cycle {cycle}: Exception - {e}")
            results["errors"] += 1

        # Small delay between cycles
        time.sleep(0.01)  # 10ms

    print(f"✅ Worker {worker_id}: {results['cards_created']} cards, {results['errors']} errors, {results['cycles_completed']} cycles")
    return results

def main():
    print("=" * 70)
    print("  Session Race Condition Test")
    print("=" * 70)
    print(f"Target: {BASE_URL}")
    print(f"Cards per cycle: {CARDS_PER_CYCLE}")
    print(f"Cycles per worker: {CYCLES}")
    print(f"Workers: {len(USERS)}")
    print(f"Expected total cards: {len(USERS) * CYCLES * CARDS_PER_CYCLE}")
    print()
    print("This test rapidly logs in as different users to maximize")
    print("the chance of triggering session corruption.")
    print()

    start_time = time.time()

    # Launch workers
    with ThreadPoolExecutor(max_workers=len(USERS)) as executor:
        futures = [
            executor.submit(session_thrash_worker, worker_id)
            for worker_id in range(len(USERS))
        ]

        results = [future.result() for future in as_completed(futures)]

    duration = time.time() - start_time

    # Calculate totals
    total_cards = sum(r["cards_created"] for r in results)
    total_errors = sum(r["errors"] for r in results)

    print()
    print("=" * 70)
    print("  Test Complete")
    print("=" * 70)
    print(f"Duration: {duration:.2f} seconds")
    print(f"Total cards created: {total_cards}")
    print(f"Total errors: {total_errors}")
    print()
    print("Next: Run validation on server to check for cross-contamination")
    print("  ssh ubuntu@54.226.2.146")
    print("  cd ~/javumbo/server")
    print("  python3 validate_race_condition.py")
    print()

if __name__ == "__main__":
    main()
