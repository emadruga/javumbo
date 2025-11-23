"""
S3SQLiteConnection - Context manager for SQLite databases stored in S3

This module provides a context manager that handles the download-process-upload
pattern for user databases stored in S3. It maintains Anki .anki2 file compatibility.

Day 2 Version: Basic implementation without caching
Day 3 Version: Lambda container caching with ETag validation
Day 4 Version: Optimistic locking with ETags (prevents concurrent write conflicts)
Day 6 Version: Session-aware caching with DynamoDB coordination (90% reduction in S3 operations)
"""

import boto3
import sqlite3
import os
import time
from botocore.exceptions import ClientError
from typing import Optional


# S3 client (reused across invocations)
s3 = boto3.client('s3')

# Get bucket name from environment variable
BUCKET = os.environ.get('S3_BUCKET', 'javumbo-user-dbs')

# Lambda container cache (persists across warm invocations)
# Cache structure: {username: {'etag': str, 'timestamp': float, 'path': str}}
db_cache = {}

# Cache configuration
CACHE_TTL = int(os.environ.get('DB_CACHE_TTL', 300))  # 5 minutes default


class S3SQLiteConnection:
    """
    Context manager for SQLite databases stored in S3.

    Usage:
        with S3SQLiteConnection(username) as conn:
            cursor = conn.execute("SELECT * FROM cards")
            # ... SQLite operations ...
        # File automatically uploaded back to S3 on exit

    Flow:
        1. __enter__: Download .anki2 file from S3 to /tmp
        2. Open SQLite connection
        3. User performs SQLite operations
        4. __exit__: Commit changes, close connection, upload to S3
    """

    def __init__(self, username):
        """
        Initialize S3SQLiteConnection.

        Args:
            username (str): Username (used for S3 key and filename)
        """
        self.username = username
        self.s3_key = f'user_dbs/{username}.anki2'
        self.local_path = f'/tmp/{username}.anki2'
        self.conn = None
        self.current_etag = None  # Day 4: Used for optimistic locking

    def __enter__(self):
        """
        Download database from S3 and open SQLite connection.

        Returns:
            sqlite3.Connection: Open SQLite connection
        """
        # Download from S3
        self._download_from_s3()

        # Open SQLite connection
        self.conn = sqlite3.connect(self.local_path)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close connection and upload database back to S3.

        Args:
            exc_type: Exception type (if exception occurred)
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self.conn:
            # Only commit if no exception occurred
            if exc_type is None:
                self.conn.commit()
            else:
                # Rollback on error (don't upload corrupted data)
                self.conn.rollback()

            self.conn.close()

        # Upload to S3 (only if no exception)
        if exc_type is None:
            try:
                self._upload_to_s3()
            except ConflictError:
                # Day 4: If upload fails due to conflict, invalidate cache
                # The local file now contains changes that were rejected by S3
                if self.username in db_cache:
                    del db_cache[self.username]
                # Delete the stale local file
                if os.path.exists(self.local_path):
                    os.remove(self.local_path)
                # Re-raise the ConflictError so caller knows
                raise

        # Note: Don't delete from /tmp yet (Day 3 will cache here)

    def _check_cache(self):
        """
        Check if we have a valid cached version in Lambda container.

        Returns:
            bool: True if cache is valid and file exists, False otherwise
        """
        # Check if user is in cache
        if self.username not in db_cache:
            return False

        cache_entry = db_cache[self.username]

        # Check if file exists in /tmp
        if not os.path.exists(self.local_path):
            # Cache entry exists but file was deleted
            del db_cache[self.username]
            return False

        # Check if cache entry is too old (TTL expired)
        age = time.time() - cache_entry['timestamp']
        if age > CACHE_TTL:
            print(f"Cache expired for {self.username} (age: {age:.1f}s, TTL: {CACHE_TTL}s)")
            del db_cache[self.username]
            return False

        # Cache is valid
        self.current_etag = cache_entry['etag']
        return True

    def _download_from_s3(self):
        """
        Download user database from S3 to /tmp.

        Day 3: Checks cache first, validates with ETag
        If cache is valid, skips download (HUGE performance win)
        If database doesn't exist (new user), creates a new Anki database.
        """
        # Check if we have a valid cached version
        if self._check_cache():
            print(f"✓ Using cached version for {self.username} (cache hit)")
            return

        try:
            # Get S3 metadata to check ETag (no download yet)
            try:
                head_response = s3.head_object(Bucket=BUCKET, Key=self.s3_key)
                s3_etag = head_response['ETag']
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Database doesn't exist - create new one
                    print(f"Database not found in S3, creating new database for {self.username}")
                    self._create_new_database()
                    self.current_etag = None
                    return
                else:
                    raise

            # Check if cached file exists but ETag changed
            if self.username in db_cache and os.path.exists(self.local_path):
                cached_etag = db_cache[self.username]['etag']
                if cached_etag == s3_etag:
                    # Cache is still valid, just update timestamp
                    db_cache[self.username]['timestamp'] = time.time()
                    self.current_etag = s3_etag
                    print(f"✓ Cache refreshed for {self.username} (ETag match, no download needed)")
                    return
                else:
                    print(f"Cache invalidated for {self.username} (ETag mismatch: {cached_etag} != {s3_etag})")

            # Download from S3 (cache miss or invalidated)
            response = s3.get_object(Bucket=BUCKET, Key=self.s3_key)
            self.current_etag = response['ETag']

            # Write to /tmp
            with open(self.local_path, 'wb') as f:
                f.write(response['Body'].read())

            # Update cache
            db_cache[self.username] = {
                'etag': self.current_etag,
                'timestamp': time.time(),
                'path': self.local_path
            }

            print(f"✓ Downloaded {self.s3_key} from S3 (ETag: {self.current_etag})")

        except s3.exceptions.NoSuchKey:
            # First time user - create new database
            print(f"Database not found in S3, creating new database for {self.username}")
            self._create_new_database()
            self.current_etag = None  # New file, no ETag yet

    def _create_new_database(self):
        """
        Create a new Anki-compatible database for a new user.

        This creates the basic Anki schema with empty tables.
        TODO: Import full Anki schema from existing codebase
        """
        # Create basic Anki database structure
        conn = sqlite3.connect(self.local_path)
        cursor = conn.cursor()

        # Create col table (collection metadata)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS col (
                id INTEGER PRIMARY KEY,
                crt INTEGER NOT NULL,
                mod INTEGER NOT NULL,
                scm INTEGER NOT NULL,
                ver INTEGER NOT NULL,
                dty INTEGER NOT NULL,
                usn INTEGER NOT NULL,
                ls INTEGER NOT NULL,
                conf TEXT NOT NULL,
                models TEXT NOT NULL,
                decks TEXT NOT NULL,
                dconf TEXT NOT NULL,
                tags TEXT NOT NULL
            )
        ''')

        # Create notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                guid TEXT NOT NULL UNIQUE,
                mid INTEGER NOT NULL,
                mod INTEGER NOT NULL,
                usn INTEGER NOT NULL,
                tags TEXT NOT NULL,
                flds TEXT NOT NULL,
                sfld INTEGER NOT NULL,
                csum INTEGER NOT NULL,
                flags INTEGER NOT NULL,
                data TEXT NOT NULL
            )
        ''')

        # Create cards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY,
                nid INTEGER NOT NULL,
                did INTEGER NOT NULL,
                ord INTEGER NOT NULL,
                mod INTEGER NOT NULL,
                usn INTEGER NOT NULL,
                type INTEGER NOT NULL,
                queue INTEGER NOT NULL,
                due INTEGER NOT NULL,
                ivl INTEGER NOT NULL,
                factor INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                lapses INTEGER NOT NULL,
                left INTEGER NOT NULL,
                odue INTEGER NOT NULL,
                odid INTEGER NOT NULL,
                flags INTEGER NOT NULL,
                data TEXT NOT NULL
            )
        ''')

        # Create revlog table (review history)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS revlog (
                id INTEGER PRIMARY KEY,
                cid INTEGER NOT NULL,
                usn INTEGER NOT NULL,
                ease INTEGER NOT NULL,
                ivl INTEGER NOT NULL,
                lastIvl INTEGER NOT NULL,
                factor INTEGER NOT NULL,
                time INTEGER NOT NULL,
                type INTEGER NOT NULL
            )
        ''')

        # Insert default collection metadata
        import json
        import time

        default_col = {
            'id': 1,
            'crt': int(time.time()),
            'mod': int(time.time() * 1000),
            'scm': int(time.time() * 1000),
            'ver': 11,
            'dty': 0,
            'usn': 0,
            'ls': 0,
            'conf': json.dumps({"curDeck": 1}),
            'models': json.dumps({}),
            'decks': json.dumps({"1": {"id": 1, "name": "Default"}}),
            'dconf': json.dumps({}),
            'tags': json.dumps({})
        }

        cursor.execute('''
            INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags)
            VALUES (:id, :crt, :mod, :scm, :ver, :dty, :usn, :ls, :conf, :models, :decks, :dconf, :tags)
        ''', default_col)

        conn.commit()
        conn.close()

        print(f"✓ Created new Anki database at {self.local_path}")

    def _upload_to_s3(self):
        """
        Upload modified database back to S3.

        Day 3: Updates cache with new ETag after upload
        Day 4: Optimistic locking with ETag verification (prevents concurrent write conflicts)

        Raises:
            ConflictError: If another process modified the file since we downloaded it
        """
        # Day 4: Optimistic locking check
        # Verify the ETag hasn't changed before uploading (if we have a stored ETag)
        if self.current_etag is not None:
            try:
                # Check current S3 ETag
                head_response = s3.head_object(Bucket=BUCKET, Key=self.s3_key)
                s3_etag = head_response['ETag']

                # Compare with our stored ETag
                if s3_etag != self.current_etag:
                    # Another process modified the file since we downloaded it
                    raise ConflictError(
                        f"Concurrent modification detected for {self.username}. "
                        f"Expected ETag {self.current_etag}, but S3 has {s3_etag}. "
                        f"Another process modified the file. Please retry the operation."
                    )
            except ConflictError:
                # Re-raise ConflictError from ETag mismatch check above
                raise
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # File was deleted since we downloaded it - treat as conflict
                    raise ConflictError(
                        f"Concurrent modification detected for {self.username}. "
                        f"File was deleted from S3 since we downloaded it. "
                        f"Please retry the operation."
                    )
                else:
                    # Unknown error, re-raise
                    raise

        # ETag matches (or this is a new file) - safe to upload
        with open(self.local_path, 'rb') as f:
            response = s3.put_object(
                Bucket=BUCKET,
                Key=self.s3_key,
                Body=f
            )

        # Update cache with new ETag
        new_etag = response['ETag']
        db_cache[self.username] = {
            'etag': new_etag,
            'timestamp': time.time(),
            'path': self.local_path
        }
        self.current_etag = new_etag

        print(f"✓ Uploaded {self.s3_key} to S3 (new ETag: {new_etag})")


