# Potential Use of Repository Pattern in Flashcard App

This document outlines potential classes within the flashcard application that could be implemented using the Repository pattern, abstracting data access logic. It also maps these potential repositories to the REST API endpoints they would likely serve.

## 1. UserRepository

*   **Purpose:** Manages user data stored in `admin.db`.
*   **Entity:** User
*   **Potential Operations:**
    *   `create(user_data)`
    *   `find_by_id(user_id)`
    *   `find_by_username(username)`
    *   `update(user_id, update_data)`
    *   `delete(user_id)`
    *   `get_password_hash(username)`
*   **Associated API Endpoints:**
    *   `POST /register` (or `POST /users`): Uses `create`, `find_by_username`.
    *   `POST /login`: Uses `find_by_username`, `get_password_hash`.
    *   `GET /users/{user_id}`: Uses `find_by_id`.
    *   `PUT /users/{user_id}`: Uses `update`.
    *   `DELETE /users/{user_id}`: Uses `delete`.
    *   `GET /users/me` (or similar for current user): Uses `find_by_id`.

## 2. CollectionRepository

*   **Purpose:** Manages the global collection settings stored in the `col` table of a user's `collection.anki2` database.
*   **Entity:** Collection (`col` table row)
*   **Potential Operations:**
    *   `get_collection_metadata(user_id)`
    *   `update_collection_metadata(user_id, metadata)`
    *   `get_models(user_id)`
    *   `update_models(user_id, models_json)`
    *   `get_deck_config(user_id)`
    *   `update_deck_config(user_id, deck_config_json)`
    *   `get_decks(user_id)`
    *   `update_decks(user_id, decks_json)`
    *   `get_last_sync_time(user_id)`
    *   `update_last_sync_time(user_id, timestamp)`
    *   `increment_usn(user_id)`
*   **Associated API Endpoints:**
    *   `GET /users/{user_id}/collection/metadata`: Uses `get_collection_metadata`.
    *   `PUT /users/{user_id}/collection/metadata`: Uses `update_collection_metadata`.
    *   `GET /users/{user_id}/collection/models`: Uses `get_models`.
    *   `PUT /users/{user_id}/collection/models`: Uses `update_models`.
    *   `GET /users/{user_id}/collection/deck-config`: Uses `get_deck_config`.
    *   `PUT /users/{user_id}/collection/deck-config`: Uses `update_deck_config`.
    *   `GET /users/{user_id}/collection/decks`: Uses `get_decks`.
    *   `PUT /users/{user_id}/collection/decks`: Uses `update_decks`.
    *   Endpoints related to synchronization (`/sync`) would heavily use `get_last_sync_time`, `update_last_sync_time`, `increment_usn`, and potentially other methods for fetching changed items based on USN (Update Sequence Number).

## 3. DeckRepository

*   **Note:** Deck information is stored within the `decks` JSON blob in the `col` table. A dedicated `DeckRepository` might operate on this JSON data *after* it's fetched by the `CollectionRepository`, or it could have specialized methods that directly query/manipulate the JSON within the database if the RDBMS supports it (SQLite's JSON capabilities are relevant here).
*   **Purpose:** Manages deck definitions.
*   **Entity:** Deck (objects within the `decks` JSON)
*   **Potential Operations (acting on the JSON structure):**
    *   `find_deck_by_id(user_id, deck_id)`
    *   `find_all_decks(user_id)`
    *   `add_deck(user_id, deck_data)`
    *   `update_deck(user_id, deck_id, update_data)`
    *   `remove_deck(user_id, deck_id)`
*   **Associated API Endpoints:**
    *   `GET /users/{user_id}/decks`: Uses `find_all_decks`.
    *   `POST /users/{user_id}/decks`: Uses `add_deck`.
    *   `GET /users/{user_id}/decks/{deck_id}`: Uses `find_deck_by_id`.
    *   `PUT /users/{user_id}/decks/{deck_id}`: Uses `update_deck`.
    *   `DELETE /users/{user_id}/decks/{deck_id}`: Uses `remove_deck`.

## 4. NoteRepository

*   **Purpose:** Manages notes (the content) in the `notes` table of `collection.anki2`.
*   **Entity:** Note
*   **Potential Operations:**
    *   `create(user_id, note_data)`
    *   `find_by_id(user_id, note_id)`
    *   `find_by_model(user_id, model_id)`
    *   `find_by_tag(user_id, tag)`
    *   `find_all(user_id)`
    *   `update(user_id, note_id, update_data)`
    *   `delete(user_id, note_id)` (Should likely also handle associated cards and add grave entries).
    *   `find_duplicates(user_id, checksum)`
    *   `get_notes_modified_since(user_id, timestamp)`
