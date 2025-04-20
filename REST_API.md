# Flashcard App REST API Documentation

This document outlines the REST API endpoints for the Flashcard application server.

---

## Authentication

Routes marked with `Authentication Required: Yes` require the user to be logged in. A valid session cookie must be sent with the request. If authentication fails or is missing, a `401 Unauthorized` error with `{"error": "Authentication required"}` will be returned.

---

## Endpoints

### 1. Health Check

*   **Endpoint:** `GET /`
*   **Description:** Simple health check to see if the server is running.
*   **Authentication Required:** No
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Content-Type: `text/html`
    *   Body: Plain text string "Flashcard Server is Running!"
*   **Error Responses:** None typically expected.

### 2. User Registration

*   **Endpoint:** `POST /register`
*   **Description:** Registers a new user account and creates their initial flashcard database.
*   **Authentication Required:** No
*   **Request Body:**
    ```json
    {
      "username": "string (1-10 chars)",
      "name": "string (1-40 chars)",
      "password": "string (10-20 chars)"
    }
    ```
*   **Success Response:**
    *   Code: `201 Created`
    *   Body:
        ```json
        {
          "message": "User registered successfully",
          "userId": integer
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: Missing fields or fields don't meet constraints (e.g., `{"error": "Missing required fields"}`, `{"error": "Username must be between 1 and 10 characters"}`).
    *   `409 Conflict`: Username already exists (e.g., `{"error": "Username already exists"}`).
    *   `500 Internal Server Error`: Database error during registration or user DB initialization (e.g., `{"error": "An internal server error occurred"}`, `{"error": "Server error during user setup after registration."}`).

### 3. User Login

*   **Endpoint:** `POST /login`
*   **Description:** Authenticates a user and establishes a session.
*   **Authentication Required:** No
*   **Request Body:**
    ```json
    {
      "username": "string",
      "password": "string"
    }
    ```
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Login successful",
          "user": {
            "userId": integer,
            "username": "string",
            "name": "string"
          }
        }
        ```
    *   *Side Effect:* Sets a session cookie containing user information.
*   **Error Responses:**
    *   `400 Bad Request`: Missing username or password (e.g., `{"error": "Username and password are required"}`).
    *   `401 Unauthorized`: Invalid username or password (e.g., `{"error": "Invalid username or password"}`).
    *   `500 Internal Server Error`: Database error during login process (e.g., `{"error": "An internal server error occurred"}`).

### 4. User Logout

*   **Endpoint:** `POST /logout`
*   **Description:** Clears the user's session information.
*   **Authentication Required:** No (but only meaningful if logged in)
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Logout successful"
        }
        ```
    *   *Side Effect:* Clears the session cookie.
*   **Error Responses:** None typically expected.

### 5. Get Next Review Card

*   **Endpoint:** `GET /review`
*   **Description:** Fetches the next card due for review in the user's currently selected deck.
*   **Authentication Required:** Yes
*   **Request Body:** None
*   **Success Response (Card Found & Due):**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "cardId": integer,
          "front": "string",
          "back": "string",
          "queue": integer
        }
        ```
    *   *Side Effect:* Stores `currentCardId` and `currentNoteId` in the server-side session.
*   **Success Response (No Card Due / Available):**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "string (e.g., 'No cards due for deck X right now.', 'No cards available for review in deck X.')"
        }
        ```
    *   *Side Effect:* Clears `currentCardId` and `currentNoteId` from the server-side session.
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: User's database file does not exist (e.g., `{"error": "User database not found. Please re-register or contact support."}`).
    *   `500 Internal Server Error`: Database error or other server issue reading collection/card data (e.g., `{"error": "Collection configuration or creation time could not be read"}`, `{"error": "Database error occurred: ..."}`).

### 6. Answer Review Card

*   **Endpoint:** `POST /answer`
*   **Description:** Submits the user's answer (ease rating) for the card currently being reviewed (identified via session). Updates card scheduling information.
*   **Authentication Required:** Yes
*   **Request Body:**
    ```json
    {
      "ease": integer (1=Again, 2=Hard, 3=Good, 4=Easy),
      "timeTaken": integer (milliseconds spent viewing card)
    }
    ```
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Answer processed successfully"
        }
        ```
    *   *Side Effect:* Clears `currentCardId` and `currentNoteId` from the server-side session.
