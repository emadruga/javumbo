"""
Javumbo Lambda Flask Application

Minimal Flask app for AWS Lambda with:
- JWT authentication (replaces Flask-Session)
- SessionAwareS3SQLite integration for session-based caching
- S3-backed user databases
- DynamoDB user management

This is a PROOF-OF-CONCEPT for Week 2 Day 7.
Full routes will be migrated in Week 3.
"""

import os
import json
import time
import hashlib
import sqlite3
import uuid
from functools import wraps
from flask import Flask, request, jsonify, g, send_file, Response
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
import boto3

# Import our custom modules
from s3_sqlite import SessionAwareS3SQLite
from session_manager import SessionConflictError
from user_repository import UserRepository
from anki_schema import init_anki_db
from verbal_tenses_deck import add_verbal_tenses_to_db

# --- Configuration ---
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # 1 hour

# Initialize JWT
jwt = JWTManager(app)

# CORS (allow requests from React app)
CORS(app, supports_credentials=True)

# Initialize user repository
user_repo = UserRepository()


# --- Constants ---
DAILY_NEW_LIMIT = 20  # Maximum number of new cards to introduce per day per user


# --- Helper Functions for Review Logic ---

def sha1_checksum(data):
    """Calculates the SHA1 checksum for Anki note syncing."""
    return hashlib.sha1(data.encode('utf-8')).hexdigest()


def _getCollectionConfig(cursor):
    """Fetches essential configuration from the col table."""
    try:
        cursor.execute("SELECT crt, conf, decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data:
            raise ValueError("Collection configuration could not be read")

        conf_dict = json.loads(col_data['conf'])
        decks_dict = json.loads(col_data['decks'])
        current_deck_id = conf_dict.get('curDeck', 1)
        deck_name = decks_dict.get(str(current_deck_id), {}).get('name', 'Default')

        return {
            "collectionCreationTime": col_data['crt'],
            "currentDeckId": current_deck_id,
            "deckName": deck_name
        }
    except (sqlite3.Error, json.JSONDecodeError, KeyError, ValueError) as e:
        app.logger.error(f"Error processing collection config: {e}")
        raise ValueError("Failed to process collection configuration")


def _calculateDayCutoff(collection_creation_time):
    """Calculates the current time and day cutoff based on collection creation."""
    now = int(time.time())
    # Calculate days since collection creation time, this is how Anki determines the 'day'
    day_cutoff = (now - collection_creation_time) // 86400
    return now, day_cutoff


def _countNewCardsReviewedToday(cursor, day_cutoff, collection_creation_time):
    """Counts cards marked as 'new' (type=0) in today's review log."""
    # Calculate the timestamp for the start of the current day relative to collection creation
    start_of_day_timestamp_ms = (collection_creation_time + day_cutoff * 86400) * 1000
    try:
        cursor.execute("""
            SELECT COUNT(*)
            FROM revlog
            WHERE id >= ? AND type = 0
        """, (start_of_day_timestamp_ms,))
        count_result = cursor.fetchone()
        return count_result[0] if count_result else 0
    except sqlite3.Error as e:
        app.logger.error(f"Error counting new cards reviewed today: {e}")
        return 0  # Fail safe: assume 0 if error occurs


def _fetchLearningCard(cursor, current_deck_id, now):
    """Fetches the next due learning/relearning card."""
    try:
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND (c.queue = 1 OR c.queue = 3) AND c.due <= ?
            ORDER BY c.due
            LIMIT 1
        """, (current_deck_id, now))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching learning card: {e}")
        return None


def _fetchReviewCard(cursor, current_deck_id, day_cutoff):
    """Fetches the next due review card."""
    try:
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds, c.due, c.ivl
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND c.queue = 2 AND c.due <= ?
            ORDER BY c.due
            LIMIT 1
        """, (current_deck_id, day_cutoff))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching review card: {e}")
        return None


def _fetchNewCard(cursor, current_deck_id):
    """Fetches the next new card randomly."""
    try:
        # Order by RANDOM() to select a random new card
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND c.queue = 0
            ORDER BY RANDOM()
            LIMIT 1
        """, (current_deck_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching new card: {e}")
        return None


def get_card_state(card_type, queue, interval):
    """
    Map card type/queue/interval to human-readable state for logging.

    Args:
        card_type: Integer - 0=new, 1=learning, 2=review, 3=relearning
        queue: Integer - -3=sched buried, -2=user buried, -1=suspended, 0=new, 1=learning, 2=review, 3=day learn, 4=preview
        interval: Integer - days for review cards, used to distinguish Young vs Mature

    Returns:
        String - Human-readable card state
    """
    if queue == -3:
        return "SchedBuried"
    if queue == -2:
        return "UserBuried"
    if queue == -1:
        return "Suspended"
    if card_type == 0:
        return "New"
    if card_type == 1 or card_type == 3:
        return "Learning" if queue == 1 else "Relearning"
    if card_type == 2:
        # Review cards: Young (<21 days) or Mature (>=21 days)
        return "Young" if interval < 21 else "Mature"
    return "Unknown"


# --- Decorator for Session-Aware DB Access ---

def with_user_db(f):
    """
    Decorator that provides session-aware database connection.

    Reads session_id from request header (X-Session-ID).
    If no session_id provided, creates new session.
    Stores connection in g.db and session_id in g.session_id.

    Usage:
        @app.route('/api/decks', methods=['GET'])
        @jwt_required()
        @with_user_db
        def get_decks():
            # g.db is now available
            cursor = g.db.execute("SELECT * FROM col")
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        username = get_jwt_identity()
        session_id = request.headers.get('X-Session-ID')

        try:
            # Create session-aware connection
            db_wrapper = SessionAwareS3SQLite(username, session_id)
            conn = db_wrapper.__enter__()

            # Store in Flask g context
            g.db = conn
            g.db_wrapper = db_wrapper
            g.session_id = db_wrapper.session_id

            # Execute route function
            response = f(*args, **kwargs)

            # Close connection (but DO NOT upload to S3)
            db_wrapper.__exit__(None, None, None)

            # Add session_id to response headers
            if isinstance(response, tuple):
                # Response is (body, status_code) or (body, status_code, headers)
                if len(response) == 3:
                    body, status, headers = response
                    headers['X-Session-ID'] = g.session_id
                    return body, status, headers
                elif len(response) == 2:
                    body, status = response
                    return body, status, {'X-Session-ID': g.session_id}
            else:
                # Response is just body
                resp = jsonify(response) if not isinstance(response, app.response_class) else response
                resp.headers['X-Session-ID'] = g.session_id
                return resp

        except SessionConflictError as e:
            return jsonify({'error': str(e), 'code': 'SESSION_CONFLICT'}), 409
        except Exception as e:
            app.logger.error(f"Error in with_user_db: {e}")
            return jsonify({'error': 'Internal server error'}), 500

    return decorated


# --- Authentication Routes ---