*   **Associated API Endpoints:**
    *   `POST /users/{user_id}/notes`: Uses `create`, `find_duplicates`.
    *   `GET /users/{user_id}/notes`: Uses `find_all` (potentially with filters for model/tag).
    *   `GET /users/{user_id}/notes/{note_id}`: Uses `find_by_id`.
    *   `PUT /users/{user_id}/notes/{note_id}`: Uses `update`.
    *   `DELETE /users/{user_id}/notes/{note_id}`: Uses `delete`.
    *   Synchronization endpoints would use `get_notes_modified_since`.

## 5. CardRepository

*   **Purpose:** Manages cards (scheduling, deck assignment) in the `cards` table of `collection.anki2`.
*   **Entity:** Card
*   **Potential Operations:**
    *   `create(user_id, card_data)` (Usually created alongside a note or when model templates change).
    *   `find_by_id(user_id, card_id)`
    *   `find_by_note_id(user_id, note_id)`
    *   `find_by_deck_id(user_id, deck_id)`
    *   `find_due_cards(user_id, deck_id, timestamp)`
    *   `find_new_cards(user_id, deck_id)`
    *   `update_scheduling(user_id, card_id, scheduling_data)`
    *   `update_deck(user_id, card_id, new_deck_id)`
    *   `update_state(user_id, card_id, state_data)` (e.g., suspend, bury, change type/queue)
    *   `delete(user_id, card_id)` (Adds grave entry).
    *   `delete_by_note_id(user_id, note_id)`
    *   `get_cards_modified_since(user_id, timestamp)`
*   **Associated API Endpoints:**
    *   `GET /users/{user_id}/cards/due`: Uses `find_due_cards`.
    *   `GET /users/{user_id}/cards/new`: Uses `find_new_cards`.
    *   `GET /users/{user_id}/decks/{deck_id}/cards`: Uses `find_by_deck_id` (potentially filtered by due/new).
    *   `GET /users/{user_id}/notes/{note_id}/cards`: Uses `find_by_note_id`.
    *   `GET /users/{user_id}/cards/{card_id}`: Uses `find_by_id`.
    *   `PUT /users/{user_id}/cards/{card_id}`: Uses `update_scheduling`, `update_state`, `update_deck`.
    *   `POST /users/{user_id}/cards/{card_id}/answer`: (High-level action) Internally uses `find_by_id`, calculates new state, then uses `update_scheduling` and potentially `add_review_log` (from RevlogRepository).
    *   `DELETE /users/{user_id}/cards/{card_id}`: Uses `delete`.
    *   Synchronization endpoints would use `get_cards_modified_since`.

## 6. RevlogRepository

*   **Purpose:** Manages review history in the `revlog` table of `collection.anki2`.
*   **Entity:** Review Log Entry
*   **Potential Operations:**
    *   `add_review(user_id, review_data)`
    *   `find_by_card_id(user_id, card_id)`
    *   `find_by_period(user_id, start_time, end_time)`
    *   `get_reviews_since(user_id, timestamp)`
*   **Associated API Endpoints:**
    *   `POST /users/{user_id}/reviews`: Uses `add_review` (often called internally after answering a card).
    *   `GET /users/{user_id}/cards/{card_id}/reviews`: Uses `find_by_card_id`.
    *   `GET /users/{user_id}/reviews`: Uses `find_by_period`.
    *   Synchronization endpoints would use `get_reviews_since`.

## 7. GraveRepository

*   **Purpose:** Manages deletion markers in the `graves` table for synchronization.
*   **Entity:** Grave Entry
*   **Potential Operations:**
    *   `add_grave(user_id, original_id, type)`
    *   `find_graves_since(user_id, usn)`
*   **Associated API Endpoints:**
    *   Deletion endpoints (`DELETE /users/.../notes/{id}`, `DELETE /users/.../cards/{id}`, etc.) would internally call `add_grave`.
    *   Synchronization endpoints would use `find_graves_since`.

---

**Conclusion:**

The Repository pattern could be beneficially applied to manage interactions with both the `admin.db` (via `UserRepository`) and the user-specific `collection.anki2` database (via `CollectionRepository`, `NoteRepository`, `CardRepository`, `RevlogRepository`, `GraveRepository`, and potentially a `DeckRepository` handling the JSON structure). This would centralize data access logic, improve testability by allowing mocks, and make the service layer cleaner by separating data persistence concerns. 