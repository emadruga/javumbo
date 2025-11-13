# JAVUMBO Refactoring Plan: Serverless Migration

## Overview

This document outlines a comprehensive plan to migrate the JAVUMBO flashcard application from a traditional containerized architecture to a serverless architecture using AWS Lambda and S3.

### Current Architecture

The application currently runs as Docker containers that can be deployed via:
- **Docker Compose**: Local development and simple deployments
- **ECS/Fargate**: AWS container orchestration service

**Key characteristics:**
- Flask/Gunicorn backend running 24/7
- SQLite databases stored on local filesystem (or EFS in AWS)
- Predictable costs but pays for idle time
- Simple architecture with direct file access

### Proposed Serverless Architecture

The new architecture will use:
- **AWS Lambda**: Serverless compute (Flask with adapter)
- **API Gateway**: REST API endpoint management
- **DynamoDB**: User authentication data (admin.db replacement)
- **S3**: Per-user `.anki2` SQLite files (maintains Anki compatibility)
- **CloudFront**: CDN for React frontend

**Key benefits:**
- True pay-per-use pricing (no cost when idle)
- Automatic scaling to handle traffic spikes
- No server maintenance required
- Maintains Anki `.anki2` file compatibility
- 95%+ cost reduction for low-medium traffic

---

## Cost Comparison

### Monthly Cost Estimates (100 Users, ~32,500 API Requests)

| Architecture | Standard | Optimized | Performance | Setup Time |
|--------------|----------|-----------|-------------|------------|
| **ECS/Fargate** | $30.71 | $4.00 (Spot+No ALB) | 35ms latency | 3-5 days |
| **Serverless (Lambda+S3)** | $0.98 | FREE* (1st year) | 100-200ms latency | 2-3 weeks |

*With AWS Free Tier: Lambda (1M requests), API Gateway (1M requests), DynamoDB (25GB+200M requests), S3 (5GB), CloudFront (1TB transfer)

### Cost Breakdown: Serverless Architecture

| Component | Specifications | Monthly Cost |
|-----------|----------------|--------------|
| Lambda Compute | 32.5K requests × 300ms × 512MB | $0.16 |
| Lambda Requests | 32,500 requests | $0.07 |
| API Gateway | 32,500 requests | $0.11 |
| DynamoDB (Auth) | 32.5K reads + 200 writes | $0.08 |
| DynamoDB Storage | <1 GB (users table) | $0.25 |
| S3 Storage | 300 MB (user .anki2 files) | $0.007 |
| S3 GET Requests | 9,750 (with 70% cache hit) | $0.004 |
| S3 PUT Requests | 9,750 (with 70% cache hit) | $0.05 |
| CloudFront | 3 GB frontend transfer | $0.26 |
| CloudWatch Logs | ~100 MB logs | $0.05 |
| **TOTAL** | | **~$0.98/month** |

**Scaling costs:**
- 500 users (~160K requests): **~$4.50/month**
- 2,000 users (~650K requests): **~$17.55/month**
- 10,000 users (~3.25M requests): **~$87/month**

---

## ⚡ Technical Implications

### Architecture Pattern: S3 as SQLite Storage

The serverless approach uses a download-process-upload pattern for user databases:

```python
# Lambda function workflow for each API request

def handle_api_request(username, request_data):
    # 1. Download user's .anki2 file from S3 (50-200ms)
    s3.download_file(
        Bucket='javumbo-user-dbs',
        Key=f'user_dbs/{username}.anki2',
        Filename='/tmp/user.anki2'
    )

    # 2. Open SQLite connection locally (5-10ms)
    conn = sqlite3.connect('/tmp/user.anki2')

    # 3. Perform database operations (10-50ms - fast, local)
    # Your existing SQLite queries work unchanged!
    cursor = conn.execute("SELECT * FROM cards WHERE ...")

    # 4. Commit changes and close (5-10ms)
    conn.commit()
    conn.close()

    # 5. Upload modified file back to S3 (50-200ms)
    s3.upload_file(
        Filename='/tmp/user.anki2',
        Bucket='javumbo-user-dbs',
        Key=f'user_dbs/{username}.anki2'
    )

    # 6. Return response to client
    return response
```

### Key Technical Changes

1. **Database Access Layer**
   - **Before**: Direct SQLite file access via filesystem
   - **After**: S3 download → SQLite operations → S3 upload wrapper

2. **Session Management**
   - **Before**: Flask-Session with filesystem storage
   - **After**: DynamoDB-backed sessions or JWT tokens

3. **Admin Database (admin.db)**
   - **Before**: Single SQLite file with users table
   - **After**: DynamoDB table with user authentication data

4. **User Databases (*.anki2)**
   - **Before**: Filesystem at `server/user_dbs/<username>.anki2`
   - **After**: S3 bucket at `s3://javumbo-user-dbs/user_dbs/<username>.anki2`
   - **Important**: File format remains unchanged (Anki compatible!)

5. **Lambda Execution Environment**
   - **Ephemeral storage**: `/tmp` directory (512MB-10GB configurable)
   - **Stateless**: Each Lambda invocation is independent
   - **Warm/Cold starts**: Container reuse enables caching

---

## ❌ Challenges & Solutions

### Challenge 1: S3 Download/Upload Latency (100-400ms per request)

**Problem**: Every API request needs to download the user's database from S3, process it, and upload it back. This adds 100-400ms latency compared to direct file access.

**Impact**:
- Cold request: 330ms total (10ms auth + 200ms S3 download + 20ms processing + 100ms S3 upload)
- User spends 5-10 seconds per flashcard review
- Extra 300ms = only 3-6% of total interaction time

**Solutions**:

#### Solution 1A: Lambda Execution Context Caching (Recommended)
```python
# Cache DB in Lambda container memory between invocations
db_cache = {}  # Global variable persists across warm starts

def get_user_db(username):
    cache_key = username
    cache_ttl = 300  # 5 minutes

    if cache_key in db_cache:
        cached_entry = db_cache[cache_key]
        if time.time() - cached_entry['timestamp'] < cache_ttl:
            # Cache hit - no S3 download needed!
            return cached_entry['path']

    # Cache miss - download from S3
    local_path = f'/tmp/{username}.anki2'
    s3.download_file(BUCKET, f'user_dbs/{username}.anki2', local_path)

    db_cache[cache_key] = {
        'path': local_path,
        'timestamp': time.time()
    }
    return local_path
```

**Benefits**:
- 70-80% cache hit rate for warm Lambda containers
- Reduces average latency to 60-100ms
- Zero additional cost
- Simple implementation

**Risks**:
- Multiple Lambda instances might have stale cached versions
- **Mitigation**: Use ETag-based optimistic locking (see Challenge 2)

#### Solution 1B: ElastiCache (Redis) for Coordination
```python
# Use Redis to coordinate cache invalidation across Lambda instances
redis_client = redis.Redis(host='elasticache-endpoint')

def get_user_db(username):
    # Check Redis for current version
    current_version = redis_client.get(f'db_version:{username}')
    cached_version = db_cache.get(username, {}).get('version')

    if cached_version == current_version:
        # Cache is valid
        return db_cache[username]['path']

    # Download fresh version
    # ... download from S3 ...
    redis_client.set(f'db_version:{username}', s3_etag)
```

**Benefits**:
- Coordinated caching across all Lambda instances
- Prevents stale data issues
- ~1ms Redis latency vs 100ms S3

**Costs**: ~$13/month (cache.t4g.micro)

**When to use**: High traffic (>500 active users) where cache coordination is critical

#### Solution 1C: Lazy Upload (Only Upload if Modified)
```python
import hashlib

def __exit__(self, exc_type, exc_val, exc_tb):
    self.conn.close()

    # Calculate hash of current file
    with open(self.local_path, 'rb') as f:
        new_hash = hashlib.md5(f.read()).hexdigest()

    # Only upload if file actually changed
    if new_hash != self.original_hash:
        s3.upload_file(self.local_path, BUCKET, self.s3_key)
        return True  # Uploaded

    return False  # No upload needed (read-only operation)
```

**Benefits**:
- Saves 30-50% of S3 PUT operations
- Reduces costs and latency for read-only requests (deck browsing, statistics)

---

### Challenge 2: Concurrent Write Conflicts

**Problem**: Two Lambda instances might download the same user's database, modify it independently, and upload their changes. The second upload overwrites the first, causing data loss.

**Example scenario**:
```
Time    Lambda A                    Lambda B
T0      Downloads user.anki2 v1     -
T1      Reviews 5 cards             Downloads user.anki2 v1
T2      Uploads v2                  Adds new card
T3      -                           Uploads v3 (overwrites v2!)

Result: Lambda A's 5 reviews are LOST ❌
```

**Impact**:
- Low probability for typical usage (same user, multiple tabs, simultaneous operations)
- High severity when it occurs (data loss)

**Solutions**:

#### Solution 2A: S3 Optimistic Locking with ETags (Recommended)
```python
class S3SQLiteConnection:
    def __enter__(self):
        # Download with version info
        response = s3.get_object(
            Bucket=BUCKET,
            Key=self.s3_key
        )
        self.current_etag = response['ETag']

        # Save to /tmp
        with open(self.local_path, 'wb') as f:
            f.write(response['Body'].read())

        self.conn = sqlite3.connect(self.local_path)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()

        # Upload with conditional write
        try:
            with open(self.local_path, 'rb') as f:
                s3.put_object(
                    Bucket=BUCKET,
                    Key=self.s3_key,
                    Body=f,
                    # Only succeeds if file hasn't changed since download
                    IfMatch=self.current_etag
                )
        except ClientError as e:
            if e.response['Error']['Code'] == 'PreconditionFailed':
                # Conflict detected! Handle gracefully
                self._handle_conflict()
            else:
                raise

    def _handle_conflict(self):
        # Retry with exponential backoff
        # Or: Return error to client asking to retry
        raise ConflictError("Database was modified by another session. Please retry.")
```

**Benefits**:
- Detects conflicts reliably
- No additional AWS services needed
- Standard pattern for distributed systems
- Zero additional cost

**Drawback**: Client must handle retry logic

#### Solution 2B: DynamoDB Distributed Lock Table
```python
# More robust: acquire exclusive lock before accessing user DB

locks_table = dynamodb.Table('javumbo-user-locks')

class LockedS3SQLiteConnection:
    def __enter__(self):
        # Acquire lock (with timeout)
        self._acquire_lock(timeout=30)

        # Now safe to download and modify
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            # Always release lock
            self._release_lock()

    def _acquire_lock(self, timeout=30):
        lock_id = str(uuid.uuid4())
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                # Atomic conditional write
                locks_table.put_item(
                    Item={
                        'username': self.username,
                        'lock_id': lock_id,
                        'acquired_at': int(time.time()),
                        'ttl': int(time.time()) + 60  # Auto-expire
                    },
                    ConditionExpression='attribute_not_exists(username)'
                )
                self.lock_id = lock_id
                return  # Lock acquired!
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    # Lock held by another Lambda, wait and retry
                    time.sleep(0.1)
                else:
                    raise

        raise TimeoutError(f"Could not acquire lock for {self.username}")

    def _release_lock(self):
        locks_table.delete_item(
            Key={'username': self.username},
            ConditionExpression='lock_id = :id',
            ExpressionAttributeValues={':id': self.lock_id}
        )
```

**Benefits**:
- Prevents conflicts entirely (mutual exclusion)
- Automatic lock expiration prevents deadlocks
- Works across all Lambda instances

**Costs**: Minimal (~$0.10/month for 10K lock operations)

**When to use**: Critical data integrity requirements or users with multiple simultaneous sessions

