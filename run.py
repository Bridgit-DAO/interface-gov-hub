#!/usr/bin/env python3
"""
MLGH Data Viewer - Entry point.

Runs the Flask app. Use: python run.py
"""
from config import BUILD_NUMBER, ENV, PORT, DEBUG, DB_PATH, DEPLOYMENT_MODE

from app import app
from extensions import db
from database import init_db
from deployment import init_deployment_safety

if __name__ == '__main__':
    init_deployment_safety(db, DEPLOYMENT_MODE)
    init_db(app)
    print(f"🚀 Starting MLGH Datatracker - BUILD {BUILD_NUMBER}")
    print(f"Environment: {ENV} mode on port {PORT}")
    print(f"Database: {DB_PATH}")
    use_reloader = DEBUG and not __import__('os').environ.get('INVOCATION_ID')
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG, use_reloader=use_reloader)
