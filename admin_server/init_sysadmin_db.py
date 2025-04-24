import sqlite3
import os
from werkzeug.security import generate_password_hash

# Database path (within admin_server)
DB_PATH = os.path.join(os.path.dirname(__file__), 'sysadmin.db')

def initialize_database():
    """Initializes the sysadmin database and creates the admins table."""
    conn = None # Initialize conn to None
    try:
        print(f"Initializing database at: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create admins table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("'admins' table created or already exists.")

        # --- Add a default admin user --- 
        default_username = 'admin'
        # Check if default admin already exists
        cursor.execute("SELECT id FROM admins WHERE username = ?", (default_username,))
        if cursor.fetchone() is None:
            # *** IMPORTANT: Use a strong, securely generated password in a real application! ***
            # Consider prompting the user or using environment variables.
            default_password = 'admin123' # Replace with a more secure default or method
            hashed_password = generate_password_hash(default_password)
            
            cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", 
                           (default_username, hashed_password))
            print(f"Default admin user '{default_username}' created.")
        else:
            print(f"Default admin user '{default_username}' already exists.")

        conn.commit()
        print("Database initialized successfully.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    # Add werkzeug to requirements
    # You might need to run: pip install Flask werkzeug
    initialize_database() 