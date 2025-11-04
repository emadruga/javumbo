# JAVUMBO Flashcard Application

This document provides a comprehensive overview of the JAVUMBO flashcard application, a full-stack project designed for spaced repetition learning. The application is composed of a React frontend, a Python Flask backend, and a separate administrative interface.

## 1. Architecture

The project is a monorepo containing several distinct components:

-   **/client**: The main user-facing single-page application (SPA) built with React.
-   **/server**: The backend REST API server built with Python and Flask.
-   **/admin_client**: A separate React-based SPA for administrative tasks.
-   **/admin_server**: The backend API supporting the admin client.
-   **/docs**: Contains all project documentation, including API specifications, database schemas, and deployment guides.

---

## 2. Server (`/server`)

The server is the core of the application, handling business logic, data persistence, and user authentication.

### Key Technologies

-   **Framework**: Python Flask
-   **WSGI Server**: Gunicorn (for production)
-   **Database**: SQLite

### Database Structure

The server utilizes two distinct SQLite database schemas:

1.  **Admin Database (`admin.db`)**: A central database that stores user credentials and information. It contains a single `users` table with `user_id`, `username`, `name`, and `password_hash`.
    -   *See: `docs/ADMIN_DB_SCHEMA.md`*
2.  **User-Specific Databases (`user_dbs/<username>.anki2`)**: Each user has their own dedicated SQLite database that stores their flashcard collection in a format compatible with the Anki desktop application. This includes tables for notes (`notes`), cards (`cards`), decks (`col`), and review history (`revlog`).
    -   *See: `docs/ANKI_DB_SCHEMA.md`*

### Core Concepts

-   **REST API**: The server exposes a comprehensive REST API for all client operations, including user authentication, deck and card management, review sessions, and collection exporting. All endpoints are documented in detail.
    -   *See: `docs/REST_API.md`*
-   **Spaced Repetition (SM-2)**: The card review scheduling logic is based on the SuperMemo-2 (SM-2) algorithm. The implementation is adapted to use deck-specific configuration parameters for calculating review intervals, similar to Anki's approach.
    -   *See: `docs/SUPERMEMO-2.md`*
-   **Repository Pattern**: The codebase is being refactored to use the Repository pattern to abstract database interactions, separating data access logic from the main application logic.
    -   *See: `docs/REPO_PATTERN.md` and `docs/TODO.md`*

---

## 3. Client (`/client`)

The client is a modern single-page application that provides a rich user experience for interacting with the flashcard system.

### Key Technologies

-   **Framework**: React
-   **Build Tool**: Vite
-   **Key Libraries**: `react-router-dom` for navigation, `axios` for API communication.

### Features

-   User registration and login.
-   Full CRUD (Create, Read, Update, Delete) operations for decks and cards.
-   An interactive review page for studying flashcards.
-   A statistics page to track review progress.
-   Functionality to export the user's collection to an `.apkg` file for use in Anki.

### Configuration

The client uses environment variables to manage configuration between development and production environments. This is crucial for setting the correct API base URL and application base path when deployed behind a reverse proxy.

-   `.env.development`: For local development (`npm run dev`).
-   `.env.production`: For production builds (`npm run build`).

Key variables include `VITE_APP_BASE_PATH` and `VITE_API_BASE_URL`.

-   *See: `docs/PRODUCTION.md`*

---

## 4. Admin Interface (`/admin_client` & `/admin_server`)

A separate, simpler interface for system administrators to perform management tasks.

-   **Technology**: React frontend (`/admin_client`) and a dedicated Python Flask backend (`/admin_server`).
-   **Functionality**: Provides views to list all registered users and their decks, reading directly from the `admin.db` and user database files.

---

## 5. Deployment

The application is designed to be deployed using two primary methods.

### Traditional Deployment

-   **Backend**: The Flask application is served by a Gunicorn WSGI server, managed by a `systemd` service.
-   **Frontend**: The React application is built into static files (`npm run build`).
-   **Reverse Proxy**: Nginx is used to serve the static frontend files and act as a reverse proxy, forwarding API requests (e.g., `/login`, `/decks`) to the Gunicorn process.

### Docker Deployment

-   **Orchestration**: `docker-compose.yml` is used to define and manage the application services.
-   **Services**:
    -   `server`: A container running the Flask/Gunicorn backend. The `./server` directory is mounted as a volume to provide access to the code and persistent SQLite databases on the host.
    -   `client`: A multi-stage build container that first builds the React app and then serves the static assets with Nginx.
-   **Networking**: A dedicated bridge network (`flashcard-net`) allows the client and server containers to communicate.

-   *For detailed instructions on both methods, see: `docs/PRODUCTION.md`*

---

## 6. Testing

The project includes a suite of unit tests for the backend API to ensure reliability and prevent regressions.

-   **Framework**: Python's built-in `unittest` module.
-   **Test File**: `server/test_api.py` contains all API tests.
-   **Execution**: Tests can be run directly from the `/server` directory:
    ```bash
    python -m unittest test_api.py -v
    ```
-   **Coverage**: The tests cover all major API endpoints, including success paths, error handling, and authentication checks.

