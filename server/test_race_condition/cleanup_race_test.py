#!/usr/bin/env python3
"""
Cleanup script for race condition test - Python version
Run this ON THE SERVER to remove all test data
"""

import sqlite3
import os
import glob

ADMIN_DB = "admin.db"
USER_DBS_DIR = "user_dbs"
TEST_PREFIX = "race"

def main():
    print("=" * 70)
    print("  Race Condition Test - Clean Slate")
    print("=" * 70)
    print()

    # Check if we're in the right directory
    if not os.path.exists(ADMIN_DB):
        print(f"❌ Error: {ADMIN_DB} not found!")
        print("   Make sure you're in the server directory:")
        print("   cd ~/javumbo/server")
        return

    # Get test users
    try:
        conn = sqlite3.connect(ADMIN_DB)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, username FROM users WHERE username LIKE ?",
            (f"{TEST_PREFIX}%",)
        )
        test_users = cursor.fetchall()
        conn.close()

        if not test_users:
            print(f"✅ No test users found with prefix '{TEST_PREFIX}'")
            print("   Nothing to clean up!")
            return

        print(f"Found {len(test_users)} test users to remove:")
        for user_id, username in test_users:
            print(f"  - {username} (ID: {user_id})")
        print()

        # Confirm
        response = input("Continue with cleanup? (y/n) ")
        if response.lower() != 'y':
            print("Cleanup cancelled")
            return

        print()

        # Delete test users from admin DB
        print("🧹 Removing test users from admin.db...")
        conn = sqlite3.connect(ADMIN_DB)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username LIKE ?", (f"{TEST_PREFIX}%",))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"   Deleted {deleted_count} users")

        # Delete test user database files
        print("🧹 Removing test user database files...")
        deleted_dbs = 0

        # Get all user database files
        db_files = glob.glob(os.path.join(USER_DBS_DIR, "user_*.db"))

        for db_file in db_files:
            try:
                # Check if this database has test markers
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) FROM notes WHERE flds LIKE ? LIMIT 1",
                    (f"%[USER:{TEST_PREFIX}%",)
                )
                count = cursor.fetchone()[0]
                conn.close()

                if count > 0:
                    print(f"   Removing: {db_file}")
                    os.remove(db_file)
                    deleted_dbs += 1

            except Exception as e:
                print(f"   ⚠️  Error checking {db_file}: {e}")
                continue

        print(f"   Deleted {deleted_dbs} database files")

        # Remove report file
        if os.path.exists("race_condition_report.json"):
            print("🧹 Removing race_condition_report.json...")
            os.remove("race_condition_report.json")

        # Verify cleanup
        print()
        conn = sqlite3.connect(ADMIN_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE username LIKE ?",
            (f"{TEST_PREFIX}%",)
        )
        remaining = cursor.fetchone()[0]
        conn.close()

        print("=" * 70)
        if remaining == 0:
            print("✅ Cleanup complete!")
            print(f"   - Removed {deleted_count} test users")
            print(f"   - Removed {deleted_dbs} test database files")
        else:
            print(f"⚠️  Warning: {remaining} test users still remain")
        print("=" * 70)
        print()
        print("Ready for a fresh test run!")
        print()

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
