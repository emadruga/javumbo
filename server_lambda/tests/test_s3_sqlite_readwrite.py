"""
Test 2.2: S3SQLiteConnection - Read/Write Persistence

Tests that data written in one connection persists and can be read
in a subsequent connection.

Expected outcome:
- Data inserted in first connection
- Data persists in S3
- Data readable in second connection

Run with:
    python test_s3_sqlite_readwrite.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from s3_sqlite import S3SQLiteConnection

s3 = boto3.client('s3')

def test_read_write():
    """Test data persistence across connections"""
    username = 'test_readwrite_002'

    print(f"\n🧪 Test 2.2: Testing read/write persistence for {username}")
    print("=" * 60)

    try:
        # First connection: Write data
        print("\n📝 First connection: Writing data...")
        with S3SQLiteConnection(username) as conn:
            # Insert a test note
            conn.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (1, 'abc123', 1, 1000, -1, '', 'Test Front\x1fTest Back', 0, 0, 0, ''))

            # Verify inserted
            cursor = conn.execute("SELECT * FROM notes WHERE id = 1")
            row = cursor.fetchone()
            assert row is not None, "Note not inserted"
            print(f"✓ Inserted test note (id=1)")

        print(f"✓ First connection closed and uploaded to S3")

        # Second connection: Read data (should use fresh download from S3)
        print("\n📖 Second connection: Reading data from S3...")
        with S3SQLiteConnection(username) as conn:
            cursor = conn.execute("SELECT flds FROM notes WHERE id = 1")
            row = cursor.fetchone()

            assert row is not None, "Note not found in second connection"

            flds = row[0]
            assert 'Test Front' in flds, "Field data corrupted"
            assert 'Test Back' in flds, "Field data corrupted"

            print(f"✓ Read test note: {flds}")
            print(f"✓ Data persisted across connections")

        # Third connection: Add more data
        print("\n📝 Third connection: Adding more data...")
        with S3SQLiteConnection(username) as conn:
            # Insert another note
            conn.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (2, 'def456', 1, 2000, -1, '', 'Second Front\x1fSecond Back', 0, 0, 0, ''))

            # Count total notes
            cursor = conn.execute("SELECT COUNT(*) FROM notes")
            count = cursor.fetchone()[0]
            assert count == 2, f"Expected 2 notes, got {count}"
            print(f"✓ Total notes: {count}")

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
        print("✅ Test 2.2 PASSED: Data persists across connections")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Test 2.2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if 'S3_BUCKET' not in os.environ:
        print("ERROR: S3_BUCKET environment variable not set")
        print("Run: export S3_BUCKET=$(cd ../terraform && terraform output -raw s3_bucket_name)")
        sys.exit(1)

    success = test_read_write()
    sys.exit(0 if success else 1)