@app.route('/api/register', methods=['POST'])
def register():
    """
    Register a new user.

    Request body:
        {
            "username": "john_doe",
            "name": "John Doe",
            "password": "securepassword123"
        }

    Returns:
        200: {"message": "User registered successfully"}
        400: {"error": "Missing required fields"} or {"error": "Username already exists"}
    """
    data = request.get_json()

    if not data or not all(k in data for k in ('username', 'name', 'password')):
        return jsonify({"error": "Missing required fields"}), 400

    username = data['username'].strip()
    name = data['name'].strip()
    password = data['password']

    # Validate inputs
    if len(username) < 1 or len(username) > 20:
        return jsonify({"error": "Username must be between 1 and 20 characters"}), 400

    if len(name) < 1 or len(name) > 50:
        return jsonify({"error": "Name must be between 1 and 50 characters"}), 400

    # Check if user exists
    if user_repo.get_user(username):
        return jsonify({"error": "Username already exists"}), 400

    # Create user in DynamoDB (password hashing done in repository)
    user_repo.create_user(username, name, password)

    # Create user database in S3 with Anki schema + sample deck
    # For initial setup, use basic S3SQLiteConnection (auto-uploads on exit)
    from s3_sqlite import S3SQLiteConnection

    # Check if DB already has full schema by checking S3 first
    import boto3
    s3 = boto3.client('s3')
    bucket = os.environ.get('S3_BUCKET', 'javumbo-user-dbs')
    s3_key = f'user_dbs/{username}.anki2'

    db_exists_in_s3 = False
    try:
        s3.head_object(Bucket=bucket, Key=s3_key)
        db_exists_in_s3 = True
    except:
        pass

    if db_exists_in_s3:
        # DB exists in S3, just download it
        print(f"✓ DB already exists in S3 for {username}")
    else:
        # Create new database with full schema
        # S3SQLiteConnection will create a minimal schema, we need to replace it
        local_path = f'/tmp/{username}.anki2'

        # Delete any existing file first
        if os.path.exists(local_path):
            os.remove(local_path)

        # Create a fresh database with full Anki schema
        import sqlite3
        conn = sqlite3.connect(local_path)
        init_anki_db(conn, user_name=name)
        add_verbal_tenses_to_db(conn, model_id="1700000000001", deck_id=2)

        # Set current deck to Verbal Tenses (deck_id=2)
        cursor = conn.execute("SELECT conf FROM col WHERE id = 1")
        col_row = cursor.fetchone()
        if col_row:
            conf_dict = json.loads(col_row[0])
            conf_dict['curDeck'] = 2  # Set Verbal Tenses as current deck
            conn.execute("UPDATE col SET conf = ? WHERE id = 1", (json.dumps(conf_dict),))
            conn.commit()
            print(f"✓ Set current deck to Verbal Tenses (deck_id=2)")
        conn.close()

        # Upload to S3
        with open(local_path, 'rb') as f:
            s3.put_object(Bucket=bucket, Key=s3_key, Body=f)
        print(f"✓ Uploaded new database to S3: {s3_key}")

    return jsonify({"message": "User registered successfully"}), 200


@app.route('/api/login', methods=['POST'])
def login():
    """
    Login user and return JWT token.

    Request body:
        {
            "username": "john_doe",
            "password": "securepassword123"
        }

    Returns:
        200: {"access_token": "eyJ..."}
        400: {"error": "Missing username or password"}
        401: {"error": "Invalid credentials"}
    """
    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400

    username = data['username']
    password = data['password']

    # Authenticate user (password check done in repository)
    if not user_repo.authenticate(username, password):
        return jsonify({"error": "Invalid credentials"}), 401

    # Get user details (without password_hash)
    user = user_repo.get_user(username)

    # Create JWT token
    access_token = create_access_token(identity=username)

    return jsonify({
        "access_token": access_token,
        "username": username,
        "name": user['name']
    }), 200


# --- Protected API Routes ---

@app.route('/api/health', methods=['GET'])
@jwt_required()
def health():
    """Simple health check for testing JWT auth."""
    username = get_jwt_identity()
    return jsonify({"status": "ok", "username": username}), 200


@app.route('/api/decks', methods=['GET'])
@jwt_required()
@with_user_db
def get_decks():
    """
    Get all decks for authenticated user.

    Uses session-aware DB connection (g.db).

    Returns:
        200: {"decks": [...]}
    """
    cursor = g.db.execute("SELECT id, crt, mod, decks FROM col WHERE id = 1")
    row = cursor.fetchone()

    if not row:
        return jsonify({"error": "No collection found"}), 404

    decks_json = row['decks']
    decks_dict = json.loads(decks_json)

    decks_list = []
    for deck_id, deck_data in decks_dict.items():
        if deck_id != "1":  # Skip default deck
            decks_list.append({
                "id": int(deck_id),
                "name": deck_data["name"],
                "desc": deck_data.get("desc", "")
            })

    return jsonify({"decks": decks_list, "session_id": g.session_id}), 200


@app.route('/api/decks', methods=['POST'])
@jwt_required()
@with_user_db
def create_deck():
    """
    Creates a new deck for the authenticated user.

    Request body:
        {
            "name": str  # Deck name (required, must be non-empty)
        }

    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        201: {"id": int, "name": str, "session_id": str}
        400: {"error": "Deck name cannot be empty"}
        409: {"error": "A deck with this name already exists"}
        500: {"error": "Failed to create deck"}
    """
    username = get_jwt_identity()
    data = request.get_json()
    deck_name = data.get('name')

    if not deck_name or not deck_name.strip():
        app.logger.warning(f"[{username}] Empty deck name in create request")
        return jsonify({"error": "Deck name cannot be empty"}), 400

    deck_name = deck_name.strip()

    try:
        cursor = g.db.execute("SELECT decks, dconf FROM col WHERE id = 1")
        col_data = cursor.fetchone()
        if not col_data:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        dconf_dict = json.loads(col_data['dconf'])

        # Generate new deck ID (using epoch ms)
        new_deck_id = str(int(time.time() * 1000))

        # Check for duplicate name (case-insensitive)
        if any(d['name'].lower() == deck_name.lower() for d in decks_dict.values()):
            app.logger.warning(f"[{username}] Duplicate deck name: {deck_name}")
            return jsonify({"error": "A deck with this name already exists"}), 409

        # Create new deck entry - using dconf ID '1' for simplicity
        new_deck = {
            "id": new_deck_id,
            "name": deck_name,
            "mod": int(time.time()),
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "conf": 1,  # Use default dconf '1'
            "desc": "",
            "dyn": 0,
            "collapsed": False,
            "extendNew": 10,
            "extendRev": 50
        }
        decks_dict[new_deck_id] = new_deck

        # Update col table
        current_mod_time = int(time.time() * 1000)
        g.db.execute("UPDATE col SET decks = ?, mod = ? WHERE id = 1",
                     (json.dumps(decks_dict), current_mod_time))
        g.db.commit()

        # HYBRID APPROACH: Force immediate S3 upload after deck creation
        g.db_wrapper.force_upload()

        app.logger.info(f"[{username}] Created deck '{deck_name}' (ID: {new_deck_id})")
        return jsonify({
            "id": int(new_deck_id),
            "name": deck_name,
            "session_id": g.session_id
        }), 201

    except Exception as e:
        app.logger.exception(f"[{username}] Error creating deck: {e}")
        g.db.rollback()
        return jsonify({"error": "Failed to create deck"}), 500


