#!/usr/bin/env python3
"""
Quick script to create test users for race condition testing.
Usage: python create_test_users.py
"""

import requests
import sys

BASE_URL = "http://54.226.2.146"
NUM_USERS = 15
PASSWORD = "password123test"  # 15 chars (meets 10-20 requirement)

def create_user(username, name):
    """Create a single test user."""
    try:
        response = requests.post(
            f"{BASE_URL}/register",
            json={
                "username": username,
                "name": name,
                "password": PASSWORD
            },
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            user_id = data.get('userId')
            print(f"✅ Created: {username} (ID: {user_id})")
            return True
        elif response.status_code == 409:
            print(f"⚠️  User already exists: {username}")
            return True  # Consider this success
        else:
            print(f"❌ Failed to create {username}: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ Exception creating {username}: {e}")
        return False

def main():
    print("=" * 60)
    print("Creating Test Users for Race Condition Test")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    print(f"Users to create: {NUM_USERS}")
    print(f"Password: {PASSWORD}")
    print()

    success_count = 0
    for i in range(NUM_USERS):
        username = f"race{i}"  # Short usernames (max 10 chars)
        name = f"Race Test User {i}"  # Name can be up to 40 chars

        if create_user(username, name):
            success_count += 1

    print()
    print("=" * 60)
    print(f"✅ Setup complete: {success_count}/{NUM_USERS} users ready")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Run: python test_race_quick.py")
    print("  2. SSH to server and run: python validate_race_condition.py")
    print()

    if success_count < NUM_USERS:
        sys.exit(1)

if __name__ == "__main__":
    main()