---

### Challenge 3: Lambda /tmp Storage Limits

**Problem**: Lambda's `/tmp` directory has size limits:
- Default: 512 MB
- Maximum: 10,240 MB (10 GB)

If multiple users' databases are cached in `/tmp`, or if files are large, you might run out of space.

**Impact**:
- For 10 MB file limit: Can cache ~50 users in default 512 MB
- With 2 GB /tmp: Can cache ~200 users

**Solutions**:

#### Solution 3A: Increase Ephemeral Storage
```yaml
# Lambda configuration
EphemeralStorage:
  Size: 2048  # 2 GB
```

**Cost**: $0.0000000309 per GB-second
- 2 GB for 1 second = $0.000000062
- Negligible cost increase (~$0.20/month for 100K invocations)

#### Solution 3B: Aggressive Cache Cleanup
```python
def cleanup_old_files():
    """Remove stale files from /tmp before they accumulate"""
    tmp_files = glob.glob('/tmp/*.anki2')

    for filepath in tmp_files:
        # Remove files older than 5 minutes
        age = time.time() - os.path.getmtime(filepath)
        if age > 300:
            os.remove(filepath)

        # Or: Remove if /tmp usage exceeds 80%
        usage = shutil.disk_usage('/tmp')
        if usage.used / usage.total > 0.8:
            # Remove oldest files first
            oldest_file = min(tmp_files, key=os.path.getmtime)
            os.remove(oldest_file)
```

**Call this at the start of each Lambda invocation**

#### Solution 3C: Stream Processing for Read-Only Operations
```python
# For operations that don't modify the DB, don't download entire file
# Use S3 Select or HTTP range requests

def get_deck_count(username):
    # Download only the first 100KB (contains col table)
    response = s3.get_object(
        Bucket=BUCKET,
        Key=f'user_dbs/{username}.anki2',
        Range='bytes=0-102400'  # First 100KB only
    )

    # Parse partial SQLite file
    # (requires custom SQLite parsing - advanced technique)
```

**When to use**: Analytics, statistics, dashboard queries

---

### Challenge 4: Cold Start Performance

**Problem**: First Lambda invocation after idle period requires:
1. Initialize Python runtime (500-2000ms)
2. Import libraries (Flask, boto3, sqlite3) (200-500ms)
3. Download DB from S3 (100-400ms)
4. Open SQLite connection (50-100ms)

**Total cold start: 850-3000ms** (vs 35ms in ECS)

**Impact**:
- Affects first user after idle period (5+ minutes)
- ~5-10% of requests in low-traffic scenarios
- User perceives as "app is slow"

**Solutions**:

#### Solution 4A: Provisioned Concurrency (Recommended for Production)
```yaml
# Keep Lambda instances always warm
Lambda:
  ProvisionedConcurrentExecutions: 2
```

**Cost**: ~$24/month for 2 instances (512MB RAM)

**Benefits**:
- Eliminates cold starts for 95%+ of requests
- Predictable performance
- Worth it for production applications

**When to use**: Production environments, >50 active daily users

#### Solution 4B: Scheduled Warming Events
```python
# CloudWatch Events trigger Lambda every 5 minutes
# Keeps containers warm during business hours

def lambda_handler(event, context):
    # Check if this is a warming ping
    if event.get('source') == 'aws.events' and event.get('detail-type') == 'Scheduled Event':
        return {
            'statusCode': 200,
            'body': 'Warming ping received'
        }

    # Normal request handling
    return handle_api_request(event)
```

**Schedule in CloudWatch Events:**
```
Rate: 5 minutes
Target: javumbo-api Lambda function
Payload: {"source": "aws.events", "detail-type": "Scheduled Event"}
```

**Cost**: Nearly free (uses free tier Lambda invocations)

**Benefits**:
- Simple implementation
- Reduces cold starts by 80-90%

**Drawback**: Still occasional cold starts (less reliable than provisioned concurrency)

#### Solution 4C: Lazy Module Loading
```python
# Don't import heavy modules until needed
# Reduces initialization time

def lambda_handler(event, context):
    # Core imports only (fast)
    import json
    import time

    # Check auth first (fast path)
    if not is_authenticated(event):
        return {'statusCode': 401}

    # Only import heavy modules if request is valid
    import sqlite3  # Lazy load
    import boto3    # Lazy load

    # Process request
    return handle_request(event)
```

**Benefit**: Reduces cold start by 200-500ms (20-30% improvement)

#### Solution 4D: Optimize Deployment Package
```bash
# Reduce Lambda package size for faster cold starts

# 1. Use Lambda Layers for large dependencies
# Layer 1: Flask + dependencies (uploaded once, reused)
# Layer 2: boto3 (can use AWS-provided layer)

# 2. Remove unnecessary files
pip install --target ./package --no-deps flask
cd package
zip -r ../lambda.zip . -x "*.pyc" "*/tests/*" "*/docs/*"

# 3. Use Python 3.11+ (faster startup than 3.9)
```

**Benefit**: Reduces cold start by 100-300ms

---

### Challenge 5: Flask Application Adaptation

**Problem**: Flask apps expect long-running WSGI servers (Gunicorn), not serverless function handlers.

**Solution**: Use AWS Lambda adapter for Flask/WSGI applications

#### Approach: aws-wsgi Library
```python
# lambda_handler.py
import awsgi
from app import app  # Your existing Flask app

def lambda_handler(event, context):
    # Convert API Gateway event to WSGI request
    # Call Flask app
    # Convert Flask response to API Gateway response
    return awsgi.response(app, event, context)
```

**Installation**:
```bash
pip install aws-wsgi
```

**Benefits**:
- Minimal code changes to existing Flask app
- Preserves Flask routing, middleware, error handling
- Standard pattern (well-documented)

**Configuration needed**:
```python
# app.py modifications

# 1. Session management: Replace Flask-Session filesystem with DynamoDB
from flask_session import Session
from flask_session.dynamodb import DynamoDBSessionInterface

app.config['SESSION_TYPE'] = 'dynamodb'
app.config['SESSION_DYNAMODB_TABLE'] = 'javumbo-sessions'

# 2. Remove Gunicorn-specific code
# (no changes needed - Lambda handles this)

# 3. Environment variables for AWS resources
import os
S3_BUCKET = os.environ['S3_BUCKET_NAME']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE_NAME']
```

**Effort**: 1-2 days to adapt existing Flask application

---

### Challenge 6: Database Migration

**Problem**: Existing SQLite databases need to be migrated to new storage locations:
- `admin.db` → DynamoDB `users` table
- `user_dbs/*.anki2` → S3 bucket

**Solution**: One-time migration script

```python
# migrate_to_serverless.py
import sqlite3
import boto3
import os
from pathlib import Path

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# 1. Migrate admin.db to DynamoDB
def migrate_admin_db():
    users_table = dynamodb.Table('javumbo-users')

    conn = sqlite3.connect('server/admin.db')
    cursor = conn.execute('SELECT user_id, username, name, password_hash FROM users')

    with users_table.batch_writer() as batch:
        for row in cursor:
            batch.put_item(Item={
                'username': row[1],  # Partition key
                'user_id': row[0],
                'name': row[2],
                'password_hash': row[3]
            })

    conn.close()
    print(f"✓ Migrated admin.db to DynamoDB")

# 2. Migrate user databases to S3
def migrate_user_databases():
    user_dbs_path = Path('server/user_dbs')

    for db_file in user_dbs_path.glob('*.anki2'):
        username = db_file.stem  # filename without extension
        s3_key = f'user_dbs/{username}.anki2'

        s3.upload_file(
            Filename=str(db_file),
            Bucket='javumbo-user-dbs',
            Key=s3_key
        )
        print(f"✓ Migrated {username}.anki2 to S3")

# 3. Verify migration
def verify_migration():
    # Check DynamoDB
    users_table = dynamodb.Table('javumbo-users')
    response = users_table.scan(Select='COUNT')
    print(f"✓ DynamoDB users count: {response['Count']}")

    # Check S3
    response = s3.list_objects_v2(
        Bucket='javumbo-user-dbs',
        Prefix='user_dbs/'
    )
    print(f"✓ S3 user databases count: {response['KeyCount']}")

if __name__ == '__main__':
    migrate_admin_db()
    migrate_user_databases()
    verify_migration()
```

**Run once before cutover to serverless**

---

## 🚀 Recommended Implementation Plan

### Phase 1: Infrastructure Setup (Week 1)

**Objective**: Set up AWS infrastructure without touching application code.

#### Tasks:

1. **Create S3 Bucket for User Databases**
   ```bash
   aws s3 mb s3://javumbo-user-dbs
   aws s3api put-bucket-versioning \
     --bucket javumbo-user-dbs \
     --versioning-configuration Status=Enabled
   ```

2. **Create DynamoDB Tables**

   **Users table** (replaces admin.db):
   ```bash
   aws dynamodb create-table \
     --table-name javumbo-users \
     --attribute-definitions \
       AttributeName=username,AttributeType=S \
     --key-schema \
       AttributeName=username,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```

   **Lock table** (for concurrency control):
   ```bash
   aws dynamodb create-table \
     --table-name javumbo-user-locks \
     --attribute-definitions \
       AttributeName=username,AttributeType=S \
     --key-schema \
       AttributeName=username,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --time-to-live-specification \
       Enabled=true,AttributeName=ttl
   ```

3. **Create Lambda Execution Role**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject"
         ],
         "Resource": "arn:aws:s3:::javumbo-user-dbs/*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "dynamodb:GetItem",
           "dynamodb:PutItem",
           "dynamodb:UpdateItem",
           "dynamodb:DeleteItem",
           "dynamodb:Query",
           "dynamodb:Scan"
         ],
         "Resource": [
           "arn:aws:dynamodb:*:*:table/javumbo-users",
           "arn:aws:dynamodb:*:*:table/javumbo-user-locks"
         ]
       },
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents"
         ],
         "Resource": "arn:aws:logs:*:*:*"
       }
     ]
   }
   ```

4. **Create Lambda Function (Empty Placeholder)**
   ```bash
   aws lambda create-function \
     --function-name javumbo-api \
     --runtime python3.11 \
     --role arn:aws:iam::ACCOUNT_ID:role/javumbo-lambda-role \
     --handler lambda_handler.handler \
     --zip-file fileb://placeholder.zip \
     --memory-size 512 \
     --timeout 30 \
     --environment Variables="{S3_BUCKET=javumbo-user-dbs,DYNAMODB_TABLE=javumbo-users}"
   ```

5. **Create API Gateway**
   ```bash
   aws apigatewayv2 create-api \
     --name javumbo-api \
     --protocol-type HTTP \
     --target arn:aws:lambda:REGION:ACCOUNT_ID:function:javumbo-api
   ```

6. **Configure CloudFront for Frontend**
   - Create S3 bucket for frontend: `javumbo-frontend`
   - Create CloudFront distribution pointing to S3
   - Configure custom domain (optional)

#### Testing Phase 1:

**Test 1.1: S3 Bucket Access**
```bash
# Upload test file
echo "test" > test.anki2
aws s3 cp test.anki2 s3://javumbo-user-dbs/test/test.anki2

# Download test file
aws s3 cp s3://javumbo-user-dbs/test/test.anki2 downloaded.anki2

# Verify
diff test.anki2 downloaded.anki2
# Should show no differences

