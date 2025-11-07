# Race Condition Unit Testing Guide

This document provides a comprehensive guide for setting up, executing, and cleaning up unit tests designed to detect and validate race conditions in the JAVUMBO flashcard application, specifically focusing on the suspected session-based race condition affecting multi-user concurrent operations.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Test Preparation](#2-test-preparation)
3. [Test Cleanup](#3-test-cleanup)
4. [Unit Test Framework](#4-unit-test-framework)
5. [Test Implementation](#5-test-implementation)
6. [Running the Tests](#6-running-the-tests)
7. [Interpreting Results](#7-interpreting-results)

---

## 1. Overview

### The Race Condition Problem

**Symptom**: Users report that flashcards they added never appear in their decks, suggesting cards may be written to other users' databases.

**Root Cause Hypothesis**:
- Flask-Session using filesystem-based sessions
- Gunicorn running with 3 worker **processes** (not threads)
- No inter-process synchronization on session file reads/writes
- Multiple workers can read stale session data simultaneously
- `session['user_id']` retrieved at route entry can be corrupted → wrong database targeted

**Why Unit Tests?**

Traditional integration tests may not consistently trigger race conditions because:
- They're timing-dependent
- They require specific concurrent execution patterns
- Standard sequential tests won't expose the bug

Our unit test framework will:
- Force concurrent execution using Python's `threading` and `multiprocessing`
- Embed traceable markers in test data
- Validate data integrity across all user databases
- Provide deterministic, repeatable test results

---

## 2. Test Preparation

### Step 1: Backup Current Data (Safety First!)

Before running any tests that might expose or trigger data corruption, create a complete backup.

```bash
# SSH to your AWS server
ssh user@54.87.11.69

# Navigate to your app directory
cd /opt/flashcard-app-teste/javumbo/server

# Create backup directory with timestamp
BACKUP_DIR="backups/pre_race_condition_test_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup admin database
cp admin.db $BACKUP_DIR/

# Backup all user databases
cp -r user_dbs $BACKUP_DIR/

# Backup session files
cp -r flask_session $BACKUP_DIR/

echo "✅ Backup created at: $BACKUP_DIR"
```

### Step 2: Document Current State

```bash
# Count existing users
sqlite3 admin.db "SELECT COUNT(*) FROM users;"

# List existing users
sqlite3 admin.db "SELECT user_id, username FROM users ORDER BY user_id;"

# Check if test users already exist
sqlite3 admin.db "SELECT username FROM users WHERE username LIKE 'test_race_%';"

# Note the output - you'll need to know which users are test users vs real users
```

### Step 3: Verify Server Configuration

```bash
# Check current Gunicorn worker count
docker exec flashcard_server ps aux | grep gunicorn

# Should show something like:
# gunicorn: master [app:app]
# gunicorn: worker [app:app]  (PID 101)
# gunicorn: worker [app:app]  (PID 102)
# gunicorn: worker [app:app]  (PID 103)

# Count workers (should be 3 for testing)
docker exec flashcard_server ps aux | grep "gunicorn: worker" | wc -l
```

### Step 4: Set Up Test Environment

```bash
# On your local development machine
cd /Users/emadruga/proj/javumbo/server

# Install test dependencies (if not already installed)
pip install -r requirements.txt

# Verify unittest is available (it's built-in)
python -c "import unittest; print('unittest available')"

# Install additional testing utilities
pip install requests  # For HTTP requests in tests
```

### Step 5: Configuration for Tests

Create a test configuration file:

```bash
# Create test config
cat > test_config_race_condition.json << 'EOF'
{
  "base_url": "http://54.87.11.69",
  "test_user_prefix": "test_race_",
  "num_test_users": 5,
  "cards_per_user": 50,
  "concurrent_threads": 10,
  "default_password": "test_password_123",
  "test_deck_name": "Race Condition Test Deck"
}
EOF
```

---

## 3. Test Cleanup

### Option A: Minimal Cleanup (Keep Test Data for Analysis)

Use this option if you want to inspect the test data after running tests.

```bash
# SSH to server
ssh user@54.87.11.69
cd /opt/flashcard-app-teste/javumbo/server

# Create archive of test results
RESULTS_DIR="backups/race_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p $RESULTS_DIR
cp user_dbs/test_race_*.db $RESULTS_DIR/

# Remove test users from admin DB (keeps their databases for forensics)
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'test_race_%';"

# Verify deletion
sqlite3 admin.db "SELECT COUNT(*) FROM users WHERE username LIKE 'test_race_%';"
# Should return: 0

echo "✅ Test users removed, databases archived to $RESULTS_DIR"
```

### Option B: Full Cleanup (Remove Everything)

Use this option to completely remove all traces of test data.

```bash
# SSH to server
ssh user@54.87.11.69
cd /opt/flashcard-app-teste/javumbo/server

# 1. Remove test users from admin database
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'test_race_%';"

# 2. Remove test user databases
rm -f user_dbs/test_race_*.db

# 3. Clear old session files (optional - they expire anyway)
find flask_session/ -type f -mtime +1 -delete

# 4. Verify cleanup
echo "Remaining users:"
sqlite3 admin.db "SELECT username FROM users;"

echo "Remaining user databases:"
ls -1 user_dbs/

# 5. Check disk space recovered
du -sh user_dbs/
```

### Option C: Automated Cleanup Script

Create a reusable cleanup script:

```bash
cat > cleanup_race_tests.sh << 'EOF'
#!/bin/bash

echo "🧹 Cleaning up race condition test data..."

# Configuration
TEST_USER_PREFIX="test_race_"
SERVER_PATH="/opt/flashcard-app-teste/javumbo/server"

# Change to server directory
cd $SERVER_PATH

# Count test users before cleanup
TEST_USER_COUNT=$(sqlite3 admin.db "SELECT COUNT(*) FROM users WHERE username LIKE '${TEST_USER_PREFIX}%';")
echo "Found $TEST_USER_COUNT test users to clean up"

# Optional: Archive test databases
read -p "Archive test databases before deletion? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ARCHIVE_DIR="backups/race_test_$(date +%Y%m%d_%H%M%S)"
    mkdir -p $ARCHIVE_DIR
    cp user_dbs/${TEST_USER_PREFIX}*.db $ARCHIVE_DIR/ 2>/dev/null
    echo "✅ Archived to $ARCHIVE_DIR"
fi

# Remove from admin database
sqlite3 admin.db "DELETE FROM users WHERE username LIKE '${TEST_USER_PREFIX}%';"

# Remove user databases
rm -f user_dbs/${TEST_USER_PREFIX}*.db

# Verify cleanup
REMAINING=$(sqlite3 admin.db "SELECT COUNT(*) FROM users WHERE username LIKE '${TEST_USER_PREFIX}%';")

if [ $REMAINING -eq 0 ]; then
    echo "✅ Cleanup complete! Removed $TEST_USER_COUNT test users"
else
    echo "⚠️  Warning: $REMAINING test users still remain"
fi
EOF

chmod +x cleanup_race_tests.sh
```

---

## 4. Unit Test Framework

### Test Architecture

Our unit tests will use Python's built-in `unittest` framework with the following structure:

```
server/
├── test_race_condition.py       # Main test suite
├── test_helpers/
│   ├── __init__.py
│   ├── race_test_client.py     # HTTP client for concurrent requests
│   ├── race_validator.py       # Database validation utilities
│   └── race_fixtures.py        # Test data generation
└── test_config_race_condition.json
```

### Key Testing Strategies

1. **Concurrent Request Simulation**: Use Python's `threading` or `asyncio` to send multiple simultaneous requests
2. **Embedded Markers**: Each test card contains metadata identifying its intended owner
3. **Post-Test Validation**: Scan all databases for misrouted cards
4. **Deterministic Execution**: Tests should be repeatable and produce consistent results
5. **Isolation**: Each test case should set up and tear down its own test users

### Test Categories

#### Category A: Session Integrity Tests
- Validate that `session['user_id']` remains consistent throughout a request
- Test concurrent logins from different users
- Verify session isolation between worker processes

#### Category B: Card Creation Race Condition Tests
- Simulate concurrent card creation from multiple users
- Validate that each card ends up in the correct user's database
- Check for cross-contamination

#### Category C: Database Write Contention Tests
- Test SQLite locking behavior under concurrent writes
- Verify that SQLite's WAL mode handles concurrent access correctly
- Confirm that the race condition is session-level, not database-level

#### Category D: Worker Process Tests
- Test behavior with different worker counts (1, 3, 5)
- Compare process-based vs thread-based workers
- Validate that single-worker configuration eliminates the race condition

---

## 5. Test Implementation

### Base Test Case Class

Create `server/test_race_condition.py`:

```python
import unittest
import requests
import sqlite3
import json
import time
import threading
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

# Load test configuration
with open('test_config_race_condition.json', 'r') as f:
    TEST_CONFIG = json.load(f)

BASE_URL = TEST_CONFIG['base_url']
TEST_USER_PREFIX = TEST_CONFIG['test_user_prefix']
NUM_TEST_USERS = TEST_CONFIG['num_test_users']
CARDS_PER_USER = TEST_CONFIG['cards_per_user']
CONCURRENT_THREADS = TEST_CONFIG['concurrent_threads']
DEFAULT_PASSWORD = TEST_CONFIG['default_password']


class RaceConditionTestCase(unittest.TestCase):
    """Base class for race condition tests with setup/teardown utilities."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests in this class."""
        print("\n" + "="*60)
        print("Setting up Race Condition Test Suite")
        print("="*60)
        cls.test_users = []
        cls.test_user_ids = {}
        cls.session_cookies = {}
        cls.created_card_ids = {}  # Track cards created by each user

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests in this class."""
        print("\n" + "="*60)
        print("Tearing down Race Condition Test Suite")
        print("="*60)
        cls._cleanup_test_users()

    def setUp(self):
        """Set up before each individual test."""
        self.test_start_time = time.time()
        print(f"\n🧪 Running: {self._testMethodName}")

    def tearDown(self):
        """Clean up after each individual test."""
        duration = time.time() - self.test_start_time
        print(f"✅ Completed: {self._testMethodName} ({duration:.2f}s)")

    # ========================================================================
    # Helper Methods: User Management
    # ========================================================================

    @classmethod
    def _create_test_user(cls, username: str, password: str, name: str) -> Tuple[bool, int]:
        """
        Create a single test user via the API.

        Returns:
            Tuple of (success: bool, user_id: int)
        """
        try:
            response = requests.post(
                f'{BASE_URL}/signup',
                json={'username': username, 'password': password, 'name': name},
                timeout=10
            )

            if response.status_code == 201:
                data = response.json()
                user_id = data.get('user_id')
                print(f"  ✅ Created user: {username} (ID: {user_id})")
                return True, user_id
            else:
                print(f"  ⚠️  Failed to create {username}: {response.status_code} - {response.text}")
                return False, None

        except Exception as e:
            print(f"  ❌ Exception creating {username}: {e}")
            return False, None

    @classmethod
    def _login_user(cls, username: str, password: str) -> requests.Session:
        """
        Log in a user and return a session with cookies.

        Returns:
            requests.Session object with authentication cookies
        """
        session = requests.Session()
        try:
            response = session.post(
                f'{BASE_URL}/login',
                json={'username': username, 'password': password},
                timeout=10
            )

            if response.status_code == 200:
                print(f"  ✅ Logged in: {username}")
                return session
            else:
                print(f"  ⚠️  Login failed for {username}: {response.status_code}")
                return None

        except Exception as e:
            print(f"  ❌ Login exception for {username}: {e}")
            return None

    @classmethod
    def _cleanup_test_users(cls):
        """Remove all test users from the system."""
        print("\n🧹 Cleaning up test users...")

        # Note: This requires direct database access or an admin API endpoint
        # For now, we'll document that manual cleanup is needed
        print(f"⚠️  Manual cleanup required:")
        print(f"   Run: sqlite3 admin.db \"DELETE FROM users WHERE username LIKE '{TEST_USER_PREFIX}%';\"")
        print(f"   Run: rm -f user_dbs/{TEST_USER_PREFIX}*.db")

    # ========================================================================
    # Helper Methods: Card Operations
    # ========================================================================

    def _add_card_with_marker(
        self,
        session: requests.Session,
        username: str,
        deck_id: int,
        sequence: int
    ) -> Tuple[bool, int, str]:
        """
        Add a single card with embedded ownership marker.

        Returns:
            Tuple of (success: bool, card_id: int, front_text: str)
        """
        timestamp = int(time.time() * 1000)
        front = f"[USER:{username}][SEQ:{sequence}][TIME:{timestamp}] Test Question {sequence}"
        back = f"Test Answer {sequence} [MARKER:{username}_{sequence}]"

        try:
            response = session.post(
                f'{BASE_URL}/add_card',
                json={'front': front, 'back': back, 'deck_id': deck_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                card_id = data.get('card_id')
                return True, card_id, front
            else:
                print(f"    ⚠️  Failed to add card for {username}: {response.status_code}")
                return False, None, front

        except Exception as e:
            print(f"    ❌ Exception adding card for {username}: {e}")
            return False, None, front

    def _add_cards_concurrently(
        self,
        username: str,
        password: str,
        deck_id: int,
        num_cards: int
    ) -> List[Tuple[bool, int, str]]:
        """
        Add multiple cards for a single user, simulating rapid user interaction.

        Returns:
            List of (success, card_id, front_text) tuples
        """
        session = self._login_user(username, password)
        if not session:
            return []

        results = []
        for i in range(num_cards):
            success, card_id, front = self._add_card_with_marker(session, username, deck_id, i)
            results.append((success, card_id, front))
            time.sleep(0.01)  # 10ms delay to simulate realistic user interaction

        return results

    # ========================================================================
    # Helper Methods: Database Validation
    # ========================================================================

    def _get_user_db_path(self, user_id: int) -> str:
        """Get the file path for a user's database."""
        # Adjust this path based on your server configuration
        return f"/opt/flashcard-app-teste/javumbo/server/user_dbs/user_{user_id}.db"

    def _validate_card_ownership(
        self,
        username: str,
        user_id: int,
        expected_card_ids: List[int]
    ) -> Dict:
        """
        Validate that all expected cards exist in the correct user's database
        and do NOT exist in any other user's database.

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'found_in_correct_db': int (count),
                'missing_cards': List[int],
                'found_in_wrong_dbs': List[Tuple[int, str]]  # (card_id, wrong_username)
            }
        """
        db_path = self._get_user_db_path(user_id)

        result = {
            'valid': True,
            'found_in_correct_db': 0,
            'missing_cards': [],
            'found_in_wrong_dbs': []
        }

        # Check correct database
        if not os.path.exists(db_path):
            print(f"  ⚠️  Database not found: {db_path}")
            result['valid'] = False
            return result

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for card_id in expected_card_ids:
            cursor.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
            if cursor.fetchone():
                result['found_in_correct_db'] += 1
            else:
                result['missing_cards'].append(card_id)
                result['valid'] = False

        conn.close()

        # Check all other test user databases for cross-contamination
        for other_username in self.test_users:
            if other_username == username:
                continue

            other_user_id = self.test_user_ids.get(other_username)
            if not other_user_id:
                continue

            other_db_path = self._get_user_db_path(other_user_id)
            if not os.path.exists(other_db_path):
                continue

            conn = sqlite3.connect(other_db_path)
            cursor = conn.cursor()

            for card_id in expected_card_ids:
                cursor.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
                if cursor.fetchone():
                    result['found_in_wrong_dbs'].append((card_id, other_username))
                    result['valid'] = False

            conn.close()

        return result

    def _scan_all_databases_for_markers(self) -> List[Dict]:
        """
        Scan all test user databases and extract ownership markers.

        Returns:
            List of dictionaries:
            [
                {
                    'database_owner': 'test_race_0',
                    'card_id': 123456,
                    'marker_username': 'test_race_1',  # From [USER:xxx] marker
                    'is_misrouted': bool
                },
                ...
            ]
        """
        violations = []

        for username in self.test_users:
            user_id = self.test_user_ids.get(username)
            if not user_id:
                continue

            db_path = self._get_user_db_path(user_id)
            if not os.path.exists(db_path):
                continue

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query all notes and extract markers
            cursor.execute("""
                SELECT c.id, n.flds
                FROM cards c
                JOIN notes n ON c.nid = n.id
            """)

            for card_id, fields in cursor.fetchall():
                # Extract [USER:xxx] marker from fields
                import re
                match = re.search(r'\[USER:([^\]]+)\]', fields)

                if match:
                    marker_username = match.group(1)
                    is_misrouted = (marker_username != username)

                    if is_misrouted:
                        violations.append({
                            'database_owner': username,
                            'card_id': card_id,
                            'marker_username': marker_username,
                            'is_misrouted': True,
                            'fields_preview': fields[:100]
                        })

            conn.close()

        return violations


# ============================================================================
# Test Cases: Session Integrity
# ============================================================================

class TestSessionIntegrity(RaceConditionTestCase):
    """Test session consistency under concurrent load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print("Creating test users for session integrity tests...")

        # Create 3 test users
        for i in range(3):
            username = f"{TEST_USER_PREFIX}{i}"
            password = DEFAULT_PASSWORD
            name = f"Test Race User {i}"

            success, user_id = cls._create_test_user(username, password, name)
            if success:
                cls.test_users.append(username)
                cls.test_user_ids[username] = user_id

    def test_concurrent_login_different_users(self):
        """
        Test that concurrent logins from different users don't interfere.

        This tests whether session files get corrupted when multiple users
        log in simultaneously.
        """
        def login_user(username):
            session = self._login_user(username, DEFAULT_PASSWORD)
            self.assertIsNotNone(session, f"Login failed for {username}")
            return (username, session)

        # Login all users concurrently
        with ThreadPoolExecutor(max_workers=len(self.test_users)) as executor:
            futures = [
                executor.submit(login_user, username)
                for username in self.test_users
            ]

            results = [future.result() for future in as_completed(futures)]

        # Verify all logins succeeded
        self.assertEqual(len(results), len(self.test_users))
        print(f"  ✅ All {len(results)} concurrent logins succeeded")

    def test_session_persistence_across_requests(self):
        """
        Test that a user's session remains valid across multiple requests.

        This tests whether session data remains consistent when the same
        user makes multiple rapid requests.
        """
        username = self.test_users[0]
        session = self._login_user(username, DEFAULT_PASSWORD)
        self.assertIsNotNone(session)

        # Make 10 rapid requests to /decks endpoint
        for i in range(10):
            response = session.get(f'{BASE_URL}/decks', timeout=10)
            self.assertEqual(
                response.status_code,
                200,
                f"Request {i} failed with status {response.status_code}"
            )

        print(f"  ✅ Session remained valid across 10 requests")


# ============================================================================
# Test Cases: Card Creation Race Conditions
# ============================================================================

class TestCardCreationRaceCondition(RaceConditionTestCase):
    """Test for race conditions during concurrent card creation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print("Creating test users for card creation race condition tests...")

        # Create 5 test users
        for i in range(5):
            username = f"{TEST_USER_PREFIX}{i}"
            password = DEFAULT_PASSWORD
            name = f"Test Race User {i}"

            success, user_id = cls._create_test_user(username, password, name)
            if success:
                cls.test_users.append(username)
                cls.test_user_ids[username] = user_id
                cls.created_card_ids[username] = []

    def test_concurrent_card_creation_same_user(self):
        """
        Test card creation when the same user adds cards from multiple threads.

        Simulates a user clicking "Add Card" rapidly or from multiple tabs.
        """
        username = self.test_users[0]
        user_id = self.test_user_ids[username]
        deck_id = 1  # Default deck
        num_cards = 20

        # Add cards concurrently from same user
        results = self._add_cards_concurrently(username, DEFAULT_PASSWORD, deck_id, num_cards)

        # Extract successful card IDs
        successful_cards = [card_id for success, card_id, _ in results if success and card_id]

        # Validate all cards are in correct database
        validation = self._validate_card_ownership(username, user_id, successful_cards)

        self.assertTrue(validation['valid'], f"Validation failed: {validation}")
        self.assertEqual(
            validation['found_in_correct_db'],
            len(successful_cards),
            f"Expected {len(successful_cards)} cards, found {validation['found_in_correct_db']}"
        )
        self.assertEqual(
            len(validation['found_in_wrong_dbs']),
            0,
            f"Found cards in wrong databases: {validation['found_in_wrong_dbs']}"
        )

        print(f"  ✅ All {len(successful_cards)} cards in correct database, no cross-contamination")

    def test_concurrent_card_creation_multiple_users(self):
        """
        Test card creation when multiple users add cards simultaneously.

        This is the PRIMARY test for detecting the race condition.
        """
        deck_id = 1  # Default deck
        cards_per_user = 30

        # Add cards concurrently from all users
        with ThreadPoolExecutor(max_workers=len(self.test_users)) as executor:
            futures = {
                executor.submit(
                    self._add_cards_concurrently,
                    username,
                    DEFAULT_PASSWORD,
                    deck_id,
                    cards_per_user
                ): username
                for username in self.test_users
            }

            results_by_user = {}
            for future in as_completed(futures):
                username = futures[future]
                results = future.result()
                results_by_user[username] = results

        # Validate each user's cards
        all_valid = True
        total_violations = 0

        for username, results in results_by_user.items():
            user_id = self.test_user_ids[username]
            successful_cards = [card_id for success, card_id, _ in results if success and card_id]

            validation = self._validate_card_ownership(username, user_id, successful_cards)

            if not validation['valid']:
                all_valid = False
                print(f"\n  ⚠️  RACE CONDITION DETECTED for {username}!")
                print(f"     Expected: {len(successful_cards)} cards")
                print(f"     Found in correct DB: {validation['found_in_correct_db']}")
                print(f"     Missing: {validation['missing_cards']}")
                print(f"     Found in wrong DBs: {validation['found_in_wrong_dbs']}")
                total_violations += len(validation['found_in_wrong_dbs'])

        # Perform marker-based scan
        violations = self._scan_all_databases_for_markers()

        if violations:
            print(f"\n  🚨 MARKER VALIDATION DETECTED {len(violations)} MISROUTED CARDS:")
            for v in violations[:5]:  # Show first 5
                print(f"     Card {v['card_id']}: belongs to {v['marker_username']}, "
                      f"found in {v['database_owner']}'s database")

        # Assertions
        self.assertTrue(
            all_valid,
            f"Race condition detected! {total_violations} cards in wrong databases"
        )
        self.assertEqual(
            len(violations),
            0,
            f"Marker validation found {len(violations)} misrouted cards"
        )

        print(f"\n  ✅ All cards correctly routed, no race condition detected")


# ============================================================================
# Test Cases: Worker Configuration
# ============================================================================

class TestWorkerConfiguration(RaceConditionTestCase):
    """Test race condition behavior with different worker configurations."""

    def test_single_worker_baseline(self):
        """
        Baseline test: Verify no race condition with single worker.

        NOTE: This requires temporarily changing Docker configuration to use
        --workers 1, then rebuilding and restarting the server.
        """
        self.skipTest("Requires manual server reconfiguration with --workers 1")

    def test_three_workers_race_condition(self):
        """
        Primary test: Verify race condition with 3 workers (current config).

        This test documents the expected behavior with the current configuration.
        """
        # This is essentially the same as test_concurrent_card_creation_multiple_users
        # but explicitly documents the worker configuration being tested
        pass


# ============================================================================
# Main Test Runner
# ============================================================================

if __name__ == '__main__':
    # Configure unittest output
    unittest.main(verbosity=2)
```

### Test Helper Modules

Create `server/test_helpers/__init__.py`:

```python
"""Helper modules for race condition testing."""
```

Create `server/test_helpers/race_validator.py`:

```python
"""Database validation utilities for race condition tests."""

import sqlite3
import os
import re
from typing import List, Dict, Tuple


def get_all_test_users(admin_db_path: str, test_prefix: str) -> List[Tuple[int, str]]:
    """
    Get all test users from admin database.

    Returns:
        List of (user_id, username) tuples
    """
    conn = sqlite3.connect(admin_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, username FROM users WHERE username LIKE ?",
        (f"{test_prefix}%",)
    )
    results = cursor.fetchall()
    conn.close()
    return results


def extract_user_marker_from_note(note_fields: str) -> str:
    """
    Extract the [USER:xxx] marker from a note's fields.

    Args:
        note_fields: The flds column from the notes table

    Returns:
        The username from the marker, or None if not found
    """
    match = re.search(r'\[USER:([^\]]+)\]', note_fields)
    return match.group(1) if match else None


def validate_database_integrity(
    user_db_path: str,
    expected_username: str
) -> Dict:
    """
    Validate that all cards in a database belong to the expected user.

    Returns:
        {
            'valid': bool,
            'total_cards': int,
            'misrouted_cards': List[Dict]
        }
    """
    if not os.path.exists(user_db_path):
        return {
            'valid': False,
            'total_cards': 0,
            'misrouted_cards': [],
            'error': 'Database file not found'
        }

    conn = sqlite3.connect(user_db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id, n.flds
        FROM cards c
        JOIN notes n ON c.nid = n.id
    """)

    all_cards = cursor.fetchall()
    misrouted = []

    for card_id, fields in all_cards:
        marker_username = extract_user_marker_from_note(fields)

        if marker_username and marker_username != expected_username:
            misrouted.append({
                'card_id': card_id,
                'expected_user': expected_username,
                'actual_user': marker_username,
                'fields_preview': fields[:150]
            })

    conn.close()

    return {
        'valid': len(misrouted) == 0,
        'total_cards': len(all_cards),
        'misrouted_cards': misrouted
    }


def generate_integrity_report(
    admin_db_path: str,
    user_dbs_dir: str,
    test_prefix: str
) -> Dict:
    """
    Generate a comprehensive integrity report for all test users.

    Returns:
        {
            'total_users': int,
            'total_cards': int,
            'total_violations': int,
            'users': List[Dict]
        }
    """
    test_users = get_all_test_users(admin_db_path, test_prefix)

    report = {
        'total_users': len(test_users),
        'total_cards': 0,
        'total_violations': 0,
        'users': []
    }

    for user_id, username in test_users:
        user_db_path = os.path.join(user_dbs_dir, f"user_{user_id}.db")
        validation = validate_database_integrity(user_db_path, username)

        report['total_cards'] += validation['total_cards']
        report['total_violations'] += len(validation['misrouted_cards'])

        report['users'].append({
            'username': username,
            'user_id': user_id,
            'validation': validation
        })

    return report
```

---

## 6. Running the Tests

### Method 1: Run All Tests

```bash
cd /Users/emadruga/proj/javumbo/server

# Run all race condition tests
python -m unittest test_race_condition.py -v
```

Expected output:
```
==============================================================
Setting up Race Condition Test Suite
==============================================================
  ✅ Created user: test_race_0 (ID: 42)
  ✅ Created user: test_race_1 (ID: 43)
  ✅ Created user: test_race_2 (ID: 44)

🧪 Running: test_concurrent_login_different_users
  ✅ Logged in: test_race_0
  ✅ Logged in: test_race_1
  ✅ Logged in: test_race_2
  ✅ All 3 concurrent logins succeeded
✅ Completed: test_concurrent_login_different_users (1.23s)
.

🧪 Running: test_concurrent_card_creation_multiple_users
  ✅ Logged in: test_race_0
  ✅ Logged in: test_race_1
  ...
  ⚠️  RACE CONDITION DETECTED for test_race_1!
     Expected: 30 cards
     Found in correct DB: 28
     Missing: []
     Found in wrong DBs: [(1730847201234, 'test_race_0'), (1730847203456, 'test_race_2')]

  🚨 MARKER VALIDATION DETECTED 2 MISROUTED CARDS:
     Card 1730847201234: belongs to test_race_1, found in test_race_0's database
     Card 1730847203456: belongs to test_race_1, found in test_race_2's database
F
...

FAILED (failures=1)
```

### Method 2: Run Specific Test Class

```bash
# Run only session integrity tests
python -m unittest test_race_condition.TestSessionIntegrity -v

# Run only card creation tests
python -m unittest test_race_condition.TestCardCreationRaceCondition -v
```

### Method 3: Run Single Test Case

```bash
# Run just the main concurrent card creation test
python -m unittest test_race_condition.TestCardCreationRaceCondition.test_concurrent_card_creation_multiple_users -v
```

### Method 4: Run with Custom Configuration

Create a test runner script:

```python
# run_race_tests.py
import sys
import unittest
import json

# Override configuration
TEST_CONFIG_OVERRIDE = {
    "num_test_users": 3,  # Fewer users for faster testing
    "cards_per_user": 20,  # Fewer cards
    "concurrent_threads": 5
}

# Save override config
with open('test_config_race_condition.json', 'w') as f:
    json.dump({
        "base_url": "http://54.87.11.69",
        "test_user_prefix": "test_race_",
        **TEST_CONFIG_OVERRIDE,
        "default_password": "test_password_123",
        "test_deck_name": "Race Condition Test Deck"
    }, f, indent=2)

# Run tests
loader = unittest.TestLoader()
suite = loader.loadTestsFromName('test_race_condition')
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with error code if tests failed
sys.exit(0 if result.wasSuccessful() else 1)
```

Run it:
```bash
python run_race_tests.py
```

---

## 7. Interpreting Results

### Success Case (No Race Condition)

```
test_concurrent_card_creation_multiple_users (test_race_condition.TestCardCreationRaceCondition) ...
  ✅ All cards correctly routed, no race condition detected
ok

----------------------------------------------------------------------
Ran 1 test in 5.234s

OK
```

**Interpretation**: The system correctly handles concurrent requests. All cards ended up in the correct user databases.

### Failure Case (Race Condition Detected)

```
test_concurrent_card_creation_multiple_users (test_race_condition.TestCardCreationRaceCondition) ...
  ⚠️  RACE CONDITION DETECTED for test_race_1!
     Expected: 30 cards
     Found in correct DB: 28
     Missing: []
     Found in wrong DBs: [(1730847201234, 'test_race_0'), (1730847203456, 'test_race_2')]

  🚨 MARKER VALIDATION DETECTED 2 MISROUTED CARDS:
     Card 1730847201234: belongs to test_race_1, found in test_race_0's database
     Card 1730847203456: belongs to test_race_1, found in test_race_2's database
FAIL

----------------------------------------------------------------------
Ran 1 test in 5.234s

FAILED (failures=1)
```

**Interpretation**: Race condition confirmed! User `test_race_1` created 30 cards, but 2 of them ended up in other users' databases.

### Analyzing Failure Details

When a test fails, examine the output to determine:

1. **Which users are affected?**
   - Look for "RACE CONDITION DETECTED for [username]"

2. **How many cards were misrouted?**
   - Check the "Found in wrong DBs" count

3. **What's the pattern?**
   - Are all violations from the same user?
   - Are they concentrated in time? (check timestamps in markers)
   - Do they correlate with high concurrency? (multiple users active simultaneously)

4. **Is it reproducible?**
   - Run the test multiple times
   - Does it fail consistently or intermittently?
   - Intermittent failures suggest a narrow race window

### Post-Failure Investigation

After detecting a race condition:

```bash
# SSH to server
ssh user@54.87.11.69
cd /opt/flashcard-app-teste/javumbo/server

# Generate detailed integrity report
python3 << 'EOF'
from test_helpers.race_validator import generate_integrity_report
import json

report = generate_integrity_report(
    'admin.db',
    'user_dbs',
    'test_race_'
)

print(json.dumps(report, indent=2))
EOF
```

### Metrics to Track

For each test run, track:

- **Total cards created**: `num_users * cards_per_user`
- **Successful API responses**: Count of 200 OK responses
- **Cards in correct databases**: Should equal successful responses
- **Cards in wrong databases**: Should be 0 (any value > 0 indicates race condition)
- **Missing cards**: Should be 0 (indicates data loss)
- **Test duration**: Shorter duration = higher concurrency = more likely to trigger race

### Expected Behavior by Configuration

| Configuration | Expected Result |
|---------------|----------------|
| 1 worker (sync) | ✅ No race condition |
| 3 workers (sync) | ⚠️ Race condition likely |
| 1 worker + threads | ⚠️ Race condition possible but less likely |
| 3 workers + Redis | ✅ No race condition |

---

## 8. Next Steps After Testing

### If Race Condition is Confirmed

1. **Document Evidence**
   - Save test output logs
   - Create database snapshots
   - Screenshot failure details

2. **Implement Fix** (Redis Migration)
   - See: [SESSION_ARCHITECTURE_ANALYSIS.md](SESSION_ARCHITECTURE_ANALYSIS.md)
   - Add Redis to `docker-compose.yml`
   - Update Flask configuration
   - Migrate session storage

3. **Re-run Tests**
   - Verify tests pass after Redis migration
   - Confirm 0 violations with same test parameters

4. **Load Testing**
   - Run comprehensive load tests from [LOAD_TESTING_PLAN.md](LOAD_TESTING_PLAN.md)
   - Validate under production-like load

### If No Race Condition is Found

1. **Increase Test Intensity**
   - More users (10-20)
   - More cards per user (100-200)
   - Shorter delays (1-5ms)
   - Longer test duration

2. **Test with Real Network Conditions**
   - Add artificial network latency
   - Simulate packet loss
   - Test from multiple geographic locations

3. **Review User Reports**
   - If users still report issues, investigate alternative root causes
   - Check server logs for other errors
   - Review database file permissions

---

## Appendix A: Quick Reference Commands

### Setup
```bash
cd /Users/emadruga/proj/javumbo/server
pip install requests
python -m unittest test_race_condition.TestCardCreationRaceCondition.test_concurrent_card_creation_multiple_users -v
```

### Cleanup
```bash
ssh user@54.87.11.69
cd /opt/flashcard-app-teste/javumbo/server
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'test_race_%';"
rm -f user_dbs/test_race_*.db
```

### Validation
```bash
# Check for misrouted cards
for db in user_dbs/test_race_*.db; do
  echo "=== $(basename $db) ==="
  sqlite3 "$db" "SELECT flds FROM notes LIMIT 3;"
done | grep -A2 "USER:test_race"
```

### Generate Report
```bash
python3 -c "
from test_helpers.race_validator import generate_integrity_report
import json
report = generate_integrity_report('admin.db', 'user_dbs', 'test_race_')
print(json.dumps(report, indent=2))
"
```

---

## Appendix B: Troubleshooting

### Problem: "Connection refused" errors

**Cause**: Server not running or wrong URL

**Solution**:
```bash
# Verify server is running
docker ps | grep flashcard_server

# Test connectivity
curl http://54.87.11.69/

# Check URL in test_config_race_condition.json
cat test_config_race_condition.json | grep base_url
```

### Problem: "Permission denied" accessing database files

**Cause**: Test running from wrong location or insufficient permissions

**Solution**:
```bash
# Tests that validate databases must run ON the server, not remotely
ssh user@54.87.11.69
cd /opt/flashcard-app-teste/javumbo/server
python -m unittest test_race_condition -v
```

### Problem: Tests hang or timeout

**Cause**: Deadlock in server or database lock contention

**Solution**:
```bash
# Check server logs
docker logs flashcard_server | tail -50

# Restart server
docker compose restart

# Reduce test intensity in config
```

### Problem: "User already exists" errors

**Cause**: Previous test run didn't clean up

**Solution**:
```bash
# Run cleanup script
./cleanup_race_tests.sh

# Or manual cleanup
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'test_race_%';"
rm -f user_dbs/test_race_*.db
```

---

**Document Version**: 1.0
**Last Updated**: 2025-01-06
**Related Documents**:
- [LOAD_TESTING_PLAN.md](LOAD_TESTING_PLAN.md)
- [GUNICORN_WORKERS_ANALYSIS.md](GUNICORN_WORKERS_ANALYSIS.md)
- [SESSION_ARCHITECTURE_ANALYSIS.md](SESSION_ARCHITECTURE_ANALYSIS.md)
