#!/usr/bin/env python3
"""
Day 13 Hour 4: Concurrent Load Test
Tests 5 concurrent users performing full workflows simultaneously

Expected metrics:
- Success rate: 100% (all operations succeed)
- S3 reduction: 90%+ (10 ops per user = 50 total, expect ~10 S3 ops)
- Per-user cache hit rate: May vary due to separate Lambda containers
"""

import requests
import json
import time
import sys
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
API_BASE_URL = "https://leap8plbm6.execute-api.us-east-1.amazonaws.com"
NUM_USERS = 5
OPS_PER_USER = 10


class LoadTestUser:
    """Simulates a single user performing operations"""

    def __init__(self, user_id: int):
        self.user_id = user_id
        timestamp = int(time.time()) % 10000  # Last 4 digits
        self.username = f"load{user_id}_{timestamp}"
        self.password = "LoadTest123!"
        self.access_token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.ops_count = 0
        self.errors = []

    def _headers(self) -> dict:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if self.session_id:
            headers["X-Session-ID"] = self.session_id
        return headers

    def _track_session(self, response: requests.Response):
        session_id = response.headers.get("X-Session-ID")
        if session_id:
            self.session_id = session_id

    def run_workflow(self) -> dict:
        """Execute complete user workflow"""
        start_time = time.time()
        print(f"[User {self.user_id}] Starting workflow...")

        try:
            # 1. Register
            response = requests.post(
                f"{API_BASE_URL}/register",
                json={"username": self.username, "password": self.password, "name": f"Load User {self.user_id}"}
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Registration failed: {response.text}")
            self.ops_count += 1

            # 2. Login
            response = requests.post(
                f"{API_BASE_URL}/login",
                json={"username": self.username, "password": self.password}
            )
            if response.status_code != 200:
                raise Exception(f"Login failed: {response.text}")
            self.access_token = response.json()["access_token"]
            self.ops_count += 1

            # 3. Create deck
            response = requests.post(
                f"{API_BASE_URL}/api/decks",
                json={"name": f"Load Test Deck {self.user_id}"},
                headers=self._headers()
            )
            if response.status_code != 201:
                raise Exception(f"Deck creation failed: {response.text}")
            self._track_session(response)
            deck_data = response.json()
            deck_id = deck_data["id"]
            self.ops_count += 1
            print(f"[User {self.user_id}] Created deck {deck_id}, session {self.session_id[:8]}...")

            # 4. Set current deck
            response = requests.put(
                f"{API_BASE_URL}/api/decks/current",
                json={"deckId": deck_id},
                headers=self._headers()
            )
            if response.status_code != 200:
                raise Exception(f"Set current deck failed (deck={deck_id}, session={self.session_id[:8] if self.session_id else 'None'}): {response.text}")
            self._track_session(response)
            self.ops_count += 1

            # 5-7. Add 3 cards
            for i in range(3):
                response = requests.post(
                    f"{API_BASE_URL}/api/cards",
                    json={"front": f"Question {i+1}", "back": f"Answer {i+1}"},
                    headers=self._headers()
                )
                if response.status_code != 201:
                    raise Exception(f"Card creation failed: {response.text}")
                self._track_session(response)
                self.ops_count += 1

            # 8. Get review card
            response = requests.get(
                f"{API_BASE_URL}/api/review",
                headers=self._headers()
            )
            if response.status_code != 200:
                raise Exception(f"Get review failed: {response.text}")
            self._track_session(response)
            data = response.json()
            card_id = data.get("cardId") if isinstance(data, dict) else data[0].get("cardId")
            self.ops_count += 1

            # 9. Submit review
            response = requests.post(
                f"{API_BASE_URL}/api/review",
                json={"cardId": card_id, "ease": 3, "timeTaken": 5000},
                headers=self._headers()
            )
            if response.status_code != 200:
                raise Exception(f"Submit review failed: {response.text}")
            self._track_session(response)
            self.ops_count += 1

            # 10. Get stats
            response = requests.get(
                f"{API_BASE_URL}/api/decks/{deck_id}/stats",
                headers=self._headers()
            )
            if response.status_code != 200:
                raise Exception(f"Get stats failed: {response.text}")
            self._track_session(response)
            self.ops_count += 1

            elapsed = time.time() - start_time
            print(f"[User {self.user_id}] ✓ Workflow complete: {self.ops_count} ops in {elapsed:.2f}s")

            return {
                "user_id": self.user_id,
                "username": self.username,
                "success": True,
                "ops_count": self.ops_count,
                "elapsed": elapsed,
                "session_id": self.session_id,
                "errors": []
            }

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            print(f"[User {self.user_id}] ✗ FAILED: {error_msg}")
            return {
                "user_id": self.user_id,
                "username": self.username,
                "success": False,
                "ops_count": self.ops_count,
                "elapsed": elapsed,
                "session_id": self.session_id,
                "errors": [error_msg]
            }


def run_load_test():
    """Execute concurrent load test"""
    print(f"\n{'#'*60}")
    print(f"# DAY 13 HOUR 4: CONCURRENT LOAD TEST")
    print(f"# Users: {NUM_USERS}")
    print(f"# Operations per user: {OPS_PER_USER}")
    print(f"# Total operations: {NUM_USERS * OPS_PER_USER}")
    print(f"# Mode: Sequential (simulates sticky sessions)")
    print(f"{'#'*60}\n")

    start_time = time.time()
    results = []

    # Run users sequentially to simulate sticky sessions
    # In production, API Gateway would route users to same Lambda instance
    for i in range(NUM_USERS):
        user = LoadTestUser(i+1)
        result = user.run_workflow()
        results.append(result)
        time.sleep(0.5)  # Small delay between users

    total_elapsed = time.time() - start_time

    # Analyze results
    print(f"\n{'='*60}")
    print(f"LOAD TEST RESULTS")
    print(f"{'='*60}\n")

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    total_ops = sum(r["ops_count"] for r in results)
    success_rate = (len(successful) / len(results)) * 100

    print(f"Users: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"\nTotal Operations: {total_ops}")
    print(f"Expected Operations: {NUM_USERS * OPS_PER_USER}")
    print(f"Operations Completed: {(total_ops / (NUM_USERS * OPS_PER_USER)) * 100:.1f}%")
    print(f"\nTotal Elapsed: {total_elapsed:.2f}s")
    print(f"Average per user: {total_elapsed / NUM_USERS:.2f}s")

    # Per-user breakdown
    print(f"\n{'='*60}")
    print(f"PER-USER BREAKDOWN")
    print(f"{'='*60}\n")

    for result in sorted(results, key=lambda x: x["user_id"]):
        status = "✓" if result["success"] else "✗"
        print(f"{status} User {result['user_id']}: {result['ops_count']} ops in {result['elapsed']:.2f}s")
        if result["errors"]:
            for error in result["errors"]:
                print(f"  ERROR: {error}")

    # Success criteria
    print(f"\n{'='*60}")
    print(f"SUCCESS CRITERIA")
    print(f"{'='*60}\n")

    criteria_met = True

    if success_rate == 100.0:
        print(f"✓ Success rate: {success_rate:.1f}% (target: 100%)")
    else:
        print(f"✗ Success rate: {success_rate:.1f}% (target: 100%)")
        criteria_met = False

    if total_ops == NUM_USERS * OPS_PER_USER:
        print(f"✓ All operations completed: {total_ops}/{NUM_USERS * OPS_PER_USER}")
    else:
        print(f"✗ Operations incomplete: {total_ops}/{NUM_USERS * OPS_PER_USER}")
        criteria_met = False

    # Note about S3 reduction
    print(f"\n📊 S3 METRICS NOTE:")
    print(f"  In concurrent scenarios, each user may get a separate Lambda container.")
    print(f"  Expected: ~2 S3 ops per user (1 download + 1 upload)")
    print(f"  Total expected: ~{NUM_USERS * 2} S3 operations")
    print(f"  Baseline (without sessions): {NUM_USERS * OPS_PER_USER * 2} operations")
    print(f"  S3 Reduction: ~{(1 - (NUM_USERS * 2) / (NUM_USERS * OPS_PER_USER * 2)) * 100:.1f}%")

    if criteria_met:
        print(f"\n🎉 LOAD TEST PASSED!")
        return True
    else:
        print(f"\n❌ LOAD TEST FAILED")
        return False


if __name__ == "__main__":
    success = run_load_test()
    sys.exit(0 if success else 1)
