from flask import Flask, jsonify, request
import sys
import os

# --- Configuration ---
ADMIN_API_PORT = 9000 # Define the port as a global variable

# Add repositories directory to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'repositories'))

# Import the specific repository instance
# Assuming user_repository.py defines a user_repository instance
from user_repository import user_repository
from deck_repository import deck_repository # Import deck_repository

app = Flask(__name__)

# --- CORS (Cross-Origin Resource Sharing) ---
# If the React client runs on a different origin (port), we need CORS
# pip install Flask-CORS
try:
    from flask_cors import CORS
    CORS(app) # Enable CORS for all origins on all routes for now
    print("CORS enabled for all routes.")
except ImportError:
    print("Flask-CORS not installed. CORS will not be enabled.")
    # Handle cases where CORS is necessary but not installed

@app.route('/')
def hello_world():
    return 'Admin API v0.1'

# --- Add User Listing Endpoint --- 
@app.route('/admin/users', methods=['GET'])
def get_users():
    """Endpoint to get a list of all regular users."""
    try:
        users = user_repository.get_all_regular_users()
        return jsonify(users)
    except Exception as e:
        # Log the error
        print(f"Error in /admin/users endpoint: {e}") 
        return jsonify({"error": "Failed to retrieve users"}), 500

# --- Admin Login Endpoint ---
@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Endpoint for sysadmin login."""
    print("Received request for /admin/login") # Debug print
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        print("Login failed: Missing username or password in request.")
        return jsonify({"error": "Missing username or password"}), 400

    username = data.get('username')
    password = data.get('password')
    print(f"Attempting login for user: {username}")

    try:
        admin_user = user_repository.find_sysadmin_by_username(username)

        if not admin_user:
            print(f"Login failed: Admin user '{username}' not found.")
            return jsonify({"error": "Invalid credentials"}), 401 # Use 401 Unauthorized

        # Check password hash
        if user_repository.verify_sysadmin_password(admin_user['password_hash'], password):
            print(f"Login successful for user: {username}")
            # TODO: Implement session management or JWT token generation
            # For now, just return success
            return jsonify({
                "message": "Login successful",
                "user": { # Send back some non-sensitive user info
                    "id": admin_user['id'],
                    "username": admin_user['username']
                }
            }), 200
        else:
            print(f"Login failed: Invalid password for user: {username}")
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        print(f"Error during admin login for {username}: {e}")
        return jsonify({"error": "An internal error occurred during login"}), 500

# --- User Decks Endpoint --- 
@app.route('/users/<username>/decks', methods=['GET'])
def get_user_decks(username):
    """Endpoint to get a list of decks for a specific regular user."""
    print(f"Received request for decks for user: {username}")
    try:
        # 1. Find the user_id for the given username from admin.db
        user = user_repository.find_regular_user_by_username(username)
        if not user:
            print(f"User '{username}' not found in admin DB.")
            return jsonify({"error": f"User '{username}' not found"}), 404 # Not Found
        
        user_id = user['user_id']
        print(f"Found user_id {user_id} for username {username}.")

        # 2. Use the deck repository to fetch decks based on user_id
        # decks = deck_repository.get_decks_by_username(username) # Old call
        decks = deck_repository.get_decks_by_user_id(user_id)

        print(f"Retrieved {len(decks)} decks for user {username} (ID: {user_id}).")
        return jsonify(decks)
        
    except Exception as e:
        # Log the error more specifically
        print(f"Error in /users/<username>/decks endpoint for user {username}: {e}")
        return jsonify({"error": f"Failed to retrieve decks for user {username}"}), 500

# --- Teardown --- 
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Close database connections at the end of the request."""
    print("App context teardown: Closing connections.") # Debug print
    # Close connections for all repositories that manage them
    repositories = [user_repository, deck_repository] 
    for repo in repositories:
        if hasattr(repo, 'close_all_connections'): # User repo has this method
             repo.close_all_connections() 
        elif hasattr(repo, '_connections'): # Close individual connections if method not present
             # Use list() to avoid modifying dict during iteration
             db_names_to_close = list(repo._connections.keys())
             for db_name in db_names_to_close:
                  if hasattr(repo, '_close_connection'): # Check if method exists
                      repo._close_connection(db_name) 

if __name__ == '__main__':
    # Ensure dependencies are installed: pip install Flask Werkzeug
    print(f"Starting Admin API server on port {ADMIN_API_PORT}...")
    app.run(debug=True, port=ADMIN_API_PORT) # Use the global variable 