from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
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

# Get the directory where app.py resides
basedir = os.path.abspath(os.path.dirname(__file__))
# print(f"Base directory detected: {basedir}") # Replaced by logger

# --- Configuration ---
PORT = 8000
ADMIN_DB_PATH = os.path.join(basedir, 'admin.db') # Path relative to app.py
FLASHCARD_DB_PATH = 'flashcards.db' # We will create user-specific DBs later, this is a placeholder
SECRET_KEY = os.urandom(24) # For session management
EXPORT_DIR = os.path.join(basedir, 'exports') # Path relative to app.py

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app, supports_credentials=True) # Allow cross-origin requests, necessary for React dev server

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
    data = request.get_json()
    username = data.get('username')
    name = data.get('name')
    password = data.get('password')

    if not all([username, name, password]):
        return jsonify({"error": "Missing required fields"}), 400

    # Validate input lengths
    if not (len(username) <= 10 and username):
        return jsonify({"error": "Username must be between 1 and 10 characters"}), 400
    if not (len(name) <= 40 and name):
        return jsonify({"error": "Name must be between 1 and 40 characters"}), 400
    if not (10 <= len(password) <= 20):
        return jsonify({"error": "Password must be between 10 and 20 characters"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    admin_conn = None
    try:
        admin_conn = sqlite3.connect(ADMIN_DB_PATH)
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute("INSERT INTO users (username, name, password_hash) VALUES (?, ?, ?)",
                       (username, name, hashed_password.decode('utf-8')))
        admin_conn.commit()
        user_id = admin_cursor.lastrowid # Get the newly inserted user ID
        app.logger.info(f"User '{username}' registered successfully with ID: {user_id}") # Use logger

        # --- Create User-Specific Anki DB --- ##
        user_db_path = get_user_db_path(user_id)
        try:
            init_anki_db(user_db_path, name)
            # --- Add Initial Flashcards --- ##
            temp_model_id = "1700000000001"
            add_initial_flashcards(user_db_path, temp_model_id)
            app.logger.info(f"Added initial flashcards for user {user_id}") # Use logger
        except Exception as db_err:
            app.logger.error(f"Failed to initialize Anki DB or add initial cards for user {user_id}: {db_err}") # Use logger
            return jsonify({"error": "Server error during user setup after registration."}), 500
        # --- ---

        return jsonify({"message": "User registered successfully", "user_id": user_id}), 201

    except sqlite3.IntegrityError: # Handles UNIQUE constraint violation for username
        return jsonify({"error": "Username already exists"}), 409
    except Exception as e:
        app.logger.error(f"Error during registration: {e}") # Use logger
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if admin_conn:
            admin_conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = None
    try:
        conn = sqlite3.connect(ADMIN_DB_PATH)
        conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name, password_hash FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Password matches, create session
            session['user_id'] = user['user_id']
            session['username'] = username
            session['name'] = user['name']
            app.logger.info(f"User '{username}' logged in successfully.") # Use logger
            return jsonify({
                "message": "Login successful",
                "user": {"user_id": user['user_id'], "username": username, "name": user['name']}
            }), 200
        else:
            # Invalid credentials
            return jsonify({"error": "Invalid username or password"}), 401

    except Exception as e:
        app.logger.error(f"Error during login: {e}") # Use logger
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/logout', methods=['POST'])
def logout():
    # Clear the user session
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('name', None)
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

# --- User Session Check ---
# Decorator to protect routes that require login
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required"}), 401
        # You could add further checks here, e.g., verify user_id against admin db
        return f(*args, **kwargs)
    return decorated_function

# --- Flashcard Review Logic ---

# TODO: Implement SM-2 algorithm logic here

@app.route('/review', methods=['GET'])
@login_required
def get_next_card():
    app.logger.debug(">>> Entering /review endpoint") # Use logger (DEBUG)
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    conn = None

    if not os.path.exists(user_db_path):
        return jsonify({"error": "User database not found. Please re-register or contact support."}), 404

    try:
        app.logger.debug("--> Attempting to connect to DB...") # Use logger (DEBUG)
        conn = sqlite3.connect(user_db_path)
        app.logger.debug("--> DB Connection successful.") # Use logger (DEBUG)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        app.logger.debug("--> Cursor created.") # Use logger (DEBUG)

        app.logger.debug("--> Executing query for conf, crt...") # Use logger (DEBUG)
        cursor.execute("SELECT conf, crt FROM col LIMIT 1")
        app.logger.debug("--> Query for conf, crt executed.") # Use logger (DEBUG)
        col_data = cursor.fetchone()
        app.logger.debug(f"--> Fetched col_data: {col_data}") # Use logger (DEBUG)

        conf_value = None
        crt_value = None

        if col_data:
            try:
                conf_value = col_data['conf']
                app.logger.debug(f"--> Checking conf: Value exists") # Simplified log
            except Exception as e:
                app.logger.error(f"Accessing col_data['conf']: {e}") # Use logger
            try:
                crt_value = col_data['crt']
                app.logger.debug(f"--> Checking crt: Value exists") # Simplified log
            except Exception as e:
                app.logger.error(f"Accessing col_data['crt']: {e}") # Use logger
        else:
            app.logger.error("col_data is None") # Use logger

        if not col_data or conf_value is None or crt_value is None:
             app.logger.error("Condition failed (col_data is None, or conf_value is None, or crt_value is None)") # Use logger
             return jsonify({"error": "Collection configuration or creation time could not be read"}), 500
        
        app.logger.debug("--> Parsing conf JSON...") # Use logger (DEBUG)
        conf_dict = json.loads(conf_value) 
        app.logger.debug("--> Parsed conf JSON.") # Use logger (DEBUG)
        crt_time_sec = crt_value 
        current_deck_id = conf_dict.get('curDeck', 1)
        app.logger.debug(f"--> Current Deck ID: {current_deck_id}, Crt Time: {crt_time_sec}") # Use logger (DEBUG)

        current_time_sec = int(time.time())
        days_passed = (current_time_sec - crt_time_sec) // 86400
        app.logger.debug(f"--> Calculated days_passed: {days_passed}") # Use logger (DEBUG)

        app.logger.debug("--> Executing query for next card...") # Use logger (DEBUG)
        cursor.execute(f"""
            SELECT c.id as card_id, c.nid, c.due, c.queue, n.flds
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.queue >= 0 AND c.did = ?
            ORDER BY CASE c.queue WHEN 0 THEN 0 WHEN 1 THEN 1 WHEN 3 THEN 1 WHEN 2 THEN 2 ELSE 3 END, c.due ASC
            LIMIT 1
        """, (current_deck_id,))
        app.logger.debug("--> Query for next card executed.") # Use logger (DEBUG)
        card_to_review = cursor.fetchone()
        app.logger.debug(f"--> Fetched card_to_review: {card_to_review}") # Use logger (DEBUG)

        if card_to_review:
            queue = card_to_review['queue']
            due = card_to_review['due']

            is_due = False
            if queue == 0:
                is_due = True
            elif queue == 1 or queue == 3:
                if due <= current_time_sec:
                    is_due = True
            elif queue == 2:
                 if due <= days_passed:
                     is_due = True

            if is_due:
                fields = card_to_review['flds'].split('\x1f')
                front = fields[0]
                back = fields[1]
                session['current_card_id'] = card_to_review['card_id']
                session['current_note_id'] = card_to_review['nid']
                app.logger.info(f"Presenting card ID {card_to_review['card_id']} for user {user_id}") # INFO level might be better
                return jsonify({
                    "card_id": card_to_review['card_id'],
                    "front": front,
                    "back": back,
                    "queue": queue
                }), 200
            else:
                session.pop('current_card_id', None)
                session.pop('current_note_id', None)
                app.logger.debug(f"Card {card_to_review['card_id']} selected but not due yet") # Use logger (DEBUG)
                return jsonify({"message": f"No cards due for deck {current_deck_id} right now."}), 200
        else:
            session.pop('current_card_id', None)
            session.pop('current_note_id', None)
            app.logger.info(f"No cards available for review in deck {current_deck_id} for user {user_id}.") # INFO level
            return jsonify({"message": f"No cards available for review in deck {current_deck_id}."}), 200

    except sqlite3.Error as db_err:
        app.logger.error(f"Database error fetching review card: {db_err}") # Use logger
        return jsonify({"error": f"Database error occurred: {db_err}"}), 500
    except Exception as e:
        app.logger.exception(f"UNEXPECTED Error fetching review card for user {user_id}: {e}") 
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        app.logger.debug("--> Entering finally block for /review") # Use logger (DEBUG)
        if conn:
            app.logger.debug("--> Closing DB connection.") # Use logger (DEBUG)
            conn.close()
        else:
            app.logger.debug("--> No DB connection to close.") # Use logger (DEBUG)

@app.route('/answer', methods=['POST'])
@login_required
def answer_card():
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)

    # --- Get data from request and session ---
    data = request.get_json()
    ease = data.get('ease') # Expected: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy)
    time_taken_ms = data.get('time_taken', 10000) # Default 10 seconds if not provided

    card_id = session.get('current_card_id')
    note_id = session.get('current_note_id')
    # fields = session.get('current_card_flds') # REMOVE: Fields are no longer stored in session

    # Adjust the check to remove dependency on fields
    if not card_id or not note_id or ease is None:
        return jsonify({"error": "Missing card information in session or invalid request (no card_id/note_id/ease)"}), 400

    if ease not in [1, 2, 3, 4]:
        return jsonify({"error": "Invalid ease rating (must be 1, 2, 3, or 4)"}), 400

    conn = None
    try:
        conn = sqlite3.connect(user_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Fetch current card state --- #
        cursor.execute("SELECT queue, type, ivl, factor, reps, lapses, left, due FROM cards WHERE id = ?", (card_id,))
        card = cursor.fetchone()
        if not card:
            return jsonify({"error": "Card not found"}), 404

        # --- Fetch collection creation time for day calculations --- #
        cursor.execute("SELECT crt FROM col LIMIT 1")
        col = cursor.fetchone()
        if not col:
             return jsonify({"error": "Collection data not found"}), 500
        crt_time_sec = col['crt']

        # --- Get current time values --- #
        current_time_sec = int(time.time())
        current_time_ms = int(current_time_sec * 1000)
        days_passed = (current_time_sec - crt_time_sec) // 86400

        # --- Store old values for revlog --- #
        last_ivl = card['ivl']
        revlog_type = card['type'] # Type of review (0=lrn, 1=rev, 2=relrn)

        # --- Initialize new card state variables --- #
        new_queue = card['queue']
        new_type = card['type']
        new_ivl = card['ivl']
        new_factor = card['factor']
        new_reps = card['reps']
        new_lapses = card['lapses']
        new_left = card['left']
        new_due = card['due']

        # --- Simplified Anki/SM-2 Scheduling Logic --- #

        # Default learning steps (seconds) and graduation intervals (days)
        # These would ideally come from deck config (dconf)
        learning_steps_sec = [60, 600] # 1 min, 10 min
        graduating_interval_good_days = 1
        graduating_interval_easy_days = 4
        relearning_steps_sec = [600] # 10 min after lapse
        easy_bonus = 1.3 # Multiplier for easy rating on review cards
        min_factor = 1300 # Minimum ease factor

        if card['queue'] == 0: # NEW Card
            new_reps = 1
            if ease == 1: # Again
                new_queue = 1 # Learning queue
                new_type = 1
                new_left = len(learning_steps_sec) # Start learning steps
                new_due = current_time_sec + learning_steps_sec[0]
                new_ivl = 0 # Interval not used directly in learning steps
                new_lapses = 0
            else: # Hard, Good, Easy -> Graduate immediately (simplified)
                new_queue = 2 # Review queue
                new_type = 2
                new_left = 0
                new_lapses = 0
                new_factor = 2500 # Initial factor
                if ease == 2: # Hard -> treat like Good for first graduation
                    new_ivl = graduating_interval_good_days
                elif ease == 3: # Good
                    new_ivl = graduating_interval_good_days
                else: # Easy
                    new_ivl = graduating_interval_easy_days
                new_due = days_passed + new_ivl # Due in days

        elif card['queue'] == 1 or card['queue'] == 3: # LEARNING or RELEARNING Card
            step_count = len(learning_steps_sec) if card['type'] == 1 else len(relearning_steps_sec)

            if ease == 1: # Again
                new_left = step_count # Reset steps
                delay = learning_steps_sec[0] if card['type'] == 1 else relearning_steps_sec[0]
                new_due = current_time_sec + delay
                new_ivl = 0
                if card['type'] == 2 or card['type'] == 3: # If it was review/relearning before this step
                     new_lapses = card['lapses'] + 1 # Increment lapses only if it already lapsed
                     new_factor = max(min_factor, card['factor'] - 200)
                new_type = 1 # Ensure it's marked as learning
            elif ease == 3: # Good
                # Calculate how many steps are completed based on 'left'
                # Anki's 'left' format is complex (e.g., 1001 means 1 step left, delay 1m)
                # Simplification: treat 'left' as number of steps remaining.
                current_step_index = step_count - card['left']
                if current_step_index + 1 < step_count: # More steps remaining
                    new_left = card['left'] - 1
                    delay = learning_steps_sec[current_step_index + 1] if card['type'] == 1 else relearning_steps_sec[current_step_index + 1]
                    new_due = current_time_sec + delay
                    new_ivl = 0
                    new_type = card['type'] # Keep type (1 or 3)
                else: # Last step completed, graduate!
                    new_queue = 2 # Review queue
                    new_type = 2
                    new_left = 0
                    new_reps = card['reps'] + 1
                    new_ivl = graduating_interval_good_days # Graduate interval
                    new_due = days_passed + new_ivl
                    # Factor remains unchanged on graduation from learning (usually)
                    new_factor = card['factor'] if card['factor'] else 2500
            elif ease == 4: # Easy -> Graduate immediately
                new_queue = 2 # Review queue
                new_type = 2
                new_left = 0
                new_reps = card['reps'] + 1
                new_ivl = graduating_interval_easy_days # Graduate interval (easy)
                new_due = days_passed + new_ivl
                new_factor = card['factor'] if card['factor'] else 2500 # Factor remains unchanged
            # Ignoring Hard (ease=2) for learning for simplicity, treat as Good
            elif ease == 2: # Hard -> Treat as Good for learning steps
                 current_step_index = step_count - card['left']
                 if current_step_index + 1 < step_count: # More steps remaining
                     new_left = card['left'] - 1
                     delay = learning_steps_sec[current_step_index + 1] if card['type'] == 1 else relearning_steps_sec[current_step_index + 1]
                     new_due = current_time_sec + delay
                     new_ivl = 0
                     new_type = card['type']
                 else: # Last step completed, graduate!
                     new_queue = 2
                     new_type = 2
                     new_left = 0
                     new_reps = card['reps'] + 1
                     new_ivl = graduating_interval_good_days
                     new_due = days_passed + new_ivl
                     new_factor = card['factor'] if card['factor'] else 2500

        elif card['queue'] == 2: # REVIEW Card
            new_reps = card['reps'] + 1
            if ease == 1: # Again (Lapse)
                new_queue = 1 # Relearning queue
                new_type = 3
                new_lapses = card['lapses'] + 1
                new_factor = max(min_factor, card['factor'] - 200)
                new_left = len(relearning_steps_sec)
                new_due = current_time_sec + relearning_steps_sec[0]
                new_ivl = 0 # Interval reset on lapse
            else: # Hard, Good, Easy
                new_queue = 2 # Stays in review
                new_type = 2
                new_left = 0 # Not in learning steps
                # Calculate next interval based on current interval, factor, and ease
                if ease == 2: # Hard
                    new_ivl = max(card['ivl'] + 1, int(card['ivl'] * 1.2))
                    new_factor = max(min_factor, card['factor'] - 150)
                elif ease == 3: # Good
                    new_ivl = max(card['ivl'] + 1, int(card['ivl'] * (card['factor'] / 1000)))
                    # Factor unchanged for Good
                else: # Easy
                    new_ivl = max(card['ivl'] + 1, int(card['ivl'] * (card['factor'] / 1000) * easy_bonus))
                    new_factor = card['factor'] + 150
                new_due = days_passed + new_ivl

        # --- Update Card --- #
        cursor.execute("""
            UPDATE cards
            SET queue = ?, type = ?, due = ?, ivl = ?, factor = ?, reps = ?, lapses = ?, left = ?, mod = ?
            WHERE id = ?
        """, (
            new_queue, new_type, new_due, new_ivl, new_factor,
            new_reps, new_lapses, new_left, current_time_sec,
            card_id
        ))

        # --- Log Review --- #
        cursor.execute("""
            INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_time_ms,
            card_id,
            -1, # usn (local only)
            ease,
            new_ivl,
            last_ivl,
            new_factor,
            time_taken_ms,
            revlog_type # Type of review (0=lrn, 1=rev, 2=relrn)
        ))

        conn.commit()

        # --- Clear session --- #
        session.pop('current_card_id', None)
        session.pop('current_note_id', None)
        # session.pop('current_card_flds', None) # Already removed

        # --- Return Answer --- #
        # answer = fields[1] # No longer need to extract answer here
        app.logger.info(f"Processed answer for card ID {card_id} for user {user_id} with ease {ease}") # INFO level
        # Return simple success message instead of answer content
        return jsonify({"message": "Answer processed successfully"}), 200

    except sqlite3.Error as e:
        app.logger.error(f"Database error processing answer for user {user_id}, card {card_id}: {e}") # Use logger
        if conn: conn.rollback()
        return jsonify({"error": "Database error occurred during review update"}), 500
    except Exception as e:
        app.logger.exception(f"Error processing answer for user {user_id}, card {card_id}: {e}") # Use logger.exception
        if conn: conn.rollback()
        # Potentially clear session variables here too?
        session.pop('current_card_id', None)
        session.pop('current_note_id', None)
        # session.pop('current_card_flds', None) # Already removed
        return jsonify({"error": "An internal server error occurred"}), 500
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
    deck_id = data.get('deckId') # Expecting deck ID as string or int
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

@app.route('/decks/<int:deck_id>/stats', methods=['GET'])
@login_required
def get_deck_stats(deck_id):
    """Calculates and returns CURRENT card status counts for a specific deck."""
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    # Timeframe parameter is ignored
    # timeframe = request.args.get('timeframe', 'today') 

    # Remove timestamp calculation
    # start_timestamp_ms = ... 

    app.logger.debug(f"Deck stats requested for deck: {deck_id}") # Simplified log

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
        if str(deck_id) not in decks_dict:
             return jsonify({"error": "Deck not found or access denied."}), 404

        # Query cards for the specific deck - id no longer needed for filtering New
        cursor.execute("SELECT queue, ivl FROM cards WHERE did = ?", (deck_id,))
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
        app.logger.error(f"Database error fetching stats for deck {deck_id}, user {user_id}: {e}")
        return jsonify({"error": "Database error occurred while fetching statistics."}), 500
    except Exception as e:
        app.logger.exception(f"Error fetching stats for deck {deck_id}, user {user_id}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/cards/<card_id>', methods=['GET'])
def get_card(card_id):
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to access card data")
        return jsonify({"error": "Unauthorized access"}), 401
    
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
        """, (card_id,))
        
        result = cursor.fetchone()
        if not result:
            app.logger.warning(f"Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404
        
        # Parse fields from the note
        fields = result[0].split('\x1f')  # Anki separator for fields
        if len(fields) < 2:
            app.logger.error(f"Card {card_id} has invalid field format")
            return jsonify({"error": "Invalid card format"}), 500
        
        # Return the card details
        return jsonify({
            "card_id": result[1],
            "front": fields[0],
            "back": fields[1]
        })
        
    except Exception as e:
        app.logger.exception(f"Error fetching card {card_id}: {str(e)}")
        return jsonify({"error": f"Error fetching card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/cards/<card_id>', methods=['PUT'])
def update_card(card_id):
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to update card")
        return jsonify({"error": "Unauthorized access"}), 401
    
    # Get request data
    data = request.json
    if not data or 'front' not in data or 'back' not in data:
        app.logger.warning("Invalid request data for card update")
        return jsonify({"error": "Front and back fields are required"}), 400
    
    front = data['front'].strip()
    back = data['back'].strip()
    
    if not front or not back:
        app.logger.warning("Empty front or back field in card update request")
        return jsonify({"error": "Front and back fields cannot be empty"}), 400
    
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
        cursor.execute("SELECT nid FROM cards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        
        if not result:
            app.logger.warning(f"Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404
        
        note_id = result[0]
        
        # Update the note fields
        new_fields = f"{front}\x1f{back}"
        checksum = sha1_checksum(front)  # Calculate checksum on first field
        current_time = int(time.time())
        
        cursor.execute("""
            UPDATE notes 
            SET flds = ?, csum = ?, mod = ?, sfld = ?
            WHERE id = ?
        """, (new_fields, int(checksum, 16) & 0xFFFFFFFF, current_time, front, note_id))
        
        # Update the card's modification time
        cursor.execute("""
            UPDATE cards
            SET mod = ?
            WHERE id = ?
        """, (current_time, card_id))
        
        # Update collection modification time
        cursor.execute("UPDATE col SET mod = ?", (int(time.time() * 1000),))
        
        conn.commit()
        app.logger.info(f"Successfully updated card {card_id}")
        return jsonify({"success": True, "message": "Card updated successfully"})
        
    except Exception as e:
        app.logger.exception(f"Error updating card {card_id}: {str(e)}")
        return jsonify({"error": f"Error updating card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/decks/<deck_id>/cards', methods=['GET'])
def get_deck_cards(deck_id):
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to access deck cards")
        return jsonify({"error": "Unauthorized access"}), 401
    
    user_id = session['user_id']
    db_path = get_user_db_path(user_id)
    
    # Check if user's database exists
    if not os.path.exists(db_path):
        app.logger.error(f"Database not found for user {user_id}")
        return jsonify({"error": "User database not found"}), 404
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Calculate offset for pagination
    offset = (page - 1) * per_page
    
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
        if str(deck_id) not in decks_dict:
            app.logger.warning(f"Deck {deck_id} not found")
            return jsonify({"error": "Deck not found"}), 404
            
        deck_name = decks_dict[str(deck_id)]['name']
        
        # Get total number of cards in the deck
        cursor.execute("""
            SELECT COUNT(*) 
            FROM cards c
            WHERE c.did = ?
        """, (deck_id,))
        total_cards = cursor.fetchone()[0]
        
        # Query to get cards for the deck with pagination
        cursor.execute("""
            SELECT c.id, n.id AS note_id, n.flds, c.mod
            FROM cards c
            JOIN notes n ON c.nid = n.id
            WHERE c.did = ?
            ORDER BY c.id DESC
            LIMIT ? OFFSET ?
        """, (deck_id, per_page, offset))
        
        cards_data = []
        for row in cursor.fetchall():
            card_id, note_id, fields, mod_time = row
            # Parse fields from the note (separated by the Anki separator \x1f)
            field_list = fields.split('\x1f')
            if len(field_list) >= 2:
                cards_data.append({
                    "card_id": card_id,
                    "note_id": note_id,
                    "front": field_list[0],
                    "back": field_list[1],
                    "modified": mod_time  # This is epoch timestamp
                })
        
        # Return the cards with pagination metadata
        return jsonify({
            "deck_id": deck_id,
            "deck_name": deck_name,
            "cards": cards_data,
            "pagination": {
                "total": total_cards,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_cards + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        app.logger.exception(f"Error fetching cards for deck {deck_id}: {str(e)}")
        return jsonify({"error": f"Error fetching cards: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/cards/<card_id>', methods=['DELETE'])
def delete_card(card_id):
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to delete card")
        return jsonify({"error": "Unauthorized access"}), 401
    
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
        cursor.execute("SELECT nid FROM cards WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        
        if not result:
            app.logger.warning(f"Card {card_id} not found")
            return jsonify({"error": "Card not found"}), 404
        
        note_id = result[0]
        
        # Begin transaction
        conn.execute("BEGIN")
        
        # Delete the card
        cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        
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
        
        app.logger.info(f"Successfully deleted card {card_id}")
        return jsonify({"success": True, "message": "Card deleted successfully"})
        
    except Exception as e:
        app.logger.exception(f"Error deleting card {card_id}: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({"error": f"Error deleting card: {str(e)}"}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/decks/<int:deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    """Delete a specific deck and all its cards"""
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to delete deck")
        return jsonify({"error": "You must be logged in"}), 401
    
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
        deck_id_str = str(deck_id)
        
        if deck_id_str not in decks_dict:
            conn.close()
            app.logger.warning(f"Attempt to delete non-existent deck {deck_id}")
            return jsonify({"error": "Deck not found"}), 404
        
        deck_name = decks_dict[deck_id_str]['name']
        app.logger.info(f"Deleting deck '{deck_name}' (ID: {deck_id}) for user {user_id}")
        
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Delete all cards in the deck
        cursor.execute("DELETE FROM cards WHERE did = ?", (deck_id,))
        cards_deleted = cursor.rowcount
        app.logger.info(f"Deleted {cards_deleted} cards from deck {deck_id}")
        
        # Remove the deck from the decks dictionary
        del decks_dict[deck_id_str]
        
        # Update the col table with the modified decks JSON
        current_time_ms = int(time.time() * 1000)
        cursor.execute("UPDATE col SET decks = ?, mod = ?", 
                      (json.dumps(decks_dict), current_time_ms))
        
        # Commit the transaction
        conn.commit()
        conn.close()
        
        return jsonify({"message": f"Deck '{deck_name}' and {cards_deleted} cards deleted successfully"}), 200
        
    except sqlite3.Error as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
            conn.close()
        app.logger.error(f"Database error while deleting deck {deck_id}: {str(e)}")
        return jsonify({"error": "Failed to delete deck due to database error"}), 500
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        app.logger.exception(f"Error deleting deck {deck_id}: {str(e)}")
        return jsonify({"error": "Failed to delete deck"}), 500

@app.route('/decks/<int:deck_id>/rename', methods=['PUT'])
def rename_deck(deck_id):
    """Renames a specific deck"""
    # Check if user is logged in
    if 'user_id' not in session:
        app.logger.warning("Unauthorized attempt to rename deck")
        return jsonify({"error": "You must be logged in"}), 401
    
    user_id = session['user_id']
    user_db_path = get_user_db_path(user_id)
    
    # Get the new name from request JSON
    data = request.get_json()
    new_name = data.get('name')
    
    if not new_name or not new_name.strip():
        return jsonify({"error": "New deck name cannot be empty"}), 400
    
    new_name = new_name.strip()
    
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
        deck_id_str = str(deck_id)
        
        if deck_id_str not in decks_dict:
            conn.close()
            app.logger.warning(f"Attempt to rename non-existent deck {deck_id}")
            return jsonify({"error": "Deck not found"}), 404
        
        # Check if another deck already has this name (case insensitive)
        for d_id, deck in decks_dict.items():
            if d_id != deck_id_str and deck['name'].lower() == new_name.lower():
                conn.close()
                return jsonify({"error": "A deck with this name already exists"}), 409
        
        old_name = decks_dict[deck_id_str]['name']
        app.logger.info(f"Renaming deck from '{old_name}' to '{new_name}' (ID: {deck_id}) for user {user_id}")
        
        # Update the deck name in the dictionary
        decks_dict[deck_id_str]['name'] = new_name
        decks_dict[deck_id_str]['mod'] = int(time.time())  # Update modification time
        
        # Update the col table with the modified decks JSON
        current_time_ms = int(time.time() * 1000)
        cursor.execute("UPDATE col SET decks = ?, mod = ?", 
                      (json.dumps(decks_dict), current_time_ms))
        
        # Commit the changes
        conn.commit()
        conn.close()
        
        return jsonify({
            "message": f"Deck renamed from '{old_name}' to '{new_name}' successfully",
            "id": deck_id,
            "name": new_name
        }), 200
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
            conn.close()
        app.logger.error(f"Database error while renaming deck {deck_id}: {str(e)}")
        return jsonify({"error": "Failed to rename deck due to database error"}), 500
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        app.logger.exception(f"Error renaming deck {deck_id}: {str(e)}")
        return jsonify({"error": "Failed to rename deck"}), 500

# --- Server Start ---
if __name__ == '__main__':
    # Initialize databases if they don't exist
    # TODO: Call database initialization functions here
    init_admin_db() # Initialize the admin database
    app.logger.info(f"Starting server on port {PORT}...") # Use logger
    app.run(host='0.0.0.0', port=PORT, debug=True) # debug=True for development 