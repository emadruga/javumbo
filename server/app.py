from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
from flask_session import Session # Import the Session extension
import sqlite3
import bcrypt
import os
import uuid
import time
import json
import zipfile
import hashlib # For Anki checksum
import shutil # For file operations (copying)
import tempfile # For creating temporary directories
import logging # Import logging module
import traceback # Keep for explicit exception logging if needed
import datetime # Import datetime
from functools import wraps

# Add near the top of server/app.py
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

# --- Configuration ---
PORT = 8000 # Port Gunicorn will listen on internally
ADMIN_DB_PATH = os.path.join(basedir, 'admin.db')
# ... other paths ...
SECRET_KEY = os.getenv('SECRET_KEY') # Load from environment
# Ensure SECRET_KEY is loaded, otherwise raise an error or use a default only for non-production
if not SECRET_KEY:
    # In production, this should ideally fail hard
    raise ValueError("No SECRET_KEY set for Flask application")


# Get the directory where app.py resides
basedir = os.path.abspath(os.path.dirname(__file__))

# --- Configuration ---
FLASHCARD_DB_PATH = 'flashcards.db' # We will create user-specific DBs later, this is a placeholder
EXPORT_DIR = os.path.join(basedir, 'exports') # Path relative to app.py
DAILY_NEW_LIMIT = 20 # Maximum number of new cards to introduce per day per user

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app, supports_credentials=True,
    origins=["https://cibernetica.inmetro.gov.br"]) # Allow cross-origin requests, necessary for React dev server


# --- Configure Flask-Session ---
# Choose a directory for session files (must be writable by the Gunicorn user)
# Ensure this directory exists or is created
SESSION_FILE_DIR = os.path.join(basedir, 'flask_session') 
if not os.path.exists(SESSION_FILE_DIR):
    os.makedirs(SESSION_FILE_DIR) # Create the directory if it doesn't exist

app.config['SESSION_TYPE'] = 'filesystem' # Use filesystem-based sessions
app.config['SESSION_FILE_DIR'] = SESSION_FILE_DIR
app.config['SESSION_PERMANENT'] = False # Or True with SESSION_LIFETIME if needed
app.config['SESSION_USE_SIGNER'] = True # Sign the session ID cookie
app.config['SESSION_COOKIE_SECURE'] = True # Important for HTTPS!
app.config['SESSION_COOKIE_HTTPONLY'] = True # Recommended
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Usually 'Lax' or 'Strict'
app.config['SESSION_COOKIE_PATH'] = '/' # Ensure cookie is sent for all paths

# Initialize the Session extension AFTER setting the config
server_session = Session(app) 
# -----------------------------


# --- Logging Configuration ---
# Configure basic logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
# You can customize the format further if needed
app.logger.info(f"Base directory detected: {basedir}")

# --- Helper Functions ---
def get_user_db_path(user_id):
    """Returns the path to the user's specific flashcard database."""
    # Ensure the base directory exists, relative to app.py
    db_dir = os.path.join(basedir, 'user_dbs') # Path relative to app.py
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        app.logger.info(f"Created user DB directory: {db_dir}") # Use logger
    return os.path.join(db_dir, f'user_{user_id}.db')

def sha1_checksum(data):
    """Calculates the SHA1 checksum for Anki note syncing."""
    return hashlib.sha1(data.encode('utf-8')).hexdigest()

# --- Database Setup (Placeholders) ---
# TODO: Implement functions to initialize admin and flashcard databases
# TODO: Implement functions to get DB connections

def init_admin_db():
    """Initializes the admin database and creates the users table if it doesn\'t exist."""
    conn = sqlite3.connect(ADMIN_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    app.logger.info(f"Admin database '{ADMIN_DB_PATH}' initialized.") # Use logger

def init_anki_db(db_path, user_name="Default User"):
    """Initializes a new Anki-compatible SQLite database at the specified path,
    using the provided user_name for the default deck.
    """
    if os.path.exists(db_path):
        app.logger.debug(f"Anki DB already exists at '{db_path}'") # Use logger (DEBUG level)
        return # Avoid re-initializing

    app.logger.info(f"Initializing Anki DB schema in '{db_path}'...") # Use logger
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Anki Schema Definition
    cursor.executescript("""
        CREATE TABLE col (
            id              integer primary key, /* arbritrary */
            crt             integer not null, /* creation time (seconds) */
            mod             integer not null, /* modification time (ms) */
            scm             integer not null, /* schema modification time (ms) */
            ver             integer not null, /* Anki version */
            dty             integer not null, /* dirty (needs sync?) 0 or 1 */
            usn             integer not null, /* update sequence number */
            ls              integer not null, /* last sync time (ms) */
            conf            text not null, /* json config */
            models          text not null, /* json array of models */
            decks           text not null, /* json array of decks */
            dconf           text not null, /* json array of deck confs */
            tags            text not null /* json array of tags */
        );
        CREATE TABLE notes (
            id              integer primary key, /* epoch ms, first note */
            guid            text not null, /* globally unique id, random */
            mid             integer not null, /* model id */
            mod             integer not null, /* modification time, epoch seconds */
            usn             integer not null, /* update sequence number, -1 for local */
            tags            text not null, /* space separated string */
            flds            text not null, /* field content separated by 0x1f */
            sfld            integer not null, /* sort field */
            csum            integer not null, /* sha1 checksum of the first field */
            flags           integer not null, /* unused */
            data            text not null /* unused */
        );
        CREATE TABLE cards (
            id              integer primary key, /* epoch ms, first card */
            nid             integer not null, /* note id */
            did             integer not null, /* deck id */
            ord             integer not null, /* template index */
            mod             integer not null, /* modification time, epoch seconds */
            usn             integer not null, /* update sequence number, -1 for local */
            type            integer not null, /* 0=new, 1=lrn, 2=rev, 3=relrn */
            queue           integer not null, /* -3=sched buried, -2=user buried, -1=suspended, 0=new, 1=lrn, 2=rev, 3=day lrn, 4=preview */
            due             integer not null, /* new: note id, rev: day, lrn: epoch seconds */
            ivl             integer not null, /* interval (days for rev, seconds for lrn) */
            factor          integer not null, /* ease factor (start at 2500) */
            reps            integer not null, /* reviews */
            lapses          integer not null, /* lapses */
            left            integer not null, /* remaining steps in learning */
            odue            integer not null, /* original due */
            odid            integer not null, /* original deck id */
            flags           integer not null, /* unused */
            data            text not null /* unused */
        );
        CREATE TABLE revlog (
            id              integer primary key, /* epoch ms timestamp */
            cid             integer not null, /* card id */
            usn             integer not null, /* update sequence number, -1 for local */
            ease            integer not null, /* 1=again, 2=hard, 3=good, 4=easy */
            ivl             integer not null, /* interval */
            lastIvl         integer not null, /* last interval */
            factor          integer not null, /* factor */
            time            integer not null, /* time taken (ms) */
            type            integer not null /* 0=lrn, 1=rev, 2=relrn, 3=cram */
        );
        CREATE TABLE graves (
            usn             integer not null,
            oid             integer not null,
            type            integer not null /* 0=card, 1=note, 2=deck */
        );
        CREATE INDEX ix_notes_usn ON notes (usn);
        CREATE INDEX ix_cards_usn ON cards (usn);
        CREATE INDEX ix_revlog_usn ON revlog (usn);
        CREATE INDEX ix_cards_nid ON cards (nid);
        CREATE INDEX ix_cards_sched ON cards (did, queue, due);
        CREATE INDEX ix_revlog_cid ON revlog (cid);
        CREATE INDEX ix_notes_csum ON notes (csum);
    """)

    # Populate 'col' table with default Anki data
    crt_time = int(time.time())
    mod_time_ms = int(time.time() * 1000)
    scm_time_ms = mod_time_ms

    default_conf = {
        "nextPos": 1, "estTimes": True, "activeDecks": [1], "sortType": "noteFld",
        "timeLim": 0, "sortBackwards": False, "addToCur": True,
        "curDeck": 1,
        "newBury": True, "newSpread": 0, "dueCounts": True, "curModel": "1",
        "collapseTime": 1200
    }

    # Model ID needs to be consistent. Using epoch time of creation is common.
    # For simplicity, let's use a fixed large number based on current time
    # NOTE: Using a fixed ID like "1" is simpler if we only ever have one model type.
    basic_model_id = "1700000000001" # Example fixed ID

    default_models = {
        basic_model_id: {
            "id": basic_model_id,
            "name": "Basic-Gemini", "type": 0, "mod": crt_time, "usn": -1,
            "sortf": 0, "did": 1, # Default deck ID
            "tmpls": [
                {
                    "name": "Card 1", "ord": 0, "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
                    "bqfmt": "", "bafmt": "", "did": None, "bfont": "Arial", "bsize": 12
                }
            ],
            "flds": [
                {"name": "Front", "ord": 0, "sticky": False, "rtl": False, "font": "Arial", "size": 20},
                {"name": "Back", "ord": 1, "sticky": False, "rtl": False, "font": "Arial", "size": 20}
            ],
            "css": ".card {\n font-family: arial;\n font-size: 20px;\n text-align: center;\n color: black;\n background-color: white;\n}\n",
            "latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}",
            "latexPost": "\\end{document}", "latexsvg": False, "ver": []
        }
    }
    default_decks = {
        "1": { # Deck ID 1 = Default deck
            "id": 1,
            "name": "Verbal Tenses",
            "mod": crt_time, "usn": -1,
            "lrnToday": [0, 0], "revToday": [0, 0], "newToday": [0, 0],
            "timeToday": [0, 0], "conf": 1, # Refers to dconf ID 1
            "desc": f"English verb tenses deck for {user_name}",
            "dyn": 0, "collapsed": False,
             "extendNew": 10, "extendRev": 50
        }
    }
    default_dconf = { # Deck configurations
        "1": { # Dconf ID 1
            "id": 1, "name": "Default", "mod": crt_time, "usn": -1,
            "maxTaken": 60, "timer": 0, "autoplay": True, "replayq": True,
            "new": {"bury": True, "delays": [1, 10], "initialFactor": 2500, "ints": [1, 4, 0], "order": 1, "perDay": 25, "separate": True},
            "rev": {"bury": True, "ease4": 1.3, "fuzz": 0.05, "ivlFct": 1, "maxIvl": 36500, "perDay": 100, "hardFactor": 1.2},
            "lapse": {"delays": [10], "leechAction": 1, "leechFails": 8, "minInt": 1, "mult": 0},
            # Removed "misc" as it's not strictly required for basic function
        }
    }

    cursor.execute(
        "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1, # id
            crt_time, # crt (creation time in seconds)
            mod_time_ms, # mod (modification time in ms)
            scm_time_ms, # scm (schema modification time in ms)
            11, # ver (Anki version this schema resembles)
            0, # dty (dirty flag)
            -1, # usn (update sequence number, -1 for local changes)
            0, # ls (last sync time in ms)
            json.dumps(default_conf), # conf JSON
            json.dumps(default_models), # models JSON
            json.dumps(default_decks), # decks JSON
            json.dumps(default_dconf), # dconf JSON
            json.dumps({}) # tags JSON (empty object)
        )
    )

    conn.commit()
    conn.close()
    app.logger.info(f"Initialized Anki DB schema in '{db_path}'") # Use logger

