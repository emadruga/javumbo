"""
Test 2.3: S3SQLiteConnection - Latency Baseline Measurement

Establishes baseline performance metrics for S3 SQLite operations.
This data will be compared against Day 3's caching implementation.

Expected outcome:
- Measure average S3 download time
- Measure average SQLite operation time
- Measure average S3 upload time
- Document total request latency

Run with:
    python test_s3_sqlite_latency.py
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from s3_sqlite import S3SQLiteConnection

s3 = boto3.client('s3')

def measure_latency():
    """Measure baseline latency for S3 SQLite operations"""
    username = 'test_latency_user'
    num_requests = 10

    print(f"\n🧪 Test 2.3: Latency Baseline Measurement")
    print("=" * 60)
    print(f"Running {num_requests} sequential requests (no caching)")
    print(f"User: {username}\n")

    # Metrics collection
    download_times = []
    query_times = []
    upload_times = []
    total_times = []

    try:
        # First, create the user database
        print("📝 Creating initial database...")
        with S3SQLiteConnection(username) as conn:
            # Insert some test data
            for i in range(10):
                conn.execute('''
                    INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (i+1, f'guid{i}', 1, 1000+i, -1, '', f'Front{i}\x1fBack{i}', 0, 0, 0, ''))
        print(f"✓ Initial database created with 10 notes\n")

        # Run latency measurements
        print("🔍 Measuring latency across 10 requests...\n")

        for i in range(num_requests):
            request_start = time.time()

            # Measure connection (download + open)
            download_start = time.time()
            with S3SQLiteConnection(username) as conn:
                download_end = time.time()
                download_time = (download_end - download_start) * 1000  # Convert to ms

                # Measure query operation
                query_start = time.time()
                cursor = conn.execute("SELECT COUNT(*) FROM notes")
                count = cursor.fetchone()[0]
                query_end = time.time()
                query_time = (query_end - query_start) * 1000

                # Measure insert operation
                conn.execute('''
                    INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (100+i, f'latency_test_{i}', 1, 2000+i, -1, '', f'Req{i} Front\x1fReq{i} Back', 0, 0, 0, ''))

            # Measure upload (happens in __exit__)
            upload_end = time.time()
            upload_time = (upload_end - download_end) * 1000

            # Total request time
            request_end = time.time()
            total_time = (request_end - request_start) * 1000

            # Store metrics
            download_times.append(download_time)
            query_times.append(query_time)
            upload_times.append(upload_time)
            total_times.append(total_time)

            print(f"Request {i+1:2d}: "
                  f"Download={download_time:6.1f}ms, "
                  f"Query={query_time:5.1f}ms, "
                  f"Upload={upload_time:6.1f}ms, "
                  f"Total={total_time:6.1f}ms")

        # Calculate statistics
        print("\n" + "=" * 60)
        print("📊 Baseline Performance Metrics")
        print("=" * 60)

        avg_download = sum(download_times) / len(download_times)
        avg_query = sum(query_times) / len(query_times)
        avg_upload = sum(upload_times) / len(upload_times)
        avg_total = sum(total_times) / len(total_times)

        min_download = min(download_times)
        max_download = max(download_times)
        min_upload = min(upload_times)
        max_upload = max(upload_times)
        min_total = min(total_times)
        max_total = max(total_times)

        print(f"\n📥 S3 Download (+ SQLite open):")
        print(f"   Average: {avg_download:.1f}ms")
        print(f"   Range:   {min_download:.1f}ms - {max_download:.1f}ms")

        print(f"\n🔍 SQLite Query:")
        print(f"   Average: {avg_query:.1f}ms")

        print(f"\n📤 S3 Upload (+ SQLite close):")
        print(f"   Average: {avg_upload:.1f}ms")
        print(f"   Range:   {min_upload:.1f}ms - {max_upload:.1f}ms")

        print(f"\n⏱️  Total Request Time:")
        print(f"   Average: {avg_total:.1f}ms")
        print(f"   Range:   {min_total:.1f}ms - {max_total:.1f}ms")

        print(f"\n💡 Key Insights:")
        print(f"   - S3 operations dominate latency ({(avg_download + avg_upload):.1f}ms = {((avg_download + avg_upload) / avg_total * 100):.0f}% of total)")
        print(f"   - SQLite queries are fast ({avg_query:.1f}ms)")
        print(f"   - Day 3 caching should reduce S3 download time by ~70-80%")

        # Expected improvement calculation
        cached_download = avg_download * 0.25  # 75% cache hit rate
        expected_improvement = avg_download - cached_download
        expected_total = avg_total - expected_improvement

        print(f"\n📈 Day 3 Expected Improvement (75% cache hit rate):")
        print(f"   - Download time: {avg_download:.1f}ms → {cached_download:.1f}ms")
        print(f"   - Total request: {avg_total:.1f}ms → {expected_total:.1f}ms")
        print(f"   - Latency reduction: {expected_improvement:.1f}ms ({(expected_improvement/avg_total*100):.0f}%)")

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

        print("\n" + "=" * 60)
        print("✅ Test 2.3 PASSED: Baseline metrics established")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Test 2.3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if 'S3_BUCKET' not in os.environ:
        print("ERROR: S3_BUCKET environment variable not set")
        print("Run: export S3_BUCKET=$(cd ../terraform && terraform output -raw s3_bucket_name)")
        sys.exit(1)

    success = measure_latency()
    sys.exit(0 if success else 1)
