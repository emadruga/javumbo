import sqlite3
import os

class BaseRepository:
    _connections = {}

    def _get_connection(self, db_name):
        """Gets a connection to the specified database, creating it if necessary."""
        if db_name not in self._connections or self._connections[db_name] is None:
            try:
                # Construct the absolute path relative to the project root
                # Assumes admin_server is one level down from the project root
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                
                if db_name == 'sysadmin.db':
                    # Sysadmin DB is within admin_server
                    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', db_name))
                elif db_name == 'admin.db':
                    # Admin DB (for regular users) is in server/
                    db_path = os.path.join(project_root, 'server', db_name)
                else:
                    # Assume it's a user-specific Anki DB in server/user_dbs/
                    db_path = os.path.join(project_root, 'server', 'user_dbs', db_name)

                # Ensure the directory exists for sysadmin.db if it's being created
                if db_name == 'sysadmin.db':
                     os.makedirs(os.path.dirname(db_path), exist_ok=True)

                print(f"Connecting to database: {db_path}") # Debug print
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
                self._connections[db_name] = conn
            except sqlite3.Error as e:
                print(f"Error connecting to database {db_path}: {e}")
                # Potentially re-raise or handle more gracefully
                raise
        return self._connections[db_name]

    def _close_connection(self, db_name):
        """Closes the connection to the specified database."""
        if db_name in self._connections and self._connections[db_name] is not None:
            self._connections[db_name].close()
            self._connections[db_name] = None

    def _execute_query(self, db_name, query, params=(), fetch_one=False, commit=False):
        """Executes a query against the specified database."""
        conn = self._get_connection(db_name)
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                conn.commit()
                return cursor.lastrowid # Return last inserted ID for INSERTs
            else:
                if fetch_one:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error executing query on {db_name}: {query} with params {params} - {e}")
            # Consider rolling back on error if within a transaction context
            raise
        finally:
            # Don't close the cursor if we might need it later (e.g., fetchmany)
            # but for simplicity here, we close it.
            # For long-running apps, manage connections/cursors more carefully.
            pass # Connection pool might be better

# Example usage pattern (will be in subclasses):
# class SpecificRepository(BaseRepository):
#     def get_something(self, id):
#         query = "SELECT * FROM my_table WHERE id = ?"
#         return self._execute_query('my_database.db', query, (id,), fetch_one=True)
#
#     def add_something(self, data):
#         query = "INSERT INTO my_table (column1) VALUES (?)"
#         return self._execute_query('my_database.db', query, (data,), commit=True) 