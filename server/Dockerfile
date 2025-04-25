# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed (e.g., for bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code into the container
COPY . .

# Ensure the user_dbs directory exists (though volume mount might create it)
RUN mkdir -p user_dbs

# Make port 8000 available to the world outside this container (for Nginx proxy)
EXPOSE 8000

# Define environment variable for Flask (optional, can be set in docker-compose)
# ENV FLASK_APP=app.py
# ENV FLASK_RUN_HOST=0.0.0.0

# Command to run the application using Gunicorn
# Bind to 0.0.0.0 to allow connections from other containers (like Nginx)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "app:app"] 