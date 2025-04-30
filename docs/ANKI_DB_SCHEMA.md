# Anki Database Schema (collection.anki2)

This document describes the schema for the `collection.anki2` SQLite database, which is compatible with the Anki flashcard application format.

This database stores the user's flashcards, decks, review history, and configuration.

## `col` Table

Stores collection-wide information and configuration.

**Schema:**

```sql
CREATE TABLE col (
    id              integer primary key, -- always 1
    crt             integer not null,    -- created timestamp
    mod             integer not null,    -- last modified timestamp
    scm             integer not null,    -- schema modification timestamp
    ver             integer not null,    -- Anki version
    dty             integer not null,    -- dirty flag (unused)
    usn             integer not null,    -- update sequence number for sync
    ls              integer not null,    -- last sync timestamp
    conf            text not null,       -- JSON object containing collection configuration
    models          text not null,       -- JSON object containing note type definitions (models)
    decks           text not null,       -- JSON object containing deck definitions
    dconf           text not null,       -- JSON object containing deck configuration options
    tags            text not null        -- JSON object containing tags (unused in standard Anki)
);
```

**Columns:**

*   `id`: INTEGER (Primary Key) - Always set to 1, representing the single collection.
*   `crt`: INTEGER (Not Null) - Timestamp (seconds since epoch) when the collection was created.
*   `mod`: INTEGER (Not Null) - Timestamp (seconds since epoch) of the last modification to the collection metadata (not card data).
*   `scm`: INTEGER (Not Null) - Schema modification timestamp. Indicates when the structure of the database itself last changed.
*   `ver`: INTEGER (Not Null) - Anki version number associated with the schema.
*   `dty`: INTEGER (Not Null) - Dirty flag, generally unused.
*   `usn`: INTEGER (Not Null) - Update Sequence Number. Used for synchronization, incremented on changes.
*   `ls`: INTEGER (Not Null) - Timestamp of the last successful synchronization.
*   `conf`: TEXT (Not Null) - JSON string containing global configuration options for the collection (e.g., scheduling settings).
*   `models`: TEXT (Not Null) - JSON string defining the structure of different note types (e.g., Basic, Cloze).
*   `decks`: TEXT (Not Null) - JSON string defining the available decks and their hierarchy.
*   `dconf`: TEXT (Not Null) - JSON string defining configuration profiles that can be applied to decks.
*   `tags`: TEXT (Not Null) - JSON string for tags (typically managed differently in modern Anki).

## `notes` Table

Stores the raw content (fields) for each flashcard note. A single note can generate multiple cards (e.g., forward and reverse).

**Schema:**

```sql
CREATE TABLE notes (
    id              integer primary key, -- note id
    guid            text not null,       -- globally unique id, almost certainly used for syncing
    mid             integer not null,    -- model id
    mod             integer not null,    -- modification timestamp
    usn             integer not null,    -- update sequence number
    tags            text not null,       -- space-separated string of tags
    flds            text not null,       -- field content separated by U+001F
    sfld            integer not null,    -- sort field (integer representation of first field's start for sorting)
    csum            integer not null,    -- field checksum used for duplicate checking
    flags           integer not null,    -- unused
    data            text not null        -- unused
);
```

**Columns:**

*   `id`: INTEGER (Primary Key) - Unique identifier for the note (timestamp of creation).
*   `guid`: TEXT (Not Null) - Globally Unique Identifier, used for syncing.
*   `mid`: INTEGER (Not Null) - ID of the model (`models` in `col` table) this note uses.
*   `mod`: INTEGER (Not Null) - Timestamp of the last modification to this note.
*   `usn`: INTEGER (Not Null) - Update Sequence Number for syncing changes to this note.
*   `tags`: TEXT (Not Null) - Space-separated list of tags associated with the note.
*   `flds`: TEXT (Not Null) - The actual content of the note's fields, separated by the Unit Separator character (U+001F).
*   `sfld`: INTEGER (Not Null) - Sort field; derived from the first field for efficient sorting.
*   `csum`: INTEGER (Not Null) - Checksum of the `sfld`, used for finding duplicate notes.
*   `flags`: INTEGER (Not Null) - Currently unused.
*   `data`: TEXT (Not Null) - Currently unused.

## `cards` Table

Stores individual cards generated from notes, along with their scheduling information.

**Schema:**

