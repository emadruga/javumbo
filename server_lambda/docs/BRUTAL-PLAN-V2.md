# 🔥 THE BRUTAL 4-HOUR DAILY PLAN - V2 (REVISED)

**Revision Date**: 2025-01-20
**Changes**: Week 2 revised with DynamoDB session management instead of Redis ElastiCache

**IMPORTANT**: Before running any tests or AWS operations, activate the conda environment:
```bash
conda activate AWS_BILLING
```

This is a no-nonsense, test-driven daily plan for completing the serverless migration in 20 days with only 4 focused hours per day. Every day has clear success criteria. If you fail a test, you don't move forward. Period.

---

## Week 1: Proof of Concept or Die Trying (Days 1-5) ✅ COMPLETED

### Status: ALL TESTS PASSED ✅

**Achievements**:
- ✅ Terraform infrastructure deployed (20 AWS resources)
- ✅ S3SQLiteConnection working (513ms baseline, 320ms cached)
- ✅ Lambda container caching (98% hit rate, 2.41x speedup)
- ✅ Optimistic locking with ETags (zero data loss)
- ✅ DynamoDB user authentication working
- ✅ All tests passing and documented

**Final Metrics**:
- Cold request: 684ms
- Warm request: 330ms
- Cache hit rate: 98%
- Zero data corruption across 1000+ operations

**Documentation**: See `REFACTOR_WEEK_1.md` for detailed day-by-day breakdown.

---

## Week 2: Session-Based Caching with DynamoDB (Days 6-9)

### REVISED ARCHITECTURE: DynamoDB Sessions Instead of Redis

**Why the change?**
- **Cost**: $0.15/month vs $13/month for Redis ElastiCache (87x cheaper)
- **Simplicity**: No VPC, no new infrastructure, no security groups
- **Reliability**: Multi-AZ replication built-in, 99.99% SLA
- **Performance**: 5-10ms DynamoDB latency vs 1-2ms Redis (negligible difference when S3 upload takes 340ms)

**The Problem Week 2 Solves**:
Current implementation uploads to S3 after EVERY operation (340ms overhead). If a user reviews 20 cards, that's 20 S3 uploads = 6.8 seconds of wasted time. Week 2 implements session-based caching to keep the DB in Lambda memory for the duration of a user session, uploading only once at session end.

---

### Day 6 (4 hours): DynamoDB Sessions + SessionManager

**Objective**: Create session management system using DynamoDB to coordinate which Lambda instance "owns" a user's database.

#### Hour 1: Create DynamoDB Sessions Table

**Terraform Update**: Add new DynamoDB table for session management.

**File**: `terraform/dynamodb.tf` (add to existing file)

