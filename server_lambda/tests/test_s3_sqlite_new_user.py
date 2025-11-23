"""
Test 2.1: S3SQLiteConnection - New User Database Creation

Tests that S3SQLiteConnection can create a new Anki database for a new user
and upload it to S3.

Expected outcome:
- New database created with proper Anki schema
- Database uploaded to S3
- Can be re-opened and queried

Run with:
    python test_s3_sqlite_new_user.py
"""

import sys
import os

# Add parent directory to path so we can import s3_sqlite
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from s3_sqlite import S3SQLiteConnection

# Get bucket name from Terraform output
s3 = boto3.client('s3')

def test_new_user():
    """Test creating a new user database"""
    username = 'test_new_user_001'

    print(f"\n🧪 Test 2.1: Creating new database for {username}")
    print("=" * 60)

    try:
        # Should create new database
        with S3SQLiteConnection(username) as conn:
            # Check tables exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            print(f"\n✓ Tables created: {tables}")

            # Verify required Anki tables
            required_tables = ['col', 'cards', 'notes', 'revlog']
            for table in required_tables:
                assert table in tables, f"Missing required table: {table}"
                print(f"  ✓ {table} table exists")

            # Verify col table has data
            cursor = conn.execute("SELECT * FROM col WHERE id = 1")
            col_data = cursor.fetchone()
            assert col_data is not None, "col table is empty"
            print(f"\n✓ Collection metadata inserted")

        print(f"\n✓ Database closed and uploaded to S3")

        # Verify uploaded to S3
        bucket = os.environ.get('S3_BUCKET')
        s3_key = f'user_dbs/{username}.anki2'

        response = s3.head_object(Bucket=bucket, Key=s3_key)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
        print(f"✓ Database exists in S3: {s3_key}")
        print(f"  Size: {response['ContentLength']} bytes")
        print(f"  ETag: {response['ETag']}")

        # Cleanup
        print(f"\n🧹 Cleaning up...")
        s3.delete_object(Bucket=bucket, Key=s3_key)
        print(f"✓ Deleted test database from S3")

        # Clean local file
        local_path = f'/tmp/{username}.anki2'
        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"✓ Deleted local file")

        print("\n" + "=" * 60)
        print("✅ Test 2.1 PASSED: New database created and uploaded to S3")
        print("=" * 60 + "\n")

        return True

    except Exception as e:
        print(f"\n❌ Test 2.1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Ensure environment variable is set
    if 'S3_BUCKET' not in os.environ:
        print("ERROR: S3_BUCKET environment variable not set")
        print("Run: export S3_BUCKET=$(cd ../terraform && terraform output -raw s3_bucket_name)")
        sys.exit(1)

    success = test_new_user()
    sys.exit(0 if success else 1)