# Cleanup
aws s3 rm s3://javumbo-user-dbs/test/test.anki2
```
✅ **Pass criteria**: File uploads and downloads without errors

**Test 1.2: DynamoDB Table Operations**
```bash
# Write test user
aws dynamodb put-item \
  --table-name javumbo-users \
  --item '{
    "username": {"S": "testuser"},
    "user_id": {"N": "999"},
    "name": {"S": "Test User"},
    "password_hash": {"S": "test_hash"}
  }'

# Read test user
aws dynamodb get-item \
  --table-name javumbo-users \
  --key '{"username": {"S": "testuser"}}'

# Delete test user
aws dynamodb delete-item \
  --table-name javumbo-users \
  --key '{"username": {"S": "testuser"}}'
```
✅ **Pass criteria**: All DynamoDB operations succeed

**Test 1.3: Lambda Invocation**
```python
# test_lambda.py
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from Lambda!'
    }
```

```bash
# Package and deploy
zip test_lambda.zip test_lambda.py
aws lambda update-function-code \
  --function-name javumbo-api \
  --zip-file fileb://test_lambda.zip

# Invoke
aws lambda invoke \
  --function-name javumbo-api \
  --payload '{}' \
  response.json

cat response.json
# Should show: {"statusCode": 200, "body": "Hello from Lambda!"}
```
✅ **Pass criteria**: Lambda executes and returns expected response

**Test 1.4: API Gateway Integration**
```bash
# Get API Gateway URL
API_URL=$(aws apigatewayv2 get-apis \
  --query "Items[?Name=='javumbo-api'].ApiEndpoint" \
  --output text)

# Test endpoint
curl $API_URL
# Should return: Hello from Lambda!
```
✅ **Pass criteria**: API Gateway successfully proxies to Lambda

**Test 1.5: IAM Permissions**
```python
# test_permissions.py
import boto3

def handler(event, context):
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')

    # Test S3 write
    s3.put_object(
        Bucket='javumbo-user-dbs',
        Key='test/permissions.txt',
        Body=b'test'
    )

    # Test DynamoDB write
    table = dynamodb.Table('javumbo-users')
    table.put_item(Item={'username': 'permtest', 'user_id': 888})

    # Cleanup
    s3.delete_object(Bucket='javumbo-user-dbs', Key='test/permissions.txt')
    table.delete_item(Key={'username': 'permtest'})

    return {'statusCode': 200, 'body': 'All permissions OK'}