```hcl
# Session management table
resource "aws_dynamodb_table" "javumbo_sessions" {
  name         = "javumbo-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "username"
    type = "S"
  }

  # TTL for automatic session cleanup
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # GSI for querying sessions by username
  global_secondary_index {
    name            = "username-index"
    hash_key        = "username"
    projection_type = "ALL"
  }

  tags = {
    Name        = "javumbo-sessions"
    Project     = "javumbo"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

**Session Item Structure**:
```json
{
  "session_id": "sess_abc123def456",
  "username": "john_doe",
  "lambda_instance_id": "i-1234567890abcdef0",
  "db_etag": "48fd9985f27f6661c21cd8e1a0fd65d4",
  "last_access": 1700000000,
  "expires_at": 1700000300,
  "status": "active"
}
```

**Deploy**:
```bash
cd terraform
terraform plan
terraform apply
```

**Update Lambda environment variables** in `terraform/lambda.tf`:
```hcl
environment {
  variables = {
    S3_BUCKET               = aws_s3_bucket.javumbo_user_dbs.id
    DYNAMODB_USERS_TABLE    = aws_dynamodb_table.javumbo_users.name
    DYNAMODB_LOCKS_TABLE    = aws_dynamodb_table.javumbo_user_locks.name
    DYNAMODB_SESSIONS_TABLE = aws_dynamodb_table.javumbo_sessions.name  # NEW
    SESSION_TTL             = "300"  # 5 minutes
  }
}
```

#### Hour 2: Implement SessionManager Class

**File Created**: `src/session_manager.py`

Core functionality:
- `create_session(username, lambda_id, db_etag)`: Atomic session creation with conflict detection
- `get_session(session_id)`: Retrieve session details
- `get_user_session(username)`: Find active session for user (if any)
- `update_session(session_id, db_etag)`: Extend TTL and update ETag
- `delete_session(session_id)`: Explicit session cleanup
- `cleanup_expired_sessions()`: Manual cleanup (DynamoDB TTL has lag)

**Key Feature**: Conditional writes prevent duplicate sessions:
```python
sessions_table.put_item(
    Item={...},
    ConditionExpression='attribute_not_exists(username)'  # Only if no active session
)
```

#### Hour 3: Implement SessionAwareS3SQLite Wrapper

**File Modified**: `src/s3_sqlite.py` (add new class)

```python
class SessionAwareS3SQLite:
    """
    Session-aware wrapper around S3SQLiteConnection.
    Keeps DB in memory for duration of user session.
    """

    def __init__(self, username, session_id=None):
        self.username = username
        self.session_id = session_id
        self.conn = None
        self.db_in_memory = False

    def __enter__(self):
        # 1. Verify/create session in DynamoDB
        # 2. Check if DB is cached in THIS Lambda instance
        # 3. Download from S3 only if needed
        # 4. Open SQLite connection
        # 5. Return connection
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        # DO NOT UPLOAD TO S3 HERE!
        # Just close SQLite connection
        # Upload happens only when session ends explicitly
        pass
```

**Critical Design Decision**: The `__exit__` method does NOT upload to S3. This is the KEY optimization. Uploads happen only when:
1. Session expires (5 min TTL)
2. User explicitly ends session (e.g., exits review mode)
3. Lambda is shutting down (via Lambda extension)

#### Hour 4: Write Test 6.1 - Session Creation and Reuse

**File Created**: `tests/test_session_manager.py`

**Test Flow**:
1. Clean up any existing sessions for test user
2. Create new session, verify returned session_id
3. Retrieve session, verify all fields (username, lambda_id, etag)
4. Update session with new ETag, verify update
5. Try to create duplicate session (should fail)
6. Delete session, verify deletion

**Success Criteria**:
- ✅ Can create session in DynamoDB
- ✅ Can retrieve session by session_id
- ✅ Can update session ETag and TTL
- ✅ Duplicate session creation prevented (conditional write)
- ✅ Can delete session cleanly

---

### Day 7 (4 hours): Flask Route Refactoring for Sessions

**Objective**: Update Flask routes to use session-aware connections, minimizing S3 uploads.

#### Hour 1: Create `@with_user_db` Decorator

**File Modified**: `src/app.py` (or new file `src/decorators.py`)

```python
from functools import wraps
from flask import g, request
from flask_jwt_extended import get_jwt_identity
from s3_sqlite import SessionAwareS3SQLite

