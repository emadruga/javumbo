# Gunicorn Workers: Processes vs Threads and Race Condition Implications

## Executive Summary

**Answer**: Gunicorn workers are **PROCESSES** by default, not threads. Counter-intuitively, **this makes the race condition WORSE** for filesystem-based sessions, not better.

---

## 1. Gunicorn Worker Models

### 1.1 Your Current Configuration

From [server/Dockerfile:34](../server/Dockerfile#L34):
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "app:app"]
```

**What this means**:
- `--workers 3` creates **3 separate OS processes**
- Default worker class: `sync` (synchronous workers = processes)
- Each process runs a complete copy of your Flask application
- Each process has its own memory space (isolated from other workers)

### 1.2 Available Gunicorn Worker Types

Gunicorn supports multiple worker types:

| Worker Type | Implementation | Concurrency Model | Use Case |
|-------------|----------------|-------------------|----------|
| **sync** (default) | **Processes** | Blocking I/O | CPU-bound tasks, our case |
| **gthread** | Processes + Threads | Multi-threaded | I/O-bound tasks |
| **gevent** | Processes + Greenlets | Asynchronous | High concurrency |
| **eventlet** | Processes + Greenlets | Asynchronous | WebSockets, long-polling |

**Your configuration uses `sync` (default)** = **Multi-process workers**

---

## 2. Process-Based Workers: How They Work

### 2.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Gunicorn Master Process                   │
│                         (PID 100)                            │
│  - Manages worker lifecycle                                  │
│  - Binds to port 0.0.0.0:8000                               │
│  - Distributes incoming requests to workers                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  Worker 1 │  │  Worker 2 │  │  Worker 3 │
│ (PID 101) │  │ (PID 102) │  │ (PID 103) │
├───────────┤  ├───────────┤  ├───────────┤
│ Flask App │  │ Flask App │  │ Flask App │
│ Copy #1   │  │ Copy #2   │  │ Copy #3   │
├───────────┤  ├───────────┤  ├───────────┤
│ Memory:   │  │ Memory:   │  │ Memory:   │
│ - app.py  │  │ - app.py  │  │ - app.py  │
│ - session │  │ - session │  │ - session │
│ - globals │  │ - globals │  │ - globals │
└───────────┘  └───────────┘  └───────────┘
     │              │              │
     └──────────────┼──────────────┘
                    │
                    ▼
        ┌─────────────────────┐
        │   Shared Resources  │
        │  - Filesystem       │
        │  - SQLite files     │
        │  - Session files    │
        └─────────────────────┘
```

### 2.2 Key Characteristics of Process-Based Workers

**Process Isolation**:
- Each worker is a **separate operating system process**
- Created using Python's `os.fork()` (on Unix systems)
- **Completely separate memory spaces**
- **Cannot share variables or Python objects** between workers
- Communication only through shared external resources (files, databases, network)

**Process Creation (when Gunicorn starts)**:
```python
# Simplified view of what Gunicorn does internally

# Master process
master_pid = os.getpid()  # e.g., PID 100

# Fork worker processes
for i in range(3):  # --workers 3
    worker_pid = os.fork()
    if worker_pid == 0:
        # Child process (worker)
        # Load Flask app
        from app import app
        # Handle requests in a loop
        while True:
            request = wait_for_request()
            response = app(request)
            send_response(response)
    else:
        # Parent process (master)
        workers.append(worker_pid)
```

---

## 3. Processes vs Threads: What's the Difference?

### 3.1 Threads (NOT what Gunicorn uses by default)

**Threads within a single process**:
```
┌────────────────────────────────────────┐
│         Single Process (PID 100)       │
│                                        │
│  ┌────────┐  ┌────────┐  ┌────────┐  │
│  │Thread 1│  │Thread 2│  │Thread 3│  │
│  └────┬───┘  └────┬───┘  └────┬───┘  │
│       └───────────┼───────────┘       │
│                   │                   │
│         SHARED MEMORY SPACE           │
│  ┌────────────────────────────────┐  │
│  │ - Global variables             │  │
│  │ - Flask app instance           │  │
│  │ - Session objects              │  │
│  │ ALL THREADS SEE SAME MEMORY    │  │
│  └────────────────────────────────┘  │
└────────────────────────────────────────┘
```

