# Production Deployment Guide (Ubuntu 22.04)

This guide outlines the steps to deploy the React frontend and Flask backend of the Flashcard application to a production Ubuntu 22.04 server.

**Assumptions:**

*   You have root or sudo access to an Ubuntu 22.04 server.
*   You have a domain name pointing to your server's IP address (optional but recommended, especially for SSL).
*   Git is installed (`sudo apt update && sudo apt install git`).
*   Node.js and npm are installed for building the client (e.g., via NodeSource: `curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs`).

## 1. Prerequisites

Update package lists and install necessary system packages:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx python3-dev build-essential
```

## 2. Clone the Repository

Clone the project code onto your server:

```bash
# Replace with your repository URL if different
git clone https://github.com/your-username/flashcard-app-v5-anki-gemini.git
cd flashcard-app-v5-anki-gemini
```

## 3. Backend (Flask) Deployment

We will use `venv` for managing Python dependencies and `gunicorn` as the WSGI server.

### 3.1. Setup Python Virtual Environment

```bash
# Navigate to the server directory
cd server

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Ensure pip is up-to-date
pip install --upgrade pip
```

### 3.2. Install Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt
# requirements.txt should include:
# Flask
# Flask-Cors
# gunicorn
# bcrypt
# python-dotenv (optional, for managing environment variables)
# ... any other specific dependencies used ...

# If requirements.txt doesn't exist or is incomplete, install manually:
# pip install Flask Flask-Cors gunicorn bcrypt python-dotenv
```

*(Note: Ensure `requirements.txt` exists in the `server` directory and lists all necessary packages, including `gunicorn`.)*

### 3.3. Configure Environment Variables

Flask needs a `SECRET_KEY`. It's best practice to set this via environment variables rather than hardcoding it.

Create a `.env` file in the `server` directory:

```plaintext
# server/.env
SECRET_KEY='your_strong_random_secret_key_here'
# Add other environment variables if needed (e.g., DATABASE_URL if configured)
# Base path as defined in the reverse proxy (nginx)
VITE_APP_BASE_PATH=/javumbo/
```

Generate a strong secret key (e.g., using `python -c 'import secrets; print(secrets.token_hex(24))'`).

Modify `server/app.py` slightly to load this if using `python-dotenv`:

```python
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
# ... rest of the app ...
```

*(Alternatively, set environment variables directly in the systemd service file.)*

### 3.4. Initialize Database

