"""
UserRepository - DynamoDB-based user management

This module provides user authentication and management using DynamoDB,
replacing the SQLite-based admin.db from the monolithic application.

Day 5 Version: Basic CRUD operations for user authentication
"""

import boto3
import os
import bcrypt
from botocore.exceptions import ClientError
from datetime import datetime

# DynamoDB client (reused across invocations)
dynamodb = boto3.resource('dynamodb')

# Get table name from environment variable
USERS_TABLE = os.environ.get('DYNAMODB_USERS_TABLE', 'javumbo-users')

# Get DynamoDB table
users_table = dynamodb.Table(USERS_TABLE)


class UserRepository:
    """
    Repository for user authentication and management.

    Replaces admin.db SQLite database with DynamoDB.

    Usage:
        repo = UserRepository()

        # Create new user
        repo.create_user('alice', 'Alice Smith', 'password123')

        # Authenticate user
        if repo.authenticate('alice', 'password123'):
            user = repo.get_user('alice')
            print(f"Welcome {user['name']}!")

    DynamoDB Schema:
        Table: javumbo-users
        Partition Key: username (S)

        Item Structure:
        {
            'username': 'alice',          # Primary key
            'name': 'Alice Smith',        # Display name
            'password_hash': '$2b$12...', # bcrypt hash
            'created_at': '2025-01-15...',# ISO timestamp
            'updated_at': '2025-01-15...'# ISO timestamp (optional)
        }
    """

    def __init__(self):
        """Initialize UserRepository."""
        self.table = users_table

    def create_user(self, username, name, password):
        """
        Create a new user in DynamoDB.

        Args:
            username (str): Username (must be unique)
            name (str): User's display name
            password (str): Plain text password (will be hashed)

        Returns:
            dict: Created user item (without password_hash)

        Raises:
            UserAlreadyExistsError: If username already exists
        """
        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # Create user item
        now = datetime.utcnow().isoformat()
        user_item = {
            'username': username,
            'name': name,
            'password_hash': password_hash,
            'created_at': now
        }

        # Put item with conditional check (username must not exist)
        try:
            self.table.put_item(
                Item=user_item,
                ConditionExpression='attribute_not_exists(username)'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise UserAlreadyExistsError(f"Username '{username}' already exists")
            else:
                raise

        # Return user data (without password_hash)
        return {
            'username': username,
            'name': name,
            'created_at': now
        }

    def get_user(self, username):
        """
        Get user by username.

        Args:
            username (str): Username to look up

        Returns:
            dict: User data (without password_hash), or None if not found
        """
        try:
            response = self.table.get_item(
                Key={'username': username}
            )

            if 'Item' not in response:
                return None

            user = response['Item']

            # Return user data without password_hash
            return {
                'username': user['username'],
                'name': user['name'],
                'created_at': user.get('created_at'),
                'updated_at': user.get('updated_at')
            }
        except ClientError:
            return None

    def authenticate(self, username, password):
        """
        Authenticate user with username and password.

        Args:
            username (str): Username
            password (str): Plain text password to verify

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={'username': username}
            )

            if 'Item' not in response:
                return False

            user = response['Item']
            password_hash = user['password_hash']

            # Verify password with bcrypt
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except ClientError:
            return False

    def update_user(self, username, name=None, password=None):
        """
        Update user information.

        Args:
            username (str): Username to update
            name (str, optional): New display name
            password (str, optional): New plain text password (will be hashed)

        Returns:
            dict: Updated user data, or None if user not found

        Raises:
            UserNotFoundError: If username doesn't exist
        """
        # Build update expression
        update_expr_parts = []
        expr_attr_values = {}
        expr_attr_names = {}

        if name is not None:
            update_expr_parts.append('#name = :name')
            expr_attr_names['#name'] = 'name'
            expr_attr_values[':name'] = name

        if password is not None:
            password_hash = bcrypt.hashpw(
                password.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            update_expr_parts.append('password_hash = :password_hash')
            expr_attr_values[':password_hash'] = password_hash

        if not update_expr_parts:
            # Nothing to update
            return self.get_user(username)

        # Add updated_at timestamp
        update_expr_parts.append('updated_at = :updated_at')
        expr_attr_values[':updated_at'] = datetime.utcnow().isoformat()

        update_expr = 'SET ' + ', '.join(update_expr_parts)

        # Update item with conditional check (username must exist)
        try:
            update_kwargs = {
                'Key': {'username': username},
                'UpdateExpression': update_expr,
                'ExpressionAttributeValues': expr_attr_values,
                'ConditionExpression': 'attribute_exists(username)',
                'ReturnValues': 'ALL_NEW'
            }

            # Only add ExpressionAttributeNames if we have any
            if expr_attr_names:
                update_kwargs['ExpressionAttributeNames'] = expr_attr_names

            response = self.table.update_item(**update_kwargs)

            user = response['Attributes']

            # Return user data without password_hash
            return {
                'username': user['username'],
                'name': user['name'],
                'created_at': user.get('created_at'),
                'updated_at': user.get('updated_at')
            }
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise UserNotFoundError(f"Username '{username}' not found")
            else:
                raise

    def delete_user(self, username):
        """
        Delete user from DynamoDB.

        Args:
            username (str): Username to delete

        Returns:
            bool: True if deleted, False if user not found
        """
        try:
            self.table.delete_item(
                Key={'username': username},
                ConditionExpression='attribute_exists(username)'
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False  # User doesn't exist
            else:
                raise

    def list_users(self, limit=100):
        """
        List all users (paginated).

        Args:
            limit (int): Maximum number of users to return

        Returns:
            list: List of user dicts (without password_hash)
        """
        try:
            response = self.table.scan(
                Limit=limit,
                ProjectionExpression='username, #name, created_at, updated_at',
                ExpressionAttributeNames={'#name': 'name'}
            )

            users = response.get('Items', [])

            return [
                {
                    'username': user['username'],
                    'name': user['name'],
                    'created_at': user.get('created_at'),
                    'updated_at': user.get('updated_at')
                }
                for user in users
            ]
        except ClientError:
            return []


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""
    pass


class UserNotFoundError(Exception):
    """Raised when attempting to update a user that doesn't exist."""
    pass