-   *See: `docs/UNIT_TESTS.md`*

---

## 7. Feature Implementation Plan

### Add Card from Decks Page

**Objective:** Allow users to add a new flashcard to a specific deck directly from the dropdown menu on the `DecksPage`.

**Plan:**

1.  **Create `handleAddCard` Function:**
    *   In `client/src/pages/DecksPage.jsx`, create a new `async` function called `handleAddCard(deckId, deckName)`.
    *   This function will make a `PUT` request to `/decks/current` to set the active deck in the backend.
    *   It will then save the `deckName` to `localStorage` so that the `AddCardPage` can display it.
    *   Finally, it will navigate the user to the `/add` route.

2.  **Update `handleDropdownAction` Function:**
    *   In `client/src/pages/DecksPage.jsx`, modify the `switch` statement inside the `handleDropdownAction` function.
    *   Add a new `case` for the action `'addCard'`.
    *   This case will call the newly created `handleAddCard` function, passing the `deck.id` and `deck.name`.

3.  **Add UI Element:**
    *   In the JSX of `client/src/pages/DecksPage.jsx`, add a new `<button>` element inside the dropdown menu.
    *   This button will be labeled "Add Card" (using the `t('cards.add')` translation key).
    *   The `onClick` handler for this button will call `handleDropdownAction` with the `'addCard'` action.

---

## Troubleshooting Session Log (July 2, 2025)

This section logs the troubleshooting steps and findings related to deploying the Flask backend with Gunicorn and systemd, specifically addressing the `status=216/GROUP` error and related issues.

**Initial Problem:**
Service failed to start with `status=216/GROUP`.

**Troubleshooting Steps & Findings:**

1.  **Initial Diagnosis (from `systemctl status`):**
    *   Error: `Failed to determine group credentials: No such file or directory`
    *   Indicated `Group=www-data` in service file might not exist.

2.  **Service File Review:**
    *   `User=emadruga`, `Group=www-data`
    *   Proposed change: `Group=emadruga` (to match existing user's primary group).

3.  **Log Directory Permissions Check:**
    *   `ls -ld /var/log/flashcard-app-teste/` showed `drwxr-xr-x 2 root root ...`
    *   **Finding:** Log directory owned by `root`, not writable by `emadruga`.
    *   **Action:** `sudo chown -R emadruga:emadruga /var/log/flashcard-app-teste/`

4.  **Environment Variable (`SECRET_KEY`) Check:**
    *   `app.py` loads `SECRET_KEY` from `.env`.
    *   `cat /opt/flashcard-app-teste/javumbo/server/.env` confirmed `SECRET_KEY` was present.
    *   **Action:** Added `EnvironmentFile=/opt/flashcard-app-teste/javumbo/server/.env` to service file to ensure `systemd` loads it.

5.  **Manual Gunicorn Execution Test:**
    *   `cd /opt/flashcard-app-teste/javumbo/server`
    *   `/opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/gunicorn ... app:app`
    *   **Finding:** Gunicorn started successfully and did not crash, indicating the application code itself was not the immediate problem when run manually. This suggested a `systemd` environment issue.

6.  **Flask Application Naming Conflict (Hypothesis):**
    *   User noted an older production app on the same server.
    *   **Hypothesis:** `Flask(__name__)` might cause a naming conflict for session/cache resources if both apps use the same default name, leading to a crash when `systemd` tries to start the second instance.
    *   **Proposed Action:** Change `app = Flask(__name__)` to `app = Flask("flashcard-app-teste")` in `server/app.py`. (This change was proposed but not yet confirmed as implemented or tested).

7.  **Virtual Environment Interpreter Path Issue (Root Cause Identified):**
    *   `journalctl` output showed: `Failed at step GROUP spawning /opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/gunicorn: No such file or directory`
    *   `ls -l /opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/gunicorn` confirmed `gunicorn` existed.
    *   `head -n 1 /opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/gunicorn` revealed: `#!/opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/python3.12`
    *   `ls -la /opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv/bin/python3.12` showed a symbolic link: `-> /home/emadruga/.conda/envs/teste12/bin/python3.12`
    *   **Critical Finding:** The virtual environment's Python interpreter was symlinked to a Conda environment inside the user's home directory (`/home/emadruga/.conda/...`). `systemd` services, even when running as the user, are typically restricted from accessing files within `/home/user` for security reasons. This restriction causes `systemd` to report "No such file or directory" when it tries to follow the symlink into the restricted area.

8.  **Final Solution (Proposed):**
    *   **Recreate the virtual environment** directly within the project directory (`/opt/flashcard-app-teste/javumbo/server/javumbo-teste-venv`) on the `maracana` server. This ensures all internal paths point to locations accessible by `systemd` and are self-contained.
    *   Commands:
        ```bash
        cd /opt/flashcard-app-teste/javumbo/server
        rm -rf javumbo-teste-venv
        python3 -m venv javumbo-teste-venv
        source javumbo-teste-venv/bin/activate
        pip install -r requirements.txt
        ```
    *   After recreation, restart the `systemd` service.

**Next Steps:**
The user will execute the virtual environment recreation steps and then attempt to start the `systemd` service.