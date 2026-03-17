"""Identity services: get_current_user, require_auth, require_role, referral codes."""
import hashlib
import time

from flask import session, flash, redirect, url_for

from extensions import db
from models import User


def generate_referral_code(username):
    """Generate a unique referral code for a user."""
    raw = f"{username}-{time.time()}"
    hash_obj = hashlib.md5(raw.encode())
    return hash_obj.hexdigest()[:8].upper()


def get_or_create_referral_code(user):
    """Get user's referral code or create one if it doesn't exist."""
    if not user.referral_code:
        user.referral_code = generate_referral_code(user.username)
        db.session.commit()
    return user.referral_code


def get_current_user():
    """Get current logged in user from session."""
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        if user:
            user_name = user.name or user.displayName or user.oauthName or user.username
            return {
                'id': user.id,
                'username': user.username,
                'name': user_name,
                'email': user.email,
                'role': user.role,
                'theme': user.theme,
                'displayName': user.displayName,
                'oauthName': user.oauthName,
                'profileImage': user.profileImage,
                'typeOfLogin': user.typeOfLogin,
                'evmAddress': user.evmAddress,
                'solanaAddress': user.solanaAddress,
            }
    return None


def require_auth(f):
    """Decorator to require authentication."""
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


def require_role(required_role):
    """Decorator to require a specific role (admin or editor for admin features)."""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('auth.login'))
            current_user = get_current_user()
            if not current_user:
                return "Access denied: Not logged in", 403
            user_role = current_user.get('role', 'user')
            if required_role == 'admin':
                if user_role not in ['admin', 'editor']:
                    return "Access denied: Admin or Editor role required", 403
            elif user_role != required_role:
                return f"Access denied: {required_role} role required", 403
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator
