# Fresh Start - Clean Test Run

Use this when you want to completely wipe test data and start over.

---

## On the Server

```bash
# SSH to server
ssh ubuntu@54.226.2.146

# Navigate to server directory
cd ~/javumbo/server

# Copy the cleanup script
# (You'll need to copy it from your local machine first)
```

### Copy cleanup script to server (from local machine):

```bash
# From your local machine in /Users/emadruga/proj/javumbo/server
scp cleanup_race_test.sh ubuntu@54.226.2.146:~/javumbo/server/

# SSH to server
ssh ubuntu@54.226.2.146
cd ~/javumbo/server

# Make it executable
chmod +x cleanup_race_test.sh

# Run cleanup
./cleanup_race_test.sh
```

---

## Or Manual Cleanup (if script doesn't work)

```bash
# SSH to server
ssh ubuntu@54.226.2.146
cd ~/javumbo/server

# 1. Remove test users from admin DB
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'race%';"

# 2. Find test user database files
sqlite3 admin.db "SELECT user_id FROM users WHERE username LIKE 'race%';"
# Note the user IDs (e.g., 2, 3, 4)

# 3. Remove those database files
rm -f user_dbs/user_2.db
rm -f user_dbs/user_3.db
rm -f user_dbs/user_4.db

# 4. Remove report file if it exists
rm -f race_condition_report.json

# 5. Verify cleanup
sqlite3 admin.db "SELECT username FROM users WHERE username LIKE 'race%';"
# Should return nothing

ls -la user_dbs/
# Should not see user_2.db, user_3.db, user_4.db
```

---

## After Cleanup - Fresh Test Run

Now you're ready for a completely clean test:

```bash
# On your LOCAL machine
cd /Users/emadruga/proj/javumbo/server

# Step 1: Create fresh test users
python create_test_users.py

# Step 2: Run the load test
python test_race_quick.py

# Step 3: Validate on server
ssh ubuntu@54.226.2.146
cd ~/javumbo/server
python3 validate_race_condition.py
```

---

## Quick Verification Commands

### Check if test users exist:
```bash
# On server
sqlite3 admin.db "SELECT user_id, username FROM users WHERE username LIKE 'race%';"
```

### Check if test databases exist:
```bash
# On server
ls -la user_dbs/user_*.db | grep -E "user_[0-9]+\.db"
```

### Check how many cards in test databases:
```bash
# On server
for db in user_dbs/user_{2,3,4}.db; do
    if [ -f "$db" ]; then
        echo "$db: $(sqlite3 "$db" 'SELECT COUNT(*) FROM cards;') cards"
    fi
done
```

---

## Common Issues

### Issue: "Database is locked"

**Solution:**
```bash
# Close any open connections
pkill -f "python.*admin.db"

# Or restart the Flask app
sudo systemctl restart flashcard-app-teste
# Or if using Docker:
docker restart flashcard_server
```

### Issue: Can't find user database files

**Problem:** Database file numbers don't match the user IDs you deleted

**Solution:** Use this to find ALL test databases by their content:
```bash
cd ~/javumbo/server/user_dbs
for db in user_*.db; do
    COUNT=$(sqlite3 "$db" "SELECT COUNT(*) FROM notes WHERE flds LIKE '%[USER:race%';" 2>/dev/null || echo "0")
    if [ "$COUNT" != "0" ]; then
        echo "$db has $COUNT test cards (DELETE THIS)"
    fi
done
```

---

## Nuclear Option (Complete Wipe)

**⚠️ WARNING: This removes ALL users and data, not just test users!**

Only use this if you're 100% sure there's no production data:

```bash
# On server - DANGER ZONE
cd ~/javumbo/server

# Backup first (just in case)
cp admin.db admin.db.backup
cp -r user_dbs user_dbs.backup

# Nuclear cleanup
rm -f admin.db
rm -rf user_dbs/*
rm -rf flask_session/*

# Restart app to reinitialize
sudo systemctl restart flashcard-app-teste
# Or Docker:
docker restart flashcard_server

# App will recreate admin.db on next request
```

---

**Ready to start fresh!** 🧹
