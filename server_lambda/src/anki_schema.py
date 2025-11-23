"""
Anki Database Schema Initialization

This module contains all the SQL DDL statements and default data structures
needed to initialize a new Anki-compatible SQLite database.

Extracted from the original monolithic app.py to keep the main application clean.
"""

import json
import time


def get_anki_schema_sql():
    """
    Returns the complete SQL DDL for creating an Anki-compatible database schema.

    Tables created:
    - col: Collection metadata (models, decks, deck configs)
    - notes: Flashcard notes (front/back content)
    - cards: Individual cards derived from notes
    - revlog: Review history log
    - graves: Deletion tracking

    Returns:
        str: Complete SQL CREATE TABLE and CREATE INDEX statements
    """
    return """
        CREATE TABLE col (
            id              integer primary key,
            crt             integer not null, /* creation time in seconds */
            mod             integer not null, /* modification time in milliseconds */
            scm             integer not null, /* schema modification time in ms */
            ver             integer not null, /* version number */
            dty             integer not null, /* dirty flag - 0 = clean, 1 = needs full sync */
            usn             integer not null, /* update sequence number, -1 for local changes */
            ls              integer not null, /* last sync time in milliseconds */
            conf            text not null, /* JSON configuration */
            models          text not null, /* JSON dict of models (note types) */
            decks           text not null, /* JSON dict of decks */
            dconf           text not null, /* JSON dict of deck configurations */
            tags            text not null  /* JSON dict of tags */
        );
        CREATE TABLE notes (
            id              integer primary key, /* epoch ms timestamp */
            guid            text not null, /* globally unique id */
            mid             text not null, /* model id (references models in col table) */
            mod             integer not null, /* modification time */
            usn             integer not null, /* update sequence number */
            tags            text not null, /* space-separated tag names */
            flds            text not null, /* field data separated by \\x1f */
            sfld            text not null, /* sort field (first field) */
            csum            integer not null, /* checksum of first field */
            flags           integer not null, /* unused */
            data            text not null /* unused */
        );
        CREATE TABLE cards (
            id              integer primary key, /* epoch ms timestamp */
            nid             integer not null, /* note id */
            did             integer not null, /* deck id */
            ord             integer not null, /* ordinal (which card template) */
            mod             integer not null, /* modification time */
            usn             integer not null, /* update sequence number */
            type            integer not null, /* 0=new, 1=learning, 2=review, 3=relearning */
            queue           integer not null, /* -3=sched buried, -2=user buried, -1=suspended, 0=new, 1=learning, 2=review, 3=day learning */
            due             integer not null, /* day number for review cards, timestamp for learning cards */
            ivl             integer not null, /* interval in days */
            factor          integer not null, /* ease factor in permille (1000 = 100%) */
            reps            integer not null, /* number of reviews */
            lapses          integer not null, /* number of times card went from review to relearning */
            left            integer not null, /* reps left till graduation */
            odue            integer not null, /* original due: only used for filtered decks */
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
    """