```
✅ **Pass criteria**: No permission errors

**Phase 1 Completion Checklist**:
- [ ] S3 bucket created with versioning enabled
- [ ] DynamoDB tables created (users + locks)
- [ ] Lambda function created with correct IAM role
- [ ] API Gateway configured and routing to Lambda
- [ ] All 5 tests pass
- [ ] Infrastructure documented (ARNs, endpoints, etc.)

---

### Phase 2: Core S3 SQLite Wrapper (Week 2)

**Objective**: Build the abstraction layer that handles S3 download/upload/caching without modifying existing Flask routes.

#### Tasks:

1. **Create S3SQLiteConnection Context Manager**

   Create `server/s3_sqlite.py`:
   ```python
   import boto3
   import sqlite3
   import os
   import time
   import hashlib
   from botocore.exceptions import ClientError

   s3 = boto3.client('s3')
   BUCKET = os.environ.get('S3_BUCKET', 'javumbo-user-dbs')

   # Global cache persists across Lambda warm starts
   db_cache = {}

   class S3SQLiteConnection:
       """Context manager for SQLite databases stored in S3"""

       def __init__(self, username, cache_enabled=True):
           self.username = username
           self.s3_key = f'user_dbs/{username}.anki2'
           self.local_path = f'/tmp/{username}.anki2'
           self.cache_enabled = cache_enabled
           self.conn = None
           self.original_hash = None
           self.current_etag = None

       def __enter__(self):
           # Check cache first
           if self.cache_enabled and self._check_cache():
               self.conn = sqlite3.connect(self.local_path)
               self.conn.row_factory = sqlite3.Row
               return self.conn

           # Download from S3
           self._download_from_s3()

           # Calculate hash for change detection
           with open(self.local_path, 'rb') as f:
               self.original_hash = hashlib.md5(f.read()).hexdigest()

           # Open connection
           self.conn = sqlite3.connect(self.local_path)
           self.conn.row_factory = sqlite3.Row

           # Update cache
           if self.cache_enabled:
               db_cache[self.username] = {
                   'timestamp': time.time(),
                   'etag': self.current_etag
               }

           return self.conn

       def __exit__(self, exc_type, exc_val, exc_tb):
           if self.conn:
               if exc_type is None:
                   self.conn.commit()
               self.conn.close()

           # Only upload if file changed
           if exc_type is None and self._file_changed():
               self._upload_to_s3()

           # Note: Don't delete from /tmp (keep for caching)

       def _check_cache(self):
           """Check if cached version is still valid"""
           if self.username not in db_cache:
               return False

           cached = db_cache[self.username]
           age = time.time() - cached['timestamp']

           # Cache valid for 5 minutes
           if age > 300:
               return False

           # Check if S3 version changed
           try:
               response = s3.head_object(Bucket=BUCKET, Key=self.s3_key)
               if response['ETag'] != cached['etag']:
                   return False
           except ClientError:
               return False

           # Cache is valid and file exists locally
           return os.path.exists(self.local_path)

       def _download_from_s3(self):
           """Download user database from S3"""
           try:
               response = s3.get_object(Bucket=BUCKET, Key=self.s3_key)
               self.current_etag = response['ETag']

               with open(self.local_path, 'wb') as f:
                   f.write(response['Body'].read())

           except s3.exceptions.NoSuchKey:
               # First time user - create new database
               self._create_new_database()
               self.current_etag = None

       def _create_new_database(self):
           """Create a new Anki-compatible database for new user"""
           # Import your existing new user DB creation logic
           from init_user_db import create_new_user_database
           create_new_user_database(self.local_path)

       def _file_changed(self):
           """Check if database was modified"""
           if not os.path.exists(self.local_path):
               return False

           with open(self.local_path, 'rb') as f:
               current_hash = hashlib.md5(f.read()).hexdigest()

           return current_hash != self.original_hash

       def _upload_to_s3(self):
           """Upload modified database back to S3 with optimistic locking"""
           try:
               with open(self.local_path, 'rb') as f:
                   if self.current_etag:
                       # Optimistic locking: only upload if version unchanged
                       s3.put_object(
                           Bucket=BUCKET,
                           Key=self.s3_key,
                           Body=f,
                           IfMatch=self.current_etag.strip('"')
                       )
                   else:
                       # New file, no lock needed
                       s3.put_object(
                           Bucket=BUCKET,
                           Key=self.s3_key,
                           Body=f
                       )

               # Invalidate cache (will be refreshed on next access)
               if self.username in db_cache:
                   del db_cache[self.username]

           except ClientError as e:
               if e.response['Error']['Code'] == 'PreconditionFailed':
                   # Conflict: file was modified by another request
                   raise ConflictError(
                       f"Database for {self.username} was modified "
                       f"by another session. Please retry your operation."
                   )
               else:
                   raise

   class ConflictError(Exception):
       """Raised when S3 optimistic lock fails"""
       pass
   ```

2. **Create DynamoDB User Repository**

   Create `server/dynamodb_users.py`:
   ```python
   import boto3
   import bcrypt
   import os
   from botocore.exceptions import ClientError

   dynamodb = boto3.resource('dynamodb')
   users_table = dynamodb.Table(os.environ.get('DYNAMODB_USERS_TABLE', 'javumbo-users'))

   class UserRepository:
       @staticmethod
       def create_user(username, name, password):
           """Create new user in DynamoDB"""
           password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

           try:
               users_table.put_item(
                   Item={
                       'username': username,
                       'name': name,
                       'password_hash': password_hash.decode('utf-8'),
                       'created_at': int(time.time())
                   },
                   ConditionExpression='attribute_not_exists(username)'
               )
               return True
           except ClientError as e:
               if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                   return False  # User already exists
               raise

       @staticmethod
       def get_user(username):
           """Get user from DynamoDB"""
           try:
               response = users_table.get_item(Key={'username': username})
               return response.get('Item')
           except ClientError:
               return None

       @staticmethod
       def verify_password(username, password):
           """Verify user password"""
           user = UserRepository.get_user(username)
           if not user:
               return False

           stored_hash = user['password_hash'].encode('utf-8')
           return bcrypt.checkpw(password.encode('utf-8'), stored_hash)

       @staticmethod
       def update_user(username, **kwargs):
           """Update user attributes"""
           update_expr = []
           expr_values = {}

           for key, value in kwargs.items():
               update_expr.append(f"{key} = :{key}")
               expr_values[f":{key}"] = value

           users_table.update_item(
               Key={'username': username},
               UpdateExpression='SET ' + ', '.join(update_expr),
               ExpressionAttributeValues=expr_values
           )
   ```

3. **Add Cleanup Utility**

   Add to `server/s3_sqlite.py`:
   ```python
   def cleanup_tmp_directory():
       """Remove old cached databases from /tmp"""
       import glob

       tmp_files = glob.glob('/tmp/*.anki2')
       current_time = time.time()

       for filepath in tmp_files:
           age = current_time - os.path.getmtime(filepath)

           # Remove files older than 10 minutes
           if age > 600:
               try:
                   os.remove(filepath)
               except OSError:
                   pass

       # Also check total /tmp usage
       usage = shutil.disk_usage('/tmp')
       if usage.used / usage.total > 0.8:
           # Over 80% full, remove oldest files
           files_by_age = sorted(tmp_files, key=os.path.getmtime)
           for filepath in files_by_age[:len(files_by_age)//2]:
               try:
                   os.remove(filepath)
               except OSError:
                   pass
   ```

#### Testing Phase 2:

**Test 2.1: S3SQLiteConnection - New User**
```python
# test_s3_sqlite_new_user.py
import os
os.environ['S3_BUCKET'] = 'javumbo-user-dbs'

from s3_sqlite import S3SQLiteConnection

def test_new_user():
    username = 'test_new_user_001'

    # Should create new DB
    with S3SQLiteConnection(username) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'col' in tables
        assert 'cards' in tables
        assert 'notes' in tables
        print(f"✓ New database created with tables: {tables}")

    # Verify uploaded to S3
    import boto3
    s3 = boto3.client('s3')
    response = s3.head_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/{username}.anki2')
    assert response['ResponseMetadata']['HTTPStatusCode'] == 200
    print(f"✓ Database uploaded to S3")

    # Cleanup
    s3.delete_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/{username}.anki2')

if __name__ == '__main__':
    test_new_user()
```
✅ **Pass criteria**: New database created and uploaded to S3

**Test 2.2: S3SQLiteConnection - Read/Write**
```python
# test_s3_sqlite_readwrite.py
import os
os.environ['S3_BUCKET'] = 'javumbo-user-dbs'

from s3_sqlite import S3SQLiteConnection

def test_read_write():
    username = 'test_readwrite_002'

    # First write
    with S3SQLiteConnection(username) as conn:
        conn.execute("INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (1, 'abc123', 1, 1000, -1, '', 'Test Front\x1fTest Back', 0, 0, 0, ''))
        print(f"✓ Inserted test note")

    # Second read (should use cache)
    with S3SQLiteConnection(username) as conn:
        cursor = conn.execute("SELECT flds FROM notes WHERE id = 1")
        row = cursor.fetchone()
        assert row is not None
        assert 'Test Front' in row[0]
        print(f"✓ Read test note: {row[0]}")

    # Cleanup
    import boto3
    s3 = boto3.client('s3')
    s3.delete_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/{username}.anki2')

if __name__ == '__main__':
    test_read_write()
```
✅ **Pass criteria**: Data persists across connections

**Test 2.3: Caching Behavior**
```python
# test_s3_sqlite_cache.py
import time
from s3_sqlite import S3SQLiteConnection

def test_caching():
    username = 'test_cache_003'

    # First access - should download from S3
    start = time.time()
    with S3SQLiteConnection(username) as conn:
        conn.execute("INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (1, 'cache', 1, 1000, -1, '', 'Cache Test', 0, 0, 0, ''))
    first_duration = time.time() - start
    print(f"First access (cold): {first_duration:.3f}s")

    # Second access - should use cache
    start = time.time()
    with S3SQLiteConnection(username) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM notes")
        count = cursor.fetchone()[0]
        assert count == 1
    second_duration = time.time() - start
    print(f"Second access (warm): {second_duration:.3f}s")

    # Cache should be significantly faster
    assert second_duration < first_duration * 0.5
    print(f"✓ Cache speedup: {first_duration/second_duration:.1f}x")

    # Cleanup
    import boto3
    s3 = boto3.client('s3')
    s3.delete_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/{username}.anki2')

if __name__ == '__main__':
    test_caching()
```
✅ **Pass criteria**: Cached access is 2x+ faster than cold access

**Test 2.4: Optimistic Locking (Conflict Detection)**
```python
# test_s3_sqlite_conflict.py
import os
import time
from s3_sqlite import S3SQLiteConnection, ConflictError

def test_conflict_detection():
    username = 'test_conflict_004'

    # Setup: Create initial database
    with S3SQLiteConnection(username) as conn:
        conn.execute("INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (1, 'conflict', 1, 1000, -1, '', 'Initial', 0, 0, 0, ''))

    # Simulate conflict: Two connections download same version
    conn1 = S3SQLiteConnection(username, cache_enabled=False)
    conn2 = S3SQLiteConnection(username, cache_enabled=False)

    db1 = conn1.__enter__()
    db2 = conn2.__enter__()

    # Both modify
    db1.execute("UPDATE notes SET flds = 'Modified by conn1' WHERE id = 1")
    db2.execute("UPDATE notes SET flds = 'Modified by conn2' WHERE id = 1")

    # First to exit succeeds
    conn1.__exit__(None, None, None)
    print(f"✓ First connection uploaded successfully")

    # Second should detect conflict
    try:
        conn2.__exit__(None, None, None)
        assert False, "Expected ConflictError"
    except ConflictError as e:
        print(f"✓ Conflict detected: {e}")

    # Cleanup
    import boto3
    s3 = boto3.client('s3')
    s3.delete_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/{username}.anki2')

if __name__ == '__main__':
    test_conflict_detection()
```
✅ **Pass criteria**: Concurrent write conflict is detected and raises ConflictError

**Test 2.5: DynamoDB User Repository**
```python
# test_dynamodb_users.py
import os
os.environ['DYNAMODB_USERS_TABLE'] = 'javumbo-users'

from dynamodb_users import UserRepository

def test_user_crud():
    # Create user
    success = UserRepository.create_user(
        username='testuser005',
        name='Test User',
        password='testpass123'
    )
    assert success
    print(f"✓ User created")

    # Duplicate should fail
    success = UserRepository.create_user(
        username='testuser005',
        name='Duplicate',
        password='pass'
    )
    assert not success
    print(f"✓ Duplicate username rejected")

    # Get user
    user = UserRepository.get_user('testuser005')
    assert user is not None
    assert user['name'] == 'Test User'
    print(f"✓ User retrieved: {user['name']}")

    # Verify password
    assert UserRepository.verify_password('testuser005', 'testpass123')
    assert not UserRepository.verify_password('testuser005', 'wrongpass')
    print(f"✓ Password verification works")

    # Update user
    UserRepository.update_user('testuser005', name='Updated Name')
    user = UserRepository.get_user('testuser005')
    assert user['name'] == 'Updated Name'
    print(f"✓ User updated")

    # Cleanup
    import boto3
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('javumbo-users')
    table.delete_item(Key={'username': 'testuser005'})

if __name__ == '__main__':
    test_user_crud()
```
✅ **Pass criteria**: All CRUD operations work correctly

**Test 2.6: /tmp Cleanup**
```python
# test_tmp_cleanup.py
import os
import time
from s3_sqlite import S3SQLiteConnection, cleanup_tmp_directory

def test_cleanup():
    # Create several cached databases
    for i in range(5):
        username = f'cleanup_test_{i:03d}'
        with S3SQLiteConnection(username) as conn:
            pass

    # Check files exist
    tmp_files = [f for f in os.listdir('/tmp') if f.endswith('.anki2')]
    print(f"Created {len(tmp_files)} temp files")

    # Modify timestamps to simulate old files
    for f in tmp_files[:3]:
        filepath = f'/tmp/{f}'
        # Set mtime to 15 minutes ago
        old_time = time.time() - 900
        os.utime(filepath, (old_time, old_time))

    # Run cleanup
    cleanup_tmp_directory()

    # Check old files removed
    remaining = [f for f in os.listdir('/tmp') if f.endswith('.anki2')]
    print(f"After cleanup: {len(remaining)} files remain")
    assert len(remaining) == 2
    print(f"✓ Old files cleaned up")

    # Cleanup
    for f in remaining:
        os.remove(f'/tmp/{f}')

    import boto3
    s3 = boto3.client('s3')
    for i in range(5):
        s3.delete_object(Bucket='javumbo-user-dbs', Key=f'user_dbs/cleanup_test_{i:03d}.anki2')

if __name__ == '__main__':
    test_cleanup()
```
✅ **Pass criteria**: Files older than threshold are removed

**Phase 2 Completion Checklist**:
- [ ] `S3SQLiteConnection` context manager implemented
- [ ] Caching with warm Lambda containers working
- [ ] Optimistic locking with ETags implemented
- [ ] `UserRepository` for DynamoDB users implemented
- [ ] /tmp cleanup utility implemented
- [ ] All 6 tests pass
- [ ] Code reviewed and documented

---

### Phase 3: Flask Application Integration (Week 3)

**Objective**: Adapt existing Flask routes to use the new S3SQLite wrapper and DynamoDB users.

#### Tasks:

1. **Create Lambda Handler Wrapper**

   Create `server/lambda_handler.py`:
   ```python
   import awsgi
   from app import app
   from s3_sqlite import cleanup_tmp_directory

   def handler(event, context):
       # Cleanup old cached files before processing request
       cleanup_tmp_directory()

       # Convert API Gateway event to WSGI and invoke Flask app
       return awsgi.response(app, event, context)
   ```

2. **Update Flask App Configuration**

   Modify `server/app.py`:
   ```python
   import os
   from flask import Flask
   from flask_cors import CORS

   app = Flask(__name__)
   CORS(app)

   # Detect if running in Lambda
   IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

   if IS_LAMBDA:
       # Lambda configuration
       app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

       # Use JWT sessions instead of filesystem sessions
       from flask_jwt_extended import JWTManager
       app.config['JWT_SECRET_KEY'] = os.environ['SECRET_KEY']
       app.config['JWT_TOKEN_LOCATION'] = ['headers']
       jwt = JWTManager(app)
   else:
       # Traditional configuration (Docker/local)
       from dotenv import load_dotenv
       load_dotenv()

       app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
       app.config['SESSION_TYPE'] = 'filesystem'

       from flask_session import Session
       Session(app)

   # Import routes (existing)
   from routes import *
   ```

3. **Update Authentication Routes**

   Modify `server/routes.py` (login/register):
   ```python
   from flask import jsonify, request
   from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
   from dynamodb_users import UserRepository
   import os

   IS_LAMBDA = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

   @app.route('/login', methods=['POST'])
   def login():
       data = request.get_json()
       username = data.get('username')
       password = data.get('password')

       if IS_LAMBDA:
           # DynamoDB authentication
           if UserRepository.verify_password(username, password):
               access_token = create_access_token(identity=username)
               return jsonify({
                   'success': True,
                   'token': access_token,
                   'username': username
               })
           else:
               return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
       else:
           # Original SQLite authentication (for local dev)
           # ... existing code ...

   @app.route('/register', methods=['POST'])
   def register():
       data = request.get_json()
       username = data.get('username')
       name = data.get('name')
       password = data.get('password')

       if IS_LAMBDA:
           # DynamoDB registration
           success = UserRepository.create_user(username, name, password)
           if success:
               # Also create S3 database
               from s3_sqlite import S3SQLiteConnection
               with S3SQLiteConnection(username) as conn:
                   pass  # Creates new database automatically

               return jsonify({'success': True})
           else:
               return jsonify({'success': False, 'error': 'Username already exists'}), 400
       else:
           # Original SQLite registration (for local dev)
           # ... existing code ...
   ```

4. **Update Database Access in Routes**

   Replace database connection logic in all routes:

   **Before**:
   ```python
   @app.route('/api/decks', methods=['GET'])
   def get_decks():
       username = session['username']
       db_path = f'user_dbs/{username}.anki2'
       conn = sqlite3.connect(db_path)
       # ... query logic ...
       conn.close()
   ```

   **After**:
   ```python
   from s3_sqlite import S3SQLiteConnection
   from flask_jwt_extended import jwt_required, get_jwt_identity

   @app.route('/api/decks', methods=['GET'])
   @jwt_required()  # If using Lambda
   def get_decks():
       if IS_LAMBDA:
           username = get_jwt_identity()
       else:
           username = session['username']

       with S3SQLiteConnection(username) as conn:
           # ... existing query logic works unchanged! ...
           cursor = conn.execute("SELECT * FROM col")
           # ...
   ```

5. **Update All Routes**

   Apply the pattern above to all routes:
   - `/api/decks` (GET, POST, PUT, DELETE)
   - `/api/cards` (GET, POST, PUT, DELETE)
   - `/api/review` (GET, POST)
   - `/api/stats` (GET)
   - `/api/export` (GET)

   Key changes:
   - Wrap database access with `S3SQLiteConnection`
   - Use `get_jwt_identity()` in Lambda mode
   - Keep existing SQLite queries unchanged

6. **Handle Conflict Errors**

   Add error handler:
   ```python
   from s3_sqlite import ConflictError

   @app.errorhandler(ConflictError)
   def handle_conflict(error):
       return jsonify({
           'success': False,
           'error': 'conflict',
           'message': str(error),
           'retry': True
       }), 409
   ```

7. **Update Frontend for JWT (if needed)**

   Modify `client/src/` to store JWT token:
   ```javascript
   // After login
   const response = await axios.post('/login', {username, password});
   if (response.data.success) {
       localStorage.setItem('token', response.data.token);
       localStorage.setItem('username', response.data.username);
   }

   // Configure axios to include token
   axios.defaults.headers.common['Authorization'] =
       `Bearer ${localStorage.getItem('token')}`;
   ```

#### Testing Phase 3:

**Test 3.1: Local Development Mode**
```bash
# Run Flask app locally (should use original SQLite)
cd server
source venv/bin/activate
python app.py

# Test endpoints
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"username":"localtest","name":"Local Test","password":"pass123"}'

curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"localtest","password":"pass123"}'
```
✅ **Pass criteria**: Local development still works with filesystem SQLite

**Test 3.2: Lambda Mode - Authentication**
```python
# test_lambda_auth.py
import json
import os

os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'javumbo-api'
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['S3_BUCKET'] = 'javumbo-user-dbs'
os.environ['DYNAMODB_USERS_TABLE'] = 'javumbo-users'

from lambda_handler import handler

def test_register_login():
    # Register
    event = {
        'httpMethod': 'POST',
        'path': '/register',
        'body': json.dumps({
            'username': 'lambdatest',
            'name': 'Lambda Test',
            'password': 'testpass'
        }),
        'headers': {'Content-Type': 'application/json'}
    }

    response = handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] == True
    print(f"✓ Registration successful")

    # Login
    event['path'] = '/login'
    event['body'] = json.dumps({
        'username': 'lambdatest',
        'password': 'testpass'
    })

    response = handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] == True
    assert 'token' in body
    token = body['token']
    print(f"✓ Login successful, token: {token[:20]}...")

    return token
