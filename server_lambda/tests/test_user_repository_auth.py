#!/usr/bin/env python3
"""
Test 5.2: UserRepository - User Authentication Test

This test validates user authentication (login verification) with DynamoDB.

Test Flow:
1. Create a test user
2. Test successful authentication with correct password
3. Test failed authentication with wrong password
4. Test failed authentication with non-existent user
5. Test password update
6. Verify authentication works with new password
7. Cleanup test user

Success Criteria:
- Correct password authenticates successfully
- Wrong password fails authentication
- Non-existent user fails authentication
- Password can be updated
- New password works for authentication
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import boto3
from user_repository import UserRepository, UserNotFoundError

# Test configuration
TEST_USERNAME = 'test_user_auth'
TEST_NAME = 'Test User Auth'
TEST_PASSWORD = 'correct_password_123'
WRONG_PASSWORD = 'wrong_password_456'
NEW_PASSWORD = 'new_password_789'

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


def test_user_authentication():
    """
    Test 5.2: User Authentication

    Tests user login verification with bcrypt password hashing.
    """
    print("\n🧪 Test 5.2: UserRepository - User Authentication Test")
    print("=" * 60)
    print(f"Testing user authentication with DynamoDB")
    print(f"Table: {DYNAMODB_USERS_TABLE}")
    print(f"Username: {TEST_USERNAME}\n")

    try:
        # Cleanup any existing test user
        cleanup_test_user()

        # Initialize repository
        repo = UserRepository()

        # Setup: Create test user
        print("📝 Setup: Creating test user...")
        repo.create_user(TEST_USERNAME, TEST_NAME, TEST_PASSWORD)
        print(f"   ✅ User created: {TEST_USERNAME}")

        # Test 1: Successful authentication with correct password
        print("\n✅ Test 1: Authenticating with CORRECT password...")
        success = repo.authenticate(TEST_USERNAME, TEST_PASSWORD)

        assert success is True, "Authentication failed with correct password"

        print(f"   ✅ Authentication successful")
        print(f"   ✅ Username: {TEST_USERNAME}")
        print(f"   ✅ Password: {TEST_PASSWORD}")

        # Test 2: Failed authentication with wrong password
        print("\n🚫 Test 2: Authenticating with WRONG password...")
        success = repo.authenticate(TEST_USERNAME, WRONG_PASSWORD)

        assert success is False, "Authentication succeeded with wrong password (SECURITY BUG!)"

        print(f"   ✅ Authentication failed (expected)")
        print(f"   ✅ Username: {TEST_USERNAME}")
        print(f"   ✅ Wrong password: {WRONG_PASSWORD}")

        # Test 3: Failed authentication with non-existent user
        print("\n🚫 Test 3: Authenticating non-existent user...")
        success = repo.authenticate('this_user_does_not_exist_12345', TEST_PASSWORD)

        assert success is False, "Authentication succeeded for non-existent user (SECURITY BUG!)"

        print(f"   ✅ Authentication failed (expected)")
        print(f"   ✅ Non-existent user rejected")

        # Test 4: Update user password
        print("\n🔄 Test 4: Updating user password...")
        updated_user = repo.update_user(TEST_USERNAME, password=NEW_PASSWORD)

        assert updated_user is not None, "update_user() returned None"
        assert updated_user['username'] == TEST_USERNAME, "Username mismatch"
        assert 'updated_at' in updated_user, "Missing updated_at timestamp"

        print(f"   ✅ Password updated successfully")
        print(f"   ✅ Username: {updated_user['username']}")
        print(f"   ✅ Updated at: {updated_user['updated_at']}")

        # Test 5: Old password should NOT work
        print("\n🚫 Test 5: Verifying old password rejected...")
        success = repo.authenticate(TEST_USERNAME, TEST_PASSWORD)

        assert success is False, "Old password still works after update (BUG!)"

        print(f"   ✅ Old password rejected (expected)")

        # Test 6: New password should work
        print("\n✅ Test 6: Authenticating with NEW password...")
        success = repo.authenticate(TEST_USERNAME, NEW_PASSWORD)

        assert success is True, "Authentication failed with new password"

        print(f"   ✅ Authentication successful with new password")
        print(f"   ✅ Username: {TEST_USERNAME}")
        print(f"   ✅ New password: {NEW_PASSWORD}")

        # Test 7: Update display name (without password)
        print("\n🔄 Test 7: Updating display name only...")
        NEW_NAME = "Updated Test User"
        updated_user = repo.update_user(TEST_USERNAME, name=NEW_NAME)

        assert updated_user is not None, "update_user() returned None"
        assert updated_user['name'] == NEW_NAME, "Name not updated"

        print(f"   ✅ Name updated successfully")
        print(f"   ✅ New name: {updated_user['name']}")

        # Verify password still works after name update
        success = repo.authenticate(TEST_USERNAME, NEW_PASSWORD)
        assert success is True, "Password broken after name update"
        print(f"   ✅ Password still works after name update")

        # Test 8: Update non-existent user
        print("\n🚫 Test 8: Updating non-existent user...")
        try:
            repo.update_user('this_user_does_not_exist_12345', name="New Name")
            print("   ❌ ERROR: Updating non-existent user succeeded (SHOULD HAVE FAILED!)")
            test_8_passed = False
        except UserNotFoundError as e:
            print(f"   ✅ UserNotFoundError raised (expected)")
            print(f"   ✅ Error message: {e}")
            test_8_passed = True

        # Cleanup
        print("\n🧹 Cleaning up...")
        cleanup_test_user()

        # Final result
        print("\n" + "=" * 60)
        print("📊 Test Results")
        print("=" * 60)
        print("✅ PASS: Correct password authenticates successfully")
        print("✅ PASS: Wrong password fails authentication")
        print("✅ PASS: Non-existent user fails authentication")
        print("✅ PASS: Password can be updated")
        print("✅ PASS: Old password rejected after update")
        print("✅ PASS: New password works after update")
        print("✅ PASS: Display name can be updated")
        if test_8_passed:
            print("✅ PASS: Update non-existent user raises error")
        else:
            print("❌ FAIL: Update non-existent user should raise error")

        print("\n" + "=" * 60)
        if test_8_passed:
            print("✅ Test 5.2 PASSED: User authentication working correctly")
        else:
            print("❌ Test 5.2 FAILED: Some authentication checks failed")
        print("=" * 60)

        return 0 if test_8_passed else 1

    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()

        # Cleanup on error
        print("\n🧹 Cleaning up...")
        cleanup_test_user()

        return 1


if __name__ == '__main__':
    sys.exit(test_user_authentication())
