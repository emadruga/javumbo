# Admin Database Schema (admin.db)

This document describes the schema for the `admin.db` SQLite database used for user authentication and management.

## `users` Table

Stores information about registered users.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique identifier for the user
    username TEXT UNIQUE NOT NULL,             -- User's chosen username (must be unique)
    name TEXT NOT NULL,                        -- User's real name or display name
    password_hash TEXT NOT NULL                -- Hashed password for security
);
```

**Columns:**

*   `user_id`: INTEGER (Primary Key, Auto Increment) - A unique numerical ID automatically assigned to each new user.
*   `username`: TEXT (Unique, Not Null) - The username chosen by the user for login. It must be unique across all users.
*   `name`: TEXT (Not Null) - The display name or real name provided by the user.
*   `password_hash`: TEXT (Not Null) - The user's password, securely hashed using a suitable algorithm (e.g., bcrypt). Never store plain text passwords. 