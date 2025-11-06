# JAVUMBO Load Testing Plan

## 1. Overview

This document outlines the comprehensive load testing strategy for the JAVUMBO flashcard application, with a specific focus on **data integrity validation** under concurrent load. The primary goal is to identify and validate the suspected race condition where flashcards are being written to incorrect user databases when multiple Gunicorn workers handle concurrent requests.

---

## 2. Critical Issue: Suspected Race Condition

### 2.1 Problem Description

**User Complaint**: Some users report that flashcards they added never appear in their decks, suggesting cards may be written to other users' databases.

### 2.2 Root Cause Hypothesis

**Architecture Analysis**:
- **Gunicorn Configuration**: 3 workers running in the Docker container ([server/Dockerfile:34](server/Dockerfile#L34))
- **Session Storage**: Flask-Session using filesystem-based sessions ([app.py:60](server/app.py#L60))
- **Database Access**: Each user has a separate SQLite database (`user_dbs/user_{user_id}.db`)
- **User Identification**: Routes use `session['user_id']` to determine which database to write to

**Potential Race Conditions**:

1. **Session Integrity Issue**:
   - Multiple Gunicorn workers may not properly isolate session data
   - Session file corruption or stale reads across workers
   - Session cookie not properly validated before database write

2. **SQLite Write Contention**:
   - SQLite databases in WAL mode allow concurrent reads but serialize writes
   - No application-level locking around multi-step operations
   - Timestamp-based ID generation (`note_id = current_time_ms`) may collide

3. **User ID Propagation**:
   - `session['user_id']` retrieved at route entry ([app.py:1826](server/app.py#L1826))
   - If session changes between retrieval and database write, wrong DB targeted
   - No validation that session user matches database owner

### 2.3 Evidence Collection Strategy

The load test MUST prove:
1. **Card Ownership**: Every inserted card is in the correct user's database
2. **Card Count**: Number of cards written = number of successful API responses
3. **Cross-Contamination**: No user has cards from another user's session
4. **Session Integrity**: Session user_id matches actual authenticated user throughout request lifecycle

---

## 3. Load Test Scenarios

### 3.1 Scenario A: Concurrent User Registration (30 users)

**Objective**: Validate that user signup works correctly under concurrent load.

**Parameters**:
- 30 simulated users
- Random names, emails, areas of interest
- Fixed password: `password123`
- All signups within 5-second window

**Validation**:
- All 30 users in `admin.db` with unique `user_id`
- Each user has a corresponding database file `user_dbs/user_{user_id}.db`
- Each user database has correct Anki schema initialization
- No duplicate usernames or emails

---

### 3.2 Scenario B: Card Writers (20% = 6 users)

**Objective**: Test concurrent card creation and validate data integrity.

**Parameters**:
- 6 users from Scenario A
- Each creates cards on random topics (History, Science, Languages, Math, Geography, Literature)
- Gradual ramp-up: Start with 1 writer, increase to 6 writers
- Each writer adds 10-50 cards over 2-minute period

**Critical Validation** (per user, per card):
1. **Pre-Write Marker**: Before API call, log `(username, timestamp, front_text, expected_deck_id)`
2. **API Response**: Capture `card_id` returned by server
3. **Post-Write Verification**:
   - Query user's database directly: `SELECT * FROM cards WHERE id = {card_id}`
   - Verify card exists in correct user's DB
   - Join with `notes` table to validate `front` and `back` match expected values
   - Verify `did` (deck ID) matches expected deck
4. **Cross-Contamination Check**:
   - Query ALL other users' databases for the same `card_id`
   - Verify card does NOT exist in any other user's database

**Ramp-Up Strategy**:
```
Time    Active Writers    Purpose
0-30s        1            Baseline (should always work)
30-60s       2            Detect first concurrent write issues
60-90s       3            Standard concurrent load
90-120s      6            Maximum concurrent card creation
```

**Data Integrity Markers**:
Each card will have a unique identifier embedded in the `front` field:
```
Front: "[USER:{username}][SEQ:{sequence_number}][TIME:{timestamp}] {topic_content}"
```

This allows post-test forensic analysis to identify misrouted cards.

---

### 3.3 Scenario C: Card Reviewers (80% = 24 users)

**Objective**: Test concurrent read-heavy operations on shared deck "Verbal Tenses".

**Setup**:
- Pre-populate "Verbal Tenses" deck with 100 cards
- All 24 users review cards concurrently
- Each user performs 20-50 reviews

**Parameters**:
- Gradual ramp-up: 5 reviewers initially, add 5 every 30 seconds until 24 active
- Each review involves:
  1. `GET /review` - Fetch next card
  2. `POST /answer` - Submit review result
  3. Track response times and error rates

**Validation**:
- All review sessions complete successfully
- No `401 Unauthorized` errors (session integrity)
- SM-2 scheduling correctly updates `cards` table in each user's DB
- Review history (`revlog` table) contains correct `user_id` references

---

## 4. Test Implementation Architecture

### 4.1 Technology Stack

- **Load Testing Framework**: Python with `asyncio` and `aiohttp`
- **Database Validation**: Direct SQLite3 queries
- **Concurrency**: `asyncio.gather()` for parallel user simulation
- **Logging**: Structured JSON logs for forensic analysis

### 4.2 Script Structure

```
load_tests/
├── config.py                 # Test configuration (API URL, user count, etc.)
├── user_generator.py         # Generate random user data
├── scenario_a_registration.py  # Test concurrent signups
├── scenario_b_writers.py     # Test card creation with validation
├── scenario_c_reviewers.py   # Test card reviews
├── validators/
│   ├── __init__.py
│   ├── db_validator.py       # Direct SQLite validation
│   ├── ownership_validator.py # Card ownership checks
│   └── session_validator.py  # Session integrity checks
├── utils/
│   ├── api_client.py         # Async HTTP client wrapper
│   ├── logger.py             # Structured logging
│   └── metrics.py            # Performance metrics collection
└── run_full_test.py          # Master orchestrator
```

### 4.3 Database Validation Logic

```python
def validate_card_ownership(username, card_id, expected_front, expected_back):
    """
    Validates that a card exists in the correct user's database
    and does not exist in any other user's database.

    Returns:
        {
            "valid": bool,
            "found_in_correct_db": bool,
            "found_in_wrong_dbs": [list of wrong usernames],
            "content_matches": bool,
            "details": {...}
        }
    """
    user_id = get_user_id_from_admin_db(username)
    user_db_path = f"server/user_dbs/user_{user_id}.db"

    # Check correct database
    conn = sqlite3.connect(user_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT n.flds, c.did
        FROM cards c
        JOIN notes n ON c.nid = n.id
        WHERE c.id = ?
    """, (card_id,))
    result = cursor.fetchone()
    conn.close()

    found_in_correct_db = result is not None
    content_matches = False
    if result:
        fields = result[0].split('\x1f')
        content_matches = (fields[0] == expected_front and fields[1] == expected_back)

    # Check ALL other user databases
    all_users = get_all_usernames_from_admin_db()
    found_in_wrong_dbs = []
    for other_username in all_users:
        if other_username == username:
            continue
        other_user_id = get_user_id_from_admin_db(other_username)
        other_db_path = f"server/user_dbs/user_{other_user_id}.db"

        if os.path.exists(other_db_path):
            conn = sqlite3.connect(other_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
            if cursor.fetchone():
                found_in_wrong_dbs.append(other_username)
            conn.close()

    return {
        "valid": found_in_correct_db and content_matches and len(found_in_wrong_dbs) == 0,
        "found_in_correct_db": found_in_correct_db,
        "found_in_wrong_dbs": found_in_wrong_dbs,
        "content_matches": content_matches,
        "card_id": card_id,
        "username": username
    }
```

---

## 5. Test Execution Flow

### 5.1 Pre-Test Setup

1. **Environment Check**:
   ```bash
   # Ensure Docker containers are running
   docker compose ps

   # Clear existing test data
   rm -f server/admin.db
   rm -rf server/user_dbs/*
   rm -rf server/flask_session/*

   # Restart containers with fresh state
   docker compose restart
   ```

2. **Initialize Admin DB**:
   ```bash
   docker exec flashcard_server python3 -c "from app import init_admin_db; init_admin_db()"
   ```

3. **Create "Verbal Tenses" Deck**:
   - Register a master user
   - Create deck with 100 pre-populated cards
   - Export deck structure for test setup

### 5.2 Test Execution

```bash
cd load_tests
python run_full_test.py --target http://54.87.11.69 --users 30 --duration 300
```

**Execution Phases**:
1. **Phase 1** (0-30s): Concurrent registration of 30 users
2. **Phase 2** (30-60s): Validation of all registrations
3. **Phase 3** (60-180s): Scenario B (writers) + Scenario C (reviewers) concurrently
4. **Phase 4** (180-240s): Continue reviews, gradually reduce writers
5. **Phase 5** (240-300s): Final validation and data integrity checks

### 5.3 Real-Time Monitoring

During test execution, display:
```
Time: 120s | Writers: 6/6 | Reviewers: 24/24 | Cards Created: 180 | Errors: 0
Data Integrity: ✅ All cards in correct DBs | Session Errors: 0 | API Errors: 0
```

### 5.4 Post-Test Validation

**Automated Checks**:
1. **Card Count Validation**:
   ```sql
   -- For each writer user
   SELECT COUNT(*) FROM cards WHERE did = {expected_deck_id}
   -- Must match number of successful POST /add_card responses
   ```

2. **Cross-Database Scan**:
   ```python
   for user in all_users:
       cards_in_db = get_all_card_ids(user.db_path)
       for card_id in cards_in_db:
           # Parse embedded marker from note.flds
           marker = extract_marker_from_card(user.db_path, card_id)
           if marker.username != user.username:
               report_integrity_violation(card_id, marker.username, user.username)
   ```

3. **Session Log Analysis**:
   ```bash
   # Check for session-related errors in server logs
   docker logs flashcard_server | grep -i "session\|401\|unauthorized"
   ```

---

## 6. Expected Outcomes

### 6.1 If Race Condition EXISTS:

**Symptoms**:
- Cards with `[USER:alice]` marker found in `user_dbs/user_7.db` (Bob's database)
- Writer reports 50 cards created, but only 45 found in their database
- Validation script reports: `Cross-contamination detected: 5 cards misrouted`

**Evidence**:
```json
{
  "integrity_violations": [
    {
      "card_id": 1730847201234,
      "expected_owner": "alice_user_123",
      "actual_owner": "bob_user_456",
      "timestamp": "2025-11-05T10:23:45Z",
      "front_marker": "[USER:alice_user_123][SEQ:23][TIME:1730847201234]",
      "gunicorn_worker": "worker_2"
    }
  ]
}
```

### 6.2 If System is CORRECT:

**Validation Results**:
```
✅ All 30 users registered successfully
✅ All 6 writers created 300 total cards
✅ 100% card ownership validation passed
✅ 0 cross-contamination incidents
✅ All 24 reviewers completed sessions without session errors
✅ Review history correctly recorded in individual databases
```

---

## 7. Root Cause Investigation Tools

### 7.1 Enhanced Logging

**Temporary App Modifications** (for testing only):

Add to [app.py:1825](server/app.py#L1825) at `add_new_card()`:
```python
@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    import threading
    worker_id = os.getpid()
    thread_id = threading.get_ident()

    user_id = session['user_id']
    username = session.get('username', 'unknown')

    # CRITICAL: Log session state at route entry
    app.logger.info(f"ADD_CARD_START | PID:{worker_id} | Thread:{thread_id} | "
                    f"SessionUser:{username} | SessionUserID:{user_id} | "
                    f"SessionID:{session.sid}")

    user_db_path = get_user_db_path(user_id)

    # Log which database file will be written to
    app.logger.info(f"ADD_CARD_TARGET_DB | PID:{worker_id} | UserID:{user_id} | "
                    f"DBPath:{user_db_path}")

    # ... existing card creation logic ...

    # Log successful write
    app.logger.info(f"ADD_CARD_SUCCESS | PID:{worker_id} | CardID:{card_id} | "
                    f"UserID:{user_id} | Username:{username}")
```

### 7.2 Session Integrity Monitor

Create `validators/session_validator.py`:
```python
def validate_session_consistency(api_client, username, password):
    """
    Performs rapid sequential requests to detect session inconsistencies.

    1. Login
    2. Get /decks (should succeed)
    3. POST /add_card (should succeed)
    4. Get /decks again (should succeed)
    5. Verify all responses reference same user_id
    """
    session_ids = []
    user_ids = []

    # Login
    response = api_client.post('/login', json={'username': username, 'password': password})
    session_ids.append(response.cookies.get('session'))

    # Multiple rapid requests
    for i in range(10):
        response = api_client.get('/decks')
        # Extract user_id from response (if API returns it)
        user_ids.append(extract_user_id_from_response(response))

    # Validate consistency
    unique_session_ids = set(session_ids)
    unique_user_ids = set(user_ids)

    return {
        "consistent": len(unique_session_ids) == 1 and len(unique_user_ids) == 1,
        "session_changes": len(unique_session_ids),
        "user_id_changes": len(unique_user_ids)
    }
```

---

## 8. Mitigation Strategies (If Race Condition Confirmed)

### 8.1 Immediate Fix Options

**Option 1: Application-Level Locking**
```python
import threading

# Global lock per user_id
_user_db_locks = {}
_locks_lock = threading.Lock()

def get_user_db_lock(user_id):
    with _locks_lock:
        if user_id not in _user_db_locks:
            _user_db_locks[user_id] = threading.Lock()
        return _user_db_locks[user_id]

@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']

    # Acquire lock for this user's database
    with get_user_db_lock(user_id):
        # All database operations here
        # ...
```

**Option 2: Session Re-Validation**
```python
def validate_session_user(expected_user_id):
    """Re-validates that session still belongs to expected user."""
    current_user_id = session.get('user_id')
    if current_user_id != expected_user_id:
        app.logger.error(f"SESSION_MISMATCH | Expected:{expected_user_id} | Got:{current_user_id}")
        raise Unauthorized("Session validation failed")
    return True

@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']
    # ... do work ...
    validate_session_user(user_id)  # Re-check before DB write
    # ... write to database ...
```

**Option 3: Database Write Verification**
```python
def add_card_with_verification(user_id, front, back, deck_id):
    """Adds card and immediately verifies it's in correct database."""
    user_db_path = get_user_db_path(user_id)

    # Write card
    card_id = insert_card(user_db_path, front, back, deck_id)

    # Immediate verification
    conn = sqlite3.connect(user_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
    if not cursor.fetchone():
        conn.close()
        app.logger.critical(f"CARD_WRITE_VERIFICATION_FAILED | CardID:{card_id} | UserID:{user_id}")
        raise IntegrityError("Card write verification failed")
    conn.close()

    return card_id
```

### 8.2 Configuration Changes

**Reduce Gunicorn Workers** (temporary diagnostic):
```dockerfile
# In server/Dockerfile, change from:
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "app:app"]

# To single worker for testing:
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:app"]
```

Run load test again. If issue disappears with 1 worker, confirms multi-worker race condition.

### 8.3 Session Storage Alternative

**Switch to Redis-backed sessions**:
```python
# In app.py
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
```

Redis provides atomic operations and proper isolation between workers.

---

## 9. Test Deliverables

### 9.1 Automated Test Reports

- `test_results_summary.json`: High-level pass/fail metrics
- `integrity_violations.json`: Detailed list of any misrouted cards
- `performance_metrics.json`: Response times, throughput, error rates
- `session_analysis.json`: Session consistency validation results

### 9.2 Forensic Evidence

- `server_logs.txt`: Complete Docker logs during test
- `database_snapshots/`: Backup of all user DBs post-test
- `api_request_log.jsonl`: Every API request/response with timestamps

### 9.3 Visual Reports

- Response time distribution graphs
- Card creation rate over time
- Error rate by scenario
- Data integrity violation timeline (if any)

---

## 10. Test Execution Timeline

### 10.1 Development Phase (3-5 days)

1. **Day 1**: Implement base test framework and user generator
2. **Day 2**: Implement Scenario A (registration) + database validators
3. **Day 3**: Implement Scenario B (writers) + ownership validation
4. **Day 4**: Implement Scenario C (reviewers) + integrate all scenarios
5. **Day 5**: Testing and refinement of load test scripts

### 10.2 Execution Phase (1 day)

1. **Morning**: Pre-test environment setup and validation
2. **Midday**: Full load test execution (5-minute run)
3. **Afternoon**: Post-test validation and report generation
4. **Evening**: Root cause analysis if issues found

### 10.3 Remediation Phase (Variable)

- **If no issues**: Document success, establish baseline metrics
- **If race condition confirmed**: Implement fix, re-test, validate

---

## 11. Success Criteria

### 11.1 Test Infrastructure Success

- [ ] All 30 users can register concurrently without errors
- [ ] Load test completes without script failures
- [ ] All API endpoints return expected status codes
- [ ] Database validation scripts execute without errors

### 11.2 Data Integrity Success (CRITICAL)

- [ ] **100% card ownership validation**: Every card in correct user's database
- [ ] **0 cross-contamination incidents**: No cards in wrong databases
- [ ] **Card count matches**: API success responses = cards in database
- [ ] **Marker validation**: All embedded markers match database owner
- [ ] **Session integrity**: No unauthorized errors during valid sessions

### 11.3 Performance Success

- [ ] Average response time for `POST /add_card` < 500ms
- [ ] Average response time for `GET /review` < 300ms
- [ ] Error rate < 1% across all scenarios
- [ ] System handles 30 concurrent users without degradation

---

## 12. Next Steps

After reviewing this plan:

1. **Approve test approach**: Confirm scenarios match user concerns
2. **Set test environment**: AWS instance or local Docker?
3. **Define acceptance criteria**: What constitutes "test passed"?
4. **Implement test scripts**: Begin with Scenario A, iterate to B and C
5. **Schedule test execution**: Coordinate with team for test window

---

## Appendix A: Quick Reference Commands

### Run Full Load Test
```bash
cd load_tests
python run_full_test.py --target http://54.87.11.69 --users 30
```

### Validate Single User's Database
```bash
python -c "from validators.ownership_validator import validate_user_db; \
           validate_user_db('alice_user_123')"
```

### Check for Cross-Contamination
```bash
python validators/cross_contamination_scan.py --scan-all
```

### Extract Integrity Violations from Logs
```bash
docker logs flashcard_server | grep "INTEGRITY_VIOLATION" > violations.log
```

### Generate Test Report
```bash
python utils/generate_report.py --input test_results/ --output report.html
```

---

## Appendix B: Test Data Specifications

### Random User Generation
```python
{
    "username": f"{random_adjective}_{random_noun}_{random_number}",  # e.g., "happy_tiger_742"
    "name": f"{random_first_name} {random_last_name}",
    "email": f"{username}@loadtest.javumbo.local",
    "password": "password123",
    "area_of_interest": random.choice([
        "Medical Terminology", "Legal Terms", "Programming",
        "Spanish Vocabulary", "French Grammar", "German Cases",
        "Biology Concepts", "Chemistry Formulas", "Physics Laws"
    ])
}
```

### Random Card Topics (for writers)
```python
CARD_TOPICS = {
    "History": ["WWI", "WWII", "Renaissance", "Ancient Rome"],
    "Science": ["Newton's Laws", "Periodic Table", "Cell Biology", "Genetics"],
    "Languages": ["Spanish Verbs", "French Adjectives", "German Articles"],
    "Math": ["Algebra", "Geometry", "Calculus", "Statistics"],
    "Geography": ["Capitals", "Rivers", "Mountains", "Countries"],
    "Literature": ["Shakespeare", "Poetry Terms", "Literary Devices"]
}
```

### Card Marker Format
```
Front: "[USER:{username}][SEQ:{sequence}][TIME:{timestamp}][TOPIC:{topic}] {actual_question}"
Back: "{actual_answer} [MARKER:{username}_{sequence}]"
```

Example:
```
Front: "[USER:alice_user_123][SEQ:42][TIME:1730847201234][TOPIC:History] Who led the Roman Empire in 49 BC?"
Back: "Julius Caesar [MARKER:alice_user_123_42]"
```

This allows forensic analysis to identify the intended owner of any card found in any database.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Author**: Claude (Claude Code)
**Status**: Ready for Review and Implementation
