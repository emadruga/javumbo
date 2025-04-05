# Flashcard App v5 - Anki Gemini

This project is a web-based flashcard application featuring:

*   A React/Vite frontend for user interaction.
*   A Python/Flask backend for handling logic and data.
*   User authentication (registration and login).
*   Flashcard review based on a simplified SM-2/Anki scheduling algorithm.
*   Anki-compatible database structure (`.db` files per user).
*   Deck export functionality to Anki-standard `.apkg` format.

## Features

*   **Frontend (React/Vite)**:
    *   Authentication page with Login and Register tabs.
    *   Review page displaying flashcards (Front & Back).
    *   Rating buttons (Again, Hard, Good, Easy) to update card scheduling.
    *   Logout functionality.
    *   Export button to download the current deck as an `.apkg` file.
*   **Backend (Python/Flask)**:
    *   REST API for frontend communication.
    *   User management (`admin.db`) with password hashing (bcrypt).
    *   Session management using Flask sessions.
    *   Separate Anki-compatible SQLite databases (`user_*.db`) created per user upon registration.
    *   Initialization with 25 sample flashcards on Generative AI for new users.
    *   Simplified SM-2/Anki scheduling logic for card reviews.
    *   APKG export generation including the user's `collection.anki2` database and required `media` file.

## Technologies Used

*   **Frontend**: React, Vite, JavaScript, Axios, react-router-dom, js-file-download
*   **Backend**: Python, Flask, Flask-Cors, SQLite3, bcrypt
*   **Database Schema**: Anki `.anki2` (SQLite3)
*   **Export Format**: Anki `.apkg` (Zip archive)

## Project Structure

```
flashcard-app-v5-anki-gemini/
├── client/            # React Frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── api/
│   │   │   └── axiosConfig.js
│   │   ├── components/
│   │   │   ├── Flashcard.jsx
│   │   │   ├── LoginForm.jsx
│   │   │   └── RegisterForm.jsx
│   │   ├── pages/
│   │   │   ├── AuthPage.jsx
│   │   │   └── ReviewPage.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── server/            # Flask Backend
│   ├── exports/         # Temporary directory for generated .apkg files
│   ├── user_dbs/        # Directory storing user-specific Anki DBs
│   ├── server_venv/     # Python virtual environment (optional)
│   ├── admin.db         # Admin database for user credentials
│   └── app.py           # Main Flask application
└── README.md          # This file
```

## Setup and Execution Instructions

You will need two separate terminal windows/tabs to run the backend server and the frontend client.

**Prerequisites:**

*   Python 3.x installed.
*   Node.js and npm (or yarn) installed.

**1. Run the Server (Flask Backend)**

*   Open **Terminal 1**.
*   Navigate to the project root directory:
    ```bash
    cd /path/to/flashcard-app-v5-anki-gemini
    ```
*   *(Recommended)* Create and activate a Python virtual environment:
    ```bash
    # Create environment (only once)
    python3 -m venv server_venv
    # Activate (macOS/Linux)
    source server_venv/bin/activate
    # Activate (Windows Git Bash)
    # source server_venv/Scripts/activate
    # Activate (Windows CMD/PowerShell)
    # .\server_venv\Scripts\activate
    ```
*   Install Python dependencies:
    ```bash
    pip install Flask Flask-Cors bcrypt
    ```
*   Run the Flask server:
    ```bash
    python server/app.py
    ```
*   The server should start running on `http://localhost:8000`.

**2. Run the Client (React Frontend)**

*   Open **Terminal 2**.
*   Navigate to the `client` directory:
    ```bash
    cd /path/to/flashcard-app-v5-anki-gemini/client
    ```
*   Install Node dependencies (if setting up for the first time):
    ```bash
    npm install
    ```
*   Run the Vite development server:
    ```bash
    npm run dev
    ```
*   The client development server will likely start on `http://localhost:5173` (check terminal output for the exact URL).

**3. Access the Application**

*   Open your web browser and navigate to the **Local** URL provided by the Vite output (usually `http://localhost:5173`).
*   You should see the application's login/register page. 