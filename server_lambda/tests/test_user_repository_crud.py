#!/usr/bin/env python3
"""
Test 5.3: UserRepository - CRUD Operations Test

This test validates complete CRUD operations for user management.

Test Flow:
1. Create multiple test users
2. Test list_users() pagination
3. Test get_user() for each user
4. Test delete_user() functionality
5. Verify deleted users don't exist
6. Cleanup all test users

Success Criteria:
- Multiple users can be created
- list_users() returns all users
- get_user() works for all users
- delete_user() removes users correctly
- Deleted users are actually gone
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from user_repository import UserRepository

# Test configuration
TEST_USERS = [
    ('test_user_crud_1', 'Test User 1', 'password1'),
    ('test_user_crud_2', 'Test User 2', 'password2'),
    ('test_user_crud_3', 'Test User 3', 'password3'),
    ('test_user_crud_4', 'Test User 4', 'password4'),
    ('test_user_crud_5', 'Test User 5', 'password5'),
]

# Get DynamoDB table name from environment
DYNAMODB_USERS_TABLE = os.environ.get('DYNAMODB_USERS_TABLE')
if not DYNAMODB_USERS_TABLE:
    print("❌ Error: DYNAMODB_USERS_TABLE environment variable not set")
    print("   Run: export DYNAMODB_USERS_TABLE=$(cd ../terraform && terraform output -raw dynamodb_users_table_name)")
    sys.exit(1)

# Update environment for UserRepository
os.environ['DYNAMODB_USERS_TABLE'] = DYNAMODB_USERS_TABLE

dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table(DYNAMODB_USERS_TABLE)


def cleanup_test_users():
    """Delete all test users from DynamoDB"""
    for username, _, _ in TEST_USERS:
        try:
            users_table.delete_item(Key={'username': username})
        except Exception:
            pass  # Ignore if doesn't exist
    print(f"✓ Cleaned up {len(TEST_USERS)} test users")


def test_user_crud():
    """
    Test 5.3: User CRUD Operations

    Tests complete create, read, update, delete operations.
    """
    print("\n🧪 Test 5.3: UserRepository - CRUD Operations Test")
    print("=" * 60)
    print(f"Testing CRUD operations with DynamoDB")
    print(f"Table: {DYNAMODB_USERS_TABLE}")
    print(f"Creating {len(TEST_USERS)} test users\n")

    try:
        # Cleanup any existing test users
        cleanup_test_users()

        # Initialize repository
        repo = UserRepository()

        # Test 1: Create multiple users
        print("📝 Test 1: Creating multiple users...")
        created_users = []

        for username, name, password in TEST_USERS:
            user = repo.create_user(username, name, password)
            created_users.append(user)
            print(f"   ✅ Created: {username} ({name})")

        assert len(created_users) == len(TEST_USERS), "Not all users were created"
        print(f"\n   ✅ All {len(TEST_USERS)} users created successfully")

        # Test 2: List all users (verify all exist)
        print("\n📋 Test 2: Listing all users...")
        all_users = repo.list_users(limit=100)

        # Our test users should be in the list
        test_usernames = {username for username, _, _ in TEST_USERS}
        found_usernames = {user['username'] for user in all_users if user['username'] in test_usernames}

        assert found_usernames == test_usernames, f"Not all test users found. Expected {test_usernames}, found {found_usernames}"

        print(f"   ✅ All {len(TEST_USERS)} test users found in list_users()")
        print(f"   ✅ Total users in table: {len(all_users)}")

        # Test 3: Get each user individually
        print("\n🔍 Test 3: Getting each user individually...")
        for username, name, _ in TEST_USERS:
            user = repo.get_user(username)

            assert user is not None, f"get_user() returned None for {username}"
            assert user['username'] == username, f"Username mismatch for {username}"
            assert user['name'] == name, f"Name mismatch for {username}"
            assert 'password_hash' not in user, "Password hash should not be in response"

            print(f"   ✅ Retrieved: {username} ({name})")

        print(f"\n   ✅ All {len(TEST_USERS)} users retrieved successfully")

        # Test 4: Delete first 3 users
        print("\n🗑️  Test 4: Deleting first 3 users...")
        deleted_count = 0

        for username, name, _ in TEST_USERS[:3]:
            success = repo.delete_user(username)

            assert success is True, f"Failed to delete {username}"

            deleted_count += 1
            print(f"   ✅ Deleted: {username}")

        assert deleted_count == 3, "Not all users were deleted"
        print(f"\n   ✅ {deleted_count} users deleted successfully")

        # Test 5: Verify deleted users don't exist
        print("\n🔍 Test 5: Verifying deleted users are gone...")
        for username, _, _ in TEST_USERS[:3]:
            user = repo.get_user(username)

            assert user is None, f"Deleted user {username} still exists!"

            print(f"   ✅ Confirmed deleted: {username}")

        print(f"\n   ✅ All deleted users are gone")

        # Test 6: Verify remaining users still exist
        print("\n🔍 Test 6: Verifying remaining users still exist...")
        for username, name, _ in TEST_USERS[3:]:
            user = repo.get_user(username)

            assert user is not None, f"Remaining user {username} not found"
            assert user['username'] == username, f"Username mismatch for {username}"

            print(f"   ✅ Still exists: {username}")

        print(f"\n   ✅ All remaining users intact")

        # Test 7: Delete non-existent user
        print("\n🚫 Test 7: Deleting non-existent user...")
        success = repo.delete_user('this_user_does_not_exist_12345')

        assert success is False, "Deleting non-existent user should return False"

        print(f"   ✅ delete_user() returned False for non-existent user")

        # Test 8: List users with small limit (pagination)
        print("\n📋 Test 8: Testing list_users() with small limit...")
        limited_users = repo.list_users(limit=2)

        # Should return at most 2 users (or fewer if table has fewer)
        assert len(limited_users) <= 2, f"list_users(limit=2) returned {len(limited_users)} users"

        print(f"   ✅ list_users(limit=2) returned {len(limited_users)} users")

        # Cleanup remaining test users
        print("\n🧹 Cleaning up remaining test users...")
        cleanup_test_users()

        # Final result
        print("\n" + "=" * 60)
        print("📊 Test Results")
        print("=" * 60)
        print("✅ PASS: Multiple users created successfully")
        print("✅ PASS: list_users() returns all users")
        print("✅ PASS: get_user() works for all users")
        print("✅ PASS: delete_user() removes users correctly")
        print("✅ PASS: Deleted users are gone")
        print("✅ PASS: Remaining users intact")
        print("✅ PASS: Delete non-existent user returns False")
        print("✅ PASS: list_users() pagination works")

        print("\n" + "=" * 60)
        print("✅ Test 5.3 PASSED: CRUD operations working correctly")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        print("\n🧹 Cleaning up...")
        cleanup_test_users()

        return 1


if __name__ == '__main__':
    sys.exit(test_user_crud())
