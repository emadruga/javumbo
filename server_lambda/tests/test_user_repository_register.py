#!/usr/bin/env python3
"""
Test 5.1: UserRepository - User Registration Test

This test validates user registration (create new user) in DynamoDB.

Test Flow:
1. Create a new user with username, name, and password
2. Verify user was created successfully
3. Verify password is hashed (not stored in plain text)
4. Verify get_user() returns correct user data
5. Verify duplicate username raises UserAlreadyExistsError
6. Cleanup test user

Success Criteria:
- User created successfully
- Password is hashed with bcrypt
- User data retrievable
- Duplicate username rejected
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from user_repository import UserRepository, UserAlreadyExistsError

# Test configuration
TEST_USERNAME = 'test_user_register'
TEST_NAME = 'Test User Registration'
TEST_PASSWORD = 'password123'

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


def cleanup_test_user():
    """Delete test user from DynamoDB"""
    try:
        users_table.delete_item(Key={'username': TEST_USERNAME})
        print(f"✓ Deleted test user from DynamoDB")
    except Exception as e:
        pass  # Ignore if doesn't exist


def test_user_registration():
    """
    Test 5.1: User Registration

    Tests creating a new user in DynamoDB.
    """
    print("\n🧪 Test 5.1: UserRepository - User Registration Test")
    print("=" * 60)
    print(f"Testing user registration in DynamoDB")
    print(f"Table: {DYNAMODB_USERS_TABLE}")
    print(f"Username: {TEST_USERNAME}\n")

    try:
        # Cleanup any existing test user
        cleanup_test_user()

        # Initialize repository
        repo = UserRepository()

        # Test 1: Create new user
        print("📝 Test 1: Creating new user...")
        created_user = repo.create_user(TEST_USERNAME, TEST_NAME, TEST_PASSWORD)

        # Verify user data returned
        assert created_user['username'] == TEST_USERNAME, "Username mismatch"
        assert created_user['name'] == TEST_NAME, "Name mismatch"
        assert 'created_at' in created_user, "Missing created_at timestamp"
        assert 'password_hash' not in created_user, "Password hash should not be in response"

        print(f"   ✅ User created: {created_user['username']}")
        print(f"   ✅ Display name: {created_user['name']}")
        print(f"   ✅ Created at: {created_user['created_at']}")

        # Test 2: Verify user exists in DynamoDB
        print("\n🔍 Test 2: Verifying user in DynamoDB...")
        response = users_table.get_item(Key={'username': TEST_USERNAME})

        assert 'Item' in response, "User not found in DynamoDB"
        db_user = response['Item']

        assert db_user['username'] == TEST_USERNAME, "Username mismatch in DB"
        assert db_user['name'] == TEST_NAME, "Name mismatch in DB"
        assert 'password_hash' in db_user, "Password hash missing in DB"
        assert 'created_at' in db_user, "created_at missing in DB"

        print(f"   ✅ User found in DynamoDB")
        print(f"   ✅ Username: {db_user['username']}")
        print(f"   ✅ Name: {db_user['name']}")

        # Test 3: Verify password is hashed (bcrypt)
        print("\n🔒 Test 3: Verifying password hashing...")
        password_hash = db_user['password_hash']

        # Bcrypt hashes start with $2b$ and are 60 characters long
        assert password_hash.startswith('$2b$'), "Password not hashed with bcrypt"
        assert len(password_hash) == 60, f"Invalid bcrypt hash length: {len(password_hash)}"
        assert password_hash != TEST_PASSWORD, "Password stored in plain text!"

        print(f"   ✅ Password hashed with bcrypt")
        print(f"   ✅ Hash: {password_hash[:20]}... (truncated)")

        # Test 4: Verify get_user() returns correct data
        print("\n📖 Test 4: Testing get_user()...")
        user = repo.get_user(TEST_USERNAME)

        assert user is not None, "get_user() returned None"
        assert user['username'] == TEST_USERNAME, "Username mismatch"
        assert user['name'] == TEST_NAME, "Name mismatch"
        assert 'password_hash' not in user, "Password hash should not be in response"
        assert 'created_at' in user, "Missing created_at timestamp"

        print(f"   ✅ get_user() returned correct data")
        print(f"   ✅ Username: {user['username']}")
        print(f"   ✅ Name: {user['name']}")

        # Test 5: Verify duplicate username raises error
        print("\n🚫 Test 5: Testing duplicate username rejection...")
        try:
            repo.create_user(TEST_USERNAME, "Another Name", "password456")
            print("   ❌ ERROR: Duplicate username was accepted (SHOULD HAVE FAILED!)")
            success = False
        except UserAlreadyExistsError as e:
            print(f"   ✅ UserAlreadyExistsError raised (expected)")
            print(f"   ✅ Error message: {e}")
            success = True

        # Test 6: Verify get_user() for non-existent user returns None
        print("\n🔍 Test 6: Testing get_user() for non-existent user...")
        non_existent_user = repo.get_user('this_user_does_not_exist_12345')

        assert non_existent_user is None, "get_user() should return None for non-existent user"

        print(f"   ✅ get_user() returned None for non-existent user")

        # Cleanup
        print("\n🧹 Cleaning up...")
        cleanup_test_user()

        # Final result
        print("\n" + "=" * 60)
        print("📊 Test Results")
        print("=" * 60)
        print("✅ PASS: User created successfully")
        print("✅ PASS: Password hashed with bcrypt")
        print("✅ PASS: User data retrievable")
        print("✅ PASS: Duplicate username rejected")
        print("✅ PASS: Non-existent user returns None")

        print("\n" + "=" * 60)
        if success:
            print("✅ Test 5.1 PASSED: User registration working correctly")
        else:
            print("❌ Test 5.1 FAILED: Duplicate username not rejected")
        print("=" * 60)

        return 0 if success else 1

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        print("\n🧹 Cleaning up...")
        cleanup_test_user()

        return 1


if __name__ == '__main__':
    sys.exit(test_user_registration())
