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

# Install dependencies (if not done already, e.g., during development)
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

---

This guide provides a solid foundation. Depending on your specific needs, you might need further configuration for database backups, more advanced logging, security hardening, etc. 