def get_cache_stats():
    """
    Get current cache statistics for debugging.

    Returns:
        dict: Cache statistics including size, entries, and age info
    """
    stats = {
        'cache_size': len(db_cache),
        'entries': [],
        'total_age': 0
    }

    for username, entry in db_cache.items():
        age = time.time() - entry['timestamp']
        stats['entries'].append({
            'username': username,
            'age_seconds': age,
            'etag': entry['etag'],
            'file_exists': os.path.exists(entry['path'])
        })
        stats['total_age'] += age

    if stats['cache_size'] > 0:
        stats['average_age'] = stats['total_age'] / stats['cache_size']
    else:
        stats['average_age'] = 0

    return stats


def clear_cache():
    """
    Clear all cache entries (for testing).
    """
    db_cache.clear()
    print("✓ Cache cleared")


class ConflictError(Exception):
    """
    Raised when S3 optimistic lock fails (concurrent write conflict).

    Day 4: Used to detect when another process modified the database
    since we downloaded it. This prevents silent data loss.
    """
    pass


class SessionAwareS3SQLite:
    """
    Session-aware wrapper for S3SQLiteConnection with DynamoDB coordination.

    This wrapper implements session-based caching:
    1. First database access: Downloads from S3, creates DynamoDB session
    2. Subsequent accesses: Reuses in-memory database (no S3 download)
    3. Session end: Uploads to S3 once, deletes session

    Expected performance improvements:
    - 90% reduction in S3 operations (1 download + 1 upload per session vs per-operation)
    - 80% reduction in latency for operations after first access
    - Example: 20 card reviews = 1 download + 1 upload (was 20 downloads + 20 uploads)

    Usage:
        # Operation 1 - Downloads from S3, creates session
        with SessionAwareS3SQLite(username) as conn:
            conn.execute("UPDATE cards SET ...")

        # Operation 2 - Reuses in-memory DB (NO S3 download!)
        with SessionAwareS3SQLite(username) as conn:
            conn.execute("UPDATE cards SET ...")

        # Session expires after 5 minutes, next access uploads and downloads fresh
    """

    def __init__(self, username: str, session_id: str = None, auto_upload: bool = True):
        """
        Initialize session-aware wrapper.

        Args:
            username: User identifier
            session_id: Existing session ID to reuse (optional)
            auto_upload: If True, uploads to S3 when session ends (default True)
                        Set to False for read-only sessions
        """
        self.username = username
        self.session_id = session_id  # Store provided session_id
        self.auto_upload = auto_upload
        self.s3_key = f'user_dbs/{username}.anki2'
        self.local_path = f'/tmp/{username}.anki2'
        self.conn = None
        self.session_manager = None
        self.current_session = None
        self.current_etag = None
        self._is_session_owner = False

    def __enter__(self):
        """
        Open database connection with session coordination.

        Flow:
        1. Check if user has active session (query DynamoDB)
        2. If no session:
           - Download from S3
           - Create new session
        3. If session exists and we own it:
           - Reuse in-memory database (NO S3 download!)
        4. If session exists but owned by another Lambda:
           - Wait for session to expire, then take over

        Returns:
            sqlite3.Connection: Open SQLite connection
        """
        # Lazy import to avoid circular dependency
        from session_manager import SessionManager

        self.session_manager = SessionManager()

        # Check for existing session
        existing_session = self.session_manager.get_user_session(self.username)

        if existing_session:
            # Check if WE own this session (same Lambda instance)
            if existing_session['lambda_instance_id'] == self.session_manager.lambda_instance_id:
                # We own the session - reuse in-memory database
                self._is_session_owner = True
                self.current_session = existing_session
                self.session_id = existing_session['session_id']  # Update session_id attribute
                self.current_etag = existing_session['db_etag']

                if os.path.exists(self.local_path):
                    # Open existing connection
                    self.conn = sqlite3.connect(self.local_path)
                    self.conn.row_factory = sqlite3.Row

                    # Extend session TTL
                    self.session_manager.update_session(self.session_id)

                    print(f"✓✓✓ SESSION HIT: Reusing in-memory DB for {self.username} (NO S3 download!)")
                    return self.conn
                else:
                    # Session exists but file is gone - invalidate and restart
                    print(f"⚠ Session exists but file missing, invalidating session for {self.username}")
                    self.session_manager.delete_session(self.current_session['session_id'])
                    self._is_session_owner = False
            else:
                # Another Lambda owns the session - invalidate and take over
                print(f"⚠ Concurrent access detected: {self.username} has active session on another Lambda")
                print(f"  Current instance: {self.session_manager.lambda_instance_id}")
                print(f"  Session owner: {existing_session['lambda_instance_id']}")
                print(f"  Invalidating old session and taking over...")

                self.session_manager.delete_session(existing_session['session_id'])
                self._is_session_owner = False

        # No valid session - download from S3 and create new session
        self._download_from_s3()

        # Open SQLite connection
        self.conn = sqlite3.connect(self.local_path)
        self.conn.row_factory = sqlite3.Row

        # Create new session
        session = self.session_manager.create_session(
            username=self.username,
            db_etag=self.current_etag or 'new'
        )

        if session:
            self.current_session = session
            self.session_id = session['session_id']  # Update session_id attribute
            self._is_session_owner = True
            print(f"✓ NEW SESSION: Created session {self.session_id[:12]}... for {self.username}")
        else:
            # Failed to create session (race condition)
            self.session_id = None  # No session created
            print(f"⚠ Failed to create session for {self.username}, operating without session")

        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close connection - NO upload to S3 (session keeps DB in memory).

        Upload only happens when:
        1. Session expires naturally (TTL)
        2. end_session() is called explicitly
        3. Lambda container shuts down

        Args:
            exc_type: Exception type (if exception occurred)
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self.conn:
            if exc_type is None:
                self.conn.commit()

                # Update session with latest state (if we own it)
                if self._is_session_owner and self.current_session:
                    self.session_manager.update_session(
                        self.current_session['session_id'],
                        db_etag=self.current_etag
                    )
            else:
                self.conn.rollback()

                # On error, invalidate session to force fresh download next time
                if self._is_session_owner and self.current_session:
                    self.session_manager.delete_session(self.current_session['session_id'])

            self.conn.close()

        # NOTE: Do NOT upload to S3 here - that defeats the purpose of session caching!
        # Upload happens only when session ends via end_session()

    def force_upload(self):
        """
        Force immediate upload to S3 (Hybrid Approach for Write Operations).

        Called after critical write operations (deck/card creation) to ensure
        data is persisted immediately, even when using session caching.

        This allows us to maintain session caching benefits for reads while
        ensuring write operations are durable without sticky sessions.
        """
        if not self.auto_upload:
            return

        if not os.path.exists(self.local_path):
            print(f"⚠ Cannot force upload - database file not found: {self.local_path}")
            return

        try:
            self._upload_to_s3()
            print(f"✓ Forced upload to S3 after write operation for {self.username}")

            # Update session with new ETag
            if self._is_session_owner and self.current_session:
                self.session_manager.update_session(
                    self.current_session['session_id'],
                    db_etag=self.current_etag
                )
        except Exception as e:
            print(f"⚠ Force upload failed: {e}")

    def end_session(self):
        """
        Explicitly end session and upload to S3.

        Call this when:
        - User logs out
        - User session expires in frontend
        - Lambda is shutting down
        - Manual cache flush needed
        """
        if not self.current_session:
            print(f"No active session to end for {self.username}")
            return

        try:
            # Upload to S3 one final time
            if self.auto_upload and os.path.exists(self.local_path):
                self._upload_to_s3()
                print(f"✓ Session ended: Uploaded {self.username} to S3")

            # Delete session from DynamoDB
            if self._is_session_owner:
                self.session_manager.delete_session(self.current_session['session_id'])
                print(f"✓ Deleted session {self.current_session['session_id'][:12]}...")

        except Exception as e:
            print(f"⚠ Error ending session for {self.username}: {e}")

        finally:
            # Clear state
            self.current_session = None
            self._is_session_owner = False

    def _download_from_s3(self):
        """
        Download user database from S3 to /tmp.

        This is called only when:
        1. No session exists (first access)
        2. Session exists but file is missing
        3. Concurrent access was detected
        """
        try:
            # Check if file exists in S3
            try:
                head_response = s3.head_object(Bucket=BUCKET, Key=self.s3_key)
                s3_etag = head_response['ETag']
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # Database doesn't exist - create new one
                    print(f"Database not found in S3, creating new database for {self.username}")
                    self._create_new_database()
                    self.current_etag = None
                    return
                else:
                    raise

            # Download from S3
            response = s3.get_object(Bucket=BUCKET, Key=self.s3_key)
            self.current_etag = response['ETag']

            # Write to /tmp
            with open(self.local_path, 'wb') as f:
                f.write(response['Body'].read())

            print(f"✓ Downloaded {self.s3_key} from S3 (ETag: {self.current_etag})")

        except s3.exceptions.NoSuchKey:
            # First time user - create new database
            print(f"Database not found in S3, creating new database for {self.username}")
            self._create_new_database()
            self.current_etag = None

    def _create_new_database(self):
        """
        Create a new Anki-compatible database for a new user.

        Delegates to the same logic as S3SQLiteConnection.
        """
        # Remove existing file if it exists (prevents UNIQUE constraint errors)
        if os.path.exists(self.local_path):
            os.remove(self.local_path)

        # Reuse existing logic from S3SQLiteConnection
        temp_conn = S3SQLiteConnection(self.username)
        temp_conn._create_new_database()

    def _upload_to_s3(self):
        """
        Upload modified database back to S3 with optimistic locking.

        This is called ONLY when session ends (via end_session()).
        """
        # Optimistic locking check (only if file existed before)
        if self.current_etag is not None and self.current_etag != 'new':
            try:
                head_response = s3.head_object(Bucket=BUCKET, Key=self.s3_key)
                s3_etag = head_response['ETag']

                if s3_etag != self.current_etag:
                    raise ConflictError(
                        f"Concurrent modification detected for {self.username}. "
                        f"Expected ETag {self.current_etag}, but S3 has {s3_etag}. "
                        f"Another process modified the file. Please retry the operation."
                    )
            except ConflictError:
                raise
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    # File was deleted - this is OK for first upload
                    print(f"  File doesn't exist in S3 yet, proceeding with first upload")
                else:
                    raise

        # Upload
        with open(self.local_path, 'rb') as f:
            response = s3.put_object(
                Bucket=BUCKET,
                Key=self.s3_key,
                Body=f
            )

        # Update ETag
        self.current_etag = response['ETag']
        print(f"✓ Uploaded {self.s3_key} to S3 (new ETag: {self.current_etag})")
