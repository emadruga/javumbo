from base_repository import BaseRepository
# We'll need password hashing later
from werkzeug.security import check_password_hash #, generate_password_hash 
import sqlite3

# Define database names as constants
SYSADMIN_DB = 'sysadmin.db'
ADMIN_DB = 'admin.db'

class UserRepository(BaseRepository):

    def __init__(self):
        # Potentially initialize connections here if needed immediately,
        # or rely on lazy connection in _get_connection
        pass

    def find_sysadmin_by_username(self, username):
        """Finds a sysadmin user by their username in the sysadmin.db."""
        query = "SELECT * FROM admins WHERE username = ?"
        # Need to ensure sysadmin.db and the admins table exist first.
        # We will create the DB initialization script next.
        try:
            # Returns a Row object or None
            return self._execute_query(SYSADMIN_DB, query, (username,), fetch_one=True)
        except Exception as e:
            # Specifically catch DB errors if the table/db doesn't exist yet
            print(f"Error finding sysadmin {username}: {e}. DB/Table might not exist yet.")
            return None

    # TODO: Add method to verify sysadmin password using hashing
    def verify_sysadmin_password(self, password_hash_from_db, provided_password):
        """Verifies the provided password against the stored hash."""
        return check_password_hash(password_hash_from_db, provided_password)

    def get_all_regular_users(self):
        """Retrieves all regular users from the main admin.db."""
        # Schema based on ADMIN_DB_SCHEMA.md (assuming a 'users' table)
        # Changed 'id' to 'user_id' based on assumption
        # Removed 'last_review_timestamp' as column does not exist
        query = "SELECT user_id, username, name FROM users ORDER BY name ASC" 
        try:
            users = self._execute_query(ADMIN_DB, query)
            # Convert Row objects to dictionaries for easier JSON serialization
            return [dict(user) for user in users] if users else []
        except sqlite3.OperationalError as e:
            print(f"Database operational error getting regular users: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting regular users: {e}")
            return [] # Return empty list on error

    # Method to find a single regular user by username
    def find_regular_user_by_username(self, username):
        """Finds a single regular user by username in admin.db and returns their data (including user_id)."""
        query = "SELECT user_id, username, name FROM users WHERE username = ? LIMIT 1"
        try:
            user = self._execute_query(ADMIN_DB, query, (username,), fetch_one=True)
            return dict(user) if user else None # Return as dict or None
        except sqlite3.OperationalError as e:
            print(f"Database operational error finding regular user {username}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error finding regular user {username}: {e}")
            return None

    # TODO: Add methods for creating, updating, deleting regular users
    # TODO: Add methods for managing user-specific Anki DBs

    def close_all_connections(self):
        """Closes all managed database connections."""
        # Iterate through the known DBs this repository might use
        for db_name in [SYSADMIN_DB, ADMIN_DB]: 
             # Potentially track all actively opened connections instead
            self._close_connection(db_name)

# Instantiate repository (could use dependency injection later)
user_repository = UserRepository() 