def get_default_anki_data(user_name="User"):
    """
    Returns default Anki collection data for a new user.

    Args:
        user_name: Name of the user (for personalized deck description)

    Returns:
        tuple: (col_row_tuple, decks_dict) ready for insertion
            - col_row_tuple: Full row for INSERT INTO col
            - decks_dict: Dictionary of deck definitions (for reference)
    """
    crt_time = int(time.time())
    mod_time_ms = int(time.time() * 1000)
    scm_time_ms = mod_time_ms

    # Default configuration
    default_conf = {
        "nextPos": 1,
        "estTimes": True,
        "activeDecks": [1],
        "sortType": "noteFld",
        "timeLim": 0,
        "sortBackwards": False,
        "addToCur": True,
        "curDeck": 1,
        "newBury": True,
        "newSpread": 0,
        "dueCounts": True,
        "curModel": "1",
        "collapseTime": 1200
    }

    # Basic note model (card template)
    basic_model_id = "1700000000001"
    default_models = {
        basic_model_id: {
            "id": basic_model_id,
            "name": "Basic-Gemini",
            "type": 0,
            "mod": crt_time,
            "usn": -1,
            "sortf": 0,
            "did": 1,
            "tmpls": [
                {
                    "name": "Card 1",
                    "ord": 0,
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
                    "bqfmt": "",
                    "bafmt": "",
                    "did": None,
                    "bfont": "Arial",
                    "bsize": 12
                }
            ],
            "flds": [
                {
                    "name": "Front",
                    "ord": 0,
                    "sticky": False,
                    "rtl": False,
                    "font": "Arial",
                    "size": 20
                },
                {
                    "name": "Back",
                    "ord": 1,
                    "sticky": False,
                    "rtl": False,
                    "font": "Arial",
                    "size": 20
                }
            ],
            "css": ".card {\n font-family: arial;\n font-size: 20px;\n text-align: center;\n color: black;\n background-color: white;\n}\n",
            "latexPre": "\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}",
            "latexPost": "\\end{document}",
            "latexsvg": False,
            "ver": []
        }
    }

    # Default decks
    default_decks = {
        "1": {
            "id": 1,
            "name": "MyFirstDeck",
            "mod": crt_time,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "conf": 1,
            "desc": "Your first flashcard deck",
            "dyn": 0,
            "collapsed": False,
            "extendNew": 10,
            "extendRev": 50
        },
        "2": {
            "id": 2,
            "name": "Verbal Tenses",
            "mod": crt_time,
            "usn": -1,
            "lrnToday": [0, 0],
            "revToday": [0, 0],
            "newToday": [0, 0],
            "timeToday": [0, 0],
            "conf": 1,
            "desc": f"English verb tenses sample deck for {user_name}",
            "dyn": 0,
            "collapsed": False,
            "extendNew": 10,
            "extendRev": 50
        }
    }

    # Deck configurations (scheduling parameters)
    default_dconf = {
        "1": {
            "id": 1,
            "name": "Default",
            "mod": crt_time,
            "usn": -1,
            "maxTaken": 60,
            "timer": 0,
            "autoplay": True,
            "replayq": True,
            "new": {
                "bury": True,
                "delays": [1, 10],
                "initialFactor": 2500,
                "ints": [1, 4, 0],
                "order": 1,
                "perDay": 25,
                "separate": True
            },
            "rev": {
                "bury": True,
                "ease4": 1.3,
                "fuzz": 0.05,
                "ivlFct": 1,
                "maxIvl": 36500,
                "perDay": 100,
                "hardFactor": 1.2
            },
            "lapse": {
                "delays": [10],
                "leechAction": 1,
                "leechFails": 8,
                "minInt": 1,
                "mult": 0
            }
        }
    }

    # Build the full row tuple for col table
    col_row = (
        1,                              # id
        crt_time,                       # crt (creation time in seconds)
        mod_time_ms,                    # mod (modification time in ms)
        scm_time_ms,                    # scm (schema modification time in ms)
        11,                             # ver (Anki version)
        0,                              # dty (dirty flag)
        -1,                             # usn (update sequence number)
        0,                              # ls (last sync time)
        json.dumps(default_conf),       # conf
        json.dumps(default_models),     # models
        json.dumps(default_decks),      # decks
        json.dumps(default_dconf),      # dconf
        json.dumps({})                  # tags
    )

    return col_row, default_decks


def init_anki_db(conn, user_name="User"):
    """
    Initialize a new Anki database with schema and default data.

    Args:
        conn: Open SQLite connection object
        user_name: User's display name (for personalized deck descriptions)

    Returns:
        dict: Dictionary of created decks (for reference)
    """
    cursor = conn.cursor()

    # Create schema
    cursor.executescript(get_anki_schema_sql())

    # Insert default collection data
    col_row, decks_dict = get_default_anki_data(user_name)
    cursor.execute("""
        INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, col_row)

    conn.commit()

    return decks_dict
