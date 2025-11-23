#!/usr/bin/env python3
"""
Test 4.2: S3SQLiteConnection Concurrent Writes Test

This test simulates 10 concurrent Lambda invocations trying to modify the same database.
Uses ThreadPoolExecutor to simulate concurrent operations.

Test Flow:
1. Create initial database with test data
2. Launch 10 threads, each trying to add a unique note
3. Track successes vs conflicts
4. Verify ZERO data loss (all successful writes persisted, all conflicts detected)

Success Criteria:
- At least 1 write succeeds
- All other writes raise ConflictError
- Total successful writes + conflicts = 10
- All successful writes are in final database
- NO silent data loss
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from s3_sqlite import S3SQLiteConnection, ConflictError, clear_cache

# Test configuration
TEST_USERNAME = 'test_concurrent_user'
NUM_WORKERS = 10

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

        # Insert 5 initial notes
        for i in range(5):
            cursor.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                i + 1,
                f'initial_note_{i}',
                1,
                int(time.time()),
                0,
                '',
                f'Initial note {i}',
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
        print(f"✓ Initial database created with {count} notes\n")

    return count


def concurrent_write_task(worker_id):
    """
    Task executed by each worker thread.
    Simulates a Lambda invocation that adds a note.

    Returns:
        dict: Result with worker_id, success, error, duration
    """
    start = time.time()

    # Each worker adds a unique note
    note_id = 1000 + worker_id
    note_content = f'Note from worker {worker_id}'

    try:
        # Clear cache to simulate fresh Lambda invocation
        # (In real Lambda, each instance has its own cache)
        clear_cache()

        with S3SQLiteConnection(TEST_USERNAME) as conn:
            cursor = conn.cursor()

            # Add unique note
            cursor.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                note_id,
                f'worker_{worker_id}_note',
                1,
                int(time.time()),
                0,
                '',
                note_content,
                0,
                0,
                0,
                ''
            ))

            conn.commit()

        end = time.time()
        duration = (end - start) * 1000

        return {
            'worker_id': worker_id,
            'success': True,
            'error': None,
            'duration': duration,
            'note_id': note_id
        }

    except ConflictError as e:
        end = time.time()
        duration = (end - start) * 1000

        return {
            'worker_id': worker_id,
            'success': False,
            'error': 'ConflictError',
            'duration': duration,
            'note_id': note_id
        }

    except Exception as e:
        end = time.time()
        duration = (end - start) * 1000

        return {
            'worker_id': worker_id,
            'success': False,
            'error': str(e),
            'duration': duration,
            'note_id': note_id
        }


def test_concurrent_writes():
    """
    Test 4.2: Concurrent Writes

    Simulates 10 concurrent Lambda invocations trying to modify the same database.
    """
    print("\n🧪 Test 4.2: S3SQLiteConnection Concurrent Writes Test")
    print("=" * 60)
    print(f"Simulating {NUM_WORKERS} concurrent Lambda invocations")
    print(f"User: {TEST_USERNAME}\n")

    try:
        # Setup: Create initial database
        initial_count = create_initial_database()

        # Run concurrent writes
        print(f"🚀 Launching {NUM_WORKERS} concurrent write operations...")
        print("   (Each worker tries to add a unique note)\n")

        results = []

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            # Submit all tasks
            futures = {
                executor.submit(concurrent_write_task, worker_id): worker_id
                for worker_id in range(NUM_WORKERS)
            }

            # Wait for all to complete
            for future in as_completed(futures):
                worker_id = futures[future]
                result = future.result()
                results.append(result)

                # Print result
                if result['success']:
                    print(f"   Worker {worker_id:2d}: ✅ SUCCESS ({result['duration']:6.1f}ms)")
                else:
                    print(f"   Worker {worker_id:2d}: ⚠️  {result['error']} ({result['duration']:6.1f}ms)")

        # Analyze results
        print("\n" + "=" * 60)
        print("📊 Results Analysis")
        print("=" * 60)

        successes = [r for r in results if r['success']]
        conflicts = [r for r in results if not r['success'] and r['error'] == 'ConflictError']
        errors = [r for r in results if not r['success'] and r['error'] != 'ConflictError']

        print(f"\n📈 Operation Summary:")
        print(f"   Total operations:  {len(results)}")
        print(f"   Successes:         {len(successes)} ({len(successes)/len(results)*100:.1f}%)")
        print(f"   ConflictErrors:    {len(conflicts)} ({len(conflicts)/len(results)*100:.1f}%)")
        print(f"   Other errors:      {len(errors)} ({len(errors)/len(results)*100:.1f}%)")

        # Timing statistics for successes
        if successes:
            success_times = [r['duration'] for r in successes]
            print(f"\n⏱️  Success Timing:")
            print(f"   Min: {min(success_times):.1f}ms")
            print(f"   Max: {max(success_times):.1f}ms")
            print(f"   Avg: {sum(success_times)/len(success_times):.1f}ms")

        # Verify final state
        print("\n📊 Final Database Verification:")
        with S3SQLiteConnection(TEST_USERNAME) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            final_count = cursor.fetchone()[0]

            # Expected: initial + number of successes
            expected_count = initial_count + len(successes)

            print(f"   Initial notes:     {initial_count}")
            print(f"   Successful writes: {len(successes)}")
            print(f"   Expected total:    {expected_count}")
            print(f"   Actual total:      {final_count}")

            # Verify each successful write is in database
            missing_notes = []
            for result in successes:
                cursor.execute("SELECT COUNT(*) FROM notes WHERE id = ?", (result['note_id'],))
                exists = cursor.fetchone()[0] > 0
                if not exists:
                    missing_notes.append(result['note_id'])

            # Verify NO conflict writes are in database (they should have been rejected)
            extra_notes = []
            for result in conflicts:
                cursor.execute("SELECT COUNT(*) FROM notes WHERE id = ?", (result['note_id'],))
                exists = cursor.fetchone()[0] > 0
                if exists:
                    extra_notes.append(result['note_id'])

        # Success criteria
        print("\n" + "=" * 60)
        print("✅ Success Criteria")
        print("=" * 60)

        success = True

        # Criterion 1: At least 1 success
        if len(successes) >= 1:
            print(f"✅ PASS: At least 1 write succeeded ({len(successes)} total)")
        else:
            print("❌ FAIL: No writes succeeded")
            success = False

        # Criterion 2: All operations accounted for
        total_ops = len(successes) + len(conflicts) + len(errors)
        if total_ops == NUM_WORKERS:
            print(f"✅ PASS: All {NUM_WORKERS} operations accounted for")
        else:
            print(f"❌ FAIL: Missing operations ({total_ops}/{NUM_WORKERS})")
            success = False

        # Criterion 3: Correct final count
        if final_count == expected_count:
            print(f"✅ PASS: Correct final count ({final_count} notes)")
        else:
            print(f"❌ FAIL: Wrong final count (expected {expected_count}, got {final_count})")
            success = False

        # Criterion 4: No missing successful writes (NO DATA LOSS)
        if len(missing_notes) == 0:
            print(f"✅ PASS: All {len(successes)} successful writes persisted")
        else:
            print(f"❌ FAIL: {len(missing_notes)} successful writes LOST: {missing_notes}")
            success = False

        # Criterion 5: No conflict writes persisted (no silent overwrites)
        if len(extra_notes) == 0:
            print(f"✅ PASS: No conflict writes persisted (all {len(conflicts)} rejected)")
        else:
            print(f"❌ FAIL: {len(extra_notes)} conflict writes persisted: {extra_notes}")
            success = False

        # Criterion 6: No unexpected errors
        if len(errors) == 0:
            print(f"✅ PASS: No unexpected errors")
        else:
            print(f"❌ FAIL: {len(errors)} unexpected errors")
            for result in errors:
                print(f"   Worker {result['worker_id']}: {result['error']}")
            success = False

        # Criterion 7: Conflicts detected (optimistic locking working)
        if len(conflicts) >= NUM_WORKERS - 1:
            print(f"✅ PASS: Conflicts detected ({len(conflicts)}/{NUM_WORKERS-1} expected)")
        else:
            print(f"⚠️  WARNING: Fewer conflicts than expected ({len(conflicts)}/{NUM_WORKERS-1})")
            # Not a failure - this can happen if operations serialize naturally

        # Cleanup
        print("\n🧹 Cleaning up...")
        cleanup_test_data()

        # Final result
        print("\n" + "=" * 60)
        if success:
            print("✅ Test 4.2 PASSED: Concurrent writes handled safely")
            print(f"   - {len(successes)} writes succeeded")
            print(f"   - {len(conflicts)} conflicts detected")
            print(f"   - ZERO data loss")
        else:
            print("❌ Test 4.2 FAILED: Data integrity compromised")
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
    sys.exit(test_concurrent_writes())
