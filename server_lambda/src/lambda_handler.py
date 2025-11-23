"""
AWS Lambda Handler for Javumbo Flask App

Uses apig-wsgi to wrap Flask WSGI app for API Gateway v2 (HTTP API).
"""

import sys
import os

# Add current directory to path (for imports)
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app
from app import app

# Import apig-wsgi (proper WSGI adapter for API Gateway)
from apig_wsgi import make_lambda_handler

# Wrap Flask app for Lambda
handler = make_lambda_handler(app)
