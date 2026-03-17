#!/usr/bin/env python3
"""Reset daveed password. Run with FLASK_ENV=production or FLASK_ENV=development.
Usage: FLASK_ENV=production python reset-password.py
       FLASK_ENV=development python reset-password.py
"""

from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import User

with app.app_context():
    user = User.query.filter_by(username='daveed').first()
    if user:
        user.password_hash = generate_password_hash('admin123')
        db.session.commit()
        print("✓ Password reset for daveed")
    else:
        print("⚠ User 'daveed' not found")
print("Username: daveed")
print("Password: admin123")
