# Race Condition Quick Test - 30 Minute Guide

This is the fast-track test to detect the suspected session race condition in JAVUMBO.

## What This Does

1. Creates 3 test users (`race0`, `race1`, `race2`)
2. Has all 3 users simultaneously add 50 cards each (150 total)
3. Each card has embedded markers like `[USER:race0]` for forensic analysis
4. Scans all databases to detect if cards ended up in the wrong user's database

**If cards are found in the wrong databases → Race condition confirmed!**

---

## Prerequisites

- Python 3.x with `requests` library
- Access to your server at http://54.87.11.69
- SSH access to the server for validation

```bash
# Install requests if needed
pip install requests
```

---

## Step 1: Create Test Users (5 minutes)

From your **local machine** in the `server/` directory:

```bash
cd /Users/emadruga/proj/javumbo/server

python create_test_users.py
```

**Expected output:**
```
============================================================
Creating Test Users for Race Condition Test
============================================================
Target: http://54.87.11.69
Users to create: 3

✅ Created: race0 (ID: 42)
✅ Created: race1 (ID: 43)
✅ Created: race2 (ID: 44)

✅ Setup complete: 3/3 users ready
```

---

## Step 2: Run Load Test (10 minutes)

From your **local machine** in the `server/` directory:

```bash
python test_race_quick.py
```

This will:
- Login all 3 users simultaneously
- Have each user rapidly add 50 cards (10ms delay between cards)
- Show progress as cards are created

**Expected output:**
```
======================================================================
  JAVUMBO Race Condition Quick Test
======================================================================
Target: http://54.87.11.69
Cards per user: 50
Total cards: 150

🚀 Starting concurrent card creation...

✅ Worker 0 (race0): Logged in
✅ Worker 1 (race1): Logged in
✅ Worker 2 (race2): Logged in
  Worker 0: 10/50 cards added
  Worker 1: 10/50 cards added
  Worker 2: 10/50 cards added
  ...
✅ Worker 0 (race0): Completed - 50 success, 0 errors
✅ Worker 1 (race1): Completed - 50 success, 0 errors
✅ Worker 2 (race2): Completed - 50 success, 0 errors

======================================================================
  Test Completed!
======================================================================
Duration: 18.45 seconds
Throughput: 8.1 cards/second
Total cards created: 150
Total errors: 0
```

---

## Step 3: Validate Results (15 minutes)

### 3a. Copy validation script to server

```bash
# From your local machine
scp validate_race_condition.py user@54.87.11.69:/opt/flashcard-app-teste/javumbo/server/
```

### 3b. SSH to server and run validation

```bash
# SSH to server
ssh user@54.87.11.69

# Navigate to server directory
cd /opt/flashcard-app-teste/javumbo/server

# Run validation
python3 validate_race_condition.py
```

---

## Interpreting Results

### ✅ No Race Condition (unlikely)

```
======================================================================
  SUMMARY
======================================================================
Total cards scanned: 150
Total violations found: 0

✅ NO RACE CONDITION DETECTED

All cards are in the correct user databases.
```

**If you see this:**
- Race condition might not exist (unlikely given user reports)
- Or test didn't generate enough load
- Try running multiple times or increasing `CARDS_PER_USER`

### 🚨 Race Condition Confirmed (expected)

```
======================================================================
  SUMMARY
======================================================================
Total cards scanned: 150
Total violations found: 8

🚨 RACE CONDITION CONFIRMED!

Found 8 cards in wrong databases.

Evidence:
  race0's database contains:
    - Card from race1 (card_id: 1730847201234)
    - Card from race2 (card_id: 1730847203456)
  race1's database contains:
    - Card from race0 (card_id: 1730847205678)
    ...

📄 Detailed report saved to: race_condition_report.json
```

**If you see this:**
- **Race condition is CONFIRMED!**
- This proves the filesystem session bug exists
- Next step: Implement Redis-backed sessions (see `docs/SESSION_ARCHITECTURE_ANALYSIS.md`)

---

## Cleanup

After testing, remove test users and data:

```bash
# On server
cd /opt/flashcard-app-teste/javumbo/server

# Remove test users from admin DB
sqlite3 admin.db "DELETE FROM users WHERE username LIKE 'race%';"

# Remove test user databases
rm -f user_dbs/user_*[0-9].db

# Verify cleanup
sqlite3 admin.db "SELECT username FROM users WHERE username LIKE 'race%';"
# Should return nothing
```

---

## Troubleshooting

### "Connection refused"

**Problem:** Can't connect to http://54.87.11.69

**Solution:**
```bash
# Check if server is running
docker ps | grep flashcard_server

# If not running, start it
docker compose up -d
```

### "Login failed"

**Problem:** Users can't login with the test password

**Solution:**
- Check that users were created successfully
- Verify password length (must be 10-20 chars)
- Check server logs: `docker logs flashcard_server`

### "Database file not found"

**Problem:** Validation can't find user databases

**Solution:**
```bash
# Check user IDs in admin DB
sqlite3 admin.db "SELECT user_id, username FROM users WHERE username LIKE 'race%';"

# Check what database files exist
ls -la user_dbs/
```

### No violations found (but you expected some)

**Problem:** Test didn't trigger race condition

**Solution:**
- Run the test multiple times (race conditions are timing-dependent)
- Edit `test_race_quick.py` and decrease `DELAY_MS` from 10 to 5 or 1
- Edit `test_race_quick.py` and increase `CARDS_PER_USER` from 50 to 100

---

## What's Next?

### If Race Condition is Confirmed:

1. **Document the evidence**
   - Save `race_condition_report.json`
   - Screenshot the validation output

2. **Implement the fix**
   - Follow the Redis migration guide in `docs/SESSION_ARCHITECTURE_ANALYSIS.md`
   - Add Redis to docker-compose
   - Update Flask session config

3. **Re-test**
   - Run this test again after implementing Redis
   - Should show 0 violations

4. **Deploy to production**
   - Test thoroughly in staging
   - Deploy Redis + updated app.py
   - Monitor for user reports

### If No Race Condition is Found:

1. **Increase test intensity**
   - Run with more users (5-10)
   - More cards per user (100-200)
   - Shorter delays (1-5ms)

2. **Check server configuration**
   - Verify Gunicorn is using multiple workers: `docker exec flashcard_server ps aux | grep gunicorn`
   - Should see 3-4 worker processes

3. **Review user reports**
   - Gather more specific details from users experiencing the issue
   - Check server logs for anomalies

---

## Time Estimate

- **Step 1 (Create users):** 5 minutes
- **Step 2 (Run test):** 10 minutes
- **Step 3 (Validate):** 15 minutes

**Total: ~30 minutes**

---

## Files Created

- `create_test_users.py` - Creates test users (run on local machine)
- `test_race_quick.py` - Load test script (run on local machine)
- `validate_race_condition.py` - Database validation (run on server)
- `race_condition_report.json` - Detailed results (created on server if violations found)

---

**Good luck! Let's find that race condition! 🏁**