**Thread Characteristics**:
- ✅ Share memory space (can access same variables)
- ✅ Lightweight (context switch ~microseconds)
- ✅ Low memory overhead
- ❌ Python GIL (Global Interpreter Lock) limits parallelism
- ❌ Race conditions on shared variables (need locks)

### 3.2 Processes (what Gunicorn DOES use)

**Separate processes**:
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Process 1       │  │ Process 2       │  │ Process 3       │
│ (PID 101)       │  │ (PID 102)       │  │ (PID 103)       │
│                 │  │                 │  │                 │
│ ISOLATED MEMORY │  │ ISOLATED MEMORY │  │ ISOLATED MEMORY │
│ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │
│ │ Flask app   │ │  │ │ Flask app   │ │  │ │ Flask app   │ │
│ │ Variables   │ │  │ │ Variables   │ │  │ │ Variables   │ │
│ │ Session obj │ │  │ │ Session obj │ │  │ │ Session obj │ │
│ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │
│                 │  │                 │  │                 │
│ CANNOT ACCESS   │  │ CANNOT ACCESS   │  │ CANNOT ACCESS   │
│ OTHER PROCESSES │  │ OTHER PROCESSES │  │ OTHER PROCESSES │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                  MUST USE EXTERNAL STORAGE
                  (files, database, Redis)
```

**Process Characteristics**:
- ✅ Complete isolation (one crash doesn't affect others)
- ✅ No Python GIL (true parallelism on multi-core CPUs)
- ✅ More stable (memory leaks contained to one process)
- ❌ Cannot share memory (need external storage)
- ❌ Higher memory overhead (each process = full app copy)
- ❌ Context switch slower (~milliseconds)

---

## 4. Why Processes Make Filesystem Session Race Conditions WORSE

### 4.1 The Paradox

**Intuition**: "Separate processes = isolated = safer from race conditions, right?"

**Reality**: **NO!** Separate processes are **MORE prone** to race conditions on **shared external resources** like files.

### 4.2 Why Processes Worsen File-Based Race Conditions

**Reason 1: No Built-In Synchronization**

With **threads** in a single process:
```python
# Threads can use Python locks
import threading

session_lock = threading.Lock()

# Thread 1
with session_lock:
    session['user_id'] = 5

# Thread 2
with session_lock:  # Waits for Thread 1 to release lock
    session['user_id'] = 8
```
- Python's `threading.Lock()` **works** because threads share memory
- Lock exists in shared memory space
- Threads can coordinate

With **processes**:
```python
# Processes CANNOT use threading.Lock()
import threading

session_lock = threading.Lock()  # ← Lives in Process 1's memory

# Process 1
with session_lock:
    session['user_id'] = 5  # Lock acquired

# Process 2 (separate memory space)
with session_lock:  # ← This is a DIFFERENT lock object!
    session['user_id'] = 8  # Lock acquired (no coordination!)
```
- Each process has its **own copy** of `session_lock`
- Locks in different memory spaces **don't coordinate**
- Both processes think they have exclusive access

**Reason 2: Independent File System Cache**

Each process has its **own file system cache state**:

```
Timeline with Processes:
T=0ms   | Process 1: open('flask_session/alice', 'r')
        | - OS caches file in Process 1's buffer
        | - Reads: {'user_id': 5}
        |
T=5ms   | Process 2: open('flask_session/alice', 'r')
        | - OS caches file in Process 2's buffer (SEPARATE!)
        | - Reads: {'user_id': 5}
        |
T=10ms  | Process 1: Modifies session, writes back
        | - open('flask_session/alice', 'w')
        | - Writes: {'user_id': 5, 'current_deck': 7}
        | - Process 1's cache updated
        | - ⚠️  Process 2's cache STILL HAS OLD DATA
        |
T=15ms  | Process 2: Modifies session, writes back
        | - open('flask_session/alice', 'w')
        | - Writes: {'user_id': 5, 'last_login': '...'}
        | - ⚠️  OVERWRITES Process 1's changes!
        | - Lost: 'current_deck': 7