```
✅ **Pass criteria**: Register and login work in Lambda mode

**Test 3.3: Lambda Mode - Protected Routes**
```python
# test_lambda_routes.py
def test_protected_routes(token):
    # Get decks (should work with token)
    event = {
        'httpMethod': 'GET',
        'path': '/api/decks',
        'headers': {
            'Authorization': f'Bearer {token}'
        }
    }

    response = handler(event, None)
    assert response['statusCode'] == 200
    print(f"✓ GET /api/decks successful")

    # Get decks without token (should fail)
    event['headers'] = {}
    response = handler(event, None)
    assert response['statusCode'] == 401
    print(f"✓ Authentication required for protected routes")

if __name__ == '__main__':
    token = test_register_login()
    test_protected_routes(token)
```
✅ **Pass criteria**: JWT authentication protects routes correctly

**Test 3.4: Lambda Mode - Database Operations**
```python
# test_lambda_db_operations.py
def test_crud_operations(token):
    # Add deck
    event = {
        'httpMethod': 'POST',
        'path': '/api/decks',
        'headers': {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'name': 'Test Deck',
            'description': 'Test Description'
        })
    }

    response = handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    deck_id = body['deck_id']
    print(f"✓ Deck created: {deck_id}")

    # Add card
    event['path'] = '/api/cards'
    event['body'] = json.dumps({
        'deck_id': deck_id,
        'front': 'Test Front',
        'back': 'Test Back'
    })

    response = handler(event, None)
    assert response['statusCode'] == 200
    print(f"✓ Card added")

    # Review card
    event['httpMethod'] = 'GET'
    event['path'] = f'/api/review/{deck_id}'
    del event['body']

    response = handler(event, None)
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body['cards']) > 0
    print(f"✓ Review session started: {len(body['cards'])} cards")

    # Submit review
    card = body['cards'][0]
    event['httpMethod'] = 'POST'
    event['path'] = '/api/review'
    event['body'] = json.dumps({
        'card_id': card['id'],
        'rating': 3
    })

    response = handler(event, None)
    assert response['statusCode'] == 200
    print(f"✓ Review submitted")

if __name__ == '__main__':
    token = test_register_login()
    test_crud_operations(token)
```
✅ **Pass criteria**: All CRUD operations work through Lambda

**Test 3.5: Conflict Handling**
```python
# test_lambda_conflicts.py
import concurrent.futures

def test_concurrent_modifications(token):
    # Simulate two concurrent review submissions
    def submit_review(rating):
        event = {
            'httpMethod': 'POST',
            'path': '/api/review',
            'headers': {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'card_id': 123,
                'rating': rating
            })
        }
        return handler(event, None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(submit_review, 3)
        future2 = executor.submit(submit_review, 4)

        response1 = future1.result()
        response2 = future2.result()

    # One should succeed, one might get 409 conflict
    statuses = [response1['statusCode'], response2['statusCode']]
    assert 200 in statuses  # At least one succeeded

    if 409 in statuses:
        print(f"✓ Conflict detected and handled")
    else:
        print(f"✓ Both requests succeeded (no conflict)")

if __name__ == '__main__':
    token = test_register_login()
    test_concurrent_modifications(token)
```
✅ **Pass criteria**: Concurrent writes either succeed or return 409 with retry instruction

**Test 3.6: Export Functionality**
```python
# test_lambda_export.py
def test_export(token):
    event = {
        'httpMethod': 'GET',
        'path': '/api/export',
        'headers': {
            'Authorization': f'Bearer {token}'
        }
    }

    response = handler(event, None)
    assert response['statusCode'] == 200

    # Should return .anki2 file
    assert response['headers']['Content-Type'] == 'application/octet-stream'
    assert '.anki2' in response['headers']['Content-Disposition']

    # Body should be base64 encoded binary
    import base64
    anki_data = base64.b64decode(response['body'])

    # Verify it's a valid SQLite file
    assert anki_data[:16] == b'SQLite format 3\x00'
    print(f"✓ Export returned valid .anki2 file ({len(anki_data)} bytes)")

if __name__ == '__main__':
    token = test_register_login()
    test_export(token)
```
✅ **Pass criteria**: Export returns valid .anki2 file compatible with Anki desktop

**Phase 3 Completion Checklist**:
- [ ] Lambda handler wrapper created
- [ ] Flask app detects Lambda vs local mode
- [ ] Authentication routes updated (JWT in Lambda, sessions locally)
- [ ] All API routes updated to use `S3SQLiteConnection`
- [ ] Error handling for conflicts implemented
- [ ] Frontend updated to use JWT tokens (if applicable)
- [ ] All 6 tests pass
- [ ] Manual testing with Postman/Insomnia completed

---

### Phase 4: Deployment & Optimization (Week 4)

**Objective**: Deploy to AWS, monitor performance, and optimize based on real-world usage.

#### Tasks:

1. **Create Deployment Package**

   ```bash
   cd server

   # Install dependencies
   pip install -r requirements.txt -t package/
   pip install awsgi -t package/

   # Copy application code
   cp -r *.py package/
   cp -r s3_sqlite.py package/
   cp -r dynamodb_users.py package/

   # Create zip
   cd package
   zip -r ../lambda_deployment.zip .
   cd ..
   zip -g lambda_deployment.zip lambda_handler.py
   ```

2. **Deploy Lambda Function**

   ```bash
   aws lambda update-function-code \
     --function-name javumbo-api \
     --zip-file fileb://lambda_deployment.zip

   # Update configuration
   aws lambda update-function-configuration \
     --function-name javumbo-api \
     --memory-size 512 \
     --timeout 30 \
     --environment Variables="{
       S3_BUCKET=javumbo-user-dbs,
       DYNAMODB_USERS_TABLE=javumbo-users,
       SECRET_KEY=your-secret-key-here
     }"
   ```

3. **Configure API Gateway Routes**

   ```bash
   # Create routes for all endpoints
   API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='javumbo-api'].ApiId" --output text)

   aws apigatewayv2 create-route \
     --api-id $API_ID \
     --route-key "POST /login" \
     --target integrations/$INTEGRATION_ID

   # Repeat for all routes:
   # POST /register, POST /login
   # GET/POST/PUT/DELETE /api/decks
   # GET/POST/PUT/DELETE /api/cards
   # GET/POST /api/review
   # GET /api/stats
   # GET /api/export

   # Or use catch-all:
   aws apigatewayv2 create-route \
     --api-id $API_ID \
     --route-key "ANY /{proxy+}" \
     --target integrations/$INTEGRATION_ID
   ```

4. **Deploy Frontend to S3/CloudFront**

   ```bash
   cd client

   # Update .env.production with API Gateway URL
   echo "VITE_API_BASE_URL=https://${API_ID}.execute-api.us-east-1.amazonaws.com" > .env.production

   # Build
   npm run build

   # Deploy to S3
   aws s3 sync dist/ s3://javumbo-frontend/ --delete

   # Invalidate CloudFront cache
   DISTRIBUTION_ID=$(aws cloudfront list-distributions \
     --query "DistributionList.Items[?Origins.Items[?DomainName=='javumbo-frontend.s3.amazonaws.com']].Id" \
     --output text)

   aws cloudfront create-invalidation \
     --distribution-id $DISTRIBUTION_ID \
     --paths "/*"
   ```

5. **Data Migration Script**

   Create and run `migrate_production_data.py`:
   ```python
   import sqlite3
   import boto3
   from pathlib import Path

   s3 = boto3.client('s3')
   dynamodb = boto3.resource('dynamodb')
   users_table = dynamodb.Table('javumbo-users')

   def migrate():
       # 1. Migrate admin.db
       conn = sqlite3.connect('admin.db')
       cursor = conn.execute('SELECT user_id, username, name, password_hash FROM users')

       with users_table.batch_writer() as batch:
           for row in cursor:
               batch.put_item(Item={
                   'username': row[1],
                   'user_id': row[0],
                   'name': row[2],
                   'password_hash': row[3]
               })
               print(f"✓ Migrated user: {row[1]}")

       conn.close()

       # 2. Migrate user databases
       user_dbs = Path('user_dbs')
       for db_file in user_dbs.glob('*.anki2'):
           username = db_file.stem

           s3.upload_file(
               Filename=str(db_file),
               Bucket='javumbo-user-dbs',
               Key=f'user_dbs/{username}.anki2'
           )
           print(f"✓ Migrated database: {username}.anki2")

       print("\n✅ Migration complete!")

   if __name__ == '__main__':
       confirm = input("Migrate production data to AWS? (yes/no): ")
       if confirm.lower() == 'yes':
           migrate()
   ```

6. **Set Up Monitoring**

   Create CloudWatch dashboard:
   ```bash
   aws cloudwatch put-dashboard \
     --dashboard-name javumbo-monitoring \
     --dashboard-body file://dashboard.json
   ```

   `dashboard.json`:
   ```json
   {
     "widgets": [
       {
         "type": "metric",
         "properties": {
           "metrics": [
             ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
             [".", "Errors", {"stat": "Sum"}],
             [".", "Duration", {"stat": "Average"}],
             [".", "ConcurrentExecutions", {"stat": "Maximum"}]
           ],
           "period": 300,
           "stat": "Average",
           "region": "us-east-1",
           "title": "Lambda Metrics"
         }
       },
       {
         "type": "metric",
         "properties": {
           "metrics": [
             ["AWS/S3", "NumberOfObjects", {"stat": "Average"}],
             [".", "BucketSizeBytes", {"stat": "Average"}]
           ],
           "period": 86400,
           "stat": "Average",
           "region": "us-east-1",
           "title": "S3 Storage"
         }
       },
       {
         "type": "metric",
         "properties": {
           "metrics": [
             ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
             [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
           ],
           "period": 300,
           "stat": "Sum",
           "region": "us-east-1",
           "title": "DynamoDB Usage"
         }
       }
     ]
   }
   ```

7. **Configure Alarms**

   ```bash
   # Lambda errors
   aws cloudwatch put-metric-alarm \
     --alarm-name javumbo-lambda-errors \
     --alarm-description "Alert on Lambda errors" \
     --metric-name Errors \
     --namespace AWS/Lambda \
     --statistic Sum \
     --period 300 \
     --threshold 5 \
     --comparison-operator GreaterThanThreshold \
     --evaluation-periods 1

   # High latency
   aws cloudwatch put-metric-alarm \
     --alarm-name javumbo-high-latency \
     --alarm-description "Alert on high latency" \
     --metric-name Duration \
     --namespace AWS/Lambda \
     --statistic Average \
     --period 300 \
     --threshold 3000 \
     --comparison-operator GreaterThanThreshold \
     --evaluation-periods 2
   ```

8. **Enable Provisioned Concurrency (Optional)**

   If cold starts are an issue:
   ```bash
   aws lambda put-provisioned-concurrency-config \
     --function-name javumbo-api \
     --provisioned-concurrent-executions 2 \
     --qualifier $LATEST_VERSION
   ```

9. **Cost Monitoring**

   Create budget alert:
   ```bash
   aws budgets create-budget \
     --account-id YOUR_ACCOUNT_ID \
     --budget file://budget.json
   ```

   `budget.json`:
   ```json
   {
     "BudgetName": "javumbo-monthly-budget",
     "BudgetLimit": {
       "Amount": "10",
       "Unit": "USD"
     },
     "TimeUnit": "MONTHLY",
     "BudgetType": "COST",
     "CostFilters": {
       "Service": ["AWS Lambda", "Amazon S3", "Amazon DynamoDB", "Amazon API Gateway"]
     }
   }
   ```

#### Testing Phase 4:

**Test 4.1: Deployment Verification**
```bash
# Get API Gateway URL
API_URL=$(aws apigatewayv2 get-apis \
  --query "Items[?Name=='javumbo-api'].ApiEndpoint" \
  --output text)

echo "API URL: $API_URL"

# Test health check (add this endpoint if not exists)
curl $API_URL/health

# Expected: {"status": "healthy", "version": "1.0.0"}
```
✅ **Pass criteria**: API Gateway returns successful response

**Test 4.2: End-to-End User Flow**
```bash
# Register new user
curl -X POST $API_URL/register \
  -H "Content-Type: application/json" \
  -d '{"username":"e2etest","name":"E2E Test","password":"testpass123"}'

# Login
TOKEN=$(curl -X POST $API_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"e2etest","password":"testpass123"}' \
  | jq -r '.token')

echo "Token: $TOKEN"

# Create deck
DECK_ID=$(curl -X POST $API_URL/api/decks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Deck","description":"E2E Test"}' \
  | jq -r '.deck_id')

echo "Deck ID: $DECK_ID"

# Add card
curl -X POST $API_URL/api/cards \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"deck_id\":$DECK_ID,\"front\":\"Test Front\",\"back\":\"Test Back\"}"

# Get decks
curl -X GET $API_URL/api/decks \
  -H "Authorization: Bearer $TOKEN"

# Review session
curl -X GET $API_URL/api/review/$DECK_ID \
  -H "Authorization: Bearer $TOKEN"
```
✅ **Pass criteria**: Complete user flow works without errors

**Test 4.3: Performance Benchmarking**
```bash
# Install Apache Bench
# brew install httpd (macOS)
# sudo apt install apache2-utils (Linux)

# Benchmark login endpoint (warm Lambda)
ab -n 100 -c 5 -T 'application/json' \
  -p login_payload.json \
  $API_URL/login

# login_payload.json:
# {"username":"e2etest","password":"testpass123"}

# Expected results:
# - Mean time: 100-300ms (warm Lambda)
# - 95th percentile: <500ms
# - 0% failed requests
```
✅ **Pass criteria**:
- Average latency < 300ms
- 95th percentile < 500ms
- 0% errors

**Test 4.4: Cold Start Measurement**
```bash
# Disable provisioned concurrency if enabled
aws lambda delete-provisioned-concurrency-config \
  --function-name javumbo-api \
  --qualifier $LATEST_VERSION

# Wait 10 minutes for Lambda to go cold
sleep 600

# Measure cold start
time curl -X POST $API_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"e2etest","password":"testpass123"}'

# Expected: 1-3 seconds (cold start)

# Second request (warm)
time curl -X POST $API_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"e2etest","password":"testpass123"}'