*   **Error Responses:**
    *   `400 Bad Request`: Missing/invalid ease rating, or `currentCardId` missing from session (e.g., `{"error": "Invalid ease rating (must be 1, 2, 3, or 4)"}`, `{"error": "Missing card information in session or invalid request..."}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The `currentCardId` from the session doesn't exist in the database (e.g., `{"error": "Card not found"}`).
    *   `500 Internal Server Error`: Database error during card update or logging (e.g., `{"error": "Database error occurred during review update"}`).

### 7. Export Collection

*   **Endpoint:** `GET /export`
*   **Description:** Generates and downloads the user's entire flashcard collection as an Anki `.apkg` file.
*   **Authentication Required:** Yes
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Content-Type: `application/zip`
    *   Body: The binary data of the `.apkg` file.
    *   *Headers:* Includes `Content-Disposition: attachment; filename="<username>_export_<timestamp>.apkg"`
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: User's database file does not exist (e.g., `{"error": "User database not found."}`).
    *   `500 Internal Server Error`: Error during file copying, zipping, or temporary file handling (e.g., `{"error": "Failed to generate export file."}`).

### 8. Add New Card

*   **Endpoint:** `POST /add_card`
*   **Description:** Adds a new flashcard (note and card) to the user's currently selected deck.
*   **Authentication Required:** Yes
*   **Request Body:**
    ```json
    {
      "front": "string",
      "back": "string"
    }
    ```
*   **Success Response:**
    *   Code: `201 Created`
    *   Body:
        ```json
        {
          "message": "Card added successfully",
          "noteId": integer,
          "cardId": integer
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: Front or back content is missing/empty (e.g., `{"error": "Front and back content cannot be empty"}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `500 Internal Server Error`: Database error reading configuration or inserting note/card (e.g., `{"error": "Collection configuration not found or invalid"}`, `{"error": "Database error occurred while adding card"}`).

### 9. Get Decks

*   **Endpoint:** `GET /decks`
*   **Description:** Retrieves a list of all decks belonging to the logged-in user.
*   **Authentication Required:** Yes
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body: Array of deck objects.
        ```json
        [
          { "id": "string", "name": "string" },
          { "id": "string", "name": "string" },
          ...
        ]
        ```
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `500 Internal Server Error`: Database error fetching deck list (e.g., `{"error": "Failed to fetch decks"}`).

### 10. Create Deck

*   **Endpoint:** `POST /decks`
*   **Description:** Creates a new deck for the logged-in user.
*   **Authentication Required:** Yes
*   **Request Body:**
    ```json
    {
      "name": "string"
    }
    ```
*   **Success Response:**
    *   Code: `201 Created`
    *   Body: Details of the newly created deck.
        ```json
        {
          "id": "string",
          "name": "string"
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: Deck name is missing or empty (e.g., `{"error": "Deck name cannot be empty"}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `409 Conflict`: A deck with the same name already exists (case-insensitive) (e.g., `{"error": "A deck with this name already exists"}`).
    *   `500 Internal Server Error`: Database error reading config or creating deck (e.g., `{"error": "Failed to create deck"}`).

### 11. Set Current Deck

*   **Endpoint:** `PUT /decks/current`
*   **Description:** Sets the currently active deck for the logged-in user (used for adding cards and reviewing).
*   **Authentication Required:** Yes
*   **Request Body:**
    ```json
    {
      "deckId": "string_or_integer"
    }
    ```
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Current deck updated successfully"
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: `deckId` is missing from the request body (e.g., `{"error": "Missing deckId"}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The provided `deckId` does not exist in the user's collection (e.g., `{"error": "Invalid deck ID"}`).
    *   `500 Internal Server Error`: Database error reading or updating the collection configuration (e.g., `{"error": "Failed to set current deck"}`).

### 12. Get Deck Statistics

*   **Endpoint:** `GET /decks/<int:deckId>/stats`
*   **Description:** Retrieves the current count of cards in various review states (New, Learning, Relearning, Young, Mature, Suspended, Buried) for a specific deck.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `deckId` (integer): The ID of the deck for which to retrieve statistics.
*   **Query Parameters:** None (The `timeframe` parameter is currently ignored by the backend).
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "counts": {
            "New": integer,
            "Learning": integer,
            "Relearning": integer,
            "Young": integer,
            "Mature": integer,
            "Suspended": integer,
            "Buried": integer
          },
          "total": integer
        }
        ```
        *(Where `total` represents the sum of all counts returned in the `counts` object).*
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified `deckId` does not exist or does not belong to the user (e.g., `{"error": "Deck not found or access denied."}`).
    *   `500 Internal Server Error`: Database error reading collection or card data (e.g., `{"error": "Collection data not found."}`, `{"error": "Database error occurred while fetching statistics."}`).

### 13. Get Card Details

*   **Endpoint:** `GET /cards/<cardId>`
*   **Description:** Retrieves the details of a specific card.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `cardId` (integer): The ID of the card to retrieve.
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "cardId": integer,
          "front": "string",
          "back": "string"
        }
        ```
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified card does not exist or does not belong to the user (e.g., `{"error": "Card not found"}`).
    *   `500 Internal Server Error`: Database error reading card data (e.g., `{"error": "Error fetching card: ..."}`).

### 14. Update Card

*   **Endpoint:** `PUT /cards/<cardId>`
*   **Description:** Updates the content of a specific flashcard.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `cardId` (integer): The ID of the card to update.
*   **Request Body:**
    ```json
    {
      "front": "string",
      "back": "string"
    }
    ```
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "success": true,
          "message": "Card updated successfully"
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: Front or back content is missing/empty (e.g., `{"error": "Front and back fields are required"}`, `{"error": "Front and back fields cannot be empty"}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified card does not exist or does not belong to the user (e.g., `{"error": "Card not found"}`).
    *   `500 Internal Server Error`: Database error updating the card (e.g., `{"error": "Error updating card: ..."}`).

### 15. Get Deck Cards

*   **Endpoint:** `GET /decks/<deckId>/cards`
*   **Description:** Retrieves a paginated list of cards in a specific deck.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `deckId` (integer): The ID of the deck for which to retrieve cards.
*   **Query Parameters:**
    *   `page` (integer, optional): The page number of results to return. Default: 1.
    *   `perPage` (integer, optional): The number of cards per page. Default: 10.
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "deckId": "string",
          "deckName": "string",
          "cards": [
            {
              "cardId": integer,
              "noteId": integer,
              "front": "string",
              "back": "string",
              "modified": integer
            },
            ...
          ],
          "pagination": {
            "total": integer,
            "page": integer,
            "perPage": integer,
            "totalPages": integer
          }
        }
        ```
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified deck does not exist or does not belong to the user (e.g., `{"error": "Deck not found"}`).
    *   `500 Internal Server Error`: Database error fetching deck or card data (e.g., `{"error": "Error fetching cards: ..."}`).

### 16. Delete Card

*   **Endpoint:** `DELETE /cards/<cardId>`
*   **Description:** Deletes a specific flashcard.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `cardId` (integer): The ID of the card to delete.
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "success": true,
          "message": "Card deleted successfully"
        }
        ```
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified card does not exist or does not belong to the user (e.g., `{"error": "Card not found"}`).
    *   `500 Internal Server Error`: Database error deleting the card (e.g., `{"error": "Error deleting card: ..."}`).

### 17. Delete Deck

*   **Endpoint:** `DELETE /decks/<int:deckId>`
*   **Description:** Deletes a specific deck and all its cards.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `deckId` (integer): The ID of the deck to delete.
*   **Request Body:** None
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Deck 'deck_name' and N cards deleted successfully"
        }
        ```
*   **Error Responses:**
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified deck does not exist or does not belong to the user (e.g., `{"error": "Deck not found"}`).
    *   `500 Internal Server Error`: Database error deleting the deck (e.g., `{"error": "Failed to delete deck due to database error"}`, `{"error": "Failed to delete deck"}`).

### 18. Rename Deck

*   **Endpoint:** `PUT /decks/<int:deckId>/rename`
*   **Description:** Renames a specific deck.
*   **Authentication Required:** Yes
*   **Path Parameters:**
    *   `deckId` (integer): The ID of the deck to rename.
*   **Request Body:**
    ```json
    {
      "name": "string"
    }
    ```
*   **Success Response:**
    *   Code: `200 OK`
    *   Body:
        ```json
        {
          "message": "Deck renamed from 'old_name' to 'new_name' successfully",
          "id": integer,
          "name": "string"
        }
        ```
*   **Error Responses:**
    *   `400 Bad Request`: New deck name is missing or empty (e.g., `{"error": "New deck name cannot be empty"}`).
    *   `401 Unauthorized`: (See Authentication section).
    *   `404 Not Found`: The specified deck does not exist or does not belong to the user (e.g., `{"error": "Deck not found"}`).
    *   `409 Conflict`: A deck with the same name already exists (case-insensitive) (e.g., `{"error": "A deck with this name already exists"}`).
    *   `500 Internal Server Error`: Database error renaming the deck (e.g., `{"error": "Failed to rename deck due to database error"}`, `{"error": "Failed to rename deck"}`).