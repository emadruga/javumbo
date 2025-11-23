#!/usr/bin/env python3
"""
Test 4.1: S3SQLiteConnection Conflict Detection Test

This test validates that optimistic locking with ETags prevents concurrent write conflicts.

Test Flow:
1. Create initial database with test data
2. Open two connections to the same database (simulating two Lambda invocations)
3. Both connections download the same version (same ETag)
4. Both connections modify data
5. First connection exits and uploads successfully
6. Second connection exits and raises ConflictError (ETag changed)

Success Criteria:
- First connection succeeds
- Second connection raises ConflictError
- No silent data loss occurs
- Error message contains "Concurrent modification detected"
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import boto3
from s3_sqlite import S3SQLiteConnection, ConflictError, clear_cache

# Test configuration
TEST_USERNAME = 'test_conflict_user'

# Get S3 bucket from environment
S3_BUCKET = os.environ.get('S3_BUCKET')
if not S3_BUCKET:
    print("❌ Error: S3_BUCKET environment variable not set")
    print("   Run: export S3_BUCKET=$(cd ../terraform && terraform output -raw s3_bucket_name)")
    sys.exit(1)

s3 = boto3.client('s3')


def cleanup_test_data():
    """Clean up test database from S3 and /tmp"""
    s3_key = f'user_dbs/{TEST_USERNAME}.anki2'
    local_path = f'/tmp/{TEST_USERNAME}.anki2'

    # Delete from S3
    try:
        s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        print(f"✓ Deleted test database from S3")
    except Exception as e:
        pass  # Ignore if doesn't exist

    # Delete local file
    if os.path.exists(local_path):
        os.remove(local_path)
        print(f"✓ Deleted local file")

    # Clear cache
    clear_cache()


def create_initial_database():
    """Create initial database with test data"""
    print("📝 Setup: Creating initial database...")

    with S3SQLiteConnection(TEST_USERNAME) as conn:
        cursor = conn.cursor()

        # Insert 5 test notes
        for i in range(5):
            cursor.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                i + 1,
                f'test_guid_{i}',
                1,
                int(time.time()),
                0,
                '',
                f'Test note {i}',
                0,
                0,
                0,
                ''
            ))

        conn.commit()

    # Verify count
    with S3SQLiteConnection(TEST_USERNAME) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM notes")
        count = cursor.fetchone()[0]
        print(f"✓ Initial database created with {count} notes")

    return count


def test_conflict_detection():
    """
    Test 4.1: Conflict Detection

    Simulates two concurrent Lambda invocations trying to modify the same database.
    """
    print("\n🧪 Test 4.1: S3SQLiteConnection Conflict Detection Test")
    print("=" * 60)
    print("Testing optimistic locking prevents concurrent write conflicts")
    print(f"User: {TEST_USERNAME}\n")

    try:
        # Setup: Create initial database
        initial_count = create_initial_database()

        # Clear cache to force both connections to download fresh
        print("\n🔍 Test: Simulating concurrent modifications...")
        clear_cache()

        # Connection 1: Download, modify, and store ETag (but don't close yet)
        print("\n📥 Connection 1: Opening (downloads DB)...")
        conn1 = S3SQLiteConnection(TEST_USERNAME)
        db1 = conn1.__enter__()
        cursor1 = db1.cursor()

        # Verify Connection 1 has the data
        cursor1.execute("SELECT COUNT(*) FROM notes")
        count1_before = cursor1.fetchone()[0]
        print(f"   Connection 1: {count1_before} notes (initial)")

        # Store Connection 1's ETag
        conn1_etag = conn1.current_etag
        print(f"   Connection 1: Downloaded with ETag {conn1_etag}")

        # Connection 1: Modify data (add 1 note)
        cursor1.execute('''
            INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            100,
            'conn1_note',
            1,
            int(time.time()),
            0,
            '',
            'Note added by Connection 1',
            0,
            0,
            0,
            ''
        ))
        cursor1.execute("SELECT COUNT(*) FROM notes")
        count1_after = cursor1.fetchone()[0]
        print(f"   Connection 1: {count1_after} notes (after insert, will commit soon)")

        # Connection 1: Commit and upload (should succeed)
        print("\n📤 Connection 1: Committing and uploading...")
        conn1.__exit__(None, None, None)
        print("   ✅ Connection 1: Upload succeeded (first writer wins)")

        # Verify S3 now has Connection 1's changes
        with S3SQLiteConnection(TEST_USERNAME) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            s3_count = cursor.fetchone()[0]
            print(f"   S3 database now has: {s3_count} notes (Connection 1's version)")

        # Connection 2: Download the ORIGINAL version (same ETag as Connection 1 started with)
        print("\n📥 Connection 2: Opening (simulating concurrent download with Connection 1's original ETag)...")

        # To simulate concurrent access, we need Connection 2 to have the OLD ETag
        # We'll manually set it by clearing cache and modifying the S3SQLiteConnection
        clear_cache()

        conn2 = S3SQLiteConnection(TEST_USERNAME)
        db2 = conn2.__enter__()

        # Manually set Connection 2's ETag to the OLD one (simulating it downloaded before Connection 1 uploaded)
        conn2.current_etag = conn1_etag
        print(f"   Connection 2: Using ETag {conn2.current_etag} (same as Connection 1's original)")

        cursor2 = db2.cursor()

        # Verify Connection 2 has the UPDATED data (because it just downloaded from S3)
        # But we'll pretend it has the old ETag
        cursor2.execute("SELECT COUNT(*) FROM notes")
        count2_before = cursor2.fetchone()[0]
        print(f"   Connection 2: {count2_before} notes (actually has Connection 1's changes)")

        # Connection 2: Modify data (add 1 different note)
        cursor2.execute('''
            INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            200,
            'conn2_note',
            1,
            int(time.time()),
            0,
            '',
            'Note added by Connection 2',
            0,
            0,
            0,
            ''
        ))
        cursor2.execute("SELECT COUNT(*) FROM notes")
        count2_after = cursor2.fetchone()[0]
        print(f"   Connection 2: {count2_after} notes (after insert, will try to commit)")

        # Connection 2: Try to commit and upload (should fail with ConflictError)
        print("\n📤 Connection 2: Attempting to commit and upload...")
        conflict_detected = False
        try:
            conn2.__exit__(None, None, None)
            print("   ❌ ERROR: Connection 2 upload succeeded (SHOULD HAVE FAILED!)")
        except ConflictError as e:
            conflict_detected = True
            print(f"   ✅ ConflictError raised (expected): {e}")

        # Verify final state
        print("\n📊 Final Verification:")
        with S3SQLiteConnection(TEST_USERNAME) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            final_count = cursor.fetchone()[0]

            # Check which notes exist
            cursor.execute("SELECT id, flds FROM notes ORDER BY id")
            notes = cursor.fetchall()

            print(f"   Final note count: {final_count}")
            print(f"   Expected: {initial_count + 1} (initial + Connection 1's note)")

            # Verify Connection 1's note exists
            cursor.execute("SELECT COUNT(*) FROM notes WHERE id = 100")
            has_conn1_note = cursor.fetchone()[0] > 0

            # Verify Connection 2's note does NOT exist
            cursor.execute("SELECT COUNT(*) FROM notes WHERE id = 200")
            has_conn2_note = cursor.fetchone()[0] > 0

            print(f"   Connection 1's note (id=100): {'✅ EXISTS' if has_conn1_note else '❌ MISSING'}")
            print(f"   Connection 2's note (id=200): {'✅ ABSENT (expected)' if not has_conn2_note else '❌ EXISTS (DATA LOSS!)'}")

        # Success criteria
        print("\n" + "=" * 60)
        print("📊 Test Results")
        print("=" * 60)

        success = True

        if conflict_detected:
            print("✅ PASS: ConflictError raised for concurrent write")
        else:
            print("❌ FAIL: ConflictError NOT raised (silent data loss!)")
            success = False

        if has_conn1_note:
            print("✅ PASS: First writer's data persisted")
        else:
            print("❌ FAIL: First writer's data lost")
            success = False

        if not has_conn2_note:
            print("✅ PASS: Second writer's data rejected (no silent overwrite)")
        else:
            print("❌ FAIL: Second writer's data persisted (data loss!)")
            success = False

        if final_count == initial_count + 1:
            print("✅ PASS: Correct final note count")
        else:
            print(f"❌ FAIL: Wrong final note count (expected {initial_count + 1}, got {final_count})")
            success = False

        # Cleanup
        print("\n🧹 Cleaning up...")
        cleanup_test_data()

        # Final result
        print("\n" + "=" * 60)
        if success:
            print("✅ Test 4.1 PASSED: Optimistic locking prevents data loss")
        else:
            print("❌ Test 4.1 FAILED: Optimistic locking NOT working")
        print("=" * 60)

        return 0 if success else 1

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        print("\n🧹 Cleaning up...")
        cleanup_test_data()

        return 1


if __name__ == '__main__':
    sys.exit(test_conflict_detection())