Run the initialization for the admin database if needed (Gunicorn won't run the `if __name__ == '__main__'` block). You might need a separate script or command. If `init_admin_db()` is idempotent (safe to run multiple times), you could call it explicitly once:

```bash
# Make sure venv is active
source venv/bin/activate
# Run this command once from the server directory
python -c 'from app import init_admin_db; init_admin_db()'
```

### 3.5. Test Gunicorn

Ensure Gunicorn can serve the app. From the `server` directory (with `venv` active):

```bash
# Make sure venv is active
source venv/bin/activate
# Test run (replace 'app:app' if your Flask instance variable or filename is different)
# This binds to localhost:8000
gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
```

Press `CTRL+C` to stop. Ensure no errors appear.

### 3.6. Create Gunicorn Systemd Service

Create a systemd service file to manage the Gunicorn process:

```bash
sudo nano /etc/systemd/system/flashcard-app.service
```

Paste the following content, adjusting paths and usernames as necessary:

```ini
[Unit]
Description=Gunicorn instance to serve Flashcard App backend
After=network.target

[Service]
# Replace 'your_user' with the actual username running the app
User=your_user
Group=www-data # Or the user's group if preferred

# Adjust WorkingDirectory to the absolute path of the 'server' directory
WorkingDirectory=/path/to/flashcard-app-v5-anki-gemini/server
# Adjust Environment path if needed, or set variables directly
# Environment="PATH=/path/to/flashcard-app-v5-anki-gemini/server/venv/bin"
# Environment="SECRET_KEY=your_strong_random_secret_key_here" # Alternative to .env

# Command to execute
# Make sure the path to gunicorn (within the venv) and app:app are correct
ExecStart=/path/to/flashcard-app-v5-anki-gemini/server/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app

Restart=always

[Install]
WantedBy=multi-user.target
```

*   Replace `/path/to/flashcard-app-v5-anki-gemini/server` with the actual absolute path.
*   Replace `your_user` with the Linux user you want to run the process as.
*   Ensure the `User` has appropriate permissions for the project directory, especially the database files and `user_dbs` directory.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable flashcard-app.service
sudo systemctl start flashcard-app.service
sudo systemctl status flashcard-app.service # Check for errors
```

## 4. Frontend (React) Deployment

### 4.1. Build the Client

Navigate to the client directory and build the production assets:

```bash
# Navigate to the client directory
cd ../client # Assuming you are in the server directory

# Install dependencies (including React, Router, Axios, Chart.js, etc.)
npm install

# Create the production build
npm run build
```

This will create an optimized build in the `client/dist` directory.

## 5. Configure Nginx as Reverse Proxy

Nginx will serve the static React files and forward API requests to the Gunicorn backend.

### 5.1. Create Nginx Server Block

Create a new Nginx configuration file for your site:

```bash
sudo nano /etc/nginx/sites-available/flashcard-app
```

Paste the following configuration, adjusting `server_name` and paths:

```nginx
server {
    listen 80;
    # Replace with your domain name or server IP address
    server_name your_domain.com www.your_domain.com;

    # Root directory for React build files
    root /path/to/flashcard-app-v5-anki-gemini/client/dist;
    index index.html;

    location / {
        # Try to serve file directly, fallback to index.html for React Router
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to the Gunicorn backend
    # Match all API paths used by the frontend
    location ~ ^/(login|logout|register|decks|review|answer|export|add_card|cards) {
        proxy_pass http://127.0.0.1:8000; # Match Gunicorn bind address
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Optional: Add locations for specific static assets if needed,
    # although the root directive usually handles this.
    # location ~* \.(css|js|png|jpg|jpeg|gif|ico)$ {
    #     expires 1d;
    #     add_header Cache-Control "public";
    # }
}
```

*   Replace `your_domain.com www.your_domain.com` with your actual domain or server IP.
*   Replace `/path/to/flashcard-app-v5-anki-gemini/client/dist` with the absolute path to the client build directory.
*   The `location ~ ^/(login|...` block lists the API endpoint prefixes. Ensure all backend routes called by the client are included here. Adjust if your API uses a base path like `/api`.

### 5.2. Enable Site and Test Configuration

Create a symbolic link to enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/flashcard-app /etc/nginx/sites-enabled/
```

*(Optional but recommended: Remove the default Nginx site if it conflicts)*
```bash
# sudo rm /etc/nginx/sites-enabled/default
```

Test the Nginx configuration:

```bash
sudo nginx -t
```

If the test is successful, restart Nginx:

```bash
sudo systemctl restart nginx
```

## 6. Configure Firewall

Allow HTTP (and HTTPS if setting up SSL) traffic through the firewall:

```bash
sudo ufw allow 'Nginx Full' # Allows both HTTP (80) and HTTPS (443)
# If only using HTTP: sudo ufw allow 'Nginx HTTP'
sudo ufw enable # If firewall is not already active
sudo ufw status
```

## 7. (Recommended) Setup SSL/TLS with Certbot

For a production site, HTTPS is essential. Use Certbot to obtain and manage free SSL certificates from Let's Encrypt.

```bash
# Install Certbot and its Nginx plugin
sudo apt install certbot python3-certbot-nginx -y

# Obtain and install the certificate (follow prompts)
# Replace your_domain.com with your actual domain
sudo certbot --nginx -d your_domain.com -d www.your_domain.com
```

Certbot will automatically modify your Nginx configuration for HTTPS and set up automatic renewal.

## 8. Final Checks

*   Visit your domain/IP address in a browser. You should see the React application.
*   Try registering, logging in, creating/selecting decks, adding cards, and reviewing cards.
*   Check Nginx logs (`/var/log/nginx/access.log`, `/var/log/nginx/error.log`) and the Gunicorn service logs (`sudo journalctl -u flashcard-app.service`) for any errors.

## 6. Docker Deployment (Alternative)

This section provides an alternative deployment method using Docker and Docker Compose.

**Assumptions:**

*   Docker and Docker Compose are installed on the host machine (`sudo apt install docker.io docker-compose-v2`).
*   The user running Docker commands belongs to the `docker` group (`sudo usermod -aG docker $USER`, then log out/in) or uses `sudo`.
*   You have cloned the repository locally.
*   A `server/.env` file exists containing at least the `SECRET_KEY`.
*   An up-to-date `server/requirements.txt` file exists, including `gunicorn`.

### 6.1. Dockerfile Setup

This deployment uses three key files for container definition:

1.  **`client/Dockerfile`:** Defines a multi-stage build process for the React client. It first builds the static assets using Node.js and then copies these assets into a lightweight Nginx image for serving.
2.  **`server/Dockerfile`:** Defines the environment for the Flask backend. It installs Python, copies the application code, installs dependencies from `requirements.txt`, and sets up Gunicorn as the WSGI server.
3.  **`client/nginx.conf`:** This configuration file is used by the Nginx server within the `client` container. It tells Nginx how to serve the built React files and how to reverse proxy API requests (like `/login`, `/review`, etc.) to the `server` container.

*(These files should exist in your repository if generated previously. Refer to their contents for details.)*

### 6.2. Docker Compose Configuration

The `docker-compose.yml` file orchestrates the building and running of the containers:

```yaml
# docker-compose.yml (Project Root)
version: '3.8'

services:
  server:
    build:
      context: ./server
      dockerfile: Dockerfile
    container_name: flashcard_server
    volumes:
      # Mount the server code directory from host into the container at /app
      # This allows the container to run the code AND provides host access
      # to the code, admin.db, and user_dbs/ directory.
      - ./server:/app
    env_file:
      # Load environment variables (like SECRET_KEY) from this file
      - ./server/.env
    expose:
      # Expose port 8000 internally for Nginx, but not to the host
      - "8000"
    restart: unless-stopped
    networks:
      - flashcard-net

  client:
    build:
      context: ./client
      dockerfile: Dockerfile
    container_name: flashcard_client
    ports:
      # Map host port 80 to container port 80 (Nginx)
      - "80:80"
      # If using SSL/HTTPS, you might map 443 instead and configure Nginx for SSL.
      # - "443:80"
    depends_on:
      - server # Ensure server starts before client
    restart: unless-stopped
    networks:
      - flashcard-net

networks:
  flashcard-net:
    driver: bridge
```

**Key Points:**

*   **`server` service:** Builds from `server/Dockerfile`, names the container, mounts the *entire* `./server` directory from the host to `/app` inside the container, loads environment variables from `server/.env`, and exposes port 8000 internally on the `flashcard-net` network.
*   **`client` service:** Builds from `client/Dockerfile`, names the container, maps port 80 on the host to port 80 (Nginx) in the container, and depends on the `server` service.
*   **Volumes (`./server:/app`):** This is the crucial part for host access. Because the entire `./server` directory is mounted into the container's `/app` directory:
    *   The Python code (`/app/app.py`) is accessible to the container.
    *   The admin database (`/app/admin.db`) is directly using the `./server/admin.db` file from the host.
    *   The user databases directory (`/app/user_dbs/`) is directly using the `./server/user_dbs/` directory from the host.
    *   Any changes made *inside* the container to files within `/app` (like database writes) are reflected immediately on the host, and vice-versa (though changing code might require a container restart unless using Flask's debug mode, which is NOT recommended for production).
*   **SQLite Container:** Note that there is no separate SQLite container. SQLite works directly with database files, which are made available to the `server` container via the volume mount.

### 6.3. Building and Running

1.  **Navigate:** Open your terminal in the project root directory (`flashcard-app-v5-anki-gemini`) where `docker-compose.yml` is located.
2.  **Ensure Prerequisites:**
    *   Confirm `server/requirements.txt` is up-to-date.
    *   Confirm `server/.env` exists and contains `SECRET_KEY=your_actual_secret_key`.
    *   If `admin.db` doesn't exist, you might need to initialize it once. The application *should* create it on first run/login attempt due to `init_admin_db()` calls, but manual creation might be needed depending on permissions.
3.  **Build Images:**
    ```bash
    docker compose build
    ```
4.  **Start Services:**
    ```bash
    # Start in detached mode (runs in background)
    docker compose up -d
    ```
5.  **Verify:**
    *   Check running containers: `docker compose ps`
    *   View logs: `docker compose logs -f` (or `docker compose logs server`, `docker compose logs client`)
    *   Access the application in your browser via the host's IP address or domain name (on port 80).

### 6.4. Stopping

```bash
docker compose down
```

This stops and removes the containers but leaves the volumes (database files and code on the host) intact.

### 6.5. Production Considerations

*   **Permissions:** The host directory `./server` (and its contents like `admin.db`, `user_dbs`) must be readable and writable by the user ID that the `server` container process runs as (defined in `server/Dockerfile` or default). Docker volumes can sometimes have permission issues; ensure the host directory permissions are compatible.
*   **SSL/HTTPS:** The provided `client/nginx.conf` uses HTTP (port 80). For production, you should enable HTTPS. Common methods include:
    *   Using a separate Nginx instance on the *host* as a primary reverse proxy that handles SSL termination and proxies requests to `localhost:80` (where the `client` container is mapped).
    *   Integrating Certbot directly into the `client` container's Nginx setup (more complex, requires volume mounts for certificates).
*   **Database Backups:** Since the database files reside directly on the host filesystem (`./server/admin.db`, `./server/user_dbs/`), standard filesystem backup procedures should be used to back them up regularly.
*   **Resource Limits:** Configure resource limits (CPU, memory) for your containers in the `docker-compose.yml` file if necessary.

### 6.6 Docker References

For further details on Docker and Docker Compose:

*   **Docker Overview:** [https://docs.docker.com/get-started/overview/](https://docs.docker.com/get-started/overview/)
*   **Docker Compose Overview:** [https://docs.docker.com/compose/](https://docs.docker.com/compose/)
*   **Dockerfile Reference:** [https://docs.docker.com/engine/reference/builder/](https://docs.docker.com/engine/reference/builder/)
*   **Docker Compose File Reference:** [https://docs.docker.com/compose/compose-file/](https://docs.docker.com/compose/compose-file/)
*   **Dockerizing Python Applications:** [https://docs.docker.com/language/python/](https://docs.docker.com/language/python/)
*   **Nginx Docker Image:** [https://hub.docker.com/_/nginx](https://hub.docker.com/_/nginx)
*   **Node.js Docker Image:** [https://hub.docker.com/_/node](https://hub.docker.com/_/node)

---

This guide provides a solid foundation. Depending on your specific needs, you might need further configuration for database backups, more advanced logging, security hardening, etc.

# Production Deployment Notes

This document outlines key considerations and steps for deploying the application to a production environment, especially when running behind a reverse proxy with a subpath.

## 7. Managing Development vs. Production Configuration

To handle differences between local development and production deployment (particularly when deploying to a subpath like `/javumbo/` behind a reverse proxy), we use environment variables managed by Vite. This avoids manual code changes for deployment.

### Strategy: `.env` Files

We utilize `.env` files in the root of the `/client` directory:

*   **`.env.development`**: Settings used when running `npm run dev`.
*   **`.env.production`**: Settings used when running `npm run build`.
*   **`.env`**: (Optional) Default settings overridden by the specific environment files.

**Important**: Variables exposed to the client-side browser code **must** be prefixed with `VITE_`.

### Example `.env` Files

**`/client/.env.development`**:
```dotenv
# Development settings (running locally, no subpath)
VITE_APP_BASE_PATH=/
# Point directly to the local Flask/Gunicorn dev server
VITE_API_BASE_URL=http://localhost:8000
```

**`/client/.env.production`**:
```dotenv
# Production settings (deployed under /javumbo/)
VITE_APP_BASE_PATH=/javumbo/
# API calls go through the reverse proxy, relative to the base path
# Use '/javumbo' if Axios baseURL needs it, or '' if using root-relative paths like '/register'.
VITE_API_BASE_URL=/javumbo
```

### Configuration Points Modified by Environment Variables

1.  **Vite Build Base Path (`client/vite.config.js`)**

    The `base` option in `vite.config.js` tells Vite the public path where assets will be served from. This needs to match the subpath in production. It reads from `process.env`.

    ```javascript
    // vite.config.js
    import { defineConfig } from 'vite';
    import react from '@vitejs/plugin-react';

    export default defineConfig(({ mode }) => {
      // Vite loads .env variables into process.env based on mode
      const appBasePath = process.env.VITE_APP_BASE_PATH || '/';

      return {
        plugins: [react()],
        // Use the environment variable for the base path
        base: appBasePath,
      };
    });
    ```

2.  **React Router Base Name (`client/src/main.jsx`)**

    The `<BrowserRouter>` needs its `basename` prop set to the application's subpath so routing works correctly. It reads from `import.meta.env`.

    ```javascript
    // src/main.jsx
    import React from 'react';
    import ReactDOM from 'react-dom/client';
    import { BrowserRouter } from 'react-router-dom';
    import App from './App';
    import './index.css';

    // Access the environment variable (exposed via import.meta.env)
    const appBasePath = import.meta.env.VITE_APP_BASE_PATH || '/';

    ReactDOM.createRoot(document.getElementById('root')).render(
      <React.StrictMode>
        <BrowserRouter basename={appBasePath}>
          <App />
        </BrowserRouter>
      </React.StrictMode>
    );
    ```

3.  **API Base URL (`client/src/api/axiosConfig.js`)**

    Axios needs to know where to send API requests. In development, it might be `http://localhost:8000`; in production, requests should typically be relative to the application's origin so they go through the reverse proxy. It reads from `import.meta.env`.

    ```javascript
    // src/api/axiosConfig.js
    import axios from 'axios';

    // Access the environment variable
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';

    const api = axios.create({
      // Use the environment variable for the baseURL
      baseURL: apiBaseUrl,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
    });

    // ... rest of Axios config ...

    export default api;
    ```

### Workflow Summary

*   Develop locally using `npm run dev`. `.env.development` settings are used.
*   When ready for deployment, run `npm run build`. `.env.production` settings are automatically used to create the production-ready bundles in the `dist` directory with the correct base paths and API URLs embedded.
*   Deploy the contents of the `client/dist` directory to the upstream server (`10.x.y.z` in the example) to be served by its Nginx instance.
*   Ensure the main reverse proxy (`example.com`) correctly forwards requests for the production subpath (e.g., `/javumbo/`) to the upstream server. 