@app.route('/api/decks/current', methods=['PUT'])
@jwt_required()
@with_user_db
def set_current_deck():
    """
    Sets the current deck for the authenticated user.

    Request body:
        {
            "deckId": int  # Deck ID (required)
        }

    Updates the `curDeck` field in `col.conf` JSON.
    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        200: {"message": "Current deck updated successfully", "session_id": str}
        400: {"error": "Missing deckId"}
        404: {"error": "Invalid deck ID"}
        500: {"error": "Failed to set current deck"}
    """
    username = get_jwt_identity()
    data = request.get_json()
    deck_id = data.get('deckId')

    if deck_id is None:
        app.logger.warning(f"[{username}] Missing deckId in set_current_deck request")
        return jsonify({"error": "Missing deckId"}), 400

    try:
        cursor = g.db.execute("SELECT conf, decks FROM col WHERE id = 1")
        col_data = cursor.fetchone()
        if not col_data:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        conf_dict = json.loads(col_data['conf'])
        decks_dict = json.loads(col_data['decks'])

        # Validate deck ID exists
        if str(deck_id) not in decks_dict:
            app.logger.warning(f"[{username}] Invalid deck ID: {deck_id}")
            return jsonify({"error": "Invalid deck ID"}), 404

        # Update current deck ID in conf
        conf_dict['curDeck'] = int(deck_id)  # Store as integer

        # Update col table
        current_mod_time = int(time.time() * 1000)
        g.db.execute("UPDATE col SET conf = ?, mod = ? WHERE id = 1",
                     (json.dumps(conf_dict), current_mod_time))
        g.db.commit()

        app.logger.info(f"[{username}] Set current deck to {deck_id}")
        return jsonify({
            "message": "Current deck updated successfully",
            "session_id": g.session_id
        }), 200

    except Exception as e:
        app.logger.exception(f"[{username}] Error setting current deck: {e}")
        g.db.rollback()
        return jsonify({"error": "Failed to set current deck"}), 500


@app.route('/api/decks/<int:deck_id>/rename', methods=['PUT'])
@jwt_required()
@with_user_db
def rename_deck(deck_id):
    """
    Renames a specific deck.

    Request body:
        {
            "name": str  # New deck name (required, must be non-empty)
        }

    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        200: {"message": str, "id": int, "name": str, "session_id": str}
        400: {"error": "New deck name cannot be empty"}
        404: {"error": "Deck not found"}
        409: {"error": "A deck with this name already exists"}
        500: {"error": "Failed to rename deck"}
    """
    username = get_jwt_identity()
    data = request.get_json()

    if not data or 'name' not in data or not data['name'].strip():
        app.logger.warning(f"[{username}] Missing or empty deck name in rename request")
        return jsonify({"error": "New deck name cannot be empty"}), 400

    new_deck_name = data['name'].strip()

    try:
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        col_data = cursor.fetchone()

        if not col_data or not col_data['decks']:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        deck_id_str = str(deck_id)

        # Check if the deck exists
        if deck_id_str not in decks_dict:
            app.logger.warning(f"[{username}] Attempt to rename non-existent deck {deck_id}")
            return jsonify({"error": "Deck not found"}), 404

        old_deck_name = decks_dict[deck_id_str]['name']

        # Check if another deck with the same name already exists (case-insensitive)
        for did, deck in decks_dict.items():
            if did != deck_id_str and deck['name'].lower() == new_deck_name.lower():
                app.logger.warning(f"[{username}] Attempt to rename deck to existing name: {new_deck_name}")
                return jsonify({"error": "A deck with this name already exists"}), 409

        # Update the deck name
        decks_dict[deck_id_str]['name'] = new_deck_name
        decks_dict[deck_id_str]['mod'] = int(time.time())  # Update modification time

        # Update the collection
        current_time_ms = int(time.time() * 1000)
        g.db.execute("UPDATE col SET decks = ?, mod = ? WHERE id = 1",
                     (json.dumps(decks_dict), current_time_ms))
        g.db.commit()

        app.logger.info(f"[{username}] Renamed deck from '{old_deck_name}' to '{new_deck_name}'")
        return jsonify({
            "message": f"Deck renamed from '{old_deck_name}' to '{new_deck_name}' successfully",
            "id": deck_id,
            "name": new_deck_name,
            "session_id": g.session_id
        }), 200

    except sqlite3.Error as e:
        app.logger.exception(f"[{username}] Database error renaming deck {deck_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": "Failed to rename deck due to database error"}), 500
    except Exception as e:
        app.logger.exception(f"[{username}] Error renaming deck {deck_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": "Failed to rename deck"}), 500


@app.route('/api/decks/<int:deck_id>', methods=['DELETE'])
@jwt_required()
@with_user_db
def delete_deck(deck_id):
    """
    Deletes a specific deck and all its associated cards and orphaned notes.

    Cascade deletion logic:
    1. Delete all cards in the deck
    2. For each affected note, check if it has remaining cards
    3. Delete orphaned notes (notes with no cards)
    4. Remove deck from col.decks JSON

    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        200: {"message": str, "session_id": str}
        404: {"error": "Deck not found"}
        500: {"error": "Failed to delete deck"}
    """
    username = get_jwt_identity()

    try:
        # Check if the deck exists in the col table's decks JSON
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        col_data = cursor.fetchone()

        if not col_data or not col_data['decks']:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        deck_id_str = str(deck_id)

        if deck_id_str not in decks_dict:
            app.logger.warning(f"[{username}] Attempt to delete non-existent deck {deck_id}")
            return jsonify({"error": "Deck not found"}), 404

        deck_name = decks_dict[deck_id_str]['name']
        app.logger.info(f"[{username}] Deleting deck '{deck_name}' (ID: {deck_id})")

        # Count cards in the deck
        cursor = g.db.execute("SELECT COUNT(*) FROM cards WHERE did = ?", (deck_id,))
        card_count = cursor.fetchone()[0]

        # Get the IDs of notes associated with this deck's cards
        cursor = g.db.execute("SELECT DISTINCT nid FROM cards WHERE did = ?", (deck_id,))
        note_ids = [row[0] for row in cursor.fetchall()]

        # Delete cards in this deck
        g.db.execute("DELETE FROM cards WHERE did = ?", (deck_id,))
        app.logger.debug(f"[{username}] Deleted {card_count} cards from deck {deck_id}")

        # For each note, check if it has any remaining cards
        # If not, delete the note
        for note_id in note_ids:
            cursor = g.db.execute("SELECT COUNT(*) FROM cards WHERE nid = ?", (note_id,))
            remaining_cards = cursor.fetchone()[0]
            if remaining_cards == 0:
                g.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                app.logger.debug(f"[{username}] Deleted orphaned note {note_id}")

        # Remove the deck from the decks JSON
        del decks_dict[deck_id_str]

        # Update the col table with the modified decks JSON
        current_time_ms = int(time.time() * 1000)
        g.db.execute("UPDATE col SET decks = ?, mod = ? WHERE id = 1",
                     (json.dumps(decks_dict), current_time_ms))
        g.db.commit()

        app.logger.info(f"[{username}] Deleted deck {deck_id} ({deck_name}) with {card_count} cards")
        return jsonify({
            "message": f"Deck '{deck_name}' and {card_count} cards deleted successfully",
            "session_id": g.session_id
        }), 200

    except sqlite3.Error as e:
        app.logger.exception(f"[{username}] Database error deleting deck {deck_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": "Failed to delete deck due to database error"}), 500
    except Exception as e:
        app.logger.exception(f"[{username}] Error deleting deck {deck_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": "Failed to delete deck"}), 500


