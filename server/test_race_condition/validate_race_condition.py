#!/usr/bin/env python3
"""
Validation script to detect race condition evidence.
Run this ON THE SERVER after the load test.

Usage: python3 validate_race_condition.py
"""

import sqlite3
import os
import re
import json

ADMIN_DB = "admin.db"
USER_DBS_DIR = "user_dbs"
TEST_USER_PREFIX = "race"

def get_test_users():
    """Get all test users from admin database."""
    try:
        conn = sqlite3.connect(ADMIN_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, username FROM users WHERE username LIKE ?",
            (f"{TEST_USER_PREFIX}%",)
        )
        users = cursor.fetchall()
        conn.close()
        return users
    except Exception as e:
        print(f"❌ Error reading admin DB: {e}")
        return []

def extract_user_marker(note_fields):
    """Extract [USER:xxx] marker from note fields."""
    match = re.search(r'\[USER:([^\]]+)\]', note_fields)
    return match.group(1) if match else None

def validate_user_database(user_id, username):
    """
    Validate that all cards in a user's database belong to that user.
    Returns dict with validation results.
    """
    db_path = os.path.join(USER_DBS_DIR, f"user_{user_id}.db")

    if not os.path.exists(db_path):
        return {
            "valid": False,
            "error": "Database file not found",
            "total_cards": 0,
            "misrouted_cards": []
        }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all cards with their note content
        cursor.execute("""
            SELECT c.id, n.flds
            FROM cards c
            JOIN notes n ON c.nid = n.id
        """)

        all_cards = cursor.fetchall()
        misrouted = []

        for card_id, fields in all_cards:
            marker_username = extract_user_marker(fields)

            if marker_username and marker_username != username:
                # Found a card that belongs to a different user!
                misrouted.append({
                    "card_id": card_id,
                    "expected_user": username,
                    "actual_user": marker_username,
                    "fields_preview": fields[:150]
                })

        conn.close()

        return {
            "valid": len(misrouted) == 0,
            "total_cards": len(all_cards),
            "misrouted_cards": misrouted
        }

    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "total_cards": 0,
            "misrouted_cards": []
        }

def main():
    print("=" * 70)
    print("  Race Condition Validation")
    print("=" * 70)
    print()

    # Check if we're in the right directory
    if not os.path.exists(ADMIN_DB):
        print(f"❌ Error: {ADMIN_DB} not found!")
        print(f"   Make sure you're running this from the server directory:")
        print(f"   cd /opt/flashcard-app-teste/javumbo/server")
        print()
        return

    if not os.path.exists(USER_DBS_DIR):
        print(f"❌ Error: {USER_DBS_DIR} directory not found!")
        return

    # Get test users
    test_users = get_test_users()

    if not test_users:
        print("⚠️  No test users found!")
        print(f"   Looking for users with prefix: {TEST_USER_PREFIX}")
        print()
        return

    print(f"Found {len(test_users)} test users:")
    for user_id, username in test_users:
        print(f"  - {username} (ID: {user_id})")
    print()

    # Validate each user's database
    print("Scanning databases for misrouted cards...")
    print()

    total_cards = 0
    total_violations = 0
    violation_details = []

    for user_id, username in test_users:
        print(f"Checking {username} (ID: {user_id})...")

        validation = validate_user_database(user_id, username)

        if "error" in validation:
            print(f"  ❌ Error: {validation['error']}")
            continue

        total_cards += validation["total_cards"]
        num_misrouted = len(validation["misrouted_cards"])

        if num_misrouted > 0:
            total_violations += num_misrouted
            print(f"  🚨 RACE CONDITION DETECTED!")
            print(f"     Total cards: {validation['total_cards']}")
            print(f"     Misrouted cards: {num_misrouted}")

            for violation in validation["misrouted_cards"][:3]:  # Show first 3
                print(f"     - Card {violation['card_id']}: belongs to {violation['actual_user']}")

            violation_details.extend(validation["misrouted_cards"])
        else:
            print(f"  ✅ OK - {validation['total_cards']} cards, all correctly routed")

    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"Total cards scanned: {total_cards}")
    print(f"Total violations found: {total_violations}")
    print()

    if total_violations > 0:
        print("🚨 RACE CONDITION CONFIRMED!")
        print()
        print(f"Found {total_violations} cards in wrong databases.")
        print()
        print("Evidence:")

        # Group violations by owner
        by_owner = {}
        for v in violation_details:
            owner = v["expected_user"]
            if owner not in by_owner:
                by_owner[owner] = []
            by_owner[owner].append(v)

        for owner, violations in by_owner.items():
            print(f"  {owner}'s database contains:")
            for v in violations[:5]:  # Show up to 5 per owner
                print(f"    - Card from {v['actual_user']} (card_id: {v['card_id']})")

        print()
        print("Next steps:")
        print("  1. This confirms the filesystem session race condition")
        print("  2. Implement Redis-backed sessions (see docs/SESSION_ARCHITECTURE_ANALYSIS.md)")
        print("  3. Re-run this test to confirm the fix")

        # Save detailed report
        report_file = "race_condition_report.json"
        with open(report_file, "w") as f:
            json.dump({
                "total_cards": total_cards,
                "total_violations": total_violations,
                "violations": violation_details
            }, f, indent=2)
        print()
        print(f"📄 Detailed report saved to: {report_file}")

    else:
        print("✅ NO RACE CONDITION DETECTED")
        print()
        print("All cards are in the correct user databases.")
        print()
        print("This could mean:")
        print("  - The race condition doesn't exist (unlikely given user reports)")
        print("  - The test didn't generate enough concurrent load")
        print("  - You're running with --workers 1 (single worker)")
        print()
        print("Try:")
        print("  - Run the test multiple times")
        print("  - Increase CARDS_PER_USER in test_race_quick.py")
        print("  - Decrease DELAY_MS to increase concurrency")

    print()
    print("=" * 70)

if __name__ == "__main__":
    main()
