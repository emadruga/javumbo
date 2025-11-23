"""
Test 3.1: S3SQLiteConnection - Cache Speedup Test

Tests that Lambda container caching significantly improves performance.

Expected outcome:
- First request (cold): Downloads from S3 (~171ms download time)
- Second request (warm): Uses cache (~0ms download time)
- Warm request should be 2x+ faster than cold request

Run with:
    python test_s3_sqlite_cache.py
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from s3_sqlite import S3SQLiteConnection, clear_cache

s3 = boto3.client('s3')

def test_cache_speedup():
    """Test that caching provides 2x+ speedup"""
    username = 'test_cache_user_001'

    print(f"\n🧪 Test 3.1: Cache Speedup Test")
    print("=" * 60)
    print(f"Testing cache speedup for {username}\n")

    try:
        # Setup: Create initial database
        print("📝 Setup: Creating initial database...")
        clear_cache()  # Ensure clean state
        with S3SQLiteConnection(username) as conn:
            # Insert 20 test notes
            for i in range(20):
                conn.execute('''
                    INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (i+1, f'guid{i}', 1, 1000+i, -1, '', f'Front{i}\x1fBack{i}', 0, 0, 0, ''))
        print(f"✓ Setup complete\n")

        # Test 1: Cold request (no cache)
        print("🥶 Test 1: COLD REQUEST (no cache)")
        print("-" * 60)
        clear_cache()  # Clear cache to simulate cold start

        cold_start = time.time()
        with S3SQLiteConnection(username) as conn:
            download_time_end = time.time()  # Approximate download time
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            count = cursor.fetchone()[0]
        cold_end = time.time()

        cold_total = (cold_end - cold_start) * 1000
        print(f"Cold request time: {cold_total:.1f}ms")
        print(f"Notes found: {count}")
        assert count == 20, f"Expected 20 notes, found {count}"
        print(f"✓ Cold request completed\n")

        # Test 2: Warm request (with cache)
        print("🔥 Test 2: WARM REQUEST (with cache)")
        print("-" * 60)

        warm_start = time.time()
        with S3SQLiteConnection(username) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            count = cursor.fetchone()[0]
        warm_end = time.time()

        warm_total = (warm_end - warm_start) * 1000
        print(f"Warm request time: {warm_total:.1f}ms")
        print(f"Notes found: {count}")
        assert count == 20, f"Expected 20 notes, found {count}"
        print(f"✓ Warm request completed\n")

        # Test 3: Multiple warm requests
        print("🔥 Test 3: CONSECUTIVE WARM REQUESTS")
        print("-" * 60)
        warm_times = []

        for i in range(5):
            start = time.time()
            with S3SQLiteConnection(username) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM notes")
                count = cursor.fetchone()[0]
            end = time.time()
            elapsed = (end - start) * 1000
            warm_times.append(elapsed)
            print(f"Request {i+1}: {elapsed:.1f}ms")

        avg_warm = sum(warm_times) / len(warm_times)
        print(f"Average warm request: {avg_warm:.1f}ms")
        print(f"✓ Consecutive warm requests completed\n")

        # Analysis
        print("=" * 60)
        print("📊 Performance Analysis")
        print("=" * 60)

        speedup = cold_total / warm_total
        improvement_pct = ((cold_total - warm_total) / cold_total) * 100

        print(f"\nCold request:     {cold_total:.1f}ms")
        print(f"Warm request:     {warm_total:.1f}ms")
        print(f"Average warm:     {avg_warm:.1f}ms")
        print(f"\nSpeedup:          {speedup:.2f}x faster")
        print(f"Improvement:      {improvement_pct:.1f}% reduction")

        # Success criteria
        print(f"\n✅ SUCCESS CRITERIA:")
        if speedup >= 2.0:
            print(f"   ✅ Speedup {speedup:.2f}x >= 2.0x (PASS)")
        else:
            print(f"   ❌ Speedup {speedup:.2f}x < 2.0x (FAIL)")
            raise AssertionError(f"Cache speedup {speedup:.2f}x is less than 2x")

        if warm_total < 100:
            print(f"   ✅ Warm request {warm_total:.1f}ms < 100ms (EXCELLENT)")
        elif warm_total < 150:
            print(f"   ✅ Warm request {warm_total:.1f}ms < 150ms (GOOD)")
        else:
            print(f"   ⚠️  Warm request {warm_total:.1f}ms >= 150ms (ACCEPTABLE, but not optimal)")

        # Cleanup
        print(f"\n🧹 Cleaning up...")
        bucket = os.environ.get('S3_BUCKET')
        s3_key = f'user_dbs/{username}.anki2'
        s3.delete_object(Bucket=bucket, Key=s3_key)
        print(f"✓ Deleted test database from S3")

        local_path = f'/tmp/{username}.anki2'
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"✓ Deleted local file")

        clear_cache()

        print("\n" + "=" * 60)
        print("✅ Test 3.1 PASSED: Cache provides 2x+ speedup")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Test 3.1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if 'S3_BUCKET' not in os.environ:
        print("ERROR: S3_BUCKET environment variable not set")
        print("Run: export S3_BUCKET=$(cd ../terraform && terraform output -raw s3_bucket_name)")
        sys.exit(1)

    success = test_cache_speedup()
    sys.exit(0 if success else 1)