@app.route('/api/decks/<int:deck_id>/stats', methods=['GET'])
@jwt_required()
@with_user_db
def get_deck_stats(deck_id):
    """
    Calculates and returns CURRENT card status counts for a specific deck.

    Card states:
    - New (queue=0): Cards never reviewed
    - Learning (queue=1): Cards in learning phase
    - Relearning (queue=3): Failed cards being relearned
    - Young (queue=2, ivl<21): Review cards with interval < 21 days
    - Mature (queue=2, ivl>=21): Review cards with interval >= 21 days
    - Suspended (queue=-1): Cards manually suspended
    - Buried (queue=-2 or -3): Cards temporarily hidden

    Uses session-aware DB connection (g.db).

    Returns:
        200: {"counts": {...}, "total": int, "session_id": str}
        404: {"error": "Deck not found"}
        500: {"error": "Database error"}
    """
    username = get_jwt_identity()

    try:
        # Verify deck exists
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['decks']:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        if str(deck_id) not in decks_dict:
            app.logger.warning(f"[{username}] Deck {deck_id} not found")
            return jsonify({"error": "Deck not found"}), 404

        # Query cards for the specific deck
        cursor = g.db.execute("SELECT queue, ivl FROM cards WHERE did = ?", (deck_id,))
        cards = cursor.fetchall()

        counts = {
            "New": 0,
            "Learning": 0,
            "Relearning": 0,
            "Young": 0,
            "Mature": 0,
            "Suspended": 0,
            "Buried": 0
        }
        total_cards = 0

        for card in cards:
            total_cards += 1
            queue = card['queue']
            ivl = card['ivl']

            if queue == 0:
                counts["New"] += 1
            elif queue == 1:
                counts["Learning"] += 1
            elif queue == 3:
                counts["Relearning"] += 1
            elif queue == 2:
                if ivl >= 21:
                    counts["Mature"] += 1
                else:
                    counts["Young"] += 1
            elif queue == -1:
                counts["Suspended"] += 1
            elif queue == -2 or queue == -3:
                counts["Buried"] += 1

        app.logger.debug(f"[{username}] Deck {deck_id} stats: {total_cards} total cards")
        return jsonify({
            "counts": counts,
            "total": total_cards,
            "session_id": g.session_id
        }), 200

    except sqlite3.Error as e:
        app.logger.exception(f"[{username}] Database error fetching stats for deck {deck_id}: {e}")
        return jsonify({"error": "Database error occurred while fetching statistics"}), 500
    except Exception as e:
        app.logger.exception(f"[{username}] Error fetching stats for deck {deck_id}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500


@app.route('/api/cards', methods=['POST'])
@jwt_required()
@with_user_db
def add_card():
    """
    Adds a new card to the current deck.

    Request body:
        {
            "front": str,  # Front of the card (required)
            "back": str    # Back of the card (required)
        }

    Creates both a Note (front/back content) and a Card (scheduling data).
    Card is added to the current deck specified in col.conf['curDeck'].

    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        201: {"message": str, "note_id": int, "card_id": int, "session_id": str}
        400: {"error": "Front and back content cannot be empty"}
        500: {"error": "Failed to add card"}
    """
    username = get_jwt_identity()
    data = request.get_json()
    front = data.get('front')
    back = data.get('back')

    if not front or not back:
        app.logger.warning(f"[{username}] Empty front/back in add_card request")
        return jsonify({"error": "Front and back content cannot be empty"}), 400

    try:
        # Get current model ID and current deck ID
        cursor = g.db.execute("SELECT models, conf FROM col WHERE id = 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['models'] or not col_data['conf']:
            app.logger.error(f"[{username}] Collection configuration not found")
            return jsonify({"error": "Collection configuration not found or invalid"}), 500

        models = json.loads(col_data['models'])
        conf_dict = json.loads(col_data['conf'])
        model_id = next(iter(models), None)
        current_deck_id = conf_dict.get('curDeck', 1)  # Get current deck ID

        if not model_id:
            app.logger.error(f"[{username}] Default note model not found")
            return jsonify({"error": "Default note model not found in collection"}), 500

        # Generate new note/card data
        current_time_sec = int(time.time())
        current_time_ms = int(current_time_sec * 1000)

        # Get max note_id and card_id to ensure uniqueness
        cursor = g.db.execute("SELECT COALESCE(MAX(id), 0) FROM notes")
        max_note_id = cursor.fetchone()[0]
        cursor = g.db.execute("SELECT COALESCE(MAX(id), 0) FROM cards")
        max_card_id = cursor.fetchone()[0]

        # Use timestamp as base, but ensure it's greater than existing IDs
        note_id = max(current_time_ms, max_note_id + 1)
        card_id = max(note_id + 1, max_card_id + 1)
        guid = str(uuid.uuid4())[:10]  # Unique ID for sync
        fields = f"{front}\x1f{back}"  # Fields separated by 0x1f
        checksum = sha1_checksum(front)  # Checksum of the first field
        usn = -1  # Update Sequence Number (-1 indicates local change)

        # Insert Note
        g.db.execute("""
            INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id, guid, model_id, current_time_sec, usn, "",
            fields, front, int(checksum, 16) & 0xFFFFFFFF, 0, ""
        ))
        app.logger.debug(f"[{username}] Inserted note {note_id}")

        # Insert Card (assign to current_deck_id)
        g.db.execute("""
            INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_id, note_id, current_deck_id, 0,
            current_time_sec, usn,
            0, 0, note_id,  # type, queue, due
            0, 2500, 0, 0, 0, 0, 0, 0, ""  # ivl, factor, reps, lapses, left, odue, odid, flags, data
        ))

        # Get deck name for logging
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        decks_data = cursor.fetchone()
        deck_name = "Unknown"
        if decks_data and decks_data['decks']:
            decks_dict = json.loads(decks_data['decks'])
            deck_name = decks_dict.get(str(current_deck_id), {}).get('name', 'Unknown')

        # Truncate front text for logging
        front_truncated = front[:15] + "..." if len(front) > 15 else front

        app.logger.info(f"[{username}] Created card {card_id} in deck {current_deck_id} ({deck_name}): \"{front_truncated}\"")

        # Update Collection Mod Time
        g.db.execute("UPDATE col SET mod = ? WHERE id = 1", (int(time.time() * 1000),))
        g.db.commit()

        # HYBRID APPROACH: Force immediate S3 upload after card creation
        g.db_wrapper.force_upload()

        return jsonify({
            "message": "Card added successfully",
            "note_id": note_id,
            "card_id": card_id,
            "session_id": g.session_id
        }), 201

    except sqlite3.Error as e:
        app.logger.exception(f"[{username}] Database error adding card: {e}")
        g.db.rollback()
        return jsonify({"error": "Database error occurred while adding card"}), 500
    except Exception as e:
        app.logger.exception(f"[{username}] Error adding card: {e}")
        g.db.rollback()
        return jsonify({"error": "An internal server error occurred"}), 500


@app.route('/api/cards/<int:card_id>', methods=['GET'])
@jwt_required()
@with_user_db
def get_card(card_id):
    """
    Fetches details of a specific card.

    Uses session-aware DB connection (g.db).

    Returns:
        200: {"cardId": int, "front": str, "back": str, "session_id": str}
        404: {"error": "Card not found"}
        500: {"error": "Invalid card format"}
    """
    username = get_jwt_identity()

    try:
        cursor = g.db.execute("""
            SELECT n.flds, c.id
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.id = ?
        """, (card_id,))

        result = cursor.fetchone()
        if not result:
            app.logger.warning(f"[{username}] Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404

        # Parse fields from the note
        fields = result[0].split('\x1f')  # Anki separator for fields
        if len(fields) < 2:
            app.logger.error(f"[{username}] Card {card_id} has invalid field format")
            return jsonify({"error": "Invalid card format"}), 500

        app.logger.debug(f"[{username}] Fetched card {card_id}")
        return jsonify({
            "cardId": result[1],
            "front": fields[0],
            "back": fields[1],
            "session_id": g.session_id
        }), 200

    except Exception as e:
        app.logger.exception(f"[{username}] Error fetching card {card_id}: {str(e)}")
        return jsonify({"error": f"Error fetching card: {str(e)}"}), 500


@app.route('/api/cards/<int:card_id>', methods=['PUT'])
@jwt_required()
@with_user_db
def update_card(card_id):
    """
    Updates the front and back content of a card.

    Request body:
        {
            "front": str,  # Front of the card (required)
            "back": str    # Back of the card (required)
        }

    Updates the underlying Note (not the Card scheduling data).
    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        200: {"success": true, "message": str, "session_id": str}
        400: {"error": "Front and back fields are required/cannot be empty"}
        404: {"error": "Card not found"}
        500: {"error": "Card has invalid field structure"}
    """
    username = get_jwt_identity()
    data = request.get_json()

    if not data or 'front' not in data or 'back' not in data:
        app.logger.warning(f"[{username}] Invalid request data for card update")
        return jsonify({"error": "Front and back fields are required"}), 400

    front = data['front'].strip()
    back = data['back'].strip()

    if not front or not back:
        app.logger.warning(f"[{username}] Empty front or back field")
        return jsonify({"error": "Front and back fields cannot be empty"}), 400

    try:
        # Get the note ID for this card
        cursor = g.db.execute("SELECT nid FROM cards WHERE id = ?", (card_id,))
        result = cursor.fetchone()

        if not result:
            app.logger.warning(f"[{username}] Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404

        note_id = result[0]

        # Update the note's fields
        # First, get the current fields to maintain any additional fields beyond front/back
        cursor = g.db.execute("SELECT flds FROM notes WHERE id = ?", (note_id,))
        current_fields = cursor.fetchone()[0]

        # Split into individual fields
        field_list = current_fields.split('\x1f')

        # Update just the front and back fields (first two)
        if len(field_list) >= 2:
            field_list[0] = front
            field_list[1] = back

            # Rejoin with the Anki separator
            new_fields = '\x1f'.join(field_list)

            # Calculate a new checksum for the first field
            checksum = int(sha1_checksum(field_list[0]), 16) & 0xFFFFFFFF

            # Update the note
            current_time = int(time.time())
            g.db.execute("""
                UPDATE notes
                SET flds = ?, sfld = ?, csum = ?, mod = ?
                WHERE id = ?
            """, (new_fields, field_list[0], checksum, current_time, note_id))

            # Update card modification time
            g.db.execute("UPDATE cards SET mod = ? WHERE id = ?", (current_time, card_id))

            # Update collection modification time
            g.db.execute("UPDATE col SET mod = ? WHERE id = 1", (int(time.time() * 1000),))

            g.db.commit()

            app.logger.info(f"[{username}] Successfully updated card {card_id}")
            return jsonify({
                "success": True,
                "message": "Card updated successfully",
                "session_id": g.session_id
            }), 200
        else:
            app.logger.error(f"[{username}] Card {card_id} has invalid field structure")
            return jsonify({"error": "Card has invalid field structure"}), 500

    except Exception as e:
        app.logger.exception(f"[{username}] Error updating card {card_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": f"Error updating card: {str(e)}"}), 500


@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
@jwt_required()
@with_user_db
def delete_card(card_id):
    """
    Deletes a specific card and its associated note if orphaned.

    If the card's note has no other cards associated with it, the note is also deleted.
    Uses session-aware DB connection (g.db) - NO S3 upload until session flush.

    Returns:
        200: {"success": true, "message": str, "session_id": str}
        404: {"error": "Card not found"}
        500: {"error": "Error deleting card"}
    """
    username = get_jwt_identity()

    try:
        # First, get card details for enhanced logging (BEFORE deletion)
        cursor = g.db.execute("""
            SELECT c.nid, c.did, c.type, c.queue, c.ivl, n.flds
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.id = ?
        """, (card_id,))
        card_data = cursor.fetchone()

        if not card_data:
            app.logger.warning(f"[{username}] Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404

        note_id = card_data['nid']
        deck_id = card_data['did']
        card_type = card_data['type']
        card_queue = card_data['queue']
        card_interval = card_data['ivl']
        fields = card_data['flds']

        # Get deck name
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        decks_data = cursor.fetchone()
        deck_name = "Unknown"
        if decks_data and decks_data['decks']:
            decks_dict = json.loads(decks_data['decks'])
            deck_name = decks_dict.get(str(deck_id), {}).get('name', 'Unknown')

        # Get card front text
        field_list = fields.split('\x1f')
        front_text = field_list[0][:15] + "..." if len(field_list[0]) > 15 else field_list[0]

        # Get card state
        card_state = get_card_state(card_type, card_queue, card_interval)

        # Delete the card
        g.db.execute("DELETE FROM cards WHERE id = ?", (card_id,))

        # Check if there are any other cards associated with this note
        cursor = g.db.execute("SELECT COUNT(*) FROM cards WHERE nid = ?", (note_id,))
        other_cards_count = cursor.fetchone()[0]

        # If no other cards use this note, delete the note too
        if other_cards_count == 0:
            g.db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            app.logger.debug(f"[{username}] Deleted orphaned note {note_id}")

        # Update collection modification time
        g.db.execute("UPDATE col SET mod = ? WHERE id = 1", (int(time.time() * 1000),))
        g.db.commit()

        app.logger.info(f"[{username}] Deleted card {card_id} from deck {deck_id} ({deck_name}): \"{front_text}\" [state: {card_state}]")
        return jsonify({
            "success": True,
            "message": "Card deleted successfully",
            "session_id": g.session_id
        }), 200

    except Exception as e:
        app.logger.exception(f"[{username}] Error deleting card {card_id}: {str(e)}")
        g.db.rollback()
        return jsonify({"error": f"Error deleting card: {str(e)}"}), 500


@app.route('/api/decks/<int:deck_id>/cards', methods=['GET'])
@jwt_required()
@with_user_db
def get_deck_cards(deck_id):
    """
    Lists all cards in a specific deck with pagination support.

    Query parameters:
        page (int, default=1): Page number
        perPage (int, default=10): Cards per page

    Uses session-aware DB connection (g.db).

    Returns:
        200: {
            "deckId": int,
            "deckName": str,
            "cards": [...],
            "pagination": {...},
            "session_id": str
        }
        404: {"error": "Deck not found"}
        500: {"error": "Error fetching cards"}
    """
    username = get_jwt_identity()

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('perPage', 10, type=int)

    # Calculate offset for pagination
    offset = (page - 1) * per_page

    try:
        # First, check if the deck exists by querying the col table's decks JSON field
        cursor = g.db.execute("SELECT decks FROM col WHERE id = 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['decks']:
            app.logger.error(f"[{username}] Collection data not found")
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        if str(deck_id) not in decks_dict:
            app.logger.warning(f"[{username}] Deck {deck_id} not found")
            return jsonify({"error": "Deck not found"}), 404

        deck_name = decks_dict[str(deck_id)]['name']

        # Get total number of cards in the deck
        cursor = g.db.execute("""
            SELECT COUNT(*)
            FROM cards c
            WHERE c.did = ?
        """, (deck_id,))
        total_cards = cursor.fetchone()[0]

        # Query to get cards for the deck with pagination
        cursor = g.db.execute("""
            SELECT c.id, n.id AS note_id, n.flds, c.mod
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.did = ?
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
        """, (deck_id, per_page, offset))

        cards_data = []
        for row in cursor.fetchall():
            card_id = row[0]
            note_id = row[1]
            fields = row[2]
            mod_time = row[3]

            # Parse fields from the note (separated by the Anki separator \x1f)
            field_list = fields.split('\x1f')
            if len(field_list) >= 2:
                cards_data.append({
                    "cardId": card_id,
                    "noteId": note_id,
                    "front": field_list[0],
                    "back": field_list[1],
                    "modified": mod_time  # This is epoch timestamp
                })

        app.logger.debug(f"[{username}] Fetched {len(cards_data)} cards from deck {deck_id} (page {page})")
        return jsonify({
            "deckId": deck_id,
            "deckName": deck_name,
            "cards": cards_data,
            "pagination": {
                "total": total_cards,
                "page": page,
                "perPage": per_page,
                "totalPages": (total_cards + per_page - 1) // per_page
            },
            "session_id": g.session_id
        }), 200

    except Exception as e:
        app.logger.exception(f"[{username}] Error fetching cards for deck {deck_id}: {str(e)}")
        return jsonify({"error": f"Error fetching cards: {str(e)}"}), 500


# --- Review Endpoints ---

@app.route('/api/review', methods=['GET'])
@jwt_required()
@with_user_db
def get_next_card():
    """
    Fetches the next card due for review using prioritized queues and daily limits.

    Priority order:
    1. Learning cards (queue=1 or 3, due <= now)
    2. Review cards (queue=2, due <= day_cutoff)
    3. New cards (queue=0, respecting daily limit of 20)

    Uses session-aware DB connection (g.db) for efficient caching.

    Returns:
        200: {
            "cardId": int,
            "front": str,
            "back": str,
            "queue": int
        }
        200: {"message": "No cards available for review in deck 'X'"}
        500: {"error": "Database error"}
    """
    username = get_jwt_identity()

    try:
        cursor = g.db.cursor()

        # Fetch configuration and calculate time cutoffs
        try:
            config = _getCollectionConfig(cursor)
            collection_creation_time = config['collectionCreationTime']
            current_deck_id = config['currentDeckId']
            deck_name = config['deckName']
        except ValueError as e:
            return jsonify({"error": str(e)}), 500

        now, day_cutoff = _calculateDayCutoff(collection_creation_time)

        # Count new cards reviewed today
        new_cards_seen_today = _countNewCardsReviewedToday(cursor, day_cutoff, collection_creation_time)

        app.logger.debug(f"User {username}, Deck {current_deck_id}: Day Cutoff={day_cutoff}, Now={now}, New Seen={new_cards_seen_today}/{DAILY_NEW_LIMIT}")

        next_card_data = None

        # 1. Check for Learning Cards
        next_card_data = _fetchLearningCard(cursor, current_deck_id, now)
        if next_card_data:
            app.logger.debug(f"Found learning card {next_card_data['id']}")

        # 2. Check for Due Review Cards
        if not next_card_data:
            next_card_data = _fetchReviewCard(cursor, current_deck_id, day_cutoff)
            if next_card_data:
                app.logger.info(f"Found review card {next_card_data['id']} (queue={next_card_data['queue']}). Card Due: {next_card_data['due']}, Card Interval: {next_card_data['ivl']} days. Current Day Cutoff: {day_cutoff}")

        # 3. Check for New Cards (respecting limit)
        if not next_card_data:
            if new_cards_seen_today < DAILY_NEW_LIMIT:
                next_card_data = _fetchNewCard(cursor, current_deck_id)
                if next_card_data:
                    app.logger.debug(f"Found new card {next_card_data['id']}")
                else:
                    app.logger.debug("No more new cards available in deck.")
            else:
                app.logger.debug(f"Daily new card limit ({DAILY_NEW_LIMIT}) reached.")

        # Format and return card if found
        if next_card_data:
            try:
                fields = next_card_data['flds'].split('\x1f')  # Anki separator
                front = fields[0]
                back = fields[1] if len(fields) > 1 else ""

                response_payload = {
                    "cardId": next_card_data['id'],
                    "noteId": next_card_data['nid'],
                    "front": front,
                    "back": back,
                    "queue": next_card_data['queue']
                }

                return jsonify(response_payload), 200

            except Exception as e:
                app.logger.error(f"Error formatting card response: {e} for cardData: {next_card_data}")
                return jsonify({"error": "Failed to process card data."}), 500
        else:
            # No card found in any queue (or new limit reached)
            cursor.execute("SELECT COUNT(*) as card_count FROM cards WHERE did = ? AND queue >= 0 AND queue <= 3", (current_deck_id,))
            count_result = cursor.fetchone()
            total_cards_in_deck = count_result['card_count'] if count_result else 0

            message = f"No cards available for review in deck '{deck_name}'."
            if total_cards_in_deck > 0:
                if new_cards_seen_today >= DAILY_NEW_LIMIT and _fetchNewCard(cursor, current_deck_id) is not None:
                    message = f"Daily limit of {DAILY_NEW_LIMIT} new cards reached for deck '{deck_name}'."
                else:
                    message = f"No cards due for deck '{deck_name}' right now."

            app.logger.info(message)
            return jsonify({"message": message}), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error in get_next_card for user {username}: {e}")
        return jsonify({"error": "A database error occurred."}), 500
    except Exception as e:
        app.logger.exception(f"Unexpected error in get_next_card for user {username}: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@app.route('/api/review', methods=['POST'])
@jwt_required()
@with_user_db
def submit_review():
    """
    Processes a user's answer to a card.

    Request body:
        {
            "cardId": int,
            "noteId": int,
            "ease": int (1-4),  # 1=Again, 2=Hard, 3=Good, 4=Easy
            "timeTaken": int    # milliseconds
        }

    Uses SM-2 algorithm to calculate new interval and due date.
    Updates cards table and logs review in revlog table.
    Uses session-aware DB (g.db) - NO S3 upload until session ends.

    Returns:
        200: {"message": "Review processed successfully", "newDue": timestamp}
        400: {"error": "Invalid input"}
        404: {"error": "Card not found"}
        500: {"error": "Database error"}
    """
    username = get_jwt_identity()
    data = request.get_json()

    # Validate input
    if not data or 'cardId' not in data or 'ease' not in data:
        return jsonify({"error": "Missing cardId or ease rating"}), 400

    card_id = data['cardId']
    note_id = data.get('noteId')
    ease = data['ease']
    time_taken = data.get('timeTaken', 0)

    # Validate ease value
    if ease not in [1, 2, 3, 4]:
        return jsonify({"error": "Invalid ease rating (must be 1, 2, 3, or 4)"}), 400

    try:
        cursor = g.db.cursor()

        # First, verify the card exists
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()
        if not card:
            return jsonify({"error": "Card not found"}), 404

        # Card properties
        current_type = card['type']
        current_queue = card['queue']
        current_due = card['due']
        current_interval = card['ivl']
        current_factor = card['factor']
        current_reps = card['reps']
        current_lapses = card['lapses']
        current_left = card['left']

        # Get collection config for scheduling
        cursor.execute("SELECT conf, crt FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data:
            return jsonify({"error": "Database error occurred during review update"}), 500

        coll_conf = json.loads(col_data['conf'])
        collection_creation_time = col_data['crt']

        # Get deck-specific configuration
        deck_id = card['did']
        cursor.execute("SELECT decks, dconf FROM col LIMIT 1")
        deck_config_data = cursor.fetchone()
        if not deck_config_data:
            return jsonify({"error": "Database configuration error"}), 500

        decks_dict = json.loads(deck_config_data['decks'])
        dconf_dict = json.loads(deck_config_data['dconf'])

        # Get the deck's configuration id
        deck_conf_id = decks_dict[str(deck_id)].get('conf', 1)
        deck_conf = dconf_dict[str(deck_conf_id)]

        # Get the configuration settings for the current card state
        if current_type == 0:  # new
            schedule_conf = deck_conf['new']
        elif current_type == 1:  # learning
            schedule_conf = deck_conf['lapse'] if current_queue == 1 else deck_conf['new']
        elif current_type == 2:  # review
            schedule_conf = deck_conf['rev']
        elif current_type == 3:  # relearning
            schedule_conf = deck_conf['lapse']
        else:
            schedule_conf = deck_conf['new']

        # Calculate new interval based on SM-2 algorithm
        new_interval = current_interval
        new_factor = current_factor
        new_due = current_due
        new_queue = current_queue
        new_type = current_type
        new_left = current_left

        # Get current time and day cutoff
        now = int(time.time())
        day_cutoff = (now - collection_creation_time) // 86400

        # Review log type
        review_log_type = current_type

        # SM-2 SCHEDULING ALGORITHM
        if current_queue == 0:  # New card
            if ease == 1:  # Again
                new_queue = 1
                new_type = 1
                new_left = schedule_conf['delays'][0]
                new_due = now + (new_left * 60)
            else:  # Hard, Good, Easy
                new_queue = 1
                new_type = 1
                step_index = 0 if ease == 2 else 1
                if step_index < len(schedule_conf['delays']):
                    new_left = schedule_conf['delays'][step_index]
                    new_due = now + (new_left * 60)
                else:
                    # Graduate to review
                    new_queue = 2
                    new_type = 2
                    new_interval = 1
                    new_due = day_cutoff + new_interval
                    new_left = 0

        elif current_queue == 1:  # Learning/relearning card
            if ease == 1:  # Again
                new_left = schedule_conf['delays'][0]
                new_due = now + (new_left * 60)
            elif ease == 2:  # Hard
                new_due = now + (current_left * 60)
            else:  # Good or Easy
                if current_left == 0 or ease == 4:
                    # Graduate to review
                    new_queue = 2
                    new_type = 2
                    new_interval = 1
                    new_due = day_cutoff + new_interval
                    new_left = 0
                else:
                    # Move to next step
                    step_index = 1
                    if step_index < len(schedule_conf['delays']):
                        new_left = schedule_conf['delays'][step_index]
                        new_due = now + (new_left * 60)
                    else:
                        # Graduate to review
                        new_queue = 2
                        new_type = 2
                        new_interval = 1
                        new_due = day_cutoff + new_interval
                        new_left = 0

        elif current_queue == 2:  # Review card
            if ease == 1:  # Again (lapse)
                # Card lapses, move to relearning
                new_queue = 1
                new_type = 3
                new_lapses = current_lapses + 1
                lapse_conf = deck_conf.get('lapse', {})
                lapse_delays = lapse_conf.get('delays', [10])
                lapse_mult = lapse_conf.get('mult', 0.0)

                if len(lapse_delays) > 0:
                    new_left = lapse_delays[0]
                    new_due = now + (new_left * 60)
                    new_interval = 0
                else:
                    new_queue = 2
                    new_type = 2
                    new_interval = max(1, int(current_interval * lapse_mult))
                    new_due = day_cutoff + new_interval
                    new_left = 0
                review_log_type = 2
            else:  # Hard, Good, Easy
                rev_conf = deck_conf.get('rev', {})
                hard_factor = rev_conf.get('hardFactor', 1.2)
                easy_bonus = rev_conf.get('ease4', 1.3)
                interval_factor = rev_conf.get('ivlFct', 1.0)

                if ease == 2:  # Hard
                    interval_adjust = hard_factor
                    factor_change = -150
                elif ease == 3:  # Good
                    interval_adjust = interval_factor
                    factor_change = 0
                else:  # ease == 4, Easy
                    interval_adjust = easy_bonus * interval_factor
                    factor_change = 150

                # Update interval
                new_interval = max(current_interval + 1, int(current_interval * interval_adjust * interval_factor))

                # Update ease factor (min 1300)
                new_factor = max(1300, current_factor + factor_change)

                # Calculate due date
                new_due = day_cutoff + new_interval

                # Keep in review queue
                new_queue = 2
                new_type = 2
                review_log_type = 1

        # Final assignment for lapses
        final_lapses = current_lapses + (1 if ease == 1 and current_queue == 2 else 0)

        # Update the card
        cursor.execute("""
            UPDATE cards
            SET type=?, queue=?, due=?, ivl=?, factor=?, reps=?, lapses=?, left=?, mod=?
            WHERE id=?
        """, (
            new_type, new_queue, new_due, new_interval, new_factor,
            current_reps + 1, final_lapses,
            new_left, now, card_id
        ))

        # Log this review
        review_id = int(time.time() * 1000)
        cursor.execute("""
            INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id, card_id, -1, ease, new_interval, current_interval,
            new_factor, time_taken, review_log_type
        ))

        # Enhanced logging
        if note_id:
            cursor.execute("SELECT flds FROM notes WHERE id = ?", (note_id,))
            note_data = cursor.fetchone()
            front_text = "Unknown"
            if note_data and note_data[0]:
                fields = note_data[0].split('\x1f')
                front_text = fields[0][:15] + "..." if len(fields[0]) > 15 else fields[0]

            old_state = get_card_state(current_type, current_queue, current_interval)
            new_state = get_card_state(new_type, new_queue, new_interval)

            app.logger.info(f"User {username} reviewed card {card_id} (\"{front_text}\") ease={ease}: {old_state} → {new_state}")

        # Update collection modification time
        cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))

        # Commit changes
        g.db.commit()

        return jsonify({"message": "Review processed successfully", "newDue": new_due}), 200

    except sqlite3.Error as e:
        app.logger.exception(f"Database error during review update: {e}")
        g.db.rollback()
        return jsonify({"error": "Database error occurred during review update"}), 500
    except Exception as e:
        app.logger.exception(f"Error processing review: {e}")
        g.db.rollback()
        return jsonify({"error": f"Error processing review: {str(e)}"}), 500


# --- Session Management Endpoints ---

@app.route('/api/session/start', methods=['POST'])
@jwt_required()
def start_session():
    """
    Explicitly start a session (optional - sessions auto-start on first DB access).

    Returns:
        200: {"session_id": "sess_abc123"}
    """
    username = get_jwt_identity()

    try:
        # Create session-aware connection (don't use 'with' - we need the wrapper)
        db_wrapper = SessionAwareS3SQLite(username)
        conn = db_wrapper.__enter__()

        # Get session_id
        session_id = db_wrapper.session_id

        # Clean up connection (but don't upload - session stays active)
        db_wrapper.__exit__(None, None, None)

        if session_id:
            print(f"✓ Session {session_id} created for {username}")
            return jsonify({"session_id": session_id}), 200
        else:
            print(f"❌ Failed to create session for {username}")
            return jsonify({"error": "Failed to create session"}), 500

    except SessionConflictError as e:
        print(f"⚠️ Session conflict for {username}: {str(e)}")
        return jsonify({'error': str(e), 'code': 'SESSION_CONFLICT'}), 409
    except Exception as e:
        print(f"❌ Error creating session for {username}: {str(e)}")
        return jsonify({"error": "Failed to create session"}), 500


@app.route('/api/session/flush', methods=['POST'])
@jwt_required()
def flush_session():
    """
    Force upload to S3 and end session.

    Request body:
        {
            "session_id": "sess_abc123"
        }

    Returns:
        200: {"success": True}
        400: {"error": "Missing session_id"}
    """
    from s3_sqlite import S3SQLiteConnection
    from session_manager import SessionManager

    username = get_jwt_identity()
    data = request.get_json()

    if not data or 'session_id' not in data:
        return jsonify({"error": "Missing session_id"}), 400

    session_id = data['session_id']

    try:
        # Force upload by opening and closing S3 connection
        with S3SQLiteConnection(username) as conn:
            # Context manager handles upload on exit
            pass

        # Delete session from DynamoDB
        session_mgr = SessionManager()
        session_mgr.delete_session(session_id)

        return jsonify({"success": True}), 200

    except Exception as e:
        app.logger.error(f"Error flushing session {session_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/session/status', methods=['GET'])
@jwt_required()
def session_status():
    """
    Check if user has active session.

    Returns:
        200: {"has_session": true/false, "session_id": "sess_abc123" or null}
    """
    from session_manager import SessionManager

    username = get_jwt_identity()
    session_mgr = SessionManager()
    session = session_mgr.get_user_session(username)

    return jsonify({
        "has_session": session is not None,
        "session_id": session['session_id'] if session else None
    }), 200


# --- Export Endpoints ---

@app.route('/api/export', methods=['GET'])
@jwt_required()
@with_user_db
def export_collection():
    """
    Exports user's entire collection to .apkg file (Anki Package format).

    .apkg format is a ZIP archive containing:
    - collection.anki2: User's SQLite database
    - media: Empty JSON file (no media support currently)

    Uses session-aware DB connection (g.db) - database is already in /tmp.

    Returns:
        Binary ZIP file with mimetype 'application/zip'
        Filename format: <username>_export_<timestamp>.apkg

    Example:
        curl -H "Authorization: Bearer <token>" \
             https://api.example.com/api/export \
             -o my_collection.apkg
    """
    from export import export_user_collection
    import io

    username = get_jwt_identity()
    db_path = f'/tmp/{username}.anki2'

    try:
        # Generate .apkg file (binary ZIP data)
        apkg_bytes, filename = export_user_collection(username, db_path)

        app.logger.info(f"[{username}] Export generated: {filename} ({len(apkg_bytes)} bytes)")

        # Return binary file for download
        return send_file(
            io.BytesIO(apkg_bytes),
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except FileNotFoundError:
        app.logger.error(f"[{username}] Database not found for export: {db_path}")
        return jsonify({"error": "User database not found"}), 404

    except Exception as e:
        app.logger.exception(f"[{username}] Export failed: {e}")
        return jsonify({"error": "Failed to generate export file"}), 500


# --- Error Handlers ---

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


# --- Static File Serving (from S3) ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    """
    Serve static frontend files from S3 bucket.

    This catch-all route serves the React SPA from S3.
    - All API routes are prefixed with /api or specific routes (/login, /register)
    - Everything else is assumed to be a frontend route

    For SPA routing, we return index.html for all non-API routes
    so React Router can handle client-side navigation.
    """
    # Initialize S3 client
    s3 = boto3.client('s3')
    bucket_name = os.environ.get('S3_FRONTEND_BUCKET', 'javumbo-frontend-prod')

    # If no path or root, serve index.html
    if not path or path == '':
        s3_key = 'index.html'
    else:
        s3_key = path

    try:
        # Try to fetch the file from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read()
        content_type = response['ContentType']

        return Response(content, mimetype=content_type)

    except s3.exceptions.NoSuchKey:
        # File not found in S3
        # For SPA routing, return index.html (React Router will handle the route)
        try:
            response = s3.get_object(Bucket=bucket_name, Key='index.html')
            content = response['Body'].read()
            return Response(content, mimetype='text/html')
        except Exception as e:
            app.logger.error(f"Failed to serve index.html: {e}")
            return jsonify({"error": "Frontend not found"}), 404

    except Exception as e:
        app.logger.error(f"Error serving static file {s3_key}: {e}")
        return jsonify({"error": "Failed to load page"}), 500


@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"Internal error: {e}")
    return jsonify({"error": "Internal server error"}), 500


# --- Local Development ---

if __name__ == '__main__':
    # For local testing only
    print("WARNING: Running Flask development server. NOT for production use.")
    print("Use Lambda or Gunicorn for production.")
    app.run(host='0.0.0.0', port=8000, debug=True)