# Expected: 100-300ms (warm)
```
✅ **Pass criteria**: Cold start < 3s, warm requests < 300ms

**Test 4.5: Concurrent Users Simulation**
```python
# test_concurrent_load.py
import concurrent.futures
import requests
import time

API_URL = "YOUR_API_GATEWAY_URL"

def simulate_user(user_id):
    start = time.time()

    # Register
    r = requests.post(f"{API_URL}/register", json={
        'username': f'loadtest_{user_id}',
        'name': f'Load Test {user_id}',
        'password': 'test123'
    })

    # Login
    r = requests.post(f"{API_URL}/login", json={
        'username': f'loadtest_{user_id}',
        'password': 'test123'
    })
    token = r.json()['token']
    headers = {'Authorization': f'Bearer {token}'}

    # Create deck
    r = requests.post(f"{API_URL}/api/decks",
        headers=headers,
        json={'name': 'Load Test Deck', 'description': 'Test'})
    deck_id = r.json()['deck_id']

    # Add 10 cards
    for i in range(10):
        requests.post(f"{API_URL}/api/cards",
            headers=headers,
            json={
                'deck_id': deck_id,
                'front': f'Front {i}',
                'back': f'Back {i}'
            })

    # Review session
    r = requests.get(f"{API_URL}/api/review/{deck_id}", headers=headers)
    cards = r.json()['cards']

    # Submit reviews
    for card in cards[:5]:
        requests.post(f"{API_URL}/api/review",
            headers=headers,
            json={'card_id': card['id'], 'rating': 3})

    duration = time.time() - start
    return duration

# Simulate 10 concurrent users
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(simulate_user, i) for i in range(10)]
    results = [f.result() for f in futures]

print(f"Average time per user: {sum(results)/len(results):.2f}s")
print(f"Min: {min(results):.2f}s, Max: {max(results):.2f}s")
```
✅ **Pass criteria**:
- 10 concurrent users complete without errors
- Average time per user < 10 seconds
- No Lambda throttling errors

**Test 4.6: Data Migration Verification**
```python
# test_migration_verification.py
import sqlite3
import boto3

def verify_migration():
    # Check all users migrated
    local_conn = sqlite3.connect('admin.db')
    local_cursor = local_conn.execute('SELECT username FROM users ORDER BY username')
    local_users = {row[0] for row in local_cursor}

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('javumbo-users')
    response = table.scan()
    dynamo_users = {item['username'] for item in response['Items']}

    assert local_users == dynamo_users
    print(f"✓ All {len(local_users)} users migrated to DynamoDB")

    # Check all user databases migrated
    from pathlib import Path
    local_dbs = {f.stem for f in Path('user_dbs').glob('*.anki2')}

    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket='javumbo-user-dbs', Prefix='user_dbs/')
    s3_dbs = {obj['Key'].split('/')[-1].replace('.anki2', '')
              for obj in response.get('Contents', [])}

    assert local_dbs == s3_dbs
    print(f"✓ All {len(local_dbs)} databases migrated to S3")

    # Verify file integrity (spot check)
    import random
    sample_user = random.choice(list(local_dbs))

    # Download from S3
    s3.download_file(
        'javumbo-user-dbs',
        f'user_dbs/{sample_user}.anki2',
        '/tmp/s3_sample.anki2'
    )

    # Compare
    local_size = Path(f'user_dbs/{sample_user}.anki2').stat().st_size
    s3_size = Path('/tmp/s3_sample.anki2').stat().st_size

    assert local_size == s3_size
    print(f"✓ File integrity verified (sample: {sample_user})")

if __name__ == '__main__':
    verify_migration()
```
✅ **Pass criteria**: All users and databases migrated with data integrity intact

**Test 4.7: Cost Validation**
```bash
# Check actual costs after 24 hours
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-02 \
  --granularity DAILY \
  --metrics BlendedCost \
  --filter file://cost-filter.json

# cost-filter.json:
{
  "Dimensions": {
    "Key": "SERVICE",
    "Values": ["AWS Lambda", "Amazon S3", "Amazon DynamoDB", "Amazon API Gateway"]
  }
}

# Expected daily cost: $0.03 - $0.10 (for 100 users)
# Extrapolated monthly: ~$1
```
✅ **Pass criteria**: Daily costs align with estimates (< $0.10/day)

**Test 4.8: Monitoring & Alerts**
```bash
# Trigger test alarm
# Invoke Lambda 10 times with invalid payload (should cause errors)
for i in {1..10}; do
  aws lambda invoke \
    --function-name javumbo-api \
    --payload '{"invalid": "payload"}' \
    /tmp/response.json
done

# Check if alarm triggered
aws cloudwatch describe-alarms \
  --alarm-names javumbo-lambda-errors \
  --query "MetricAlarms[0].StateValue"

# Expected: "ALARM"
```
✅ **Pass criteria**: CloudWatch alarm triggers on error threshold

**Phase 4 Completion Checklist**:
- [ ] Lambda function deployed with all code
- [ ] API Gateway configured with all routes
- [ ] Frontend deployed to S3/CloudFront
- [ ] Production data migrated (users + databases)
- [ ] CloudWatch dashboard created
- [ ] CloudWatch alarms configured
- [ ] Cost budget alerts set up
- [ ] Provisioned concurrency configured (if needed)
- [ ] All 8 tests pass
- [ ] Documentation updated with deployment instructions
- [ ] Rollback plan documented

---

### Phase 4 Alternative: Deployment & Optimization (Using Terraform)

**Objective**: Deploy the entire serverless infrastructure using Infrastructure as Code (Terraform) for reproducibility, version control, and easier management.

#### Why Terraform?

**Advantages over AWS CLI:**
- **Declarative**: Define desired state, Terraform handles implementation
- **Version Control**: Track infrastructure changes in git
- **Reproducible**: Deploy identical environments (dev, staging, prod)
- **State Management**: Track resource dependencies and prevent drift
- **Plan Before Apply**: Preview changes before executing
- **Idempotent**: Safe to run multiple times

#### Prerequisites

```bash
# Install Terraform
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify
terraform --version
```

#### Project Structure

```
javumbo/
├── terraform/
│   ├── main.tf              # Main infrastructure definition
│   ├── variables.tf         # Input variables
│   ├── outputs.tf           # Output values
│   ├── lambda.tf            # Lambda function resources
│   ├── api_gateway.tf       # API Gateway configuration
│   ├── dynamodb.tf          # DynamoDB tables
│   ├── s3.tf                # S3 buckets
│   ├── cloudfront.tf        # CloudFront distribution
│   ├── iam.tf               # IAM roles and policies
│   ├── cloudwatch.tf        # Monitoring and alarms
│   ├── terraform.tfvars     # Variable values (gitignored!)
│   └── backend.tf           # Terraform state backend
```

---

#### Task 1: Create Terraform Configuration Files

**1.1: Create `terraform/variables.tf`**

```hcl
variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "javumbo"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "secret_key" {
  description = "Flask secret key for JWT tokens"
  type        = string
  sensitive   = true
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_ephemeral_storage" {
  description = "Lambda ephemeral storage in MB"
  type        = number
  default     = 2048
}

variable "enable_provisioned_concurrency" {
  description = "Enable Lambda provisioned concurrency"
  type        = bool
  default     = false
}

variable "provisioned_concurrent_executions" {
  description = "Number of provisioned concurrent executions"
  type        = number
  default     = 2
}

variable "frontend_domain_name" {
  description = "Custom domain for frontend (optional)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "JAVUMBO"
    ManagedBy   = "Terraform"
  }
}
```

**1.2: Create `terraform/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.tags
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for AWS region
data "aws_region" "current" {}
```

**1.3: Create `terraform/s3.tf`**

```hcl
# S3 bucket for user .anki2 databases
resource "aws_s3_bucket" "user_databases" {
  bucket = "${var.project_name}-user-dbs-${var.environment}"

  tags = {
    Name = "User Databases"
  }
}

