#!/bin/bash
# Cleanup script for race condition test
# Run this ON THE SERVER to remove all test data

echo "============================================================"
echo "  Race Condition Test - Clean Slate"
echo "============================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "admin.db" ]; then
    echo "❌ Error: admin.db not found!"
    echo "   Make sure you're in the server directory"
    echo "   cd ~/javumbo/server"
    exit 1
fi

# Count test users before cleanup
TEST_USER_COUNT=$(sqlite3 admin.db "SELECT COUNT(*) FROM users WHERE username LIKE 'race%';")
echo "Found $TEST_USER_COUNT test users to remove"

# Get test user IDs
echo ""
echo "Test users to be deleted:"
sqlite3 admin.db "SELECT user_id, username FROM users WHERE username LIKE 'race%';"

echo ""
read -p "Continue with cleanup? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled"
    exit 0
fi

# Remove test users from admin database
echo ""
echo "🧹 Removing test users from admin.db..."
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'race%';"

# Remove test user database files
echo "🧹 Removing test user database files..."
for db in user_dbs/user_*.db; do
    if [ -f "$db" ]; then
        # Check if database belongs to a test user by looking for race markers
        HAS_MARKERS=$(sqlite3 "$db" "SELECT COUNT(*) FROM notes WHERE flds LIKE '%[USER:race%' LIMIT 1;" 2>/dev/null || echo "0")

        if [ "$HAS_MARKERS" != "0" ]; then
            echo "  Removing: $db"
            rm -f "$db"
        fi
    fi
done

# Remove any test report files
if [ -f "race_condition_report.json" ]; then
    echo "🧹 Removing race_condition_report.json..."
    rm -f race_condition_report.json
fi

# Verify cleanup
REMAINING=$(sqlite3 admin.db "SELECT COUNT(*) FROM users WHERE username LIKE 'race%';")

echo ""
echo "============================================================"
if [ "$REMAINING" -eq 0 ]; then
    echo "✅ Cleanup complete!"
    echo "   - Removed $TEST_USER_COUNT test users"
    echo "   - Removed test database files"
else
    echo "⚠️  Warning: $REMAINING test users still remain"
fi
echo "============================================================"
echo ""
echo "Ready for a fresh test run!"
echo "Run: python create_test_users.py"