def with_user_db(f):
    """
    Decorator that provides session-aware database connection.

    Reads session_id from request header (X-Session-ID).
    If no session_id provided, creates new session.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        username = get_jwt_identity()
        session_id = request.headers.get('X-Session-ID')

        with SessionAwareS3SQLite(username, session_id) as conn:
            g.db = conn
            g.session_id = session_id  # Pass session_id to response
            return f(*args, **kwargs)

    return decorated
```

**Usage**:
```python
@app.route('/api/decks', methods=['GET'])
@jwt_required()
@with_user_db
def get_decks():
    # g.db is now available, connected to user's database
    cursor = g.db.execute("SELECT * FROM col")
    # ...
```

#### Hour 2: Refactor Review Routes (Highest Traffic)

**Routes to update**:
- `GET /api/review/<deck_id>` - Get cards for review
- `POST /api/review` - Submit review rating

**Before**:
```python
@app.route('/api/review', methods=['POST'])
def submit_review():
    username = session['username']
    with S3SQLiteConnection(username) as conn:  # Download + Upload EVERY TIME
        # ... update card ...
    return jsonify({'success': True})
```

**After**:
```python
@app.route('/api/review', methods=['POST'])
@jwt_required()
@with_user_db
def submit_review():
    # g.db already connected, NO upload until session ends
    card_id = request.json['card_id']
    rating = request.json['rating']

    # Update card using g.db
    g.db.execute("UPDATE cards SET ... WHERE id = ?", (card_id,))

    # Return session_id to client so it can reuse
    return jsonify({
        'success': True,
        'session_id': g.session_id
    })
```

#### Hour 3: Refactor Deck/Card Management Routes

**Routes to update**:
- `GET /api/decks` - List decks
- `POST /api/decks` - Create deck
- `GET /api/cards` - List cards in deck
- `POST /api/cards` - Add card to deck

**Pattern**: Replace all `with S3SQLiteConnection(username) as conn:` with `@with_user_db` decorator.

#### Hour 4: Session Lifecycle Endpoints

**New endpoints for explicit session control**:

```python
@app.route('/api/session/start', methods=['POST'])
@jwt_required()
def start_session():
    """
    Explicitly start a session (optional - automatic if not provided).
    Returns session_id to client.
    """
    username = get_jwt_identity()
    # Create session...
    return jsonify({'session_id': session_id})

@app.route('/api/session/flush', methods=['POST'])
@jwt_required()
def flush_session():
    """
    Force upload to S3 and end session.
    Called when user exits review mode or after 20 cards.
    """
    username = get_jwt_identity()
    session_id = request.json['session_id']

    # 1. Download DB from /tmp
    # 2. Upload to S3
    # 3. Delete session from DynamoDB

    return jsonify({'success': True})

@app.route('/api/session/status', methods=['GET'])
@jwt_required()
def session_status():
    """
    Check if user has active session.
    """
    username = get_jwt_identity()
    session = SessionManager.get_user_session(username)

    return jsonify({
        'has_session': session is not None,
        'session_id': session['session_id'] if session else None
    })
```

**Success Criteria**:
- ✅ All existing unit tests pass (no breaking changes)
- ✅ Review session: 20 operations = 1 S3 download + 1 S3 upload (not 20 of each)
- ✅ Session endpoints return valid session_ids
- ✅ Decorator correctly attaches `g.db` to request context

---

### Day 8 (4 hours): Frontend Session Management

**Objective**: Update React app to use sessions efficiently, batching operations.

#### Hour 1: Create `useDBSession` Hook

**File Created**: `client_lambda/src/hooks/useDBSession.js`

```javascript
import { useState, useCallback, useEffect } from 'react';
import axios from 'axios';

export const useDBSession = () => {
  const [sessionId, setSessionId] = useState(null);
  const [isActive, setIsActive] = useState(false);

  const startSession = useCallback(async () => {
    try {
      const response = await axios.post('/api/session/start');
      setSessionId(response.data.session_id);
      setIsActive(true);
      return response.data.session_id;
    } catch (error) {
      console.error('Failed to start session:', error);
      return null;
    }
  }, []);

  const endSession = useCallback(async () => {
    if (!sessionId) return;

    try {
      await axios.post('/api/session/flush', { session_id: sessionId });
      setSessionId(null);
      setIsActive(false);
    } catch (error) {
      console.error('Failed to end session:', error);
    }
  }, [sessionId]);

  // Auto-flush after 5 minutes idle
  useEffect(() => {
    if (!isActive) return;

    const timeout = setTimeout(() => {
      console.log('Session idle timeout, flushing...');
      endSession();
    }, 5 * 60 * 1000);

    return () => clearTimeout(timeout);
  }, [isActive, endSession]);

  return { sessionId, isActive, startSession, endSession };
};
```

#### Hour 2: Update ReviewPage to Use Sessions

**File Modified**: `client_lambda/src/pages/ReviewPage.jsx`

```javascript
import { useDBSession } from '../hooks/useDBSession';

function ReviewPage() {
  const { sessionId, startSession, endSession } = useDBSession();
  const [cards, setCards] = useState([]);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);

  useEffect(() => {
    // Start session when entering review mode
    const initSession = async () => {
      const sid = await startSession();
      // Load cards with session_id
      const response = await axios.get(`/api/review/${deckId}`, {
        headers: { 'X-Session-ID': sid }
      });
      setCards(response.data.cards);
    };

    initSession();

    // Cleanup: End session when leaving review page
    return () => {
      endSession();
    };
  }, [deckId]);

  const submitReview = async (rating) => {
    await axios.post('/api/review',
      { card_id: cards[currentCardIndex].id, rating },
      { headers: { 'X-Session-ID': sessionId } }
    );

    // Move to next card
    setCurrentCardIndex(prev => prev + 1);

    // End session after 20 cards or at end
    if (currentCardIndex >= 19 || currentCardIndex >= cards.length - 1) {
      await endSession();
    }
  };

  // ... rest of component
}
```

#### Hour 3: Add Session Indicators to UI

**Visual feedback for users**:

```javascript
function SessionIndicator({ isActive }) {
  if (!isActive) return null;

  return (
    <div className="session-indicator">
      <span className="status-dot active"></span>
      <span>Session active (changes will be saved on exit)</span>
    </div>
  );
}
```

**Warn before leaving with unsaved changes**:
```javascript
useEffect(() => {
  if (!isActive) return;

  const handleBeforeUnload = (e) => {
    e.preventDefault();
    e.returnValue = 'You have an active session. Changes will be saved when you close this tab.';
  };

  window.addEventListener('beforeunload', handleBeforeUnload);
  return () => window.removeEventListener('beforeunload', handleBeforeUnload);
}, [isActive]);
```

#### Hour 4: Test End-to-End Flow

**Manual Testing Checklist**:
1. Open app, navigate to review page
2. Verify session starts automatically (check DevTools network tab for session_id)
3. Review 5 cards, check that X-Session-ID header is sent
4. Check CloudWatch: Verify only 1 S3 download at start
5. Complete review session or exit page
6. Verify `/api/session/flush` called
7. Check CloudWatch: Verify S3 upload happened on flush
8. Re-enter review page, verify new session created

**Success Criteria**:
- ✅ Session starts automatically on review page
- ✅ Session ID included in all API requests
- ✅ First card review: ~500ms (cold), next cards: ~100ms (warm)
- ✅ Session ends on page exit or after 20 cards
- ✅ Data persists after session end
- ✅ No data loss on session timeout

---

### Day 9 (4 hours): Production Deployment & Monitoring

**Objective**: Deploy to AWS, measure real-world performance, validate cost savings.

#### Hour 1: Update Lambda Deployment Package

**Build deployment package**:
```bash
cd server_lambda/src

# Install dependencies
pip install -r ../requirements.txt -t package/
pip install awsgi -t package/

# Copy application code
cp -r *.py package/

# Create zip
cd package
zip -r ../lambda_deployment.zip .
cd ..
zip -g lambda_deployment.zip lambda_handler.py

# Deploy
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://lambda_deployment.zip
```

**Update Lambda configuration**:
```bash
aws lambda update-function-configuration \
  --function-name javumbo-api \
  --environment Variables="{
    S3_BUCKET=javumbo-user-dbs-509324282531,
    DYNAMODB_USERS_TABLE=javumbo-users,
    DYNAMODB_SESSIONS_TABLE=javumbo-sessions,
    SESSION_TTL=300
  }"
```

#### Hour 2: Create CloudWatch Dashboard

**Metrics to track**:
- Lambda invocations (count)
- Lambda duration (avg, p50, p95, p99)
- Lambda errors (count, rate)
- S3 GET/PUT requests (count - should be much lower)
- DynamoDB read/write capacity (sessions table)
- Session duration (custom metric)

**Create dashboard via Console or CLI**:
```bash
aws cloudwatch put-dashboard \
  --dashboard-name javumbo-serverless \
  --dashboard-body file://cloudwatch-dashboard.json
```

#### Hour 3: Load Testing with Real Sessions

**Simulate 10 users reviewing cards**:

**File Created**: `tests/load_test_sessions.py`

```python
import requests
import time
import concurrent.futures

API_URL = "https://leap8plbm6.execute-api.us-east-1.amazonaws.com"

def simulate_review_session(user_id):
    """Simulate one user reviewing 20 cards."""
    username = f"loadtest_user_{user_id}"

    # Login (get JWT token)
    response = requests.post(f"{API_URL}/login", json={
        'username': username,
        'password': 'testpass'
    })
    token = response.json()['token']
    headers = {'Authorization': f'Bearer {token}'}

    # Start session
    response = requests.post(f"{API_URL}/api/session/start", headers=headers)
    session_id = response.json()['session_id']
    headers['X-Session-ID'] = session_id

    # Review 20 cards
    start = time.time()
    for i in range(20):
        requests.post(f"{API_URL}/api/review",
            json={'card_id': i+1, 'rating': 3},
            headers=headers
        )
    duration = time.time() - start

    # End session
    requests.post(f"{API_URL}/api/session/flush",
        json={'session_id': session_id},
        headers=headers
    )

    return duration

# Run 10 concurrent users
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(simulate_review_session, i) for i in range(10)]
    results = [f.result() for f in futures]

print(f"Average session duration: {sum(results)/len(results):.2f}s")
print(f"Min: {min(results):.2f}s, Max: {max(results):.2f}s")
```

**Expected Results**:
- Session duration for 20 cards: 2-4 seconds (vs 10+ seconds without sessions)
- S3 GET requests: 10 (one per user session start)
- S3 PUT requests: 10 (one per user session end)
- Total operations: 200 card reviews, but only 20 S3 operations (90% reduction)

#### Hour 4: Document Week 2 Results

**Create**: `docs/REFACTOR_WEEK_2.md`

Document:
- Day 6: DynamoDB sessions implementation
- Day 7: Flask route refactoring
- Day 8: Frontend session management
- Day 9: Load testing results

**Key Metrics to Record**:
- S3 operations before vs after: ~200 → ~20 (90% reduction)
- Average review latency: 500ms → 100ms (80% improvement)
- Cost impact: Calculate DynamoDB session costs (~$0.15/month)
- User experience: Time to review 20 cards: 10s → 3s (70% faster)

**Success Criteria**:
- ✅ Deploy succeeds without errors
- ✅ Load test: 10 users, 20 cards each = 200 operations
- ✅ S3 operations: 20 total (10 GET + 10 PUT) - not 400
- ✅ p95 latency <200ms for warm requests
- ✅ No data loss under concurrent load
- ✅ Monthly cost increase: <$1 (DynamoDB sessions)

---

## Week 3: Flask Integration - Make It Real (Days 10-14)

### Day 10 (4 hours): Lambda Handler + Local Dev Mode

**Objective**: Wrap Flask app for Lambda while preserving local development.

**Hour 1**: Create `lambda_handler.py` with awsgi wrapper
**Hour 2**: Modify `app.py` to detect Lambda vs local mode
**Hour 3**: Test local mode still works (Test 10.1)
**Hour 4**: Deploy Lambda and test with simple `/health` endpoint

**Success Criteria**:
- ✅ Local development works unchanged
- ✅ Lambda returns 200 for `/health` endpoint via API Gateway

---

### Day 11 (4 hours): Authentication Refactor

**Objective**: Make authentication work in Lambda mode with JWT.

**Hour 1**: Install `flask-jwt-extended`, update `/login` endpoint
**Hour 2**: Update `/register` endpoint to use DynamoDB + S3SQLiteConnection
**Hour 3**: Write Test 11.1 (Lambda auth) and make it PASS
**Hour 4**: Test 11.2 (protected routes require JWT)

**Success Criteria**:
- ✅ Can register user via Lambda (stored in DynamoDB + S3)
- ✅ Can login and receive JWT token
- ✅ Protected routes require valid JWT

---

### Day 12 (4 hours): Core API Routes Migration (Part 1)

**Objective**: Migrate remaining deck/card endpoints to use SessionAwareS3SQLite.

**Hour 1-2**: Update `/api/decks` endpoints (GET, POST, PUT, DELETE)
**Hour 3**: Write Test 12.1 for deck operations
**Hour 4**: Deploy to Lambda and test manually

**Success Criteria**:
- ✅ Can list decks via API Gateway
- ✅ Can create/edit/delete deck (verified in S3)
- ✅ Test 12.1 passes

---

### Day 13 (4 hours): Statistics & Export Endpoints

**Objective**: Complete stats and export functionality in Lambda.

**Hour 1**: Update `/api/stats` endpoint
**Hour 2**: Update `/api/export` endpoint (binary response handling)
**Hour 3**: Test export - verify .anki2 file opens in Anki desktop
**Hour 4**: Write Test 13.1 (export validation)

**Success Criteria**:
- ✅ Statistics endpoint works correctly
- ✅ Export returns valid .anki2 file
- ✅ File opens in Anki desktop without errors

---

### Day 14 (4 hours): Frontend Integration

**Objective**: Update React frontend to work with Lambda backend.

**Hour 1**: Update React app to store JWT in localStorage
**Hour 2**: Configure axios to send Authorization header
**Hour 3**: Update `.env.production` with API Gateway URL, build and deploy to S3
**Hour 4**: Test end-to-end: frontend → API Gateway → Lambda

**Success Criteria**:
- ✅ Frontend can communicate with Lambda backend
- ✅ JWT authentication works end-to-end
- ✅ All features work (decks, cards, review, stats, export)

---

## Week 4: Polish & Production (Days 15-19)

### Day 15 (4 hours): Error Handling + Retry Logic

**Hour 1**: Add ConflictError handler to Flask app
**Hour 2**: Update frontend to retry on 409 conflicts
**Hour 3**: Test concurrent operations from multiple browser tabs
**Hour 4**: Stress test retry logic

**Success Criteria**:
- ✅ Users never see raw 409 errors
- ✅ Conflicts handled gracefully with automatic retry
- ✅ Multi-tab usage works without issues

---

### Day 16 (4 hours): Monitoring + Logging

**Hour 1**: Add structured logging to Lambda (JSON format)
**Hour 2**: Create CloudWatch dashboard with key metrics
**Hour 3**: Set up alarms for error rate >5%
**Hour 4**: Trigger errors intentionally and verify alarms fire

**Success Criteria**:
- ✅ Can detect and diagnose issues in CloudWatch
- ✅ Alarms trigger on error threshold
- ✅ Logs are structured and searchable

---

### Day 17 (4 hours): Data Migration Script

**Hour 1**: Code `migrate_to_serverless.py` - admin.db to DynamoDB
**Hour 2**: Code user database migration to S3
**Hour 3**: Run migration on TEST data (not production yet!)
**Hour 4**: Verify migration with Test 17.1

**Success Criteria**:
- ✅ Test migration succeeds with 100% data integrity
- ✅ All users in DynamoDB
- ✅ All databases in S3

---

### Day 18 (4 hours): End-to-End Testing

**Hour 1**: Register new user in Lambda environment
**Hour 2**: Create deck, add 10 cards, review 5 cards
**Hour 3**: Export deck and verify in Anki desktop
**Hour 4**: Have someone else test the app

**Success Criteria**:
- ✅ Full user workflow works without errors
- ✅ External tester can use app successfully
- ✅ Export opens in Anki desktop correctly

---

### Day 19 (4 hours): Production Cutover

**Hour 1**: Backup EVERYTHING
**Hour 2**: Run production migration script
**Hour 3**: Cutover - Update DNS/CloudFront to point to Lambda
**Hour 4**: Monitor for 1 hour

**ROLLBACK PLAN**: Revert frontend to old API URL

**Success Criteria**:
- ✅ Production running on serverless with <1% error rate
- ✅ Users can login and use app
- ✅ No data loss

---

## The BRUTAL Truth

**Critical Rules**:
1. **NO SKIPPING TESTS**: If a test fails, you don't move to next day. Period.
2. **NO SHORTCUTS**: Every test must pass before proceeding.
3. **BACKUP EVERYTHING**: Before production migration, backup twice.
4. **MONITOR OBSESSIVELY**: During cutover, watch CloudWatch like a hawk.
5. **ROLLBACK READY**: Have rollback plan and be prepared to execute in <5 minutes.

**Success Metrics** (by Day 19):
- ✅ 100% data integrity (zero data loss)
- ✅ <1% error rate in production
- ✅ <300ms average latency (warm requests)
- ✅ <$2/month costs for 100 users (DynamoDB sessions + existing)
- ✅ 90% reduction in S3 operations (sessions working)

**Now execute Week 2 Day 6 and report back.**