```

**With threads** (hypothetically):
- Threads share the same process
- Threads share the same file descriptor table
- OS can coordinate file access better
- **But Python still doesn't use locks on session files!**

**Reason 3: No Coordination on File Writes**

```python
# What Flask-Session does (simplified)

# Process 1
def save_session():
    data = pickle.dumps(session_data)
    with open(session_file, 'wb') as f:  # ← No inter-process lock!
        f.write(data)

# Process 2 (simultaneously)
def save_session():
    data = pickle.dumps(session_data)
    with open(session_file, 'wb') as f:  # ← Also no lock!
        f.write(data)  # ← RACE! Last write wins
```

**Key Point**: Flask-Session's filesystem backend does **NOT use `fcntl.flock()`** or other inter-process file locking.

### 4.3 Concrete Example: Adding Cards

**Scenario**: Alice adds a card, two processes handle it simultaneously

```python
# Your code: server/app.py:1826-1827
@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']  # ← THE CRITICAL LINE
    user_db_path = get_user_db_path(user_id)
```

**Timeline with Process Workers**:

```
T=0ms   | Alice clicks "Add Card" → Request A arrives
        | Gunicorn assigns to Process 1
        |
T=1ms   | Process 1: session['user_id']
        | - Flask-Session: open('flask_session/alice_session_id', 'rb')
        | - Read: {'user_id': 5, 'username': 'alice'}
        | - Process 1 now has: user_id = 5
        |
T=2ms   | Alice's browser retries (slow network) → Request B arrives
        | Gunicorn assigns to Process 2 (Process 1 is busy)
        |
T=3ms   | Process 2: session['user_id']
        | - Flask-Session: open('flask_session/alice_session_id', 'rb')
        | - Read: {'user_id': 5, 'username': 'alice'}
        | - Process 2 now has: user_id = 5
        |
T=10ms  | Process 1: Insert card into user_5.db
        | - Card ID: 1730847201234
        | - Success!
        |
T=12ms  | Process 2: Insert card into user_5.db
        | - Card ID: 1730847203456 (different timestamp)
        | - Success!
        |
        | ✅ Both cards in user_5.db (correct!)
```

**But what if there's a bug in session handling?**

```
T=0ms   | Alice clicks "Add Card" → Request arrives
        | Gunicorn assigns to Process 1
        |
T=1ms   | Process 1: session['user_id']
        | - Reads session file
        | - user_id = 5 (Alice)
        |
T=2ms   | Bob logs in on another browser → Updates session
        | Process 2 handles login
        | - Saves session: {'user_id': 8, 'username': 'bob'}
        |
T=3ms   | ⚠️  BUG: Flask-Session writes to WRONG file
        | OR: Session ID collision
        | OR: Race condition in session file naming
        | - Process 1's cached session file path gets corrupted
        |
