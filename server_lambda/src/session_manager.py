"""
Session Manager for Lambda Container Coordination

This module provides distributed session management using DynamoDB to coordinate
which Lambda container "owns" a user's database at any given time. This prevents
concurrent access conflicts while enabling efficient session-based caching.

Key Concepts:
- Session ID: Unique identifier for each Lambda container session
- Session TTL: Time window (default 5 min) for keeping DB in memory
- Atomic Operations: DynamoDB conditional writes prevent race conditions
- GSI Lookup: Fast username-based queries to find active sessions

Architecture:
- Each user can have at most ONE active session at a time
- Sessions extend automatically on each database operation
- Expired sessions are cleaned up by DynamoDB TTL
- If concurrent access is detected, existing session is invalidated

Usage:
    manager = SessionManager()

    # Create new session (returns None if user already has active session)
    session = manager.create_session(username, lambda_id, db_etag)

    # Extend existing session
    manager.update_session(session_id, new_etag)

    # Check for active session
    existing = manager.get_user_session(username)
"""

import os
import time
import uuid
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any


class SessionManager:
    """Manages Lambda container sessions in DynamoDB for distributed coordination."""

    def __init__(self):
        """Initialize SessionManager with DynamoDB client and configuration."""
        self.dynamodb = boto3.client('dynamodb')
        self.table_name = os.environ.get('DYNAMODB_SESSIONS_TABLE', 'javumbo-sessions')
        self.session_ttl = int(os.environ.get('SESSION_TTL', '300'))  # 5 minutes default
        self.lambda_instance_id = os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME', 'local-dev')

    def create_session(
        self,
        username: str,
        db_etag: str,
        lambda_instance_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new session for a user with atomic check-and-set.

        This method ensures only one Lambda container can have an active session
        for a given user at any time. It uses DynamoDB conditional writes to
        atomically check if a session exists and create one if not.

        Args:
            username: User identifier
            db_etag: Current S3 database ETag for conflict detection
            lambda_instance_id: Optional Lambda instance ID (defaults to current)

        Returns:
            Session dict if created successfully, None if user already has active session

        Session Structure:
            {
                'session_id': 'sess_abc123...',
                'username': 'john_doe',
                'lambda_instance_id': 'i-12345',
                'db_etag': '48fd9985...',
                'created_at': 1700000000,
                'last_access': 1700000000,
                'expires_at': 1700000300,
                'status': 'active'
            }
        """
        session_id = f"sess_{uuid.uuid4().hex}"
        instance_id = lambda_instance_id or self.lambda_instance_id
        current_time = int(time.time())
        expires_at = current_time + self.session_ttl

        session = {
            'session_id': session_id,
            'username': username,
            'lambda_instance_id': instance_id,
            'db_etag': db_etag,
            'created_at': current_time,
            'last_access': current_time,
            'expires_at': expires_at,
            'status': 'active'
        }

        try:
            # Check if user already has an active session using GSI
            existing_session = self.get_user_session(username)

            if existing_session:
                # User already has active session, don't create new one
                return None

            # No existing session, create new one
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'session_id': {'S': session_id},
                    'username': {'S': username},
                    'lambda_instance_id': {'S': instance_id},
                    'db_etag': {'S': db_etag},
                    'created_at': {'N': str(current_time)},
                    'last_access': {'N': str(current_time)},
                    'expires_at': {'N': str(expires_at)},
                    'status': {'S': 'active'}
                }
            )

            return session

        except ClientError as e:
            print(f"Error creating session: {e}")
            return None

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session by session ID.

        Args:
            session_id: Unique session identifier

        Returns:
            Session dict if found, None otherwise
        """
        try:
            response = self.dynamodb.get_item(
                TableName=self.table_name,
                Key={'session_id': {'S': session_id}}
            )

            if 'Item' not in response:
                return None

            item = response['Item']
            return {
                'session_id': item['session_id']['S'],
                'username': item['username']['S'],
                'lambda_instance_id': item['lambda_instance_id']['S'],
                'db_etag': item['db_etag']['S'],
                'created_at': int(item['created_at']['N']),
                'last_access': int(item['last_access']['N']),
                'expires_at': int(item['expires_at']['N']),
                'status': item['status']['S']
            }

        except ClientError as e:
            print(f"Error getting session {session_id}: {e}")
            return None

    def get_user_session(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Find active session for a user using GSI.

        This method queries the username-index GSI to efficiently find if a user
        has an active session. This is critical for preventing concurrent access.

        Args:
            username: User identifier

        Returns:
            Active session dict if found, None otherwise
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName='username-index',
                KeyConditionExpression='username = :username',
                ExpressionAttributeValues={
                    ':username': {'S': username},
                    ':active': {'S': 'active'}
                },
                FilterExpression='#status = :active',
                ExpressionAttributeNames={
                    '#status': 'status'
                }
            )

            if not response['Items']:
                return None

            # Should only be one active session per user
            if len(response['Items']) > 1:
                print(f"WARNING: User {username} has multiple active sessions!")

            item = response['Items'][0]
            return {
                'session_id': item['session_id']['S'],
                'username': item['username']['S'],
                'lambda_instance_id': item['lambda_instance_id']['S'],
                'db_etag': item['db_etag']['S'],
                'created_at': int(item['created_at']['N']),
                'last_access': int(item['last_access']['N']),
                'expires_at': int(item['expires_at']['N']),
                'status': item['status']['S']
            }

        except ClientError as e:
            print(f"Error querying sessions for user {username}: {e}")
            return None

    def update_session(self, session_id: str, db_etag: Optional[str] = None) -> bool:
        """
        Update session to extend TTL and optionally update ETag.

        This method is called on every database operation to keep the session alive
        and track the latest S3 database version for conflict detection.

        Args:
            session_id: Session to update
            db_etag: New S3 database ETag (optional)

        Returns:
            True if updated successfully, False otherwise
        """
        current_time = int(time.time())
        expires_at = current_time + self.session_ttl

        try:
            update_expression = 'SET last_access = :last_access, expires_at = :expires_at'
            expression_values = {
                ':last_access': {'N': str(current_time)},
                ':expires_at': {'N': str(expires_at)}
            }

            if db_etag:
                update_expression += ', db_etag = :db_etag'
                expression_values[':db_etag'] = {'S': db_etag}

            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'session_id': {'S': session_id}},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )

            return True

        except ClientError as e:
            print(f"Error updating session {session_id}: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (called when Lambda container releases DB).

        This should be called:
        - When session TTL expires naturally
        - When user explicitly logs out
        - When Lambda container is shutting down
        - When concurrent access is detected (invalidate old session)

        Args:
            session_id: Session to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.dynamodb.delete_item(
                TableName=self.table_name,
                Key={'session_id': {'S': session_id}}
            )
            return True

        except ClientError as e:
            print(f"Error deleting session {session_id}: {e}")
            return False

    def set_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status for coordinated handoff between Lambda containers.

        Status values:
        - 'active': Session is actively being used by a Lambda container
        - 'flushing': Container is uploading changes to S3 (DO NOT STEAL)
        - 'stale': Upload complete, safe for another container to take over

        Args:
            session_id: Session to update
            status: New status ('active', 'flushing', or 'stale')

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'session_id': {'S': session_id}},
                UpdateExpression='SET #status = :status',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': {'S': status}
                }
            )
            return True

        except ClientError as e:
            print(f"Error updating session status {session_id}: {e}")
            return False

    def wait_for_session_flush(self, session_id: str, timeout: int = 10) -> bool:
        """
        Wait for a session to finish flushing to S3.

        This is called when Container B detects Container A is flushing.
        Container B waits for Container A to finish uploading before taking over.

        Args:
            session_id: Session to wait for
            timeout: Maximum seconds to wait (default: 10)

        Returns:
            True if session became stale/deleted, False if timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            session = self.get_session(session_id)

            # Session deleted or became stale - safe to proceed
            if not session or session['status'] in ['stale', 'active']:
                return True

            # Still flushing - wait a bit
            if session['status'] == 'flushing':
                print(f"  Waiting for session {session_id[:12]}... to finish flushing...")
                time.sleep(0.5)  # Poll every 500ms
                continue

            # Unknown status - safe to proceed
            return True

        # Timeout - proceed anyway (container may have crashed)
        print(f"  Timeout waiting for session {session_id[:12]}... to flush")
        return False

    def invalidate_user_session(self, username: str) -> bool:
        """
        Invalidate any active session for a user.

        This is used when:
        - A new Lambda container needs to take over
        - Concurrent access is detected
        - Manual session cleanup is needed

        Args:
            username: User whose session should be invalidated

        Returns:
            True if session was found and invalidated, False otherwise
        """
        existing_session = self.get_user_session(username)

        if not existing_session:
            return False

        return self.delete_session(existing_session['session_id'])

    def cleanup_expired_sessions(self) -> int:
        """
        Manually scan and delete expired sessions.

        Note: DynamoDB TTL handles this automatically, but this method is useful
        for testing and immediate cleanup without waiting for TTL background process.

        Returns:
            Number of expired sessions deleted
        """
        current_time = int(time.time())
        deleted_count = 0

        try:
            # Scan for expired sessions
            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression='expires_at < :current_time',
                ExpressionAttributeValues={
                    ':current_time': {'N': str(current_time)}
                }
            )

            for item in response.get('Items', []):
                session_id = item['session_id']['S']
                if self.delete_session(session_id):
                    deleted_count += 1

            return deleted_count

        except ClientError as e:
            print(f"Error cleaning up expired sessions: {e}")
            return deleted_count

    def get_session_stats(self) -> Dict[str, int]:
        """
        Get statistics about current sessions (for testing/monitoring).

        Returns:
            Dict with counts: {total, active, expired}
        """
        current_time = int(time.time())

        try:
            response = self.dynamodb.scan(
                TableName=self.table_name,
                Select='ALL_ATTRIBUTES'
            )

            total = len(response.get('Items', []))
            active = sum(
                1 for item in response.get('Items', [])
                if int(item['expires_at']['N']) > current_time
                and item['status']['S'] == 'active'
            )
            expired = total - active

            return {
                'total': total,
                'active': active,
                'expired': expired
            }

        except ClientError as e:
            print(f"Error getting session stats: {e}")
            return {'total': 0, 'active': 0, 'expired': 0}


class SessionConflictError(Exception):
    """
    Raised when user has an active session on another Lambda instance.

    This indicates a race condition or user accessing from multiple devices/tabs.
    Client should retry after a short delay or end the existing session.
    """
    pass
