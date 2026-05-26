#!/usr/bin/env python3
"""Reset a user's password to a random strong value (CLI only).

Usage:
  FLASK_ENV=development python reset-password.py [username]
  FLASK_ENV=production python reset-password.py [username]

Prints the new password once to stdout — store it securely; it is not saved elsewhere.
"""

import secrets
import sys

from werkzeug.security import generate_password_hash

from app import app
from extensions import db
from models import User

username = (sys.argv[1] if len(sys.argv) > 1 else 'daveed').strip()
new_password = secrets.token_urlsafe(24)

with app.app_context():
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"⚠ User {username!r} not found")
        sys.exit(1)

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    print(f"✓ Password reset for {username}")
    print(f"Username: {username}")
    print(f"New password: {new_password}")
    print("Store this password securely; it will not be shown again.")