# --- API Routes (Placeholders) ---

@app.route('/')
def index():
    return "Flashcard Server is Running!"

# TODO: Implement Authentication routes (/register, /login, /logout)
@app.route('/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    
    if not data or not all(k in data for k in ('username', 'name', 'password')):
        return jsonify({"error": "Missing required fields"}), 400
    
    username = data['username'].strip()
    name = data['name'].strip()
    password = data['password']
    
    # Validate username and password length
    if len(username) < 1 or len(username) > 10:
        return jsonify({"error": "Username must be between 1 and 10 characters"}), 400
    
    if len(name) < 1 or len(name) > 40:
        return jsonify({"error": "Name must be between 1 and 40 characters"}), 400
    
    if len(password) < 10 or len(password) > 20:
        return jsonify({"error": "Password must be between 10 and 20 characters"}), 400
    
    # Hash the password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Initialize admin database if it doesn't exist yet
    init_admin_db()
    
    # Check if username already exists
    conn = sqlite3.connect(ADMIN_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Username already exists"}), 409
    
    # Insert the new user
    try:
        cursor.execute(
            "INSERT INTO users (username, name, password_hash) VALUES (?, ?, ?)",
            (username, name, password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        app.logger.info(f"User registered: {username} (ID: {user_id})")
        
        # Create user flashcard database
        user_db_path = get_user_db_path(user_id)
        init_anki_db(user_db_path, user_name=name)
        add_initial_flashcards(user_db_path, "1700000000001")  # Using fixed model ID from init
        
        return jsonify({
            "message": "User registered successfully",
            "userId": user_id
        }), 201
    except Exception as e:
        conn.rollback()
        conn.close()
        app.logger.exception(f"Error during registration: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/login', methods=['POST'])
def login():
    """Authenticates a user and creates a session."""
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Username and password are required"}), 400
    
    username = data['username']
    password = data['password']
    
    # Initialize admin database if it doesn't exist yet
    init_admin_db()
    
    try:
        conn = sqlite3.connect(ADMIN_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Verify password
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Create session
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            
            app.logger.info(f"User logged in: {username} (ID: {user['user_id']})")
            
            return jsonify({
                "message": "Login successful",
                "user": {
                    "userId": user['user_id'],
                    "username": user['username'],
                    "name": user['name']
                }
            }), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        app.logger.exception(f"Error during login: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user session
    session.pop('user_id', None)
    session.pop('username', None)
    # Remove the name variable from session since we don't store it anymore
    app.logger.info("User logged out.") # Use logger
    return jsonify({"message": "Logout successful"}), 200

# TODO: Implement Flashcard routes (/review, /answer, /export)
# TODO: Implement User session management

# --- Flashcard Generation ---

def generate_ai_flashcards():
    """Generates a list of flashcards about verbal tenses in English, with each example
    sentence as its own flashcard including Portuguese translations."""
    # Define the structure of verbal tenses
    tenses = [
        # Simple Present
        {
            "name": "Simple Present: I work",
            "usage": "Usage: For habits, routines, facts, and general truths.",
            "usage_pt": "Uso: Para hábitos, rotinas, fatos e verdades gerais.",
            "examples": [
                {
                    "en": "She plays tennis every weekend.",
                    "pt": "Ela joga tênis todos os fins de semana."
                },
                {
                    "en": "The sun rises in the east.", 
                    "pt": "O sol nasce no leste."
                },
                {
                    "en": "They live in New York.",
                    "pt": "Eles moram em Nova York."
                }
            ]
        },
        {
            "name": "Simple Present: Negatives",
            "usage": "Form: Subject + do/does + not + verb",
            "usage_pt": "Forma: Sujeito + do/does + not + verbo",
            "examples": [
                {
                    "en": "I do not (don't) speak French.",
                    "pt": "Eu não falo francês."
                },
                {
                    "en": "He does not (doesn't) own a car.",
                    "pt": "Ele não possui um carro."
                },
                {
                    "en": "They do not (don't) like coffee.",
                    "pt": "Eles não gostam de café."
                }
            ]
        },
        {
            "name": "Simple Present: Questions",
            "usage": "Form: Do/Does + subject + verb?",
            "usage_pt": "Forma: Do/Does + sujeito + verbo?",
            "examples": [
                {
                    "en": "Do you enjoy swimming?",
                    "pt": "Você gosta de nadar?"
                },
                {
                    "en": "Does she work here?",
                    "pt": "Ela trabalha aqui?"
                },
                {
                    "en": "Do they understand the rules?",
                    "pt": "Eles entendem as regras?"
                }
            ]
        },
        
        # Present Continuous/Progressive
        {
            "name": "Present Continuous: I am working",
            "usage": "Usage: For actions happening now or around now, and temporary situations.",
            "usage_pt": "Uso: Para ações acontecendo agora ou por volta de agora, e situações temporárias.",
            "examples": [
                {
                    "en": "She is studying for her exam.",
                    "pt": "Ela está estudando para o exame dela."
                },
                {
                    "en": "They are building a new house this year.",
                    "pt": "Eles estão construindo uma casa nova este ano."
                },
                {
                    "en": "I am learning to play the guitar.",
                    "pt": "Eu estou aprendendo a tocar guitarra."
                }
            ]
        },
        {
            "name": "Present Continuous: Negatives",
            "usage": "Form: Subject + am/is/are + not + verb-ing",
            "usage_pt": "Forma: Sujeito + am/is/are + not + verbo-ing",
            "examples": [
                {
                    "en": "He is not (isn't) sleeping right now.",
                    "pt": "Ele não está dormindo agora."
                },
                {
                    "en": "We are not (aren't) having dinner yet.",
                    "pt": "Nós não estamos jantando ainda."
                },
                {
                    "en": "I am not waiting any longer.",
                    "pt": "Eu não estou esperando mais."
                }
            ]
        },
        {
            "name": "Present Continuous: Questions",
            "usage": "Form: Am/Is/Are + subject + verb-ing?",
            "usage_pt": "Forma: Am/Is/Are + sujeito + verbo-ing?",
            "examples": [
                {
                    "en": "Are you listening to me?",
                    "pt": "Você está me ouvindo?"
                },
                {
                    "en": "Is it raining outside?",
                    "pt": "Está chovendo lá fora?"
                },
                {
                    "en": "Are they coming to the party?",
                    "pt": "Eles estão vindo para a festa?"
                }
            ]
        },
        
        # Present Perfect
        {
            "name": "Present Perfect: I have worked",
            "usage": "Usage: For past actions with present results, experiences, and unfinished time periods.",
            "usage_pt": "Uso: Para ações passadas com resultados presentes, experiências e períodos de tempo inacabados.",
            "examples": [
                {
                    "en": "I have visited Paris twice.",
                    "pt": "Eu já visitei Paris duas vezes."
                },
                {
                    "en": "She has lived here for five years.",
                    "pt": "Ela tem morado aqui por cinco anos."
                },
                {
                    "en": "They have already finished their homework.",
                    "pt": "Eles já terminaram a lição de casa."
                }
            ]
        },
        {
            "name": "Present Perfect: Negatives",
            "usage": "Form: Subject + have/has + not + past participle",
            "usage_pt": "Forma: Sujeito + have/has + not + particípio passado",
            "examples": [
                {
                    "en": "I have not (haven't) seen that movie.",
                    "pt": "Eu não vi esse filme."
                },
                {
                    "en": "She has not (hasn't) called me back.",
                    "pt": "Ela não me ligou de volta."
                },
                {
                    "en": "We have not (haven't) been to that restaurant.",
                    "pt": "Nós não fomos àquele restaurante."
                }
            ]
        },
        {
            "name": "Present Perfect: Questions",
            "usage": "Form: Have/Has + subject + past participle?",
            "usage_pt": "Forma: Have/Has + sujeito + particípio passado?",
            "examples": [
                {
                    "en": "Have you ever climbed a mountain?",
                    "pt": "Você já escalou uma montanha?"
                },
                {
                    "en": "Has he sent the email?",
                    "pt": "Ele enviou o email?"
                },
                {
                    "en": "Have they arrived yet?",
                    "pt": "Eles já chegaram?"
                }
            ]
        },
        
        # Present Perfect Continuous
        {
            "name": "Present Perfect Continuous: I have been working",
            "usage": "Usage: For ongoing actions that started in the past and continue to the present, often emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que começaram no passado e continuam até o presente, frequentemente enfatizando a duração.",
            "examples": [
                {
                    "en": "I have been waiting for an hour.",
                    "pt": "Eu estou esperando há uma hora."
                },
                {
                    "en": "She has been teaching since 2010.",
                    "pt": "Ela está ensinando desde 2010."
                },
                {
                    "en": "They have been traveling all month.",
                    "pt": "Eles estão viajando o mês todo."
                }
            ]
        },
        {
            "name": "Present Perfect Continuous: Negatives",
            "usage": "Form: Subject + have/has + not + been + verb-ing",
            "usage_pt": "Forma: Sujeito + have/has + not + been + verbo-ing",
            "examples": [
                {
                    "en": "I have not (haven't) been feeling well.",
                    "pt": "Eu não tenho me sentido bem."
                },
                {
                    "en": "He has not (hasn't) been working lately.",
                    "pt": "Ele não tem trabalhado ultimamente."
                },
                {
                    "en": "They have not (haven't) been studying enough.",
                    "pt": "Eles não têm estudado o suficiente."
                }
            ]
        },
        {
            "name": "Present Perfect Continuous: Questions",
            "usage": "Form: Have/Has + subject + been + verb-ing?",
            "usage_pt": "Forma: Have/Has + sujeito + been + verbo-ing?",
            "examples": [
                {
                    "en": "Have you been exercising regularly?",
                    "pt": "Você tem se exercitado regularmente?"
                },
                {
                    "en": "Has she been living alone?",
                    "pt": "Ela tem morado sozinha?"
                },
                {
                    "en": "Have they been practicing for the concert?",
                    "pt": "Eles têm praticado para o concerto?"
                }
            ]
        },
        
        # Simple Past
        {
            "name": "Simple Past: I worked",
            "usage": "Usage: For completed actions in the past.",
            "usage_pt": "Uso: Para ações completas no passado.",
            "examples": [
                {
                    "en": "She visited her grandmother last week.",
                    "pt": "Ela visitou a avó dela na semana passada."
                },
                {
                    "en": "They bought a new car yesterday.",
                    "pt": "Eles compraram um carro novo ontem."
                },
                {
                    "en": "I watched a movie last night.",
                    "pt": "Eu assisti um filme ontem à noite."
                }
            ]
        },
        {
            "name": "Simple Past: Negatives",
            "usage": "Form: Subject + did + not + verb",
            "usage_pt": "Forma: Sujeito + did + not + verbo",
            "examples": [
                {
                    "en": "I did not (didn't) go to the party.",
                    "pt": "Eu não fui à festa."
                },
                {
                    "en": "She did not (didn't) like the book.",
                    "pt": "Ela não gostou do livro."
                },
                {
                    "en": "They did not (didn't) finish their work.",
                    "pt": "Eles não terminaram o trabalho deles."
                }
            ]
        },
        {
            "name": "Simple Past: Questions",
            "usage": "Form: Did + subject + verb?",
            "usage_pt": "Forma: Did + sujeito + verbo?",
            "examples": [
                {
                    "en": "Did you call him?",
                    "pt": "Você ligou para ele?"
                },
                {
                    "en": "Did she arrive on time?",
                    "pt": "Ela chegou na hora?"
                },
                {
                    "en": "Did they win the game?",
                    "pt": "Eles ganharam o jogo?"
                }
            ]
        },
        
        # Past Continuous/Progressive
        {
            "name": "Past Continuous: I was working",
            "usage": "Usage: For actions in progress at a specific time in the past, often interrupted by another action.",
            "usage_pt": "Uso: Para ações em progresso em um momento específico no passado, frequentemente interrompidas por outra ação.",
            "examples": [
                {
                    "en": "I was reading when the phone rang.",
                    "pt": "Eu estava lendo quando o telefone tocou."
                },
                {
                    "en": "They were having dinner at 8 PM.",
                    "pt": "Eles estavam jantando às 8 da noite."
                },
                {
                    "en": "She was sleeping when I came home.",
                    "pt": "Ela estava dormindo quando eu cheguei em casa."
                }
            ]
        },
        {
            "name": "Past Continuous: Negatives",
            "usage": "Form: Subject + was/were + not + verb-ing",
            "usage_pt": "Forma: Sujeito + was/were + not + verbo-ing",
            "examples": [
                {
                    "en": "I was not (wasn't) listening carefully.",
                    "pt": "Eu não estava ouvindo com atenção."
                },
                {
                    "en": "They were not (weren't) expecting visitors.",
                    "pt": "Eles não estavam esperando visitantes."
                },
                {
                    "en": "She was not (wasn't) driving fast.",
                    "pt": "Ela não estava dirigindo rápido."
                }
            ]
        },
        {
            "name": "Past Continuous: Questions",
            "usage": "Form: Was/Were + subject + verb-ing?",
            "usage_pt": "Forma: Was/Were + sujeito + verbo-ing?",
            "examples": [
                {
                    "en": "Were you waiting for me?",
                    "pt": "Você estava esperando por mim?"
                },
                {
                    "en": "Was he telling the truth?",
                    "pt": "Ele estava dizendo a verdade?"
                },
                {
                    "en": "Were they working late?",
                    "pt": "Eles estavam trabalhando até tarde?"
                }
            ]
        },
        
        # Past Perfect
        {
            "name": "Past Perfect: I had worked",
            "usage": "Usage: For actions completed before another past action or time.",
            "usage_pt": "Uso: Para ações completadas antes de outra ação passada ou tempo.",
            "examples": [
                {
                    "en": "I had finished dinner before she called.",
                    "pt": "Eu tinha terminado o jantar antes de ela ligar."
                },
                {
                    "en": "They had left before I arrived.",
                    "pt": "Eles tinham saído antes de eu chegar."
                },
                {
                    "en": "She had studied Spanish before moving to Madrid.",
                    "pt": "Ela tinha estudado espanhol antes de se mudar para Madri."
                }
            ]
        },
        {
            "name": "Past Perfect: Negatives",
            "usage": "Form: Subject + had + not + past participle",
            "usage_pt": "Forma: Sujeito + had + not + particípio passado",
            "examples": [
                {
                    "en": "I had not (hadn't) seen the movie before.",
                    "pt": "Eu não tinha visto o filme antes."
                },
                {
                    "en": "She had not (hadn't) completed her work.",
                    "pt": "Ela não tinha completado o trabalho dela."
                },
                {
                    "en": "They had not (hadn't) heard the news.",
                    "pt": "Eles não tinham ouvido as notícias."
                }
            ]
        },
        {
            "name": "Past Perfect: Questions",
            "usage": "Form: Had + subject + past participle?",
            "usage_pt": "Forma: Had + sujeito + particípio passado?",
            "examples": [
                {
                    "en": "Had you met him before?",
                    "pt": "Você tinha conhecido ele antes?"
                },
                {
                    "en": "Had she ever visited London?",
                    "pt": "Ela já tinha visitado Londres?"
                },
                {
                    "en": "Had they received my message?",
                    "pt": "Eles tinham recebido minha mensagem?"
                }
            ]
        },
        
        # Past Perfect Continuous
        {
            "name": "Past Perfect Continuous: I had been working",
            "usage": "Usage: For ongoing actions that started before and continued up to another time in the past, emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que começaram antes e continuaram até outro momento no passado, enfatizando a duração.",
            "examples": [
                {
                    "en": "I had been studying for three hours when she called.",
                    "pt": "Eu estava estudando há três horas quando ela ligou."
                },
                {
                    "en": "They had been living there for years before they moved.",
                    "pt": "Eles estavam morando lá por anos antes de se mudarem."
                },
                {
                    "en": "She had been working all day before she went home.",
                    "pt": "Ela estava trabalhando o dia todo antes de ir para casa."
                }
            ]
        },
        {
            "name": "Past Perfect Continuous: Negatives",
            "usage": "Form: Subject + had + not + been + verb-ing",
            "usage_pt": "Forma: Sujeito + had + not + been + verbo-ing",
            "examples": [
                {
                    "en": "I had not (hadn't) been sleeping well before the exam.",
                    "pt": "Eu não estava dormindo bem antes do exame."
                },
                {
                    "en": "She had not (hadn't) been feeling well.",
                    "pt": "Ela não estava se sentindo bem."
                },
                {
                    "en": "They had not (hadn't) been paying attention.",
                    "pt": "Eles não estavam prestando atenção."
                }
            ]
        },
        {
            "name": "Past Perfect Continuous: Questions",
            "usage": "Form: Had + subject + been + verb-ing?",
            "usage_pt": "Forma: Had + sujeito + been + verbo-ing?",
            "examples": [
                {
                    "en": "Had you been waiting long?",
                    "pt": "Você estava esperando há muito tempo?"
                },
                {
                    "en": "Had she been working there before?",
                    "pt": "Ela estava trabalhando lá antes?"
                },
                {
                    "en": "Had they been expecting this outcome?",
                    "pt": "Eles estavam esperando este resultado?"
                }
            ]
        },
        
        # Simple Future
        {
            "name": "Simple Future: I will work",
            "usage": "Usage: For predictions, promises, offers, and decisions made at the moment of speaking.",
            "usage_pt": "Uso: Para previsões, promessas, ofertas e decisões tomadas no momento da fala.",
            "examples": [
                {
                    "en": "I will help you tomorrow.",
                    "pt": "Eu vou te ajudar amanhã."
                },
                {
                    "en": "She will probably arrive late.",
                    "pt": "Ela provavelmente vai chegar atrasada."
                },
                {
                    "en": "They will be here soon.",
                    "pt": "Eles estarão aqui em breve."
                }
            ]
        },
        {
            "name": "Simple Future: Negatives",
            "usage": "Form: Subject + will + not + verb",
            "usage_pt": "Forma: Sujeito + will + not + verbo",
            "examples": [
                {
                    "en": "I will not (won't) be available tomorrow.",
                    "pt": "Eu não estarei disponível amanhã."
                },
                {
                    "en": "She will not (won't) agree to these terms.",
                    "pt": "Ela não vai concordar com estes termos."
                },
                {
                    "en": "They will not (won't) finish on time.",
                    "pt": "Eles não vão terminar a tempo."
                }
            ]
        },
        {
            "name": "Simple Future: Questions",
            "usage": "Form: Will + subject + verb?",
            "usage_pt": "Forma: Will + sujeito + verbo?",
            "examples": [
                {
                    "en": "Will you attend the meeting?",
                    "pt": "Você vai participar da reunião?"
                },
                {
                    "en": "Will she join us for dinner?",
                    "pt": "Ela vai se juntar a nós para o jantar?"
                },
                {
                    "en": "Will they accept our offer?",
                    "pt": "Eles vão aceitar nossa oferta?"
                }
            ]
        },
        
        # Future Continuous/Progressive
        {
            "name": "Future Continuous: I will be working",
            "usage": "Usage: For actions that will be in progress at a specific time in the future.",
            "usage_pt": "Uso: Para ações que estarão em andamento em um momento específico no futuro.",
            "examples": [
                {
                    "en": "This time tomorrow, I will be flying to Paris.",
                    "pt": "Amanhã a esta hora, eu estarei voando para Paris."
                },
                {
                    "en": "She will be studying when you call.",
                    "pt": "Ela estará estudando quando você ligar."
                },
                {
                    "en": "They will be waiting for us when we arrive.",
                    "pt": "Eles estarão esperando por nós quando chegarmos."
                }
            ]
        },
        {
            "name": "Future Continuous: Negatives",
            "usage": "Form: Subject + will + not + be + verb-ing",
            "usage_pt": "Forma: Sujeito + will + not + be + verbo-ing",
            "examples": [
                {
                    "en": "I will not (won't) be working this weekend.",
                    "pt": "Eu não estarei trabalhando neste fim de semana."
                },
                {
                    "en": "She will not (won't) be attending the conference.",
                    "pt": "Ela não estará participando da conferência."
                },
                {
                    "en": "They will not (won't) be staying with us.",
                    "pt": "Eles não estarão ficando conosco."
                }
            ]
        },
        {
            "name": "Future Continuous: Questions",
            "usage": "Form: Will + subject + be + verb-ing?",
            "usage_pt": "Forma: Will + sujeito + be + verbo-ing?",
            "examples": [
                {
                    "en": "Will you be using the car tomorrow?",
                    "pt": "Você estará usando o carro amanhã?"
                },
                {
                    "en": "Will she be coming to the party?",
                    "pt": "Ela estará vindo para a festa?"
                },
                {
                    "en": "Will they be joining us for lunch?",
                    "pt": "Eles estarão se juntando a nós para o almoço?"
                }
            ]
        },
        
        # Future Perfect
        {
            "name": "Future Perfect: I will have worked",
            "usage": "Usage: For actions that will be completed before a specific time in the future.",
            "usage_pt": "Uso: Para ações que serão concluídas antes de um momento específico no futuro.",
            "examples": [
                {
                    "en": "By next month, I will have finished my degree.",
                    "pt": "Até o próximo mês, eu terei terminado meu curso."
                },
                {
                    "en": "She will have completed the project by Friday.",
                    "pt": "Ela terá completado o projeto até sexta-feira."
                },
                {
                    "en": "They will have moved into their new house by Christmas.",
                    "pt": "Eles terão se mudado para a nova casa até o Natal."
                }
            ]
        },
        {
            "name": "Future Perfect: Negatives",
            "usage": "Form: Subject + will + not + have + past participle",
            "usage_pt": "Forma: Sujeito + will + not + have + particípio passado",
            "examples": [
                {
                    "en": "I will not (won't) have read the book by then.",
                    "pt": "Eu não terei lido o livro até lá."
                },
                {
                    "en": "She will not (won't) have arrived by that time.",
                    "pt": "Ela não terá chegado até aquela hora."
                },
                {
                    "en": "They will not (won't) have made a decision before the deadline.",
                    "pt": "Eles não terão tomado uma decisão antes do prazo."
                }
            ]
        },
        {
            "name": "Future Perfect: Questions",
            "usage": "Form: Will + subject + have + past participle?",
            "usage_pt": "Forma: Will + sujeito + have + particípio passado?",
            "examples": [
                {
                    "en": "Will you have finished by tomorrow?",
                    "pt": "Você terá terminado até amanhã?"
                },
                {
                    "en": "Will she have prepared everything?",
                    "pt": "Ela terá preparado tudo?"
                },
                {
                    "en": "Will they have solved the problem by then?",
                    "pt": "Eles terão resolvido o problema até lá?"
                }
            ]
        },
        
        # Future Perfect Continuous
        {
            "name": "Future Perfect Continuous: I will have been working",
            "usage": "Usage: For ongoing actions that will continue up to a specific time in the future, emphasizing duration.",
            "usage_pt": "Uso: Para ações contínuas que continuarão até um momento específico no futuro, enfatizando a duração.",
            "examples": [
                {
                    "en": "By next week, I will have been working here for five years.",
                    "pt": "Até a próxima semana, eu estarei trabalhando aqui há cinco anos."
                },
                {
                    "en": "She will have been studying for six hours by the time she finishes.",
                    "pt": "Ela estará estudando por seis horas quando terminar."
                },
                {
                    "en": "They will have been traveling for two days when they arrive.",
                    "pt": "Eles estarão viajando por dois dias quando chegarem."
                }
            ]
        },
        {
            "name": "Future Perfect Continuous: Negatives",
            "usage": "Form: Subject + will + not + have + been + verb-ing",
            "usage_pt": "Forma: Sujeito + will + not + have + been + verbo-ing",
            "examples": [
                {
                    "en": "I will not (won't) have been waiting for more than an hour.",
                    "pt": "Eu não estarei esperando por mais de uma hora."
                },
                {
                    "en": "She will not (won't) have been teaching for very long.",
                    "pt": "Ela não estará ensinando por muito tempo."
                },
                {
                    "en": "They will not (won't) have been living there for much time.",
                    "pt": "Eles não estarão morando lá por muito tempo."
                }
            ]
        },
        {
            "name": "Future Perfect Continuous: Questions",
            "usage": "Form: Will + subject + have + been + verb-ing?",
            "usage_pt": "Forma: Will + sujeito + have + been + verbo-ing?",
            "examples": [
                {
                    "en": "Will you have been working all day?",
                    "pt": "Você estará trabalhando o dia todo?"
                },
                {
                    "en": "Will she have been practicing enough?",
                    "pt": "Ela estará praticando o suficiente?"
                },
                {
                    "en": "Will they have been searching for long?",
                    "pt": "Eles estarão procurando por muito tempo?"
                }
            ]
        }
    ]
    
    # Create cards based on the new structure
    cards = []
    
    for tense in tenses:
        tense_name = tense["name"]
        usage = tense["usage"]
        usage_pt = tense["usage_pt"]
        
        # For each example, create a flashcard with the English sentence as the front and
        # Portuguese translation, tense name, and usage as the back
        for example in tense["examples"]:
            front = example["en"]
            back = f'(a) "{example["pt"]}"\n\n(b) {tense_name}\n\n(c) {usage_pt}'
            cards.append((front, back))
    
    return cards

def add_initial_flashcards(db_path, model_id):
    """Adds the initial set of flashcards about verbal tenses to the user's Anki DB."""
    cards_to_add = generate_ai_flashcards()
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        current_time_sec = int(time.time())
        current_time_ms = int(current_time_sec * 1000)
        deck_id = 1 # Default deck
        usn = -1 # Local changes

        for i, (front, back) in enumerate(cards_to_add):
            note_id = current_time_ms + i # Simple unique ID generation
            card_id = note_id + 1 # Ensure card ID is different from note ID
            guid = str(uuid.uuid4())[:10] # Short unique ID
            fields = f"{front}\x1f{back}" # Fields separated by 0x1f
            checksum = sha1_checksum(front) # Checksum of the first field (sort field)

            # Insert Note
            cursor.execute("""
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (note_id, guid, model_id, current_time_sec, usn, "verbal_tenses", fields, front, int(checksum, 16) & 0xFFFFFFFF, 0, ""))

            # Insert Card (New card state)
            cursor.execute("""
                INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                card_id, note_id, deck_id, 0, current_time_sec, usn,
                0, # type = new
                0, # queue = new
                note_id, # due = note id for new cards (or ord)
                0, # ivl
                2500, # factor (initial ease)
                0, # reps
                0, # lapses
                0, # left (steps remaining, starts at 0 for simple new cards)
                0, # odue (original due)
                0, # odid (original deck id)
                0, # flags
                "" # data
            ))

        conn.commit()
    except Exception as e:
        app.logger.error(f"Error adding initial flashcards to {db_path}: {e}") # Use logger
        if conn: conn.rollback() # Rollback changes if error occurs
        raise # Re-raise the exception to be caught by the caller
    finally:
        if conn:
            conn.close()

# --- Helper Functions for Review Logic ---

def _getDbConnection(userDbPath):
    """Establishes and returns a database connection with row factory."""
    try:
        conn = sqlite3.connect(userDbPath)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        app.logger.error(f"Database connection error to {userDbPath}: {e}")
        raise  # Re-raise the exception to be handled by the caller

def _getCollectionConfig(cursor):
    """Fetches essential configuration from the col table."""
    try:
        cursor.execute("SELECT crt, conf, decks FROM col LIMIT 1")
        colData = cursor.fetchone()
        if not colData:
            raise ValueError("Collection configuration could not be read")

        confDict = json.loads(colData['conf'])
        decksDict = json.loads(colData['decks'])
        currentDeckId = confDict.get('curDeck', 1)
        deckName = decksDict.get(str(currentDeckId), {}).get('name', 'Default')

        return {
            "collectionCreationTime": colData['crt'],
            "currentDeckId": currentDeckId,
            "deckName": deckName
        }
    except (sqlite3.Error, json.JSONDecodeError, KeyError, ValueError) as e:
        app.logger.error(f"Error processing collection config: {e}")
        raise ValueError("Failed to process collection configuration")

def _calculateDayCutoff(collectionCreationTime):
    """Calculates the current time and day cutoff based on collection creation."""
    now = int(time.time())
    # Calculate days since collection creation time, this is how Anki determines the 'day'
    dayCutoff = (now - collectionCreationTime) // 86400
    return now, dayCutoff

def _countNewCardsReviewedToday(cursor, dayCutoff, collectionCreationTime):
    """Counts cards marked as 'new' (type=0) in today's review log."""
    # Calculate the timestamp for the start of the current day relative to collection creation
    startOfDayTimestampMs = (collectionCreationTime + dayCutoff * 86400) * 1000
    try:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM revlog 
            WHERE id >= ? AND type = 0
        """, (startOfDayTimestampMs,))
        countResult = cursor.fetchone()
        return countResult[0] if countResult else 0
    except sqlite3.Error as e:
        app.logger.error(f"Error counting new cards reviewed today: {e}")
        return 0 # Fail safe: assume 0 if error occurs

def _fetchLearningCard(cursor, currentDeckId, now):
    """Fetches the next due learning/relearning card."""
    try:
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND (c.queue = 1 OR c.queue = 3) AND c.due <= ?
            ORDER BY c.due
            LIMIT 1
        """, (currentDeckId, now))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching learning card: {e}")
        return None

def _fetchReviewCard(cursor, currentDeckId, dayCutoff):
    """Fetches the next due review card."""
    try:
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds, c.due, c.ivl
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND c.queue = 2 AND c.due <= ?
            ORDER BY c.due
            LIMIT 1
        """, (currentDeckId, dayCutoff))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching review card: {e}")
        return None

def _fetchNewCard(cursor, currentDeckId):
    """Fetches the next new card randomly.""" # <-- Updated docstring
    try:
        # Order by RANDOM() to select a random new card
        cursor.execute("""
            SELECT c.id, c.nid, c.queue, n.flds
            FROM cards c JOIN notes n ON c.nid = n.id
            WHERE c.did = ? AND c.queue = 0
            ORDER BY RANDOM() 
            LIMIT 1
        """, (currentDeckId,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        app.logger.error(f"Error fetching new card: {e}")
        return None

def _formatCardResponse(cardData):
    """Formats the card data for the JSON response and updates session."""
    if not cardData:
        return None
    
    try:
        fields = cardData['flds'].split('\x1f') # Anki separator
        front = fields[0]
        back = fields[1] if len(fields) > 1 else ""
        
        # Store the current card ID in the session for the answer endpoint
        session['currentCardId'] = cardData['id']
        session['currentNoteId'] = cardData['nid']
        
        return {
            "cardId": cardData['id'],
            "front": front,
            "back": back,
            "queue": cardData['queue']
        }
    except Exception as e:
        app.logger.error(f"Error formatting card response: {e} for cardData: {cardData}")
        # Clear potentially inconsistent session data
        session.pop('currentCardId', None)
        session.pop('currentNoteId', None)
        return None

# --- Authentication Decorator ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        # You could add further checks here, e.g., verify user_id against admin db
        return f(*args, **kwargs)
    return decorated_function

# --- Flashcard Review Logic ---

@app.route('/review', methods=['GET'])
@login_required
def get_next_card():
    """Fetches the next card due for review using prioritized queues and daily limits."""
    userId = session['user_id']
    userDbPath = get_user_db_path(userId)
    
    if not os.path.exists(userDbPath):
        app.logger.error(f"User database not found for user {userId} at {userDbPath}")
        return jsonify({"error": "User database not found. Please re-register or contact support."}), 404
    
    conn = None
    try:
        conn = _getDbConnection(userDbPath)
        cursor = conn.cursor()

        # Fetch configuration and calculate time cutoffs
        try:
            config = _getCollectionConfig(cursor)
            collectionCreationTime = config['collectionCreationTime']
            currentDeckId = config['currentDeckId']
            deckName = config['deckName']
        except ValueError as e:
            # Error logged in helper, return error response
            return jsonify({"error": str(e)}), 500

        now, dayCutoff = _calculateDayCutoff(collectionCreationTime)
        
        # Count new cards reviewed today
        newCardsSeenToday = _countNewCardsReviewedToday(cursor, dayCutoff, collectionCreationTime)
        
        app.logger.debug(f"User {userId}, Deck {currentDeckId}: Day Cutoff={dayCutoff}, Now={now}, New Seen={newCardsSeenToday}/{DAILY_NEW_LIMIT}")

        nextCardData = None

        # 1. Check for Learning Cards
        nextCardData = _fetchLearningCard(cursor, currentDeckId, now)
        if nextCardData:
            app.logger.debug(f"Found learning card {nextCardData['id']}")

        # 2. Check for Due Review Cards
        if not nextCardData:
            nextCardData = _fetchReviewCard(cursor, currentDeckId, dayCutoff)
            if nextCardData:
                # Log details if a review card (Young or Mature) is fetched
                app.logger.info(f"Found review card {nextCardData['id']} (queue={nextCardData['queue']}). Card Due: {nextCardData['due']}, Card Interval: {nextCardData['ivl']} days. Current Day Cutoff: {dayCutoff}")

        # 3. Check for New Cards (respecting limit)
        if not nextCardData:
            if newCardsSeenToday < DAILY_NEW_LIMIT:
                nextCardData = _fetchNewCard(cursor, currentDeckId)
                if nextCardData:
                    app.logger.debug(f"Found new card {nextCardData['id']}")
                else:
                     app.logger.debug("No more new cards available in deck.")
            else:
                app.logger.debug(f"Daily new card limit ({DAILY_NEW_LIMIT}) reached.")

        # Format and return card if found
        if nextCardData:
            responsePayload = _formatCardResponse(nextCardData)
            if responsePayload:
                 return jsonify(responsePayload), 200
            else:
                # Error formatting or card invalid, treat as internal error
                return jsonify({"error": "Failed to process card data."}), 500
        else:
            # No card found in any queue (or new limit reached)
            session.pop('currentCardId', None)
            session.pop('currentNoteId', None)
            
            # Check total remaining cards for message accuracy
            cursor.execute("SELECT COUNT(*) as card_count FROM cards WHERE did = ? AND queue >= 0 AND queue <= 3", (currentDeckId,))
            countResult = cursor.fetchone()
            totalCardsInDeck = countResult['card_count'] if countResult else 0
            
            message = f"No cards available for review in deck '{deckName}'."
            if totalCardsInDeck > 0:
                if newCardsSeenToday >= DAILY_NEW_LIMIT and _fetchNewCard(cursor, currentDeckId) is not None:
                    message = f"Daily limit of {DAILY_NEW_LIMIT} new cards reached for deck '{deckName}'."
                else: 
                    message = f"No cards due for deck '{deckName}' right now."
                    
            app.logger.info(message) # Log the final message
            return jsonify({"message": message}), 200
            
    except sqlite3.Error as e:
        app.logger.error(f"Database error in get_next_card for user {userId}: {e}")
        # Use traceback.format_exc() for detailed debug logs if needed
        # app.logger.error(traceback.format_exc())
        return jsonify({"error": f"A database error occurred."}), 500
    except Exception as e:
        app.logger.exception(f"Unexpected error in get_next_card for user {userId}: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500
    finally:
        if conn:
            conn.close()

@app.route('/answer', methods=['POST'])
@login_required
def answer_card():
    """Processes a user's answer to the current card in the session.
    Expects: {'ease': 1-4, 'timeTaken': milliseconds} in the request body.
    Note: ease 1 = Again, 2 = Hard, 3 = Good, 4 = Easy
    """
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    
    # Get the current card ID from the session
    current_card_id = session.get('currentCardId')
    current_note_id = session.get('currentNoteId')
    
    # Get the ease from the request body (1-4)
    data = request.get_json()
    
    if not data or 'ease' not in data:
        app.logger.warning("Missing ease in answer request")
        return jsonify({"error": "Missing ease rating"}), 400
    
    ease = data.get('ease')
    time_taken = data.get('timeTaken', 0)  # Use timeTaken parameter instead of time_taken
    
    # Validate ease value
    if ease not in [1, 2, 3, 4]:
        app.logger.warning(f"Invalid ease value: {ease}")
        return jsonify({"error": "Invalid ease rating (must be 1, 2, 3, or 4)"}), 400
    
    # Make sure we have a current card in the session
    if not current_card_id or not current_note_id:
        app.logger.warning("Missing card information in session for answer processing")
        return jsonify({"error": "Missing card information in session or invalid request. Please get a card first."}), 400
    
    # Process the answer
    conn = None
    try:
        app.logger.info(f"Processing answer for card {current_card_id} (note {current_note_id}) with ease {ease}")
        
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First, verify the card exists
        cursor.execute("SELECT * FROM cards WHERE id = ?", (current_card_id,))
        card = cursor.fetchone()
        if not card:
            app.logger.warning(f"Card not found: {current_card_id}")
            return jsonify({"error": "Card not found"}), 404
        
        # Card properties to update
        current_type = card['type']  # Current card type
        current_queue = card['queue']  # Current queue (e.g., new, learning, review)
        current_due = card['due']  # Current due date/time
        current_interval = card['ivl']  # Current interval
        current_factor = card['factor']  # Current ease factor
        current_reps = card['reps']  # Review count
        current_lapses = card['lapses']  # Number of times card was forgotten
        current_left = card['left']  # Learning steps left
        
        # Get collection config for scheduling
        cursor.execute("SELECT conf, crt FROM col LIMIT 1") # <-- Fetch crt as well
        col_data = cursor.fetchone()
        if not col_data:
            app.logger.error("Collection configuration not found")
            return jsonify({"error": "Database error occurred during review update"}), 500
        
        coll_conf = json.loads(col_data['conf'])
        collectionCreationTime = col_data['crt'] # <-- Store crt
        
        # Get deck-specific configuration 
        deck_id = card['did']
        # No need to fetch decks/dconf again if we already have col_data
        # cursor.execute("SELECT decks, dconf FROM col LIMIT 1")
        # col_data_deck = cursor.fetchone() # This is redundant
        # decks_dict = json.loads(col_data_deck['decks'])
        # dconf_dict = json.loads(col_data_deck['dconf'])

        # Fetch decks and dconf from col table (assuming they exist as TEXT columns)
        cursor.execute("SELECT decks, dconf FROM col LIMIT 1")
        deck_config_data = cursor.fetchone()
        if not deck_config_data:
             app.logger.error("Decks or Dconf configuration not found in col table")
             return jsonify({"error": "Database configuration error"}), 500

        decks_dict = json.loads(deck_config_data['decks'])
        dconf_dict = json.loads(deck_config_data['dconf'])
        
        # Get the deck's configuration id
        deck_conf_id = decks_dict[str(deck_id)].get('conf', 1)  # Default to 1 if not found
        deck_conf = dconf_dict[str(deck_conf_id)]
        
        # Get the configuration settings for the current card state
        if current_type == 0:  # 0 = new
            schedule_conf = deck_conf['new']
        elif current_type == 1:  # 1 = learning
            schedule_conf = deck_conf['lapse'] if current_queue == 1 else deck_conf['new']
        elif current_type == 2:  # 2 = review
            schedule_conf = deck_conf['rev']
        elif current_type == 3:  # 3 = relearning
            schedule_conf = deck_conf['lapse']
        else:
            schedule_conf = deck_conf['new']  # Default fallback
        
        # Anki scheduling algorithm simplified - this is a very simplified version!
        new_interval = current_interval
        new_factor = current_factor
        new_due = current_due
        new_queue = current_queue
        new_type = current_type
        new_left = current_left
        
        # Get the current time and calculate day cutoff relative to collection creation
        now = int(time.time())
        # today = now // 86400 # Don't use epoch day
        dayCutoff = (now - collectionCreationTime) // 86400 # <-- Use dayCutoff
        
        # Log this review in the revlog table
        review_id = int(time.time() * 1000)  # Timestamp as ID
        review_log_type = current_type # Default log type
        
        # Calculate new interval based on ease and current state
        if current_queue == 0:  # New card
            if ease == 1:  # Again
                new_queue = 1  # Learning
                new_type = 1  # Learning
                new_left = schedule_conf['delays'][0]  # Reset steps
                new_due = now + (new_left * 60)  # Due in X minutes
            else:  # Hard, Good, Easy
                new_queue = 1  # Learning
                new_type = 1  # Learning
                step_index = 0 if ease == 2 else 1  # 2=Hard -> first step, 3=Good -> second step
                if step_index < len(schedule_conf['delays']):
                    new_left = schedule_conf['delays'][step_index]
                    new_due = now + (new_left * 60)  # Due in X minutes
                else:
                    # Graduate to review
                    new_queue = 2  # Review
                    new_type = 2  # Review
                    new_interval = 1  # 1 day for first review
                    new_due = dayCutoff + new_interval  # <-- Use dayCutoff
                    new_left = 0  # No more steps
        
        elif current_queue == 1:  # Learning/relearning card
            if ease == 1:  # Again
                # Reset to first step
                new_left = schedule_conf['delays'][0]
                new_due = now + (new_left * 60)  # Due in X minutes
            elif ease == 2:  # Hard - stay in same position
                new_due = now + (current_left * 60)  # Due in same X minutes
            else:  # Good or Easy
                if current_left == 0 or ease == 4:  # Last step or marked easy
                    # Graduate to review
                    new_queue = 2  # Review
                    new_type = 2  # Review
                    new_interval = 1  # 1 day for first review
                    new_due = dayCutoff + new_interval  # <-- Use dayCutoff
                    new_left = 0  # No more steps
                else:
                    # Move to next step
                    step_index = 1  # Skip to next step
                    if step_index < len(schedule_conf['delays']):
                        new_left = schedule_conf['delays'][step_index]
                        new_due = now + (new_left * 60)  # Due in X minutes
                    else:
                        # Graduate to review
                        new_queue = 2  # Review
                        new_type = 2  # Review
                        new_interval = 1  # 1 day for first review
                        new_due = dayCutoff + new_interval  # <-- Use dayCutoff
                        new_left = 0  # No more steps
        
        elif current_queue == 2:  # Review card
            if ease == 1:  # Again (fail)
                # Card lapses, move to relearning
                new_queue = 1  # Learning (relearning)
                new_type = 3  # Relearning
                new_lapses = current_lapses + 1
                # Correctly access lapse delays from deck_conf
                lapse_conf = deck_conf.get('lapse', {})
                lapse_delays = lapse_conf.get('delays', [10]) # Default delay if missing
                lapse_mult = lapse_conf.get('mult', 0.0) # Lapse interval multiplier

                if len(lapse_delays) > 0:
                    new_left = lapse_delays[0]
                    new_due = now + (new_left * 60)
                    new_interval = 0 # Interval is 0 during learning/relearning steps
                else:
                    # No relearning steps defined, reschedule based on lapse multiplier
                    new_queue = 2  # Stay in review queue
                    new_type = 2  # Still a review card conceptually
                    new_interval = max(1, int(current_interval * lapse_mult)) # Apply multiplier
                    new_due = dayCutoff + new_interval
                    new_left = 0
                review_log_type = 2 # Type 2 for relearn/lapse
            else:  # Hard, Good, Easy
                # Calculate new interval based on ease button
                # Get review config safely
                rev_conf = deck_conf.get('rev', {})
                hard_factor = rev_conf.get('hardFactor', 1.2)
                easy_bonus = rev_conf.get('ease4', 1.3) # Called ease4 in Anki JSON
                interval_factor = rev_conf.get('ivlFct', 1.0) # General interval factor

                if ease == 2:  # Hard
                    # factor_adjust = 0.8 # This isn't how factor is adjusted
                    interval_adjust = hard_factor
                    factor_change = -150 # Anki-like adjustment
                elif ease == 3:  # Good
                    # factor_adjust = 1.0 # Replaced
                    interval_adjust = interval_factor # Use the general interval factor
                    factor_change = 0 # No change for Good in basic Anki SM2 variant
                else:  # ease == 4, Easy
                    # factor_adjust = 1.3 # Replaced
                    interval_adjust = easy_bonus * interval_factor # Easy bonus applies on top
                    factor_change = 150 # Anki-like adjustment
                
                # Update interval: apply interval factor and specific ease multiplier
                # The calculation is more complex in real Anki, involving fuzz factor etc.
                # Simplified: Interval = Previous Interval * Ease Multiplier * General Interval Factor
                new_interval = max(current_interval + 1, int(current_interval * interval_adjust * interval_factor))
                
                # Update ease factor (min 1300)
                # factor_change = 0 if ease == 2 else 15 if ease == 3 else 30  # Old logic
                new_factor = max(1300, current_factor + factor_change)
                
                # Calculate due date
                new_due = dayCutoff + new_interval # <-- Use dayCutoff
                
                # Keep in review queue
                new_queue = 2
                new_type = 2
                review_log_type = 1 # Type 1 for review success
        
        # Final assignment for lapses (only increases on review lapse)
        final_lapses = current_lapses + (1 if ease == 1 and current_queue == 2 else 0)

        # Update the card
        cursor.execute("""
            UPDATE cards 
            SET type=?, queue=?, due=?, ivl=?, factor=?, reps=?, lapses=?, left=?, mod=?
            WHERE id=?
        """, (
            new_type, new_queue, new_due, new_interval, new_factor,
            current_reps + 1, final_lapses, # Use final_lapses
            new_left, now, current_card_id
        ))
        
        # Log this review
        cursor.execute("""
            INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id, current_card_id, -1, ease, new_interval, current_interval,
            new_factor, time_taken, review_log_type # <-- Use calculated review_log_type
        ))
        
        # Update collection modification time
        cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
        
        # Commit the changes
        conn.commit()
        
        # Clear the current card from the session
        session.pop('currentCardId', None)
        session.pop('currentNoteId', None)
        
        return jsonify({"message": "Answer processed successfully"}), 200
    
    except sqlite3.Error as e:
        app.logger.exception(f"Database error during review update: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": "Database error occurred during review update"}), 500
    except Exception as e:
        app.logger.exception(f"Error processing review: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": f"Error processing review: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

# --- APKG Export Logic ---
@app.route('/export', methods=['GET'])
@login_required
def export_deck():
    user_id = session['user_id']
    username = session.get('username', 'user') # Get username for filename
    user_db_path = get_user_db_path(user_id)

    if not os.path.exists(user_db_path):
        return jsonify({"error": "User database not found."}), 404

    temp_dir = None
    apkg_path = None
    try:
        # Create a temporary directory for staging the APKG contents
        temp_dir = tempfile.mkdtemp()
        app.logger.info(f"Created temporary directory for export: {temp_dir}") # Use logger

        # 1. Copy the user's database to the temp dir as collection.anki2
        anki2_path = os.path.join(temp_dir, 'collection.anki2')
        shutil.copy2(user_db_path, anki2_path) # copy2 preserves metadata
        app.logger.info(f"Copied user DB to {anki2_path}") # Use logger

        # 2. Create the media file (required by Anki, even if empty)
        media_path = os.path.join(temp_dir, 'media')
        with open(media_path, 'w') as f:
            json.dump({}, f) # Empty JSON object for no media
        app.logger.info(f"Created empty media file at {media_path}") # Use logger

        # 3. Create the APKG zip file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        apkg_filename = f"{username}_export_{timestamp}.apkg"
        apkg_path = os.path.join(EXPORT_DIR, apkg_filename)

        # Ensure export directory exists
        if not os.path.exists(EXPORT_DIR):
            os.makedirs(EXPORT_DIR)
            app.logger.info(f"Created export directory: {EXPORT_DIR}")

        with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(anki2_path, arcname='collection.anki2')
            zf.write(media_path, arcname='media')
        app.logger.info(f"Created APKG file at {apkg_path}") # Use logger

        # 4. Send the file to the user
        return send_file(
            apkg_path,
            as_attachment=True,
            download_name=apkg_filename,
            mimetype='application/zip' # Standard mimetype for zip/apkg
        )

    except Exception as e:
        app.logger.exception(f"Error during APKG export for user {user_id}: {e}") # Use logger.exception
        # Clean up temporary directory if it exists, even on error
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                app.logger.info(f"Cleaned up temporary directory: {temp_dir}") # Use logger
            except Exception as cleanup_err:
                app.logger.error(f"Error cleaning up temp directory {temp_dir}: {cleanup_err}") # Use logger
        # Clean up partial apkg file if it exists
        if apkg_path and os.path.exists(apkg_path):
             try:
                 os.remove(apkg_path)
                 app.logger.info(f"Cleaned up partial APKG file: {apkg_path}") # Use logger
             except Exception as cleanup_err:
                 app.logger.error(f"Error cleaning up APKG file {apkg_path}: {cleanup_err}") # Use logger

        return jsonify({"error": "Failed to generate export file."}), 500
    finally:
        # Clean up the temporary directory after sending or on error (if not already done)
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                app.logger.info(f"Cleaned up temporary directory after request: {temp_dir}") # Use logger
            except Exception as cleanup_err:
                app.logger.error(f"Error cleaning up temp directory {temp_dir} in finally block: {cleanup_err}") # Use logger
        # Clean up the created APKG file from the server *after* sending is complete
        # Note: Flask's send_file typically handles this if using TemporaryFile,
        # but since we save it first, we clean it up manually. Be careful with background tasks.
        # For simplicity here, we assume sync processing and clean up immediately.
        # In a production scenario, might need a background job for cleanup.
        if apkg_path and os.path.exists(apkg_path):
             try:
                 # This might be too soon if send_file is async in some setups,
                 # but usually okay for standard Flask development server.
                 # Consider adding a small delay or using Flask's after_request handler.
                 # time.sleep(1) # Small delay as a simple precaution
                 os.remove(apkg_path)
                 app.logger.info(f"Cleaned up APKG file after request: {apkg_path}") # Use logger
             except Exception as cleanup_err:
                 app.logger.error(f"Error cleaning up APKG file {apkg_path} in finally block: {cleanup_err}") # Use logger

# --- Add Card Logic ---
@app.route('/add_card', methods=['POST'])
@login_required
def add_new_card():
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)

    data = request.get_json()
    front = data.get('front')
    back = data.get('back')

    if not front or not back:
        return jsonify({"error": "Front and back content cannot be empty"}), 400

    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get current model ID and current deck ID
        cursor.execute("SELECT models, conf FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['models'] or not col_data['conf']:
            return jsonify({"error": "Collection configuration not found or invalid"}), 500

        models = json.loads(col_data['models'])
        conf_dict = json.loads(col_data['conf'])
        model_id = next(iter(models), None)
        current_deck_id = conf_dict.get('curDeck', 1) # Get current deck ID

        if not model_id:
             return jsonify({"error": "Default note model not found in collection"}), 500

        # deck_id = 1 # No longer assume deck 1

        # --- Generate New Note/Card Data --- #
        current_time_sec = int(time.time())
        current_time_ms = int(current_time_sec * 1000)
        note_id = current_time_ms # Use timestamp for unique Note ID
        card_id = note_id + 1 # Simple unique Card ID
        guid = str(uuid.uuid4())[:10] # Unique ID for sync
        fields = f"{front}\x1f{back}" # Fields separated by 0x1f
        checksum = sha1_checksum(front) # Checksum of the first field
        usn = -1 # Update Sequence Number (-1 indicates local change)

        # --- Insert Note --- #
        cursor.execute("""
            INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id, guid, model_id, current_time_sec, usn, "",
            fields, front, int(checksum, 16) & 0xFFFFFFFF, 0, ""
        ))
        app.logger.info(f"Inserted note {note_id} for user {user_id}") # Use logger

        # --- Insert Card (assign to current_deck_id) --- #
        cursor.execute("""
            INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_id, note_id, current_deck_id, 0, # <<< Use current_deck_id for did
            current_time_sec, usn,
            0, 0, note_id, # type, queue, due
            0, 2500, 0, 0, 0, 0, 0, 0, "" # ivl, factor, reps, lapses, left, odue, odid, flags, data
        ))
        app.logger.info(f"Inserted card {card_id} into deck {current_deck_id} for note {note_id}, user {user_id}") # Use logger

        # --- Update Collection Mod Time --- #
        cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
        conn.commit()

        return jsonify({"message": "Card added successfully", "note_id": note_id, "card_id": card_id}), 201

    except sqlite3.Error as e:
        app.logger.error(f"Database error adding card for user {user_id}: {e}") # Use logger
        if conn: conn.rollback()
        return jsonify({"error": "Database error occurred while adding card"}), 500
    except Exception as e:
        app.logger.exception(f"Error adding card for user {user_id}: {e}") # Use logger.exception
        if conn: conn.rollback()
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if conn:
            conn.close()

# --- Deck Management API ---

@app.route('/decks', methods=['GET'])
@login_required
def get_decks():
    """Fetches the list of decks for the current user."""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['decks']:
            return jsonify({"error": "Collection data not found or invalid"}), 500

        decks_dict = json.loads(col_data['decks'])
        # Convert dictionary to list of objects expected by frontend
        decks_list = [{"id": k, "name": v["name"]} for k, v in decks_dict.items()]
        # Sort by name for consistency
        decks_list.sort(key=lambda x: x["name"])

        return jsonify(decks_list), 200

    except Exception as e:
        app.logger.exception(f"Error fetching decks for user {user_id}: {e}") # Use logger.exception
        return jsonify({"error": "Failed to fetch decks"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/decks', methods=['POST'])
@login_required
def create_deck():
    """Creates a new deck for the current user."""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)

    data = request.get_json()
    deck_name = data.get('name')
    if not deck_name or not deck_name.strip():
        return jsonify({"error": "Deck name cannot be empty"}), 400
    deck_name = deck_name.strip()

    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch current decks and dconf
        cursor.execute("SELECT decks, dconf FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data:
            return jsonify({"error": "Collection data not found"}), 500

        decks_dict = json.loads(col_data['decks'])
        dconf_dict = json.loads(col_data['dconf'])

        # Generate new deck ID (using epoch ms)
        new_deck_id = str(int(time.time() * 1000))

        # Check for duplicate name (case-insensitive)
        if any(d['name'].lower() == deck_name.lower() for d in decks_dict.values()):
            return jsonify({"error": "A deck with this name already exists"}), 409

        # Create new deck entry - using dconf ID '1' for simplicity for now
        new_deck = {
            "id": new_deck_id,
            "name": deck_name,
            "mod": int(time.time()),
            "usn": -1,
            "lrnToday": [0, 0], "revToday": [0, 0], "newToday": [0, 0],
            "timeToday": [0, 0], "conf": 1, # Use default dconf '1'
            "desc": "", "dyn": 0, "collapsed": False,
            "extendNew": 10, "extendRev": 50
        }
        decks_dict[new_deck_id] = new_deck

        # Update col table
        current_mod_time = int(time.time() * 1000)
        cursor.execute("UPDATE col SET decks = ?, mod = ?",
                       (json.dumps(decks_dict), current_mod_time))
        conn.commit()

        app.logger.info(f"Created new deck '{deck_name}' (ID: {new_deck_id}) for user {user_id}") # Use logger
        return jsonify({"id": new_deck_id, "name": deck_name}), 201

    except Exception as e:
        app.logger.exception(f"Error creating deck for user {user_id}: {e}") # Use logger.exception
        if conn: conn.rollback()
        return jsonify({"error": "Failed to create deck"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/decks/current', methods=['PUT'])
@login_required
def set_current_deck():
    """Sets the current deck for the user."""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)

    data = request.get_json()
    deck_id = data.get('deckId') # Expecting deckId parameter in camelCase
    if deck_id is None:
        return jsonify({"error": "Missing deckId"}), 400

    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Fetch current config and decks to validate deck_id
        cursor.execute("SELECT conf, decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data:
            return jsonify({"error": "Collection data not found"}), 500

        conf_dict = json.loads(col_data['conf'])
        decks_dict = json.loads(col_data['decks'])

        # Validate deck ID exists
        if str(deck_id) not in decks_dict:
            return jsonify({"error": "Invalid deck ID"}), 404

        # Update current deck ID in conf
        conf_dict['curDeck'] = int(deck_id) # Store as integer

        # Update col table
        current_mod_time = int(time.time() * 1000)
        cursor.execute("UPDATE col SET conf = ?, mod = ?",
                       (json.dumps(conf_dict), current_mod_time))
        conn.commit()

        app.logger.info(f"Set current deck to {deck_id} for user {user_id}") # Use logger
        return jsonify({"message": "Current deck updated successfully"}), 200

    except Exception as e:
        app.logger.exception(f"Error setting current deck for user {user_id}: {e}") # Use logger.exception
        if conn: conn.rollback()
        return jsonify({"error": "Failed to set current deck"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/decks/<int:deckId>/stats', methods=['GET'])
@login_required
def get_deck_stats(deckId):
    """Calculates and returns CURRENT card status counts for a specific deck."""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    # Timeframe parameter is ignored
    # timeframe = request.args.get('timeframe', 'today') 

    # Remove timestamp calculation
    # start_timestamp_ms = ... 

    app.logger.debug(f"Deck stats requested for deck: {deckId}") # Simplified log

    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Verify deck exists (as before)
        cursor.execute("SELECT decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['decks']:
             return jsonify({"error": "Collection data not found."}), 500
        decks_dict = json.loads(col_data['decks'])
        if str(deckId) not in decks_dict:
             return jsonify({"error": "Deck not found or access denied."}), 404

        # Query cards for the specific deck - id no longer needed for filtering New
        cursor.execute("SELECT queue, ivl FROM cards WHERE did = ?", (deckId,))
        cards = cursor.fetchall()

        counts = {
            "New": 0, "Learning": 0, "Relearning": 0,
            "Young": 0, "Mature": 0, "Suspended": 0, "Buried": 0
        }
        total_cards = 0

        for card in cards:
            total_cards += 1
            queue = card['queue']
            ivl = card['ivl']
            # card_creation_ms = card['id'] # No longer needed

            if queue == 0:
                counts["New"] += 1 # Count ALL new cards
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

        response_data = {
            "counts": counts,
            "total": total_cards # Total is now sum of counts
            # "timeframe": "current" # Indicate it's current state
        }

        return jsonify(response_data), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error fetching stats for deck {deckId}, user {user_id}: {e}")
        return jsonify({"error": "Database error occurred while fetching statistics."}), 500
    except Exception as e:
        app.logger.exception(f"Error fetching stats for deck {deckId}, user {user_id}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/cards/<cardId>', methods=['GET'])
@login_required
def get_card(cardId):
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    # Check if user's database exists
    if not os.path.exists(db_path):
        app.logger.error(f"Database not found for user {user_id}")
        return jsonify({"error": "User database not found"}), 404
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to get the card details
        cursor.execute("""
            SELECT n.flds, c.id
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.id = ?
        """, (cardId,))
        
        result = cursor.fetchone()
        if not result:
            app.logger.warning(f"Card {cardId} not found")
            return jsonify({"error": "Card not found"}), 404
        
        # Parse fields from the note
        fields = result[0].split('\x1f')  # Anki separator for fields
        if len(fields) < 2:
            app.logger.error(f"Card {cardId} has invalid field format")
            return jsonify({"error": "Invalid card format"}), 500
        
        # Return the card details using camelCase
        return jsonify({
            "cardId": result[1],
            "front": fields[0],
            "back": fields[1]
        })
        
    except Exception as e:
        app.logger.exception(f"Error fetching card {cardId}: {str(e)}")
        return jsonify({"error": f"Error fetching card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/cards/<cardId>', methods=['PUT'])
@login_required
def update_card(cardId):
    # Get request data
    data = request.json
    if not data or 'front' not in data or 'back' not in data:
        app.logger.warning("Invalid request data for card update")
        return jsonify({"error": "Front and back fields are required"}), 400
    
    front = data['front'].strip()
    back = data['back'].strip()
    
    if not front or not back:
        app.logger.warning("Empty front or back field")
        return jsonify({"error": "Front and back fields cannot be empty"}), 400
    
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the note ID for this card
        cursor.execute("SELECT nid FROM cards WHERE id = ?", (cardId,))
        result = cursor.fetchone()
        
        if not result:
            app.logger.warning(f"Card {cardId} not found")
            return jsonify({"error": "Card not found"}), 404
        
        note_id = result[0]
        
        # Update the note's fields
        # First, get the current fields to maintain any additional fields beyond front/back
        cursor.execute("SELECT flds FROM notes WHERE id = ?", (note_id,))
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
            
            # Begin transaction
            conn.execute("BEGIN")
            
            # Update the note
            current_time = int(time.time())
            cursor.execute("""
                UPDATE notes 
                SET flds = ?, sfld = ?, csum = ?, mod = ? 
                WHERE id = ?
            """, (new_fields, field_list[0], checksum, current_time, note_id))
            
            # Update card modification time
            cursor.execute("UPDATE cards SET mod = ? WHERE id = ?", (current_time, cardId))
            
            # Update collection modification time
            cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
            
            # Commit the transaction
            conn.commit()
            
            app.logger.info(f"Successfully updated card {cardId}")
            return jsonify({"success": True, "message": "Card updated successfully"})
        else:
            app.logger.error(f"Card {cardId} has invalid field structure")
            return jsonify({"error": "Card has invalid field structure"}), 500
            
    except Exception as e:
        app.logger.exception(f"Error updating card {cardId}: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": f"Error updating card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/cards/<cardId>', methods=['DELETE'])
@login_required
def delete_card(cardId):
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    # Check if user's database exists
    if not os.path.exists(db_path):
        app.logger.error(f"Database not found for user {user_id}")
        return jsonify({"error": "User database not found"}), 404
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, get the note ID for this card
        cursor.execute("SELECT nid FROM cards WHERE id = ?", (cardId,))
        result = cursor.fetchone()
        
        if not result:
            app.logger.warning(f"Card {cardId} not found")
            return jsonify({"error": "Card not found"}), 404
        
        note_id = result[0]
        
        # Begin transaction
        conn.execute("BEGIN")
        
        # Delete the card
        cursor.execute("DELETE FROM cards WHERE id = ?", (cardId,))
        
        # Check if there are any other cards associated with this note
        cursor.execute("SELECT COUNT(*) FROM cards WHERE nid = ?", (note_id,))
        other_cards_count = cursor.fetchone()[0]
        
        # If no other cards use this note, delete the note too
        if other_cards_count == 0:
            cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        
        # Update collection modification time
        cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
        
        # Commit the transaction
        conn.commit()
        
        app.logger.info(f"Successfully deleted card {cardId}")
        return jsonify({"success": True, "message": "Card deleted successfully"})
        
    except Exception as e:
        app.logger.exception(f"Error deleting card {cardId}: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": f"Error deleting card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/decks/<int:deckId>', methods=['DELETE'])
@login_required
def delete_deck(deckId):
    """Delete a specific deck and all its cards"""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    
    # Check if user DB exists
    if not os.path.exists(user_db_path):
        app.logger.error(f"User database not found for user {user_id}")
        return jsonify({"error": "User database not found"}), 500
    
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First check if the deck exists in the col table's decks JSON
        cursor.execute("SELECT decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        
        if not col_data or not col_data['decks']:
            conn.close()
            app.logger.warning(f"Collection data not found or invalid")
            return jsonify({"error": "Collection data not found"}), 500
            
        decks_dict = json.loads(col_data['decks'])
        deck_id_str = str(deckId)
        
        if deck_id_str not in decks_dict:
            conn.close()
            app.logger.warning(f"Attempt to delete non-existent deck {deckId}")
            return jsonify({"error": "Deck not found"}), 404
        
        deck_name = decks_dict[deck_id_str]['name']
        app.logger.info(f"Deleting deck '{deck_name}' (ID: {deckId}) for user {user_id}")
        
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Count cards in the deck
        cursor.execute("SELECT COUNT(*) FROM cards WHERE did = ?", (deckId,))
        card_count = cursor.fetchone()[0]
        
        # Get the IDs of notes associated with this deck's cards
        cursor.execute("SELECT DISTINCT nid FROM cards WHERE did = ?", (deckId,))
        note_ids = [row[0] for row in cursor.fetchall()]
        
        # Delete cards in this deck
        cursor.execute("DELETE FROM cards WHERE did = ?", (deckId,))
        app.logger.debug(f"Deleted {card_count} cards from deck {deckId}")
        
        # For each note, check if it has any remaining cards
        # If not, delete the note
        for note_id in note_ids:
            cursor.execute("SELECT COUNT(*) FROM cards WHERE nid = ?", (note_id,))
            remaining_cards = cursor.fetchone()[0]
            if remaining_cards == 0:
                cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                app.logger.debug(f"Deleted orphaned note {note_id}")
        
        # Remove the deck from the decks JSON
        del decks_dict[deck_id_str]
        
        # Update the col table with the modified decks JSON
        current_time_ms = int(time.time() * 1000)
        cursor.execute("UPDATE col SET decks = ?, mod = ?", 
                     (json.dumps(decks_dict), current_time_ms))
        
        # Commit the transaction
        conn.commit()
        
        app.logger.info(f"Successfully deleted deck '{deck_name}' with {card_count} cards")
        return jsonify({
            "message": f"Deck '{deck_name}' and {card_count} cards deleted successfully"
        }), 200
        
    except sqlite3.Error as e:
        app.logger.exception(f"Database error deleting deck {deckId}: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"error": "Failed to delete deck due to database error"}), 500
    except Exception as e:
        app.logger.exception(f"Error deleting deck {deckId}: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"error": "Failed to delete deck"}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/decks/<int:deckId>/rename', methods=['PUT'])
@login_required
def rename_deck(deckId):
    """Rename a specific deck"""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    
    # Get new deck name from request
    data = request.get_json()
    if not data or 'name' not in data or not data['name'].strip():
        app.logger.warning("Missing or empty deck name in rename request")
        return jsonify({"error": "New deck name cannot be empty"}), 400
    
    new_deck_name = data['name'].strip()
    
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First get the decks from the col table
        cursor.execute("SELECT decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        
        if not col_data or not col_data['decks']:
            app.logger.warning("Collection data not found or invalid")
            return jsonify({"error": "Collection data not found"}), 500
            
        decks_dict = json.loads(col_data['decks'])
        deck_id_str = str(deckId)
        
        # Check if the deck exists
        if deck_id_str not in decks_dict:
            app.logger.warning(f"Attempt to rename non-existent deck {deckId}")
            return jsonify({"error": "Deck not found"}), 404
        
        old_deck_name = decks_dict[deck_id_str]['name']
        
        # Check if another deck with the same name already exists
        # Case insensitive comparison
        for did, deck in decks_dict.items():
            if did != deck_id_str and deck['name'].lower() == new_deck_name.lower():
                app.logger.warning(f"Attempt to rename deck to existing name: {new_deck_name}")
                return jsonify({"error": "A deck with this name already exists"}), 409
        
        # Update the deck name
        decks_dict[deck_id_str]['name'] = new_deck_name
        decks_dict[deck_id_str]['mod'] = int(time.time())  # Update modification time
        
        # Update the collection
        current_time_ms = int(time.time() * 1000)
        cursor.execute("UPDATE col SET decks = ?, mod = ?", 
                      (json.dumps(decks_dict), current_time_ms))
        conn.commit()
        
        app.logger.info(f"Renamed deck from '{old_deck_name}' to '{new_deck_name}'")
        return jsonify({
            "message": f"Deck renamed from '{old_deck_name}' to '{new_deck_name}' successfully",
            "id": deckId,
            "name": new_deck_name
        }), 200
        
    except sqlite3.Error as e:
        app.logger.exception(f"Database error renaming deck {deckId}: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"error": "Failed to rename deck due to database error"}), 500
    except Exception as e:
        app.logger.exception(f"Error renaming deck {deckId}: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
        return jsonify({"error": "Failed to rename deck"}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.route('/decks/<deckId>/cards', methods=['GET'])
@login_required
def get_deck_cards(deckId):
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    # Check if user's database exists
    if not os.path.exists(db_path):
        app.logger.error(f"Database not found for user {user_id}")
        return jsonify({"error": "User database not found"}), 404
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    perPage = request.args.get('perPage', 10, type=int)
    
    # Calculate offset for pagination
    offset = (page - 1) * perPage
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First, check if the deck exists by querying the col table's decks JSON field
        cursor.execute("SELECT decks FROM col LIMIT 1")
        col_data = cursor.fetchone()
        if not col_data or not col_data['decks']:
            app.logger.warning("Collection data not found or invalid")
            return jsonify({"error": "Collection data not found"}), 500
            
        decks_dict = json.loads(col_data['decks'])
        if str(deckId) not in decks_dict:
            app.logger.warning(f"Deck {deckId} not found")
            return jsonify({"error": "Deck not found"}), 404
            
        deck_name = decks_dict[str(deckId)]['name']
        
        # Get total number of cards in the deck
        cursor.execute("""
            SELECT COUNT(*) 
            FROM cards c
            WHERE c.did = ?
        """, (deckId,))
        total_cards = cursor.fetchone()[0]
        
        # Query to get cards for the deck with pagination
        cursor.execute("""
            SELECT c.id, n.id AS note_id, n.flds, c.mod
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.did = ?
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
        """, (deckId, perPage, offset))
        
        cards_data = []
        for row in cursor.fetchall():
            card_id, note_id, fields, mod_time = row
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
        
        # Return the cards with pagination metadata using camelCase
        return jsonify({
            "deckId": deckId,
            "deckName": deck_name,
            "cards": cards_data,
            "pagination": {
                "total": total_cards,
                "page": page,
                "perPage": perPage,
                "totalPages": (total_cards + perPage - 1) // perPage
            }
        })
        
    except Exception as e:
        app.logger.exception(f"Error fetching cards for deck {deckId}: {str(e)}")
        return jsonify({"error": f"Error fetching cards: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

# --- Server Start ---
if __name__ == '__main__':
    # Initialize databases if they don't exist
    # TODO: Call database initialization functions here
    init_admin_db() # Initialize the admin database
    app.logger.info(f"Starting server on port {PORT}...") # Use logger
    app.run(host='0.0.0.0', port=PORT, debug=True) # debug=True for development 