```sql
CREATE TABLE cards (
    id              integer primary key, -- card id (timestamp)
    nid             integer not null,    -- note id
    did             integer not null,    -- deck id
    ord             integer not null,    -- card template index (0-based)
    mod             integer not null,    -- modification timestamp
    usn             integer not null,    -- update sequence number
    type            integer not null,    -- card type (0=new, 1=learning, 2=review, 3=relearning)
    queue           integer not null,    -- queue state (-3=sched buried, -2=user buried, -1=suspended, 0=new, 1=learning, 2=review, 3=day learn, 4=preview)
    due             integer not null,    -- due date (day offset for review, timestamp for learn)
    ivl             integer not null,    -- interval (days for review, seconds for learn/relearn)
    factor          integer not null,    -- ease factor (times 1000)
    reps            integer not null,    -- number of reviews
    lapses          integer not null,    -- number of times failed (lapsed)
    left            integer not null,    -- reps left today (for learn/relearn)
    odue            integer not null,    -- original due date for filtered decks
    odid            integer not null,    -- original deck id for filtered decks
    flags           integer not null,    -- currently unused
    data            text not null        -- currently unused
);
```

**Columns:**

*   `id`: INTEGER (Primary Key) - Unique identifier for the card (timestamp of creation).
*   `nid`: INTEGER (Not Null) - ID of the parent note (`notes` table).
*   `did`: INTEGER (Not Null) - ID of the deck this card belongs to (`decks` in `col` table).
*   `ord`: INTEGER (Not Null) - The 0-based index of the card template within the note's model that generated this card.
*   `mod`: INTEGER (Not Null) - Timestamp of the last modification to this card's state.
*   `usn`: INTEGER (Not Null) - Update Sequence Number for syncing changes to this card.
*   `type`: INTEGER (Not Null) - Current state of the card: 0=New, 1=Learning, 2=Review, 3=Relearning.
*   `queue`: INTEGER (Not Null) - More detailed queue status: -3=Sched Buried, -2=User Buried, -1=Suspended, 0=New, 1=Learning, 2=Review, 3=Day Learn, 4=Preview.
*   `due`: INTEGER (Not Null) - Due date. For review cards (type 2), it's the number of days since collection creation date. For learning cards (type 1/3), it's a timestamp.
*   `ivl`: INTEGER (Not Null) - Interval. For review cards, it's the number of days until the next review. For learning/relearning, it can be seconds or days depending on the step.
*   `factor`: INTEGER (Not Null) - Ease Factor, multiplied by 1000. Affects how much the interval increases on a successful review.
*   `reps`: INTEGER (Not Null) - Total number of times this card has been reviewed.
*   `lapses`: INTEGER (Not Null) - Number of times this card went from review state back to learning state (failed).
*   `left`: INTEGER (Not Null) - For learning cards, indicates reviews/steps left for the current session.
*   `odue`: INTEGER (Not Null) - Original due date, used when cards are in filtered decks.
*   `odid`: INTEGER (Not Null) - Original deck ID, used when cards are in filtered decks.
*   `flags`: INTEGER (Not Null) - Currently unused.
*   `data`: TEXT (Not Null) - Currently unused.

## `revlog` Table

Stores a log of all reviews conducted.

**Schema:**

```sql
CREATE TABLE revlog (
    id              integer primary key, -- review log id (timestamp)
    cid             integer not null,    -- card id
    usn             integer not null,    -- update sequence number (for sync)
    ease            integer not null,    -- rating given (1-4: Again, Hard, Good, Easy)
    ivl             integer not null,    -- new interval
    lastIvl         integer not null,    -- previous interval
    factor          integer not null,    -- new ease factor
    time            integer not null,    -- time taken for review (milliseconds)
    type            integer not null     -- review type (0=learn, 1=review, 2=relearn, 3=cram/filtered)
);
```

**Columns:**

*   `id`: INTEGER (Primary Key) - Timestamp (milliseconds since epoch) of the review.
*   `cid`: INTEGER (Not Null) - ID of the card (`cards` table) that was reviewed.
*   `usn`: INTEGER (Not Null) - Update Sequence Number for syncing this review log entry.
*   `ease`: INTEGER (Not Null) - The user's rating for the review: 1 (Again), 2 (Hard), 3 (Good), 4 (Easy).
*   `ivl`: INTEGER (Not Null) - The new interval assigned to the card after this review.
*   `lastIvl`: INTEGER (Not Null) - The interval the card had before this review.
*   `factor`: INTEGER (Not Null) - The new ease factor of the card after this review.
*   `time`: INTEGER (Not Null) - Time spent on the review in milliseconds.
*   `type`: INTEGER (Not Null) - Type of review: 0=Learn, 1=Review, 2=Relearn, 3=Filtered/Cram.

## `graves` Table

Stores information about deleted items (cards, notes, decks) for synchronization purposes.

**Schema:**

```sql
CREATE TABLE graves (
    usn             integer not null, -- update sequence number
    oid             integer not null, -- original id
    type            integer not null  -- type (0=card, 1=note, 2=deck)
);
```

**Columns:**

*   `usn`: INTEGER (Not Null) - Update Sequence Number associated with the deletion event.
*   `oid`: INTEGER (Not Null) - The original ID of the deleted item (card id, note id, or deck id).
*   `type`: INTEGER (Not Null) - Type of the deleted item: 0=Card, 1=Note, 2=Deck. 