T=10ms  | Process 1: user_db_path = get_user_db_path(user_id)
        | - user_id is now 8 (corrupted!) instead of 5
        | - Returns: 'user_dbs/user_8.db' (Bob's DB!)
        |
T=15ms  | Process 1: Inserts Alice's card into user_8.db
        | - Alice's card is now in Bob's database
        | - Alice later checks her deck: Card missing!
```

**Why processes make this worse**:
1. **No shared memory**: Process 1 can't see Process 2's memory changes
2. **No coordination**: No locks between processes on session files
3. **Independent caches**: Each process caches file paths, file handles separately
4. **Race on file writes**: Both processes can write to session files simultaneously

---

## 5. Would Threads Be Better?

### 5.1 Threading Worker Class

Gunicorn supports threaded workers:
```bash
gunicorn --workers 1 --threads 4 app:app
```

Or:
```bash
gunicorn --workers 2 --threads 2 app:app  # 2 processes × 2 threads = 4 concurrent handlers
```

### 5.2 Would Threads Reduce Race Conditions?

**Short Answer**: **Slightly**, but **not enough** to fix the problem.

**Analysis**:

**Benefit 1**: Shared memory in each process
```
Process 1 (PID 101)
├── Thread 1 ──┐
├── Thread 2 ──┼──> SHARED memory space
├── Thread 3 ──┘    - Can use threading.Lock()
```

**BUT**:
- Flask-Session **doesn't use locks** even with threads!
- Threads still read/write session **files** (external resource)
- File system race conditions **still exist**

**Benefit 2**: Fewer processes = less cache divergence
- 1 process with 4 threads: Single file cache
- 4 processes: 4 separate file caches

**BUT**:
- Still no guarantee of cache consistency
- OS can still serve stale cached file data

**Conclusion**: Threads **marginally reduce** the race condition risk, but **don't eliminate it**.

---

## 6. Real Solution: Redis (Process-Safe by Design)

### 6.1 Why Redis Works with Processes

**Redis is a separate server process** that ALL worker processes connect to:

```
┌────────────────────────────────────────────────────┐
│  Gunicorn Process 1 (PID 101)                      │
│    └─> Redis Client ───┐                           │
│                         │                           │
│  Gunicorn Process 2 (PID 102)                      │
│    └─> Redis Client ───┼────> Redis Server         │
│                         │      (PID 500)            │
│  Gunicorn Process 3 (PID 103)                      │
│    └─> Redis Client ───┘      - Single-threaded    │
│                                - Event loop         │
│                                - Serialized access  │
└────────────────────────────────────────────────────┘
```

**How Redis Provides Process-Safe Synchronization**:

1. **Network Protocol**: All processes communicate via TCP/Unix socket
2. **Atomic Commands**: Redis commands execute atomically (no interruption)
3. **Single-Threaded Event Loop**: Redis processes one command at a time
4. **Queue-Based**: If 3 processes send commands simultaneously, Redis queues them

**Example**:
```
T=0ms   | Process 1 sends: GET session:alice
        | Redis receives, executes, returns: {'user_id': 5}
        |
T=1ms   | Process 2 sends: GET session:alice (simultaneously)
        | Redis queues command (Process 1's command still executing)
        |
T=2ms   | Redis finishes Process 1's command
        | Redis now executes Process 2's command
        | Returns: {'user_id': 5}
        |
        | ✅ Both processes get consistent data
        | ✅ No file system race conditions
        | ✅ No cache inconsistencies
```

### 6.2 Redis Works Regardless of Worker Type

Redis works with:
- ✅ Process-based workers (`sync`)
- ✅ Thread-based workers (`gthread`)
- ✅ Async workers (`gevent`, `eventlet`)

**Reason**: Redis is **external** to all workers, provides its own synchronization.

---

## 7. SQLite: Similar Process Issues

### 7.1 Your User Databases

Each user has a SQLite database:
```
user_dbs/
├── user_5.db   (Alice)
├── user_8.db   (Bob)
└── user_12.db  (Charlie)
```

### 7.2 SQLite Handles Multi-Process Access

**Good News**: SQLite has **built-in file locking** for multi-process access!

```python
# Process 1
conn1 = sqlite3.connect('user_5.db')
conn1.execute("INSERT INTO cards ...")  # ← Acquires write lock

# Process 2 (simultaneously)
conn2 = sqlite3.connect('user_5.db')
conn2.execute("INSERT INTO cards ...")  # ← Waits for Process 1's lock to release
```

SQLite uses:
- **File-level locking** (`fcntl` on Unix, `LockFileEx` on Windows)
- **WAL mode** (Write-Ahead Logging) for better concurrency
- **Automatic retry** on lock contention

**Why This Works**:
- SQLite **explicitly designed** for multi-process access
- Uses OS-level file locks (all processes respect)
- Transactions ensure atomicity

### 7.3 So Why Do Cards End Up in Wrong Databases?

**The bug is NOT in SQLite locking**.

**The bug is in session management** → wrong `user_id` → wrong database path:

```python
# The vulnerable code path
user_id = session['user_id']  # ← Gets WRONG user_id due to session race
user_db_path = get_user_db_path(user_id)  # ← Returns wrong path
conn = sqlite3.connect(user_db_path)  # ← Opens wrong database
conn.execute("INSERT INTO cards ...")  # ← SQLite correctly writes to the opened DB
                                       #   But it's the WRONG database!
```

**Analogy**:
- SQLite is a secure safe with proper locks ✅
- But you're giving it the **wrong key** (wrong user_id) ❌
- SQLite correctly opens the safe you specified
- But you specified Bob's safe when you meant Alice's safe

---

## 8. Summary: Processes vs Threads and Race Conditions

### 8.1 Quick Comparison

| Aspect | Processes (Gunicorn default) | Threads (optional) |
|--------|------------------------------|-------------------|
| **Memory** | Isolated, separate | Shared within process |
| **Synchronization** | Requires external mechanisms | Can use Python locks |
| **File Access** | Independent caches per process | Shared cache (better) |
| **Flask-Session File Race** | ⚠️  **HIGH RISK** | ⚠️  **MEDIUM RISK** |
| **SQLite Safety** | ✅ Safe (SQLite handles it) | ✅ Safe (SQLite handles it) |
| **Session Bug Impact** | ❌ **WORSE** (no coordination) | ⚠️  **BETTER** (but not safe) |
| **Solution** | ✅ Use Redis | ✅ Use Redis |

### 8.2 Key Insights

1. **Processes are NOT safer for filesystem sessions**
   - Separate processes = no built-in coordination
   - Each process has independent file cache
   - Flask-Session doesn't use inter-process locks

2. **Threads would be slightly better**
   - Shared memory enables potential coordination
   - But Flask-Session still doesn't use locks
   - Still vulnerable to file system race conditions

3. **SQLite is NOT the problem**
   - SQLite handles multi-process access correctly
   - The bug is: wrong user_id → wrong database selected
   - Root cause: session data corruption/race condition

4. **Redis is the proper solution**
   - Works with both processes and threads
   - Provides atomic operations
   - External server = proper synchronization
   - Industry-standard for multi-worker deployments

### 8.3 Recommendation

**Keep process-based workers** (`--workers 3`):
- Better for CPU-bound tasks
- More stable (crashes isolated)
- True parallelism (no GIL)

**Fix the session race condition** with Redis:
- Add Redis to Docker Compose
- Change `SESSION_TYPE` to `'redis'`
- All worker processes will safely coordinate through Redis

**Result**: Process isolation + Redis synchronization = Safe, scalable, correct!

---

## 9. Testing the Hypothesis

### 9.1 Experiment 1: Single Worker

**Test**:
```dockerfile
# Temporarily change Dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:app"]
```

**Rebuild and deploy**:
```bash
docker compose build --no-cache
docker compose up -d
```

**Expected Result**:
- If race condition disappears → Confirms multi-process issue
- If race condition persists → Problem is elsewhere (but unlikely)

### 9.2 Experiment 2: Thread Workers

**Test**:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "3", "app:app"]
```

**Expected Result**:
- If race condition reduces → Confirms process isolation makes it worse
- Threads share memory → less file cache divergence

### 9.3 Experiment 3: Add Redis (Proper Fix)

**Test**: Follow migration instructions in [SESSION_ARCHITECTURE_ANALYSIS.md](SESSION_ARCHITECTURE_ANALYSIS.md)

**Expected Result**:
- Race condition completely eliminated
- Works with any worker configuration (processes or threads)

---

## 10. Final Answer to Your Question

**Q**: Are Gunicorn workers implemented as threads or processes in Python?

**A**: **Processes** (by default, with `--workers N` flag).

**Q**: Does this choice make Gunicorn workers more prone to race conditions?

**A**: **YES, absolutely!** Process-based workers are **MORE prone** to race conditions on **shared external resources** like filesystem-based sessions because:

1. **No shared memory** → Cannot use Python locks for coordination
2. **Independent file caches** → Each process caches files separately
3. **No built-in synchronization** → Flask-Session doesn't use inter-process file locks
4. **Cache divergence** → One process's file cache can become stale while another process writes

**The irony**: Processes provide **better isolation** (good for stability) but **worse coordination** (bad for shared resources).

**The solution**: Use **Redis** (or any proper external synchronization mechanism) that is **explicitly designed** for multi-process access.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Related Documents**:
- [SESSION_ARCHITECTURE_ANALYSIS.md](SESSION_ARCHITECTURE_ANALYSIS.md)
- [LOAD_TESTING_PLAN.md](LOAD_TESTING_PLAN.md)