# Enable versioning for data protection
resource "aws_s3_bucket_versioning" "user_databases" {
  bucket = aws_s3_bucket.user_databases.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "user_databases" {
  bucket = aws_s3_bucket.user_databases.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule for old versions
resource "aws_s3_bucket_lifecycle_configuration" "user_databases" {
  bucket = aws_s3_bucket.user_databases.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  rule {
    id     = "intelligent-tiering"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

# S3 bucket for frontend
resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project_name}-frontend-${var.environment}"

  tags = {
    Name = "Frontend Static Assets"
  }
}

# Frontend bucket public access for CloudFront
resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

# CloudFront Origin Access Identity
resource "aws_cloudfront_origin_access_identity" "frontend" {
  comment = "OAI for ${var.project_name} frontend"
}

# Bucket policy for CloudFront access
resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.frontend.iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })
}
```

**1.4: Create `terraform/dynamodb.tf`**

```hcl
# Users table (replaces admin.db)
resource "aws_dynamodb_table" "users" {
  name         = "${var.project_name}-users-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "User Authentication"
  }
}

# User locks table (for concurrency control)
resource "aws_dynamodb_table" "user_locks" {
  name         = "${var.project_name}-user-locks-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "username"

  attribute {
    name = "username"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "User Lock Management"
  }
}
```

**1.5: Create `terraform/iam.tf`**

```hcl
# Lambda execution role
resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-lambda-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "Lambda Execution Role"
  }
}

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Custom policy for S3 and DynamoDB access
resource "aws_iam_role_policy" "lambda_custom" {
  name = "${var.project_name}-lambda-custom-${var.environment}"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.user_databases.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.users.arn,
          aws_dynamodb_table.user_locks.arn
        ]
      }
    ]
  })
}
```

**1.6: Create `terraform/lambda.tf`**

```hcl
# Create Lambda deployment package
data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = "${path.module}/../server/package"
  output_path = "${path.module}/.terraform/lambda_deployment.zip"
}

# Lambda function
resource "aws_lambda_function" "api" {
  filename         = data.archive_file.lambda_package.output_path
  function_name    = "${var.project_name}-api-${var.environment}"
  role            = aws_iam_role.lambda_execution.arn
  handler         = "lambda_handler.handler"
  source_code_hash = data.archive_file.lambda_package.output_base64sha256
  runtime         = "python3.11"
  memory_size     = var.lambda_memory_size
  timeout         = var.lambda_timeout

  ephemeral_storage {
    size = var.lambda_ephemeral_storage
  }

  environment {
    variables = {
      S3_BUCKET              = aws_s3_bucket.user_databases.id
      DYNAMODB_USERS_TABLE   = aws_dynamodb_table.users.name
      DYNAMODB_LOCKS_TABLE   = aws_dynamodb_table.user_locks.name
      SECRET_KEY             = var.secret_key
      AWS_LAMBDA_FUNCTION_NAME = "${var.project_name}-api-${var.environment}"
    }
  }

  tags = {
    Name = "API Lambda Function"
  }
}

# Lambda function URL (alternative to API Gateway for simple setups)
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"

  cors {
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
    expose_headers    = ["*"]
    max_age          = 86400
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = 14

  tags = {
    Name = "Lambda Logs"
  }
}

# Provisioned Concurrency (optional, for production)
resource "aws_lambda_provisioned_concurrency_config" "api" {
  count                             = var.enable_provisioned_concurrency ? 1 : 0
  function_name                     = aws_lambda_function.api.function_name
  provisioned_concurrent_executions = var.provisioned_concurrent_executions
  qualifier                         = aws_lambda_function.api.version
}
```

**1.7: Create `terraform/api_gateway.tf`**

```hcl
# HTTP API Gateway
resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["*"]
    expose_headers = ["*"]
    max_age       = 86400
  }

  tags = {
    Name = "API Gateway"
  }
}

# Lambda integration
resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.api.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

# Default route (catch-all)
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Deployment stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      errorMessage   = "$context.error.message"
    })
  }

  tags = {
    Name = "Default Stage"
  }
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = 14

  tags = {
    Name = "API Gateway Logs"
  }
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
```

**1.8: Create `terraform/cloudfront.tf`**

```hcl
# CloudFront distribution for frontend
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US, Canada, Europe
  aliases             = var.frontend_domain_name != "" ? [var.frontend_domain_name] : []

  origin {
    domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.frontend.cloudfront_access_identity_path
    }
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.frontend.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  # SPA fallback - serve index.html for all routes
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.frontend_domain_name == ""
    # For custom domain, add:
    # acm_certificate_arn      = var.acm_certificate_arn
    # ssl_support_method       = "sni-only"
    # minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "Frontend Distribution"
  }
}
```

**1.9: Create `terraform/cloudwatch.tf`**

```hcl
# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Invocations" }],
            [".", "Errors", { stat = "Sum", label = "Errors" }],
            [".", "Duration", { stat = "Average", label = "Avg Duration" }],
            [".", "ConcurrentExecutions", { stat = "Maximum", label = "Max Concurrent" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Lambda Metrics"
          dimensions = {
            FunctionName = [aws_lambda_function.api.function_name]
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "Requests" }],
            [".", "4XXError", { stat = "Sum", label = "4XX Errors" }],
            [".", "5XXError", { stat = "Sum", label = "5XX Errors" }],
            [".", "Latency", { stat = "Average", label = "Avg Latency" }]
          ]
          period = 300
          region = var.aws_region
          title  = "API Gateway Metrics"
          dimensions = {
            ApiId = [aws_apigatewayv2_api.main.id]
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", { stat = "Sum" }],
            [".", "ConsumedWriteCapacityUnits", { stat = "Sum" }]
          ]
          period = 300
          region = var.aws_region
          title  = "DynamoDB Capacity"
        }
      }
    ]
  })
}

# Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when Lambda errors exceed threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  tags = {
    Name = "Lambda Errors Alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.project_name}-lambda-duration-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 3000
  alarm_description   = "Alert when Lambda duration is high"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  tags = {
    Name = "Lambda Duration Alarm"
  }
}

# Budget alert
resource "aws_budgets_budget" "monthly" {
  name              = "${var.project_name}-monthly-budget-${var.environment}"
  budget_type       = "COST"
  limit_amount      = "10"
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = "2025-01-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = []
  }
}
```

**1.10: Create `terraform/outputs.tf`**

```hcl
output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "lambda_function_url" {
  description = "Lambda Function URL (alternative to API Gateway)"
  value       = aws_lambda_function_url.api.function_url
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.frontend.id
}

output "s3_user_databases_bucket" {
  description = "S3 bucket for user databases"
  value       = aws_s3_bucket.user_databases.id
}

output "s3_frontend_bucket" {
  description = "S3 bucket for frontend"
  value       = aws_s3_bucket.frontend.id
}

output "dynamodb_users_table" {
  description = "DynamoDB users table name"
  value       = aws_dynamodb_table.users.name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.api.function_name
}
```

**1.11: Create `terraform/terraform.tfvars`**

```hcl
# Variable values for deployment
project_name  = "javumbo"
environment   = "prod"
aws_region    = "us-east-1"

# Generate a secure random secret:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
secret_key    = "YOUR_SECRET_KEY_HERE"

# Lambda configuration
lambda_memory_size      = 512
lambda_timeout          = 30
lambda_ephemeral_storage = 2048

# Provisioned concurrency (optional, costs extra)
enable_provisioned_concurrency    = false
provisioned_concurrent_executions = 2

# Custom domain (optional)
frontend_domain_name = ""

# Tags
tags = {
  Project     = "JAVUMBO"
  Environment = "Production"
  ManagedBy   = "Terraform"
}
```

**⚠️ Important**: Add `terraform.tfvars` to `.gitignore`:
```bash
echo "terraform/terraform.tfvars" >> .gitignore
echo "terraform/.terraform/" >> .gitignore
echo "terraform/*.tfstate*" >> .gitignore
```

**1.12: Create `terraform/backend.tf` (Optional - Recommended for Teams)**

```hcl
# Store Terraform state in S3 for team collaboration
terraform {
  backend "s3" {
    bucket         = "javumbo-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "javumbo-terraform-locks"
  }
}

# Note: Create the S3 bucket and DynamoDB table manually first:
# aws s3 mb s3://javumbo-terraform-state
# aws dynamodb create-table \
#   --table-name javumbo-terraform-locks \
#   --attribute-definitions AttributeName=LockID,AttributeType=S \
#   --key-schema AttributeName=LockID,KeyType=HASH \
#   --billing-mode PAY_PER_REQUEST
```

---

#### Task 2: Deploy Infrastructure with Terraform

**2.1: Initialize Terraform**

```bash
cd terraform

# Initialize (downloads providers)
terraform init
```

**2.2: Prepare Lambda Deployment Package**

Before running Terraform, create the Lambda package:

```bash
cd ../server

# Create package directory
mkdir -p package

# Install dependencies
pip install -r requirements.txt -t package/
pip install awsgi -t package/

# Copy application code
cp *.py package/
cp s3_sqlite.py package/
cp dynamodb_users.py package/

cd ../terraform
```

**2.3: Validate Configuration**

```bash
# Check syntax
terraform validate

# Format files
terraform fmt -recursive
```

**2.4: Plan Deployment**

```bash
# Preview changes
terraform plan -out=tfplan

# Review output carefully
# Shows what will be created, modified, or destroyed
```

**2.5: Apply Changes**

```bash
# Deploy infrastructure
terraform apply tfplan

# Alternatively, apply without explicit plan:
terraform apply

# Type "yes" when prompted
```

**Expected output:**
```
Apply complete! Resources: 25 added, 0 changed, 0 destroyed.

Outputs:

api_gateway_url = "https://abc123def.execute-api.us-east-1.amazonaws.com"
cloudfront_domain = "d1234567890.cloudfront.net"
dynamodb_users_table = "javumbo-users-prod"
lambda_function_name = "javumbo-api-prod"
s3_frontend_bucket = "javumbo-frontend-prod"
s3_user_databases_bucket = "javumbo-user-dbs-prod"
```

**2.6: Deploy Frontend**

```bash
cd ../client

# Update .env.production with API Gateway URL
echo "VITE_API_BASE_URL=$(cd ../terraform && terraform output -raw api_gateway_url)" > .env.production

# Build
npm run build

# Get S3 bucket name
S3_BUCKET=$(cd ../terraform && terraform output -raw s3_frontend_bucket)

# Deploy
aws s3 sync dist/ s3://$S3_BUCKET/ --delete

# Get CloudFront distribution ID
CF_DIST_ID=$(cd ../terraform && terraform output -raw cloudfront_distribution_id)

# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id $CF_DIST_ID \
  --paths "/*"
```

**2.7: Migrate Data**

```bash
cd ../server

# Run migration script (from Phase 4)
python migrate_production_data.py
```

---

#### Task 3: Terraform State Management

**3.1: View Current State**

```bash
# List resources
terraform state list

# Show specific resource
terraform state show aws_lambda_function.api
```

**3.2: Import Existing Resources (if needed)**

If you manually created resources earlier:

```bash
# Import Lambda function
terraform import aws_lambda_function.api javumbo-api-prod

# Import S3 bucket
terraform import aws_s3_bucket.user_databases javumbo-user-dbs-prod
```

**3.3: Manage Resource Drift**

```bash
# Detect changes made outside Terraform
terraform plan -refresh-only

# Apply detected changes to state
terraform apply -refresh-only
```

---

#### Task 4: Update and Manage Infrastructure

**4.1: Update Lambda Code**

```bash
cd ../server

# Make code changes
# ...

# Rebuild package
rm -rf package
mkdir package
pip install -r requirements.txt -t package/
pip install awsgi -t package/
cp *.py package/

cd ../terraform

# Plan and apply (Terraform detects package changes)
terraform plan
terraform apply
```

**4.2: Modify Configuration**

```bash
# Edit terraform.tfvars
vim terraform.tfvars

# Change values, e.g.:
lambda_memory_size = 1024
enable_provisioned_concurrency = true

