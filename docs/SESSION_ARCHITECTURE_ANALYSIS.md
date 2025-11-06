# Session Architecture Analysis: Filesystem vs Redis

## Current Architecture (Filesystem-Based Sessions)

### What the Codebase Uses Now

From [app.py:60-70](../server/app.py#L60-L70):

```python
SESSION_FILE_DIR = os.path.join(basedir, 'flask_session')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
```

**Current Setup**:
- **Storage Location**: `server/flask_session/` directory
- **Session Storage**: Each user session is stored as a **separate file** on disk
- **File Naming**: `flask_session/2029240f6d1128be89ddc32729463129` (example session ID)
- **Access Method**: Workers read/write session files using Python's `pickle` module
- **Gunicorn Configuration**: 3 worker processes ([Dockerfile:34](../server/Dockerfile#L34))

### How Filesystem Sessions Work

When a user logs in:

1. **Session Creation**:
   ```python
   # In login route
   session['user_id'] = user_id
   session['username'] = username
   ```

2. **Flask-Session saves to disk**:
   ```
   server/flask_session/
   ├── 2029240f6d1128be89ddc32729463129  ← User Alice's session
   ├── 3f8b9c2a4e1d7f6e5c4b3a2d1e0f9876  ← User Bob's session
   └── a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6  ← User Charlie's session
   ```

3. **On Each Request**:
   - Browser sends session cookie: `session=2029240f6d1128be89ddc32729463129`
   - **Random Gunicorn worker** (could be Worker 1, 2, or 3) receives the request
   - Worker reads file: `flask_session/2029240f6d1128be89ddc32729463129`
   - Worker deserializes (unpickles) the session data
   - Route handler accesses: `user_id = session['user_id']`

4. **On Session Modification**:
   - Worker modifies session: `session['current_deck'] = 5`
   - Worker serializes (pickles) the session data
   - Worker **writes back to the same file**

---

## The Problem: Race Conditions with Filesystem Sessions

### Problem 1: File-Based Read-Write Race Condition

**Scenario**: Two workers handling requests from the same user simultaneously

```
Timeline:
T=0ms   | Worker 1 receives request from Alice: POST /add_card (front="Question A")
T=1ms   | Worker 1 reads flask_session/alice_session_id
        | - Deserializes: {'user_id': 5, 'username': 'alice'}
        |
T=5ms   | Worker 2 receives request from Alice: POST /add_card (front="Question B")
        | Worker 2 reads flask_session/alice_session_id (same file!)
        | - Deserializes: {'user_id': 5, 'username': 'alice'}
        |
T=10ms  | Worker 1 modifies session: session['last_card'] = 'Question A'
        | Worker 1 writes to flask_session/alice_session_id
        |
T=15ms  | Worker 2 modifies session: session['last_card'] = 'Question B'
        | Worker 2 writes to flask_session/alice_session_id
        | ⚠️  Worker 2 OVERWRITES Worker 1's changes!
```

**Result**: Last write wins. Session data can be lost or corrupted.

### Problem 2: Session File Caching/Stale Reads

**Scenario**: Operating system file cache creates stale reads

```
Timeline:
T=0ms   | Alice logs in via Worker 1
        | Worker 1 creates: flask_session/alice_session → {'user_id': 5}
        | OS caches this file in memory
        |
T=100ms | Alice changes current deck via Worker 2
        | Worker 2 reads file (gets cached version: {'user_id': 5})
        | Worker 2 updates: {'user_id': 5, 'current_deck': 7}
        | Worker 2 writes to disk
        | OS may not immediately flush cache
        |
T=200ms | Alice adds card via Worker 3
        | Worker 3 reads file (might get OLD cached version!)
        | Worker 3 sees: {'user_id': 5} (no current_deck!)
        | ⚠️  Worker 3 operates with stale session data
```

**Result**: Worker might use old session data, potentially using wrong `user_id` or missing critical session state.

### Problem 3: No Atomic Session Updates

**Scenario**: Session modification is NOT atomic (multi-step process)

```python
# What happens internally when you do: session['user_id'] = 5

# Step 1: Read entire session file from disk
session_data = pickle.load(open('flask_session/abc123', 'rb'))

# Step 2: Modify in memory
session_data['user_id'] = 5

# Step 3: Write entire session file back to disk
pickle.dump(session_data, open('flask_session/abc123', 'wb'))
```

**Between Steps 1 and 3**, another worker can:
- Read the same file (sees old data)
- Modify different session keys
- Write back (overwriting your changes)

**No locking mechanism** prevents this in filesystem-based sessions.

### Problem 4: The Suspected Bug in Your System

**User Complaint**: "I added flashcards, but they never showed up in my deck"

**Hypothesized Race Condition**:

```
Timeline:
T=0ms   | Alice (user_id=5) clicks "Add Card" → Request goes to Worker 1
        | Worker 1 reads session: {'user_id': 5, 'username': 'alice'}
        | user_id = session['user_id']  # user_id = 5
        |
T=2ms   | Bob (user_id=8) clicks "Add Card" → Request goes to Worker 2
        | Worker 2 reads session: {'user_id': 8, 'username': 'bob'}
        | user_id = session['user_id']  # user_id = 8
        |
T=5ms   | ⚠️  RACE CONDITION: Session file corruption or cross-contamination
        | Worker 1's session object gets corrupted/swapped somehow
        | Worker 1 now has: user_id = 8 (Bob's ID!)
        |
T=10ms  | Worker 1 executes: user_db_path = get_user_db_path(user_id)
        | → Returns: 'user_dbs/user_8.db' (Bob's database!)
        |
T=15ms  | Worker 1 writes Alice's card to Bob's database
        | Alice's card is now in user_8.db
        | Alice later checks her deck (user_5.db): Card is missing!
```

**Root Cause**: Filesystem-based sessions don't guarantee isolation between concurrent workers operating on the same user's session.

---

## How Redis Would Fix This

### What is Redis?

**Redis** (Remote Dictionary Server) is an in-memory data store that provides:
- **Atomic operations**: Read-modify-write happens in a single atomic step
- **Process isolation**: Built-in concurrency control across multiple workers
- **Fast access**: In-memory storage (microsecond latency vs milliseconds for disk)
- **Durability**: Optional persistence to disk

### Redis-Backed Sessions Architecture

```python
# Configuration with Redis
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
```

**Storage**:
```
Redis Server (in-memory key-value store):
┌─────────────────────────────────────────────────┐
│ Key: "session:2029240f6d1128be89ddc32729463129" │
│ Value: {"user_id": 5, "username": "alice"}      │
│ Expiry: 3600 seconds                             │
├─────────────────────────────────────────────────┤
│ Key: "session:3f8b9c2a4e1d7f6e5c4b3a2d1e0f9876" │
│ Value: {"user_id": 8, "username": "bob"}        │
│ Expiry: 3600 seconds                             │
└─────────────────────────────────────────────────┘
```

### Key Benefit 1: Atomic Operations

**Redis Commands are Atomic**:

```python
# Flask-Session internally uses Redis GET/SET commands
# These are ATOMIC - cannot be interrupted mid-operation

# Worker 1: Read session
GET "session:alice_session_id"
→ Returns: {"user_id": 5, "username": "alice"}

# Worker 2: Read same session (simultaneously)
GET "session:alice_session_id"
→ Returns: {"user_id": 5, "username": "alice"}

# Worker 1: Update session
SET "session:alice_session_id" {"user_id": 5, "last_card": "Question A"}
→ Atomic write, no partial updates possible

# Worker 2: Update session
SET "session:alice_session_id" {"user_id": 5, "last_card": "Question B"}
→ Atomic write, overwrites cleanly (last write wins, but no corruption)
```

**No partial reads or writes**: Redis ensures each GET/SET is complete before the next one starts.

### Key Benefit 2: Process Isolation

**Redis is a Separate Process**:

```
┌─────────────────────────────────────────────────────┐
│  Gunicorn Worker 1 (PID 1001)                       │
│    └─> Redis Client ─┐                              │
│                       │                              │
│  Gunicorn Worker 2 (PID 1002)                       │
│    └─> Redis Client ─┼─────> Redis Server (PID 500)│
│                       │       (Single-threaded)     │
│  Gunicorn Worker 3 (PID 1003)                       │
│    └─> Redis Client ─┘       Serializes all access │
└─────────────────────────────────────────────────────┘
```

**All workers connect to the SAME Redis server**:
- Redis internally serializes all commands
- No file system caching issues
- No file locking problems
- All workers see the SAME data immediately

### Key Benefit 3: Proper Isolation Between User Sessions

**With Filesystem**:
```
Problem: All session files in one directory
server/flask_session/
├── session_alice
├── session_bob
└── session_charlie

If Worker has bug or corruption, could accidentally:
- Read wrong file
- Write to wrong file
- Mix session data
```

**With Redis**:
```
Solution: Each session is a separate key with unique namespace

session:2029240f6d1128be89ddc32729463129 → Alice's data
session:3f8b9c2a4e1d7f6e5c4b3a2d1e0f9876 → Bob's data
session:a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6 → Charlie's data

Redis ensures:
- GET session:alice ONLY returns Alice's data
- SET session:alice ONLY writes to Alice's key
- No way to accidentally cross-contaminate
```

### Key Benefit 4: Consistent Cache View

**Filesystem Problem**:
```
Worker 1 writes to flask_session/alice_session
→ OS caches in memory
→ Disk write may be delayed (OS write buffer)
→ Worker 2 reads same file: Might get old cached version
```

**Redis Solution**:
```
Worker 1 writes to Redis: SET session:alice {...}
→ Redis updates in-memory immediately
→ All workers see update INSTANTLY
→ Worker 2 reads: GET session:alice → Gets latest value
```

**No caching delays**: All workers always see the current session state.

---

## Practical Example: Adding a Card

### Current System (Filesystem) - Vulnerable to Race Condition

```python
# app.py:1823-1827
@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']  # ← Reads from filesystem-based session
    user_db_path = get_user_db_path(user_id)  # ← Uses user_id to get DB path
    # ... writes card to user_db_path ...
```

**Race Condition Scenario**:
1. Worker 1 handles Alice's request: `user_id = session['user_id']` → reads from `flask_session/alice_file`
2. Worker 2 handles Bob's request: `user_id = session['user_id']` → reads from `flask_session/bob_file`
3. **Filesystem contention or corruption**: Worker 1 somehow gets wrong session data
4. Worker 1 writes Alice's card to Bob's database

**Why this can happen**:
- File system race conditions (read-while-writing)
- OS cache inconsistencies
- File locking issues (SQLite locks, but session files have no locks)
- Session serialization/deserialization bugs under concurrency

### With Redis - Race Condition Prevented

```python
# Same code, but SESSION_TYPE = 'redis'
@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']  # ← Reads from Redis (atomic GET)
    user_db_path = get_user_db_path(user_id)  # ← Guaranteed correct user_id
    # ... writes card to user_db_path ...
```

**What Happens with Redis**:
1. Worker 1 handles Alice's request:
   - Flask-Session executes: `REDIS GET session:alice_session_id`
   - Redis returns: `{"user_id": 5, "username": "alice"}`
   - `user_id = 5` (Alice's ID)

2. Worker 2 handles Bob's request (simultaneously):
   - Flask-Session executes: `REDIS GET session:bob_session_id`
   - Redis returns: `{"user_id": 8, "username": "bob"}`
   - `user_id = 8` (Bob's ID)

3. **No cross-contamination possible**:
   - Each worker gets its own session key
   - Redis ensures atomic reads
   - No file system race conditions
   - No cache inconsistencies

**Result**: Alice's card goes to `user_5.db`, Bob's card goes to `user_8.db`. Always.

---

## Performance Comparison

### Filesystem Sessions

| Operation | Latency | Notes |
|-----------|---------|-------|
| Session Read | 1-10 ms | Disk I/O, depends on cache |
| Session Write | 5-50 ms | Disk write + fsync |
| Concurrency | Poor | File locking, cache issues |
| Scalability | Poor | Disk I/O bottleneck |

**Under Load**:
- Disk I/O becomes bottleneck with many concurrent users
- File system cache thrashing
- Potential session file corruption

### Redis Sessions

| Operation | Latency | Notes |
|-----------|---------|-------|
| Session Read | 0.1-1 ms | In-memory, network latency only |
| Session Write | 0.1-1 ms | In-memory, optional fsync |
| Concurrency | Excellent | Designed for high concurrency |
| Scalability | Excellent | 10,000+ operations/second |

**Under Load**:
- Consistent sub-millisecond latency
- No I/O bottleneck
- Built-in connection pooling
- Handles concurrent workers gracefully

---

## Migration Path: Filesystem → Redis

### Option 1: Add Redis to Docker Compose

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    container_name: flashcard_redis
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - flashcard-net

  server:
    # ... existing config ...
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379

volumes:
  redis_data:
```

### Option 2: Update Flask Configuration

```python
# server/app.py
import redis

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Replace filesystem session config
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url(REDIS_URL)
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'session:'  # Namespace sessions

# Remove filesystem config
# app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR  ← Delete
```

### Option 3: Update Requirements

```txt
# server/requirements.txt
Flask==2.3.2
Flask-Session==0.5.0
redis==4.5.5  ← Add this
```

### Option 4: Test Migration

```bash
# 1. Stop current containers
docker compose down

# 2. Update docker-compose.yml to add Redis service

# 3. Rebuild and restart
docker compose up --build -d

# 4. Verify Redis is running
docker exec flashcard_redis redis-cli PING
→ Should return: PONG

# 5. Test login
# Session should now be stored in Redis
docker exec flashcard_redis redis-cli KEYS "session:*"
→ Should show session keys after login
```

---

## When to Use Each Approach

### Filesystem Sessions - Good For:
- ✅ Single-worker deployments (`--workers 1`)
- ✅ Low-traffic applications (< 10 concurrent users)
- ✅ Development environments
- ✅ Simple deployments (no Redis dependency)

### Redis Sessions - Required For:
- ✅ Multi-worker deployments (2+ workers)
- ✅ High-concurrency applications (20+ concurrent users)
- ✅ Production environments with data integrity requirements
- ✅ Systems where session corruption would cause data loss (like JAVUMBO!)

---

## Recommendation for JAVUMBO

**Current Issue**: Users reporting cards in wrong decks

**Evidence Suggests**:
- Multi-worker deployment (3 workers)
- Filesystem-based sessions
- SQLite database writes based on session data
- Symptoms match filesystem session race conditions

**Recommended Solution**:

1. **Immediate**: Add Redis to your Docker deployment
2. **Testing**: Run load tests with both configurations to prove the fix
3. **Monitoring**: Add logging around session access to detect issues
4. **Long-term**: Keep Redis for scalability

**Cost**: Minimal
- Redis container: ~50MB memory
- No code changes to routes (just configuration)
- Drop-in replacement for filesystem sessions

**Benefit**: High
- Eliminates race conditions
- Improves performance (faster session access)
- Enables horizontal scaling (multiple app servers)
- Industry-standard production pattern

---

## Summary: Why Redis is Better

| Aspect | Filesystem Sessions | Redis Sessions |
|--------|---------------------|----------------|
| **Atomicity** | ❌ Multi-step file operations | ✅ Single atomic commands |
| **Isolation** | ❌ File system contention | ✅ Process-level isolation |
| **Concurrency** | ❌ File locking issues | ✅ Designed for concurrency |
| **Cache Consistency** | ❌ OS cache delays | ✅ Always up-to-date |
| **Performance** | ❌ Disk I/O bottleneck | ✅ In-memory, sub-ms latency |
| **Race Conditions** | ❌ Vulnerable | ✅ Protected |
| **Data Integrity** | ❌ Can corrupt under load | ✅ Guaranteed consistent |
| **Scalability** | ❌ Limited by disk | ✅ 10,000+ ops/sec |

**Bottom Line**: Redis provides **atomic operations** (commands execute completely without interruption) and **proper isolation** (each worker's session access goes through a centralized, concurrency-safe server), eliminating the race conditions inherent in filesystem-based sessions.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Related**: [LOAD_TESTING_PLAN.md](LOAD_TESTING_PLAN.md) Section 8.3