# Apply changes
terraform plan
terraform apply
```

**4.3: Scale Resources**

```bash
# Increase Lambda memory
terraform apply -var="lambda_memory_size=1024"

# Enable provisioned concurrency
terraform apply -var="enable_provisioned_concurrency=true"
```

---

#### Task 5: Multi-Environment Setup

**5.1: Create Workspace for Each Environment**

```bash
# Create dev environment
terraform workspace new dev
terraform workspace select dev
terraform apply -var="environment=dev"

# Create staging environment
terraform workspace new staging
terraform workspace select staging
terraform apply -var="environment=staging"

# Switch to production
terraform workspace select default  # or 'prod'
```

**5.2: Or Use Separate Directories**

```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf -> ../../main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   ├── staging/
│   │   ├── main.tf -> ../../main.tf
│   │   ├── terraform.tfvars
│   │   └── backend.tf
│   └── prod/
│       ├── main.tf -> ../../main.tf
│       ├── terraform.tfvars
│       └── backend.tf
```

---

#### Task 6: Destroy Infrastructure (Cleanup)

**⚠️ Warning**: This deletes all resources!

```bash
# Plan destruction
terraform plan -destroy

# Destroy all resources
terraform destroy

# Type "yes" to confirm
```

---

#### Testing Phase 4 (Terraform):

**Test 4T.1: Terraform Validation**
```bash
cd terraform

# Validate syntax
terraform validate

# Expected: "Success! The configuration is valid."
```
✅ **Pass criteria**: Configuration validates without errors

**Test 4T.2: Terraform Plan (Dry Run)**
```bash
# Plan without applying
terraform plan

# Expected: Shows 25+ resources to create
# No errors or warnings
```
✅ **Pass criteria**: Plan succeeds, shows expected resource count

**Test 4T.3: Infrastructure Deployment**
```bash
# Apply configuration
terraform apply -auto-approve

# Check outputs
terraform output
```
✅ **Pass criteria**: All resources created successfully, outputs displayed

**Test 4T.4: Lambda Function Verification**
```bash
# Get Lambda function name
LAMBDA_NAME=$(terraform output -raw lambda_function_name)

# Invoke Lambda
aws lambda invoke \
  --function-name $LAMBDA_NAME \
  --payload '{"httpMethod":"GET","path":"/health"}' \
  response.json

cat response.json
# Expected: {"statusCode":200, ...}
```
✅ **Pass criteria**: Lambda invokes successfully

**Test 4T.5: API Gateway Endpoint**
```bash
# Get API URL
API_URL=$(terraform output -raw api_gateway_url)

# Test endpoint
curl $API_URL/health

# Expected: {"status":"healthy"}
```
✅ **Pass criteria**: API Gateway routes to Lambda correctly

**Test 4T.6: S3 Bucket Access**
```bash
# Get bucket name
S3_BUCKET=$(terraform output -raw s3_user_databases_bucket)

# Test upload
echo "test" > test.txt
aws s3 cp test.txt s3://$S3_BUCKET/test/test.txt

# Test download
aws s3 cp s3://$S3_BUCKET/test/test.txt downloaded.txt

# Verify
diff test.txt downloaded.txt

# Cleanup
aws s3 rm s3://$S3_BUCKET/test/test.txt
rm test.txt downloaded.txt
```
✅ **Pass criteria**: S3 bucket accessible with correct permissions

**Test 4T.7: DynamoDB Table Operations**
```bash
# Get table name
TABLE_NAME=$(terraform output -raw dynamodb_users_table)

# Write test item
aws dynamodb put-item \
  --table-name $TABLE_NAME \
  --item '{"username":{"S":"tftest"},"name":{"S":"TF Test"}}'

# Read test item
aws dynamodb get-item \
  --table-name $TABLE_NAME \
  --key '{"username":{"S":"tftest"}}'

# Delete test item
aws dynamodb delete-item \
  --table-name $TABLE_NAME \
  --key '{"username":{"S":"tftest"}}'
```
✅ **Pass criteria**: DynamoDB operations succeed

**Test 4T.8: CloudFront Distribution**
```bash
# Get CloudFront domain
CF_DOMAIN=$(terraform output -raw cloudfront_domain)

# Test access (may take 5-10 minutes for distribution to deploy)
curl -I https://$CF_DOMAIN

# Expected: HTTP 200 OK (or 403 if no content uploaded yet)
```
✅ **Pass criteria**: CloudFront distribution is active

**Test 4T.9: IAM Permissions Verification**
```bash
# Test Lambda can access S3
aws lambda invoke \
  --function-name $LAMBDA_NAME \
  --payload '{
    "httpMethod":"POST",
    "path":"/test-permissions",
    "body":"{}"
  }' \
  response.json

# Check logs for permission errors
aws logs tail /aws/lambda/$LAMBDA_NAME --follow
```
✅ **Pass criteria**: No permission denied errors

**Test 4T.10: End-to-End Flow**
```bash
# Get API URL
API_URL=$(terraform output -raw api_gateway_url)

# Register user
curl -X POST $API_URL/register \
  -H "Content-Type: application/json" \
  -d '{"username":"tftest","name":"TF Test","password":"test123"}'

# Login
TOKEN=$(curl -X POST $API_URL/login \
  -H "Content-Type: application/json" \
  -d '{"username":"tftest","password":"test123"}' \
  | jq -r '.token')

echo "Token: $TOKEN"

# Create deck
curl -X POST $API_URL/api/decks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"TF Test Deck","description":"Test"}'
```
✅ **Pass criteria**: Complete user flow works through Terraform-deployed infrastructure

**Test 4T.11: Resource Tagging**
```bash
# Verify all resources have correct tags
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=JAVUMBO \
  --query 'ResourceTagMappingList[*].ResourceARN'

# Expected: List of all created resources
```
✅ **Pass criteria**: All resources properly tagged

**Test 4T.12: State File Security**
```bash
# Check state file doesn't contain sensitive data in plain text
grep -i "secret_key" terraform.tfstate

# If using S3 backend:
aws s3api get-object-attributes \
  --bucket javumbo-terraform-state \
  --key prod/terraform.tfstate \
  --object-attributes ServerSideEncryption

# Expected: Encryption enabled
```
✅ **Pass criteria**: State file encrypted, sensitive values marked as sensitive

---

#### Terraform Phase Completion Checklist:

- [ ] All Terraform configuration files created
- [ ] `terraform.tfvars` added to `.gitignore`
- [ ] Terraform initialized successfully
- [ ] Configuration validated with `terraform validate`
- [ ] Plan reviewed with `terraform plan`
- [ ] Infrastructure deployed with `terraform apply`
- [ ] All 12 Terraform tests pass
- [ ] Frontend deployed to S3/CloudFront
- [ ] Production data migrated
- [ ] CloudWatch dashboard accessible
- [ ] All resource outputs documented
- [ ] Team members can access Terraform state (if using remote backend)
- [ ] Rollback procedure tested with `terraform destroy` in dev environment

---

#### Advantages of Terraform Approach

**vs Manual AWS CLI Deployment:**

| Aspect | AWS CLI | Terraform |
|--------|---------|-----------|
| **Setup Time** | 3-4 hours | 4-6 hours (first time) |
| **Reproducibility** | Manual, error-prone | Automatic, reliable |
| **Version Control** | Scripts in git | Full IaC in git |
| **Team Collaboration** | Difficult | Easy (shared state) |
| **Drift Detection** | Manual checks | Automatic |
| **Rollback** | Manual recreation | `terraform destroy` |
| **Documentation** | Separate docs needed | Code is documentation |
| **Multi-Environment** | Duplicate scripts | Workspaces/modules |
| **Cost** | Free | Free |

**When to use Terraform:**
- ✅ Team of 2+ developers
- ✅ Multiple environments (dev, staging, prod)
- ✅ Need infrastructure versioning
- ✅ Automated CI/CD pipeline
- ✅ Complex infrastructure

**When AWS CLI is sufficient:**
- ✅ Solo developer
- ✅ Single environment
- ✅ Quick prototype/POC
- ✅ Learning AWS services

---

## Success Criteria

The migration is considered successful when:

1. **Functionality**: All features work identically to containerized version
2. **Performance**: 95th percentile latency < 500ms for warm requests
3. **Cost**: Monthly cost < $2 for 100 users (or FREE with free tier)
4. **Reliability**: 99.9% uptime (measured over 1 week)
5. **Data Integrity**: No data loss, all operations preserve database consistency
6. **Anki Compatibility**: Exported `.anki2` files open in Anki desktop without errors

---

## Rollback Plan

If critical issues arise during migration:

1. **DNS Failover**: Point domain back to ECS/Fargate deployment
2. **Database Recovery**: Restore from S3 versioning or DynamoDB point-in-time recovery
3. **Code Rollback**: Revert Lambda function to previous version
4. **Incremental Rollback**: Route 10% traffic to serverless, 90% to ECS during transition

---

## Future Optimizations

Post-migration enhancements to consider:

1. **ElastiCache**: Add Redis for cross-Lambda cache coordination (~$13/month)
2. **EFS Alternative**: For high-frequency users, mount EFS to Lambda (faster than S3)
3. **Database Sharding**: Split large `.anki2` files into metadata + data files
4. **CDN Edge Functions**: Move authentication to CloudFront Functions (lower cost)
5. **Auto-Scaling DynamoDB**: Switch to provisioned capacity with auto-scaling at scale
6. **Lambda@Edge**: Deploy API closer to users globally

---

## Appendix: Cost Tracking Template

Track actual costs weekly:

| Week | Lambda | API GW | DynamoDB | S3 | CloudFront | Total | Notes |
|------|--------|--------|----------|----|-----------:|-------|-------|
| 1    | $0.16  | $0.11  | $0.33    | $0.06 | $0.26 | $0.92 | Initial deployment |
| 2    | $0.18  | $0.13  | $0.35    | $0.07 | $0.28 | $1.01 | 10% traffic increase |
| 3    |        |        |          |    |           |       |       |
| 4    |        |        |          |    |           |       |       |

---

## Appendix: Useful Commands

### Lambda Management
```bash
# View logs
aws logs tail /aws/lambda/javumbo-api --follow

# Update environment variables
aws lambda update-function-configuration \
  --function-name javumbo-api \
  --environment Variables="{KEY=VALUE}"

# Invoke manually
aws lambda invoke \
  --function-name javumbo-api \
  --payload '{"httpMethod":"GET","path":"/health"}' \
  response.json
```

### S3 Management
```bash
# List user databases
aws s3 ls s3://javumbo-user-dbs/user_dbs/

# Download specific user DB
aws s3 cp s3://javumbo-user-dbs/user_dbs/username.anki2 ./

# Enable versioning (if not already)
aws s3api put-bucket-versioning \
  --bucket javumbo-user-dbs \
  --versioning-configuration Status=Enabled
```

### DynamoDB Management
```bash
# Query user
aws dynamodb get-item \
  --table-name javumbo-users \
  --key '{"username":{"S":"testuser"}}'

# Scan all users
aws dynamodb scan --table-name javumbo-users

# Enable point-in-time recovery
aws dynamodb update-continuous-backups \
  --table-name javumbo-users \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true
```

---

## Contact & Support

For issues during migration:
- **AWS Support**: Submit ticket through AWS Console
- **Project Lead**: [Your contact info]
- **Documentation**: See `/docs` directory for detailed specs
- **GitHub Issues**: [Repository URL]

---

**Document Version**: 1.0
**Last Updated**: 2025-01-12
**Author**: Claude Code Assistant
**Status**: Ready for Implementation
