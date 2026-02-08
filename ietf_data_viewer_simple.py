#!/usr/bin/env python3
"""
MLTF Data Viewer - Shows the MLTF datatracker data from test files
This displays the Meta-Layer Task Force data so you can see it working.

⚠️ CRITICAL: THIS IS THE MLTF VERSION - DO NOT REVERT TO IETF ⚠️
If you see "IETF Data Viewer" in the docstring, this file has been reverted incorrectly.
The correct version should say "MLTF Data Viewer" and "Meta-Layer Task Force".

BUILD: 1
Last Updated: 2026-01-23 (Ordinals integration with markdown detection)
"""

# Build number for cache busting and version tracking
BUILD_NUMBER = 52

from flask import Flask, render_template_string, request, redirect, url_for, flash, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import re
import json
import uuid
import requests
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
import time

# Import file processing libraries
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

try:
    import markdown2
    import bleach
    MARKDOWN_SUPPORT = True
except ImportError:
    MARKDOWN_SUPPORT = False

# Rate limiting for security
rate_limit_store = defaultdict(list)

def check_rate_limit(identifier, max_requests=5, window_seconds=300):
    """Simple in-memory rate limiting"""
    now = time.time()
    key = f"{identifier}"

    # Clean old entries
    rate_limit_store[key] = [timestamp for timestamp in rate_limit_store[key]
                           if now - timestamp < window_seconds]

    # Check if under limit
    if len(rate_limit_store[key]) >= max_requests:
        return False

    # Add current request
    rate_limit_store[key].append(now)
    return True

# Database initialization
def init_db():
    """Initialize database and create tables"""
    with app.app_context():
        db.create_all()

        # Run database migrations for ordinals support
        migrate_ordinals_support()

        # Migrate hardcoded users to database if not already done
        if User.query.count() == 0:
            migrate_hardcoded_users()

        # Load published drafts from database into memory
        published_drafts = PublishedDraft.query.all()
        for draft in published_drafts:
            draft_entry = {
                'name': draft.name,
                'title': draft.title,
                'authors': draft.authors,
                'group': draft.group,
                'status': draft.status,
                'rev': draft.rev,
                'pages': draft.pages,
                'words': draft.words,
                'date': draft.date,
                'abstract': draft.abstract,
                'stream': draft.stream
            }
            DRAFTS.append(draft_entry)

        print(f"Database initialized: {User.query.count()} users, {len(published_drafts)} published drafts loaded")

def migrate_ordinals_support():
    """Add ordinals support columns to existing submission table"""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if ordinals columns exist
        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]
        
        ordinals_columns = {
            'sourceType': ('TEXT', 'file'),
            'ordinalId': ('TEXT', None),
            'ordinalContentUrl': ('TEXT', None),
            'ordinalContentType': ('TEXT', None),
            'inscriptionNumber': ('INTEGER', None),
            'blockHeight': ('INTEGER', None),
            'inscriptionTimestamp': ('DATETIME', None),
            'doc_type': ('TEXT', 'draft')
        }
        
        added_columns = []
        for col_name, (col_type, default_value) in ordinals_columns.items():
            if col_name not in columns:
                if default_value:
                    cursor.execute(f"ALTER TABLE submission ADD COLUMN {col_name} {col_type} DEFAULT '{default_value}'")
                else:
                    cursor.execute(f"ALTER TABLE submission ADD COLUMN {col_name} {col_type}")
                added_columns.append(col_name)
        
        # Migrate existing ML numbers to new format (ML-001 -> ML-Draft-001)
        cursor.execute("SELECT id, ml_number FROM submission WHERE ml_number IS NOT NULL")
        submissions = cursor.fetchall()
        migrated_count = 0
        for sub_id, ml_num in submissions:
            if ml_num and not ml_num.startswith('ML-Draft-') and not ml_num.startswith('ML-RFC-'):
                # Old format: ML-001, ML-002, etc.
                # Extract number and convert to ML-Draft-XXX
                try:
                    num_part = ml_num.split('-')[-1]
                    new_ml_num = f"ML-Draft-{num_part}"
                    cursor.execute("UPDATE submission SET ml_number = ? WHERE id = ?", (new_ml_num, sub_id))
                    migrated_count += 1
                except (ValueError, IndexError):
                    pass
        
        conn.commit()
        conn.close()
        
        if added_columns:
            print(f"✅ Added columns to submission table: {', '.join(added_columns)}")
        else:
            print("✅ All columns already exist in submission table")
        
        if migrated_count > 0:
            print(f"✅ Migrated {migrated_count} ML numbers to new format (ML-Draft-XXX)")
    except Exception as e:
        print(f"⚠️  Error migrating ordinals support: {e}")
        # Non-fatal - table might already have columns

def migrate_hardcoded_users():
    """Migrate hardcoded users to database"""
    hardcoded_users = {
        'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@metalayer.org', 'role': 'admin', 'theme': 'dark'},
        'daveed': {'password': 'admin123', 'name': 'Daveed', 'email': 'daveed@bridgit.io', 'role': 'admin', 'theme': 'dark'},
        'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor', 'theme': 'dark'},
        'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user', 'theme': 'dark'},
        'shiftshapr': {'password': 'mynewpassword123', 'name': 'Shift Shapr', 'email': 'shiftshapr@example.com', 'role': 'editor', 'theme': 'dark'}
    }

    for username, user_data in hardcoded_users.items():
        if not User.query.filter_by(username=username).first():
            user = User(
                username=username,
                password_hash=generate_password_hash(user_data['password']),
                name=user_data['name'],
                email=user_data['email'],
                role=user_data.get('role', 'user'),
                theme=user_data.get('theme', 'dark')
            )
            db.session.add(user)

    db.session.commit()
    print(f"Migrated {len(hardcoded_users)} hardcoded users to database")

# Environment configuration
ENV = os.environ.get('FLASK_ENV', 'production').lower()
IS_PRODUCTION = ENV == 'production'
IS_DEVELOPMENT = ENV == 'development'

# Set up paths based on environment
if IS_DEVELOPMENT:
    INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance_dev')
    DB_NAME = 'datatracker_dev.db'
    PORT = int(os.environ.get('FLASK_PORT', 8001))
    DEBUG = True
else:
    INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    DB_NAME = 'datatracker.db'
    PORT = int(os.environ.get('FLASK_PORT', 8000))
    DEBUG = False

# DEPLOYMENT SAFETY - Block data modifications during deployment
deployment_flag_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".deployment_{'dev' if IS_DEVELOPMENT else 'prod'}")
DEPLOYMENT_MODE = os.path.exists(deployment_flag_file)
if DEPLOYMENT_MODE:
    print("🚨 DEPLOYMENT MODE ENABLED - Data modifications blocked")

def check_deployment_safety(operation="database operation"):
    """Check if operations are allowed during deployment"""
    if DEPLOYMENT_MODE:
        error_msg = f"🚨 BLOCKED: {operation} not allowed during deployment"
        print(error_msg)
        raise RuntimeError(error_msg)

def init_deployment_safety():
    """Initialize deployment safety checks after database is set up"""
    if DEPLOYMENT_MODE:
        # Override SQLAlchemy session methods to check deployment safety
        global original_add, original_commit, original_delete, original_create_all
        original_add = db.session.add
        original_commit = db.session.commit
        original_delete = db.session.delete
        original_create_all = db.create_all

        def safe_add(instance):
            check_deployment_safety("database add operation")
            return original_add(instance)

        def safe_commit():
            check_deployment_safety("database commit operation")
            return original_commit()

        def safe_delete(instance):
            check_deployment_safety("database delete operation")
            return original_delete(instance)

        def safe_create_all(*args, **kwargs):
            check_deployment_safety("database schema creation")
            return original_create_all(*args, **kwargs)

        # Monkey patch the session and DDL methods
        db.session.add = safe_add
        db.session.commit = safe_commit
        db.session.delete = safe_delete
        db.create_all = safe_create_all
        print("🚨 Database operations blocked during deployment")

# Ensure instance directory exists
os.makedirs(INSTANCE_DIR, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')  # For flash messages

# Database setup
DB_PATH = os.path.join(INSTANCE_DIR, DB_NAME)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = DEBUG

# Session security configuration
app.config['SESSION_COOKIE_SECURE'] = not IS_DEVELOPMENT  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS access to session cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

db = SQLAlchemy(app)

# Database Models
class Submission(db.Model):
    id = db.Column(db.String(8), primary_key=True)
    title = db.Column(db.String(255))
    authors = db.Column(db.JSON)  # List of author dicts
    abstract = db.Column(db.Text)
    group = db.Column(db.String(50))
    filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    draft_name = db.Column(db.String(255))
    status = db.Column(db.String(20), default='submitted')  # submitted, approved, rejected
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_by = db.Column(db.String(100), default='Anonymous User')
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    ml_number = db.Column(db.String(20), nullable=True)  # ML-Draft-001, ML-RFC-001, etc.
    doc_type = db.Column(db.String(10), default='draft')  # 'draft' or 'rfc'
    pages = db.Column(db.Integer, default=1)  # Calculated page count
    words = db.Column(db.Integer, default=0)  # Calculated word count
    # Ordinal integration fields
    sourceType = db.Column(db.String(20), default='file')  # 'file' or 'ordinal'
    ordinalId = db.Column(db.String(255), nullable=True)  # Inscription ID
    ordinalContentUrl = db.Column(db.String(500), nullable=True)  # URL to content
    ordinalContentType = db.Column(db.String(100), nullable=True)  # MIME type
    inscriptionNumber = db.Column(db.Integer, nullable=True)  # Ordinal inscription number
    blockHeight = db.Column(db.Integer, nullable=True)  # Bitcoin block height
    inscriptionTimestamp = db.Column(db.DateTime, nullable=True)  # When inscribed
    # Revision fields
    parent_draft_name = db.Column(db.String(255), nullable=True)  # Link to parent draft for revisions
    revision_number = db.Column(db.String(10), nullable=True)  # e.g., "01", "02"
    what_changed = db.Column(db.Text, nullable=True)  # Description of changes in this revision
    is_revision = db.Column(db.Boolean, default=False)  # Flag to indicate this is a revision

class PublishedDraft(db.Model):
    """Store published/approved drafts separately from original test data"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, index=True)
    title = db.Column(db.String(255))
    authors = db.Column(db.JSON)
    group = db.Column(db.String(50))
    status = db.Column(db.String(20), default='active')
    rev = db.Column(db.String(5), default='00')
    pages = db.Column(db.Integer, default=1)
    words = db.Column(db.Integer, default=0)
    date = db.Column(db.String(10))  # YYYY-MM-DD
    abstract = db.Column(db.Text)
    stream = db.Column(db.String(20), default='mltf')
    submission_id = db.Column(db.String(8), db.ForeignKey('submission.id'), nullable=True)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draft_name = db.Column(db.String(255), index=True)
    text = db.Column(db.Text)
    author = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    original_text = db.Column(db.Text, nullable=True)  # Store original text for edit history

    # Relationship for replies
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)

class DocumentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    draft_name = db.Column(db.String(255), index=True)
    action = db.Column(db.String(50))
    user = db.Column(db.String(100))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class WorkingGroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_acronym = db.Column(db.String(50), index=True)
    user_name = db.Column(db.String(100), index=True)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, index=True)
    password_hash = db.Column(db.String(255))

    # Web3Auth fields
    web3authVerifierId = db.Column(db.String(255), unique=True, index=True)  # Web3Auth unique identifier
    typeOfLogin = db.Column(db.String(50))  # 'google', 'wallet', 'twitter', 'email_passwordless'

    # Display name system (user-editable)
    displayName = db.Column(db.String(50))  # User's chosen display name
    displayNameSetAt = db.Column(db.DateTime)  # When user first set/changed it

    # OAuth data (read-only reference)
    oauthName = db.Column(db.String(100))  # Original name from OAuth provider
    name = db.Column(db.String(100))  # Legacy field - will be deprecated
    email = db.Column(db.String(100), unique=True, index=True)
    profileImage = db.Column(db.String(500))  # Avatar URL

    # Wallet data (always visible)
    evmAddress = db.Column(db.String(42), unique=True, index=True)  # EVM wallet address
    solanaAddress = db.Column(db.String(44), unique=True, index=True)  # Solana wallet address

    # Handle (unique identifier)
    handle = db.Column(db.String(50), unique=True, index=True)  # Unique handle for user

    # Other fields
    role = db.Column(db.String(20), default='user')  # admin, editor, user
    theme = db.Column(db.String(10), default='dark')  # light, dark, auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class UserFollow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    draft_name = db.Column(db.String(100), nullable=False)
    followed_at = db.Column(db.DateTime, default=datetime.utcnow)
    notification_level = db.Column(db.String(20), default='all')  # all, significant, major, comments, none

    # Relationship
    user = db.relationship('User', backref=db.backref('follows', lazy=True))

    __table_args__ = (db.UniqueConstraint('user_id', 'draft_name', name='unique_user_draft_follow'),)

    NOTIFICATION_LEVELS = {
        'all': 'All changes and comments',
        'significant': 'Only significant changes (state changes, new revisions)',
        'major': 'Only major changes (IESG actions, RFC publication)',
        'comments': 'Only comments',
        'none': 'No notifications (just tracking)'
    }

class WorkingGroupChair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_acronym = db.Column(db.String(50), index=True)  # Remove unique constraint to allow multiple chairs
    chair_name = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=False)
    set_at = db.Column(db.DateTime, default=datetime.utcnow)

# Users are now stored in database - this dict is kept for backward compatibility during migration

# Store document history in memory
DOCUMENT_HISTORY = {}

# Store comments in memory
COMMENTS = {}

# Store comment likes in memory
COMMENT_LIKES = {}

# Store comment replies in memory
COMMENT_REPLIES = {}

# Store working group chairs in memory
WORKING_GROUP_CHAIRS = {}

# Configuration for file uploads
UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'xml', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Comment edit/delete time limit (in minutes)
EDIT_DELETE_TIME_MINUTES = 15

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_draft_name(title, authors):
    """Generate a draft name from title and authors"""
    # Extract first author's last name
    first_author = authors[0] if authors else "unknown"
    author_last = first_author.split()[-1].lower() if first_author else "unknown"
    
    # Create a slug from the title
    title_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    title_slug = re.sub(r'\s+', '-', title_slug.strip())
    title_slug = title_slug[:30]  # Limit length
    
    return f"draft-{author_last}-{title_slug}"

def require_auth(f):
    """Decorator to require authentication"""
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_role(required_role):
    """Decorator to require a specific role (admin or editor can access admin features)"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
            current_user = get_current_user()
            if not current_user:
                return "Access denied: Not logged in", 403
            
            user_role = current_user.get('role', 'user')
            
            # Admin and editor can access admin pages
            if required_role == 'admin':
                if user_role not in ['admin', 'editor']:
                    return "Access denied: Admin or Editor role required", 403
            # For other roles, exact match required
            elif user_role != required_role:
                return f"Access denied: {required_role} role required", 403
            
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

def shorten_inscription_id(inscription_id, chars_each_side=8):
    """
    Shorten an inscription ID to show first N chars...last N chars
    Example: 8e24de515cc0dc305188f3c4a0e563466723bf9cf8d4576184bf3d13e287615bi0
    becomes: 8e24de51....7615bi0 (with chars_each_side=8)
    
    Always includes the 'i0' at the end as it's part of the ordinal identifier.
    """
    if not inscription_id:
        return ''
    
    # Ensure we have enough characters
    if len(inscription_id) <= (chars_each_side * 2 + 4):
        return inscription_id
    
    # Extract parts
    start = inscription_id[:chars_each_side]
    end = inscription_id[-chars_each_side:]
    
    return f'{start}....{end}'

def get_current_user():
    """Get current logged in user"""
    if 'user' in session:
        user = User.query.filter_by(username=session['user']).first()
        if user:
            # Use displayName or oauthName as fallback if name is not set
            user_name = user.name or user.displayName or user.oauthName or user.username
            return {
                'id': user.id,
                'username': user.username,
                'name': user_name,
                'email': user.email,
                'role': user.role,
                'theme': user.theme,
                # Web3Auth fields
                'displayName': user.displayName,
                'oauthName': user.oauthName,
                'profileImage': user.profileImage,
                'typeOfLogin': user.typeOfLogin,
                'evmAddress': user.evmAddress,
                'solanaAddress': user.solanaAddress
            }
    return None

def render_page(title, content, theme=None, user_menu=None):
    """Helper to render a page with BASE_TEMPLATE including build number"""
    if theme is None:
        theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    if user_menu is None:
        user_menu = generate_user_menu()
    return BASE_TEMPLATE.format(
        title=title,
        theme=theme,
        user_menu=user_menu,
        content=content,
        build_number=BUILD_NUMBER
    )

def generate_user_menu():
    """Generate user menu HTML for navbar"""
    current_user = get_current_user()
    if current_user:
        user_role = current_user.get('role', 'user')
        is_admin = user_role in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']
        admin_link = '<li><a class="dropdown-item" href="/admin/">Admin Dashboard</a></li>' if is_admin else ''
        # Display name priority: displayName > oauthName > name > username
        display_name = (current_user.get('displayName') or
                       current_user.get('oauthName') or
                       current_user.get('name') or
                       current_user['username'])

        return f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                {display_name}
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="/submit/status/">My Submissions</a></li>
                {admin_link}
                <li><a class="dropdown-item" href="/profile/">Profile</a></li>
                <li><a class="dropdown-item" href="/logout/">Logout</a></li>
            </ul>
        </div>
        """
    else:
        return """
        <div class="nav-item">
            <a class="nav-link" href="#" onclick="event.preventDefault(); loginWithWeb3Auth(); return false;">Sign In</a>
        </div>
        """

def add_to_document_history(draft_name, action, user, details=""):
    """Add an entry to document history"""
    if draft_name not in DOCUMENT_HISTORY:
        DOCUMENT_HISTORY[draft_name] = []
    
    entry = {
        'action': action,
        'user': user,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'details': details
    }
    DOCUMENT_HISTORY[draft_name].insert(0, entry)  # Add to beginning (most recent first)

def toggle_comment_like(draft_name, comment_id, user):
    """Toggle like on a comment"""
    like_key = f"{draft_name}:{comment_id}"
    if like_key not in COMMENT_LIKES:
        COMMENT_LIKES[like_key] = set()
    
    if user in COMMENT_LIKES[like_key]:
        COMMENT_LIKES[like_key].remove(user)
        return False  # Unliked
    else:
        COMMENT_LIKES[like_key].add(user)
        return True  # Liked

def get_comment_likes(draft_name, comment_id):
    """Get like count for a comment"""
    like_key = f"{draft_name}:{comment_id}"
    return len(COMMENT_LIKES.get(like_key, set()))

def is_comment_liked(draft_name, comment_id, user):
    """Check if user has liked a comment"""
    like_key = f"{draft_name}:{comment_id}"
    return user in COMMENT_LIKES.get(like_key, set())

def is_user_following_draft(draft_name, user):
    """Check if a user is following a specific draft"""
    if not user:
        return False
    return UserFollow.query.filter_by(user_id=user['id'], draft_name=draft_name).first() is not None

def get_user_follow(draft_name, user):
    """Get the UserFollow object for a user and draft"""
    if not user:
        return None
    return UserFollow.query.filter_by(user_id=user['id'], draft_name=draft_name).first()

def get_notification_controls(draft_name, user):
    """Generate HTML for notification level controls"""
    if not user:
        return ''

    follow = get_user_follow(draft_name, user)
    if not follow:
        return ''

    current_level = follow.notification_level
    options = []
    for level, description in UserFollow.NOTIFICATION_LEVELS.items():
        selected = 'selected' if level == current_level else ''
        options.append(f'<option value="{level}" {selected}>{description}</option>')

    return f'''
    <form method="post" action="/doc/draft/{draft_name}/update-notification/" class="mt-2">
        <label class="form-label small">Notification Level:</label>
        <select name="notification_level" class="form-select form-select-sm mb-1">
            {''.join(options)}
        </select>
        <button type="submit" class="btn btn-outline-secondary btn-sm w-100">Update Notifications</button>
    </form>
    '''

def should_notify_user(follow, event_type):
    """
    Determine if a user should be notified based on their notification level and event type.

    Event types:
    - 'comment': New comment added
    - 'revision': New revision uploaded
    - 'state_change': Document state changed
    - 'major_change': Major events (IESG actions, RFC publication)
    """
    level = follow.notification_level

    if level == 'none':
        return False
    elif level == 'comments':
        return event_type == 'comment'
    elif level == 'major':
        return event_type in ['major_change']
    elif level == 'significant':
        return event_type in ['revision', 'state_change', 'major_change']
    elif level == 'all':
        return True

    return False  # Default to no notification for unknown levels

def get_users_to_notify(draft_name, event_type):
    """
    Get all users who should be notified for a specific event on a document.
    Returns list of (user, follow) tuples.
    """
    follows = UserFollow.query.filter_by(draft_name=draft_name).all()
    users_to_notify = []

    for follow in follows:
        if should_notify_user(follow, event_type):
            user = User.query.get(follow.user_id)
            if user:
                users_to_notify.append((user, follow))

    return users_to_notify

def add_comment_reply(draft_name, parent_comment_id, reply_text, user):
    """Add a reply to a comment"""
    # Create reply in database
    reply = Comment(
        draft_name=draft_name,
        text=reply_text,
        author=user['name'],
        parent_id=int(parent_comment_id)
    )
    db.session.add(reply)
    db.session.commit()
    return reply

def build_comment_tree(draft_name):
    """Build a tree structure of comments with nested replies"""
    # Get all comments for this draft (including deleted ones, but mark them)
    all_comments = Comment.query.filter_by(draft_name=draft_name).order_by(Comment.timestamp).all()

    # Create a dictionary for quick lookup
    comment_dict = {}
    for comment in all_comments:
        comment_dict[comment.id] = {
            'id': str(comment.id),
            'author': comment.author,
            'date': comment.timestamp.strftime('%Y-%m-%d %H:%M'),
            'comment': comment.text if not comment.is_deleted else '[Deleted]',
            'avatar': ''.join([word[0].upper() for word in comment.author.split()[:2]]),
            'replies': [],
            'timestamp': comment.timestamp,
            'edited_at': comment.edited_at,
            'is_deleted': comment.is_deleted,
            'original_text': comment.original_text
        }

    # Build the tree
    top_level_comments = []
    for comment in all_comments:
        if comment.parent_id is None:
            # Top-level comment
            top_level_comments.append(comment_dict[comment.id])
        else:
            # Reply - add to parent's replies
            if comment.parent_id in comment_dict:
                comment_dict[comment.parent_id]['replies'].append(comment_dict[comment.id])

    return top_level_comments

def can_edit_delete_comment(comment, current_user):
    """Check if current user can edit/delete this comment"""
    if not current_user:
        return False
    if comment['author'] != current_user['name']:
        return False
    if comment.get('is_deleted', False):
        return False
    
    # Check time limit
    comment_time = comment.get('timestamp')
    if comment_time:
        time_diff = datetime.utcnow() - comment_time
        time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
        return time_diff <= time_limit
    return False

def render_comment_tree(comments, draft_name, level=0):
    """Recursively render comments and their nested replies"""
    if not comments:
        return ""
    
    indent_class = f"ms-{level * 4}" if level > 0 else ""
    html = f'<div class="{indent_class} mt-2">' if level > 0 else '<div class="mt-2">'

    for comment in comments:
        comment_id = comment.get('id', 'unknown')
        like_count = get_comment_likes(draft_name, comment_id)
        is_liked = is_comment_liked(draft_name, comment_id, get_current_user()['name']) if get_current_user() else False
        current_user = get_current_user()
        can_edit_delete = can_edit_delete_comment(comment, current_user)
        is_deleted = comment.get('is_deleted', False)
        edited_at = comment.get('edited_at')
        edited_text = f" (edited {edited_at.strftime('%Y-%m-%d %H:%M')})" if edited_at else ""

        # Like button styling
        like_btn_class = "btn-outline-danger" if is_liked else "btn-outline-secondary"
        like_icon = "❤️" if is_liked else "🤍"

        # Size styling based on nesting level
        avatar_size = max(30 - level * 5, 20)  # Decrease avatar size for nested replies
        font_size = max(14 - level * 2, 12)    # Decrease font size for nested replies
        card_class = "mb-2" if level > 0 else "mb-3"

        # Edit/Delete buttons HTML
        edit_delete_buttons = ""
        if can_edit_delete:
            edit_click = f"editComment('{comment_id}')"
            delete_click = f"deleteComment('{comment_id}')"
            edit_delete_buttons = f"""
                    <button class="btn btn-sm btn-outline-warning" onclick="{edit_click}" style="font-size: {font_size - 2}px;">
                        Edit
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="{delete_click}" style="font-size: {font_size - 2}px;">
                        Delete
                    </button>
            """

        # Build onclick handlers outside f-string
        like_click = f"toggleLike('{comment_id}')"
        reply_click = f"toggleReply('{comment_id}')"
        like_button = f'<button class="btn btn-sm {like_btn_class}" onclick="{like_click}" style="font-size: {font_size - 2}px;">{like_icon} {like_count}</button>' if not is_deleted else ''
        reply_button = f'<button class="btn btn-sm btn-outline-primary" onclick="{reply_click}" style="font-size: {font_size - 2}px;">Reply</button>' if not is_deleted else ''
        deleted_badge = '<small class="text-muted ms-2" style="font-style: italic;">[Deleted]</small>' if is_deleted else ''
        deleted_style = 'opacity: 0.5; font-style: italic;' if is_deleted else ''

        html += f"""
        <div class="card {card_class}" id="comment-{comment_id}">
            <div class="card-body py-2">
                <div class="d-flex align-items-center mb-1">
                    <div class="avatar bg-{"secondary" if level > 0 else "primary"} text-white rounded-circle me-2" style="width: {avatar_size}px; height: {avatar_size}px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: {font_size - 2}px;">
                        {comment['avatar']}
                    </div>
                    <div>
                        <strong style="font-size: {font_size}px;">{comment['author']}</strong>
                        <small class="text-muted ms-2">{comment['date']}{edited_text}</small>
                        {deleted_badge}
                    </div>
                </div>
                <p class="mb-2" style="font-size: {font_size}px; {deleted_style}">{comment['comment']}</p>
                <div class="d-flex gap-2 align-items-center">
                    {like_button}
                    {reply_button}
                    {edit_delete_buttons}
                </div>

                <!-- Reply form (hidden by default) -->
                <div id="reply-form-{comment_id}" class="mt-3" style="display: none;">
                    <form method="POST" class="d-flex gap-2">
                        <input type="hidden" name="action" value="reply">
                        <input type="hidden" name="parent_comment_id" value="{comment_id}">
                        <input type="text" name="reply_text" class="form-control" placeholder="Write a reply..." required style="font-size: {font_size}px;">
                        <button type="submit" class="btn btn-primary btn-sm" style="font-size: {font_size - 2}px;">Reply</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="{reply_click}" style="font-size: {font_size - 2}px;">Cancel</button>
                    </form>
                </div>

                <!-- Nested replies -->
                {render_comment_tree(comment.get('replies', []), draft_name, level + 1)}
            </div>
        </div>
        """

    html += '</div>'
    return html


# Load MLTF data from test files
def load_draft_data():
    """Load draft data from test files"""
    # Return empty list - test documents removed per user request
    drafts = []
    return drafts

def load_group_data():
    """Load group data from test files"""
    groups = []

    # Desirable Properties mapping for better names and descriptions
    dp_descriptions = {
        'dp1-federated-auth': {
            'title': 'Federated Authentication & Accountability',
            'desc': 'Developing standards for federated authentication systems that enable cross-platform identity verification while maintaining accountability and audit trails.'
        },
        'dp2-participant-agency': {
            'title': 'Participant Agency and Empowerment',
            'desc': 'Creating frameworks that empower participants with full control over their digital presence, decision-making authority, and ability to shape their environment.'
        },
        'dp3-adaptive-governance': {
            'title': 'Adaptive Governance Supporting an Exponentially Growing Community',
            'desc': 'Designing governance systems that can scale with exponential community growth while maintaining fairness, participation, and adaptability to emerging challenges.'
        },
        'dp4-data-sovereignty': {
            'title': 'Data Sovereignty and Privacy',
            'desc': 'Establishing protocols for complete data ownership, privacy by design, and user-controlled data portability across the Meta-Layer ecosystem.'
        },
        'dp5-decentralized-namespace': {
            'title': 'Decentralized Namespace',
            'desc': 'Developing decentralized naming systems that provide persistent, user-controlled identifiers and namespaces independent of centralized authorities.'
        },
        'dp6-commerce': {
            'title': 'Commerce',
            'desc': 'Creating secure, transparent commerce protocols that enable value exchange, micropayments, and economic interactions within the Meta-Layer.'
        },
        'dp7-simplicity-interoperability': {
            'title': 'Simplicity and Interoperability',
            'desc': 'Designing systems that reduce complexity while ensuring seamless interoperability between different platforms, tools, and communities.'
        },
        'dp8-collaborative-environment': {
            'title': 'Collaborative Environment and Meta-Communities',
            'desc': 'Building frameworks for meta-communities that span multiple platforms and enable fluid collaboration across organizational boundaries.'
        },
        'dp9-developer-incentives': {
            'title': 'Developer and Community Incentives',
            'desc': 'Creating incentive structures that reward developers and communities for contributing to the ecosystem while aligning with long-term sustainability.'
        },
        'dp10-education': {
            'title': 'Education',
            'desc': 'Developing educational frameworks and tools that help participants understand and effectively use the Meta-Layer capabilities.'
        },
        'dp21-multi-modal': {
            'title': 'Multi-modal',
            'desc': 'Enabling seamless interaction across multiple communication modalities including text, voice, video, AR/VR, and emerging interaction paradigms.'
        },
        'dp11-safe-ethical-ai': {
            'title': 'Safe and Ethical AI',
            'desc': 'Establishing ethical frameworks and safety protocols for AI systems operating within the Meta-Layer to ensure alignment with human values.'
        },
        'dp12-community-ai-governance': {
            'title': 'Community-Based AI Governance',
            'desc': 'Creating community-driven governance models for AI systems that ensure transparency, accountability, and collective oversight.'
        },
        'dp13-ai-containment': {
            'title': 'AI Containment',
            'desc': 'Developing containment strategies and technical measures to prevent AI systems from exceeding intended boundaries or causing unintended consequences.'
        },
        'dp14-trust-transparency': {
            'title': 'Trust and Transparency',
            'desc': 'Building trust through transparent decision-making, auditable processes, and verifiable system behaviors throughout the Meta-Layer.'
        },
        'dp15-security-provenance': {
            'title': 'Security and Provenance',
            'desc': 'Ensuring security through comprehensive provenance tracking, secure infrastructure, and verifiable data lineage across all interactions.'
        },
        'dp16-roadmap-milestones': {
            'title': 'Roadmap and Milestones',
            'desc': 'Developing structured roadmaps with clear milestones that guide the evolution of the Meta-Layer while maintaining community alignment.'
        },
        'dp17-financial-sustainability': {
            'title': 'Financial Sustainability',
            'desc': 'Creating financial models and incentive structures that ensure the long-term sustainability and equitable growth of the Meta-Layer ecosystem.'
        },
        'dp18-feedback-reputation': {
            'title': 'Feedback Loops and Reputation',
            'desc': 'Implementing feedback mechanisms and reputation systems that reward positive contributions and maintain community standards.'
        },
        'dp19-community-engagement': {
            'title': 'Amplifying Presence and Community Engagement',
            'desc': 'Developing systems that amplify community participation, enhance visibility of contributions, and strengthen community bonds.'
        },
        'dp20-community-ownership': {
            'title': 'Community Ownership',
            'desc': 'Ensuring community ownership through decentralized governance, shared decision-making, and equitable distribution of value and control.'
        }
    }

    try:
        with open('/home/ubuntu/datatracker/test/data/group-aliases', 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                # Extract group name from the line
                match = re.search(r'xfilter-([^:]+):', line)
                if match:
                    group_name = match.group(1)

                    # Use specific DP description if available, otherwise generate generic one
                    if group_name in dp_descriptions:
                        dp_info = dp_descriptions[group_name]
                        group_title = dp_info['title']
                        description = dp_info['desc']
                    else:
                        # Fallback for non-DP groups
                        group_title = group_name.replace('-', ' ').title()
                        description = f'The {group_title} Working Group focuses on {group_title.lower()} standards and protocols for the Internet.'

                    groups.append({
                        'acronym': group_name,
                        'name': f'{group_title} Working Group',
                        'type': 'Working Group',
                        'state': 'Active',
                        'chairs': [f'Chair {i+1}' for i in range(1 + (hash(group_name) % 2))],  # 1-2 chairs
                        'description': description
                    })
    except FileNotFoundError:
        print("Group aliases file not found")
    return groups

# Load the data
DRAFTS = load_draft_data()
GROUPS = load_group_data()

# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="{theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="/static/images/overweb_logo.png">
    <link rel="shortcut icon" type="image/png" href="/static/images/overweb_logo.png">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {{
            /* Light theme (default) */
            --bg-color: #ffffff;
            --bg-secondary: #f7f9fa;
            --bg-tertiary: #e1e8ed;
            --text-primary: #14171a;
            --text-secondary: #657786;
            --text-muted: #aab8c2;
            --border-color: #e1e8ed;
            --border-hover: #ccd6dd;
            --accent-color: #1d9bf0;
            --accent-hover: #1a8cd8;
            --success-color: #00ba7c;
            --warning-color: #f7b529;
            --error-color: #f4212e;
            --navbar-bg: #ffffff;
            --navbar-text: #14171a;
            --navbar-border: #e1e8ed;
            --card-bg: #ffffff;
            --card-border: #e1e8ed;
            --input-bg: #ffffff;
            --input-border: #657786;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            --shadow-hover: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}

        [data-theme="dark"] {{
            /* Dark theme */
            --bg-color: #000000;
            --bg-secondary: #16181c;
            --bg-tertiary: #1d1f23;
            --text-primary: #ffffff;
            --text-secondary: #8b98a5;
            --text-muted: #6c7b8a;
            --border-color: #2f3336;
            --border-hover: #3d4043;
            --accent-color: #1d9bf0;
            --accent-hover: #1a8cd8;
            --success-color: #00ba7c;
            --warning-color: #f7b529;
            --error-color: #f4212e;
            --navbar-bg: #16181c;
            --navbar-text: #ffffff;
            --navbar-border: #2f3336;
            --card-bg: #16181c;
            --card-border: #2f3336;
            --input-bg: #16181c;
            --input-border: #3d4043;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
            --shadow-hover: 0 2px 8px rgba(0, 0, 0, 0.4);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            margin: 0;
            min-height: 100vh;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}

        /* Modern navbar similar to X */
        .navbar {{
            background-color: var(--navbar-bg) !important;
            border-bottom: 1px solid var(--navbar-border);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            box-shadow: var(--shadow);
            padding: 0;
            height: 53px;
            z-index: 2147483646 !important; /* Just below dropdown max */
            position: relative !important;
            overflow: visible !important;
        }}

        .navbar-brand {{
            color: var(--navbar-text) !important;
            font-weight: 700;
            font-size: 18px;
            padding: 16px 20px;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .navbar-brand:hover {{
            color: var(--accent-color) !important;
        }}

        .navbar-brand img {{
            height: 24px;
            width: auto;
            object-fit: contain;
        }}

        /* White logo for dark mode */
        [data-theme="dark"] .navbar-brand img {{
            filter: brightness(0) invert(1);
        }}

        .navbar-nav {{
            align-items: center;
        }}

        .nav-link {{
            color: var(--text-secondary) !important;
            font-weight: 500;
            padding: 16px 20px;
            margin: 0;
            border-radius: 0;
            transition: all 0.2s ease;
        }}

        .nav-link:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color) !important;
        }}

        .nav-link.active {{
            color: var(--accent-color) !important;
            border-bottom: 3px solid var(--accent-color);
            background-color: transparent;
        }}

        /* Theme toggle button */
        .theme-toggle {{
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 18px;
            padding: 16px 20px;
            cursor: pointer;
            transition: color 0.2s ease;
        }}

        .theme-toggle:hover {{
            color: var(--accent-color);
        }}

        /* Cards with modern styling */
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            box-shadow: var(--shadow);
            transition: all 0.2s ease;
        }}

        .card:hover {{
            box-shadow: var(--shadow-hover);
            border-color: var(--border-hover);
        }}

        .card-header {{
            background-color: transparent;
            border-bottom: 1px solid var(--card-border);
            border-radius: 16px 16px 0 0 !important;
            padding: 16px 20px;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .card-body {{
            padding: 20px;
        }}

        /* Buttons styled like X */
        .btn {{
            border-radius: 20px;
            font-weight: 700;
            padding: 8px 16px;
            transition: all 0.2s ease;
        }}

        .btn-primary {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .btn-primary:hover {{
            background-color: var(--accent-hover);
            border-color: var(--accent-hover);
            transform: translateY(-1px);
        }}

        .btn-outline-primary {{
            border-color: var(--text-secondary);
            color: var(--text-primary);
        }}

        .btn-outline-primary:hover {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .btn-outline-secondary {{
            border-color: var(--border-color);
            color: var(--text-secondary);
        }}

        .btn-outline-secondary:hover {{
            background-color: var(--bg-secondary);
            border-color: var(--border-hover);
            color: var(--text-primary);
        }}

        /* Form inputs */
        .form-control {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        input.form-control, textarea.form-control, select.form-control {{
            color: var(--text-primary) !important;
            background-color: var(--input-bg) !important;
            border-color: var(--input-border) !important;
        }}

        [data-theme="dark"] input,
        [data-theme="dark"] textarea,
        [data-theme="dark"] select,
        [data-theme="dark"] input.form-control,
        [data-theme="dark"] textarea.form-control,
        [data-theme="dark"] select.form-control {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        .form-control:focus {{
            border-color: var(--accent-color);
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
            background-color: var(--input-bg);
        }}

        .form-control::placeholder {{
            color: var(--text-muted);
        }}

        .form-select {{
            background-color: var(--input-bg) !important;
            border: 1px solid var(--input-border) !important;
            border-radius: 8px;
            color: var(--text-primary) !important;
            padding: 12px 16px;
            transition: all 0.2s ease;
        }}

        [data-theme="dark"] .form-select {{
            color: #ffffff !important;
            background-color: #16181c !important;
            border-color: #3d4043 !important;
        }}

        /* Alerts */
        .alert {{
            border-radius: 12px;
            border: none;
            padding: 16px 20px;
        }}

        .alert-info {{
            background-color: rgba(29, 155, 240, 0.1);
            color: var(--accent-color);
        }}

        /* Badges */
        .badge {{
            border-radius: 12px;
            font-weight: 500;
            padding: 4px 8px;
        }}

        /* Tables */
        .table {{
            color: var(--text-primary);
            border-color: var(--border-color);
        }}

        .table thead th {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
            border-color: var(--border-color);
            font-weight: 600;
            padding: 12px;
        }}

        .table tbody td {{
            background-color: var(--card-bg);
            color: var(--text-primary);
            border-color: var(--border-color);
            padding: 12px;
        }}

        .table-hover tbody tr:hover td {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
        }}
        
        .table-hover tbody tr:hover td * {{
            color: var(--text-primary);
        }}

        .table-responsive {{
            border-radius: 8px;
            overflow: hidden;
        }}

        /* Pagination */
        .pagination .page-link {{
            background-color: var(--card-bg);
            color: var(--text-primary);
            border-color: var(--border-color);
        }}

        .pagination .page-link:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
            border-color: var(--border-hover);
        }}

        .pagination .page-item.active .page-link {{
            background-color: var(--accent-color);
            border-color: var(--accent-color);
            color: white;
        }}

        .pagination .page-item.disabled .page-link {{
            background-color: var(--bg-secondary);
            color: var(--text-muted);
            border-color: var(--border-color);
        }}

        /* Dropdown menus in tables */
        .table .dropdown {{
            position: relative;
        }}

        .table .dropdown-menu {{
            background-color: var(--card-bg);
            border-color: var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            min-width: 120px;
            z-index: 1050;
            margin-top: 4px;
        }}

        .table .dropdown-item {{
            color: var(--text-primary);
            padding: 8px 16px;
            cursor: pointer;
        }}

        .table .dropdown-item:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
        }}

        .table .dropdown-toggle {{
            background-color: transparent;
            border-color: var(--accent-color);
            color: var(--accent-color);
        }}

        .table .dropdown-toggle:hover {{
            background-color: var(--accent-color);
            color: white;
            border-color: var(--accent-color);
        }}

        /* Ensure table doesn't clip dropdowns */
        .table-responsive {{
            overflow: visible !important;
        }}

        .card-body {{
            overflow: visible !important;
        }}

        /* Breadcrumbs */
        .breadcrumb {{
            background-color: transparent;
            padding: 0;
            margin-bottom: 20px;
        }}

        .breadcrumb-item a {{
            color: var(--text-secondary);
        }}

        .breadcrumb-item.active {{
            color: var(--text-primary);
            font-weight: 500;
        }}

        /* Flash messages */
        #flash-messages {{
            position: fixed;
            top: 70px;
            right: 20px;
            z-index: 1000;
            max-width: 400px;
        }}

        .flash-message {{
            margin-bottom: 10px;
            padding: 12px 16px;
            border-radius: 12px;
            font-weight: 500;
            box-shadow: var(--shadow);
        }}

        .flash-success {{
            background-color: rgba(0, 186, 124, 0.1);
            color: var(--success-color);
            border: 1px solid rgba(0, 186, 124, 0.2);
        }}

        .flash-error {{
            background-color: rgba(244, 33, 46, 0.1);
            color: var(--error-color);
            border: 1px solid rgba(244, 33, 46, 0.2);
        }}

        .flash-info {{
            background-color: rgba(247, 181, 41, 0.1);
            color: var(--warning-color);
            border: 1px solid rgba(247, 181, 41, 0.2);
        }}

        /* Avatar styling */
        .avatar {{
            border-radius: 50%;
            object-fit: cover;
        }}

        /* Wider content layout for better readability */
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding-left: 24px;
            padding-right: 24px;
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            .navbar-brand {{
                font-size: 16px;
                padding: 16px 15px;
            }}

            .nav-link {{
                padding: 16px 12px;
                font-size: 14px;
            }}

            .theme-toggle {{
                padding: 16px 15px;
            }}

            .card {{
                border-radius: 12px;
            }}

            .card-header {{
                border-radius: 12px 12px 0 0 !important;
            }}

            .container {{
                padding-left: 15px;
                padding-right: 15px;
            }}
        }}

        @media (min-width: 1200px) {{
            .container {{
                padding-left: 40px;
                padding-right: 40px;
            }}
        }}

        /* Custom scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--border-color);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: var(--border-hover);
        }}

        /* Dropdown menu z-index fix - maximum priority to ensure it's above everything */
        .dropdown-menu {{
            z-index: 2147483647 !important; /* Maximum possible z-index value */
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            background-color: var(--card-bg);
            margin-top: 8px;
            overflow: visible !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
            min-width: 200px;
        }}

        /* Ensure dropdown container doesn't clip */
        .dropdown {{
            position: relative !important;
            overflow: visible !important;
        }}

        /* Prevent any parent from clipping the dropdown */
        .navbar .dropdown {{
            overflow: visible !important;
        }}

        /* Force dropdown to be on top of everything */
        .navbar .dropdown-menu {{
            z-index: 2147483647 !important;
            position: absolute !important;
            top: 100% !important;
            left: 0 !important;
        }}

        .dropdown-item {{
            color: var(--text-primary);
            padding: 12px 16px;
            transition: background-color 0.2s ease;
        }}

        .dropdown-item:hover {{
            background-color: var(--bg-secondary);
            color: var(--accent-color);
        }}

        .dropdown-toggle {{
            border: none;
            background: none;
            color: var(--text-secondary);
            font-weight: 500;
            padding: 16px 12px;
            border-radius: 8px;
            transition: all 0.2s ease;
        }}

        .dropdown-toggle:hover {{
            background-color: var(--bg-secondary);
            color: var(--text-primary);
        }}

        .dropdown-toggle:focus {{
            box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.1);
        }}
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/">
                <img src="/static/images/overweb_logo.png" alt="Overweb" />
                MLTF
            </a>
            <div class="navbar-nav">
                <a class="nav-link" href="/doc/all/">
                    <i class="fas fa-file-alt me-1"></i>Documents
                </a>
                <a class="nav-link" href="/group/">
                    <i class="fas fa-users me-1"></i>Working Groups
                </a>
                <!-- <a class="nav-link" href="/meeting/">
                    <i class="fas fa-calendar me-1"></i>Meetings
                </a>
                <a class="nav-link" href="/person/">
                    <i class="fas fa-user-friends me-1"></i>People
                </a> -->
                <a class="nav-link" href="/submit/">
                    <i class="fas fa-plus me-1"></i>Submit Draft
                </a>
            </div>
            <div class="navbar-nav ms-auto">
                {user_menu}
                <button class="theme-toggle" id="theme-toggle" title="Toggle theme">
                    <i class="fas fa-moon"></i>
                </button>
            </div>
        </div>
    </nav>

    <div id="flash-messages"></div>
    {content}

    <div class="container-fluid mt-5 py-3" style="border-top: 1px solid var(--border-color); background-color: var(--bg-secondary);">
        <div class="text-center text-muted small">
            Build {build_number} | MLTF Datatracker
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Theme switching functionality
        const themeToggle = document.getElementById('theme-toggle');
        const html = document.documentElement;
        const icon = themeToggle.querySelector('i');

        // Load saved theme - prefer user preference over localStorage
        const userTheme = html.getAttribute('data-theme') || 'dark';
        const savedTheme = userTheme !== 'light' && userTheme !== 'dark' && userTheme !== 'auto' ?
            (localStorage.getItem('theme') || 'dark') : userTheme;
        html.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);

        function updateThemeIcon(theme) {{
            if (theme === 'dark') {{
                icon.className = 'fas fa-sun';
                themeToggle.title = 'Switch to light mode';
            }} else {{
                icon.className = 'fas fa-moon';
                themeToggle.title = 'Switch to dark mode';
            }}
        }}

        themeToggle.addEventListener('click', () => {{
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        }});

        // Flash message auto-hide
        setTimeout(() => {{
            const flashMessages = document.querySelectorAll('.flash-message');
            flashMessages.forEach(msg => {{
                msg.style.opacity = '0';
                setTimeout(() => msg.remove(), 300);
            }});
        }}, 5000);

        // Web3Auth Integration
        let web3auth = null;

        // Function to load script dynamically
        function loadScript(src) {{
            return new Promise((resolve, reject) => {{
                const script = document.createElement('script');
                script.src = src;
                script.onload = () => resolve();
                script.onerror = (e) => reject(e);
                document.head.appendChild(script);
            }});
        }}

        // Initialize Web3Auth after ensuring scripts are loaded
        async function initWeb3Auth() {{
            try {{
                await loadScript('https://cdn.jsdelivr.net/npm/web3@1.10.0/dist/web3.min.js');
                await loadScript('https://unpkg.com/@web3auth/modal@10.13.1/dist/modal.umd.min.js');

                await new Promise(resolve => {{
                    const checkWeb3Auth = () => {{
                        if (window.Modal && window.Modal.Web3Auth) {{
                            resolve();
                        }} else {{
                            setTimeout(checkWeb3Auth, 100);
                        }}
                    }};
                    checkWeb3Auth();
                }});

                const Web3AuthConstructor = window.Modal.Web3Auth;
                const web3AuthConfig = {{
                    clientId: "BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk",
                    web3AuthNetwork: 'sapphire_devnet',
                    chainConfig: {{
                        chainNamespace: 'eip155',
                        chainId: '0x1',
                        rpcTarget: 'https://rpc.ankr.com/eth',
                        displayName: 'Ethereum Mainnet',
                        blockExplorerUrl: 'https://etherscan.io',
                        ticker: 'ETH',
                        tickerName: 'Ethereum',
                    }},
                    uiConfig: {{
                        mode: 'dark',
                        theme: {{
                            primary: '#1d9bf0'
                        }},
                        loginMethodsOrder: ['google', 'twitter', 'email_passwordless', 'wallet'],
                        defaultLanguage: 'en',
                    }},
                }};

                web3auth = new Web3AuthConstructor(web3AuthConfig);
                await web3auth.init();
                console.log('Web3Auth initialized successfully');

                // Check if we should trigger login modal
                const urlParams = new URLSearchParams(window.location.search);
                if (urlParams.get('show_login') === '1') {{
                    // Remove the parameter from URL
                    window.history.replaceState({{}}, '', window.location.pathname);
                    // Show login modal
                    await loginWithWeb3Auth();
                }}
            }} catch (error) {{
                console.error('Web3Auth initialization failed:', error);
            }}
        }}

        async function loginWithWeb3Auth() {{
            if (!web3auth) {{
                alert("Web3Auth not initialized. Please refresh the page.");
                return;
            }}

            try {{
                // Logout first to ensure clean state
                try {{
                    await web3auth.logout();
                }} catch (e) {{
                    // Ignore if not logged in
                }}

                // Connect without specifying a provider - shows modal with all options
                const web3authProvider = await web3auth.connect();
                const userInfo = await web3auth.getUserInfo();
                
                console.log('User info received:', userInfo);
                
                // Get wallet address - with retry and error handling
                let evmAddress = '';
                try {{
                    if (web3authProvider) {{
                        const web3 = new Web3(web3authProvider);
                        // Wait a bit for provider to be ready
                        await new Promise(resolve => setTimeout(resolve, 500));
                        const accounts = await web3.eth.getAccounts();
                        if (accounts && accounts.length > 0) {{
                            evmAddress = accounts[0];
                        }}
                    }}
                }} catch (addrError) {{
                    console.warn('Could not get EVM address:', addrError);
                    // Not critical for social logins
                }}

                // Build the payload - handle different structures
                // For email_passwordless, verifierId might be different
                const finalVerifierId = userInfo.verifierId || userInfo.email || evmAddress || 'unknown';
                const finalTypeOfLogin = userInfo.typeOfLogin || 'unknown';
                
                const payload = {{
                    verifierId: finalVerifierId,
                    typeOfLogin: finalTypeOfLogin,
                    email: userInfo.email || '',
                    name: userInfo.name || userInfo.email?.split('@')[0] || '',
                    profileImage: userInfo.profileImage || '',
                    evmAddress: evmAddress || '',
                }};

                console.log('Sending payload:', payload);
                console.log('typeOfLogin:', finalTypeOfLogin);

                // Send to backend
                const response = await fetch('/api/auth/web3auth', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }});

                const result = await response.json();
                if (response.ok) {{
                    window.location.href = '/';
                }} else {{
                    console.error('Backend error:', result);
                    alert('Login failed: ' + (result.error || 'Unknown error'));
                }}
            }} catch (error) {{
                console.error('Login failed:', error);
                if (error.message && !error.message.includes('user closed')) {{
                    alert('Login failed: ' + error.message);
                }}
            }}
        }}

        // Initialize Web3Auth on page load
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initWeb3Auth);
        }} else {{
            initWeb3Auth();
        }}

        // Make loginWithWeb3Auth available globally
        window.loginWithWeb3Auth = loginWithWeb3Auth;
    </script>
</body>
</html>
"""

SUBMIT_TEMPLATE = """
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item active">Submit Draft</li>
        </ol>
    </nav>
    
    <h1>Submit Internet-Draft</h1>
    <p class="lead">Submit a new Meta-Layer Draft to the MLTF datatracker</p>
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>Draft Submission Form</h5>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <!-- Tabs for Upload File vs From Ordinal -->
                    <ul class="nav nav-tabs mb-3" id="submissionTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" id="upload-tab" data-bs-toggle="tab" 
                                    data-bs-target="#upload" type="button" role="tab">
                                <i class="bi bi-upload"></i> Upload File
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="ordinal-tab" data-bs-toggle="tab" 
                                    data-bs-target="#ordinal" type="button" role="tab">
                                <i class="bi bi-coin"></i> From Ordinal
                            </button>
                        </li>
                    </ul>
                    
                    <div class="tab-content" id="submissionTabContent">
                        <!-- Upload File Tab -->
                        <div class="tab-pane fade show active" id="upload" role="tabpanel">
                            <form method="POST" enctype="multipart/form-data" id="uploadForm">
                                <input type="hidden" name="sourceType" value="file">
                                
                                <div class="mb-3">
                                    <label for="title" class="form-label">Document Title *</label>
                                    <input type="text" class="form-control" id="title" name="title" required 
                                           placeholder="Enter the document title">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="authors" class="form-label">Authors *</label>
                                    <input type="text" class="form-control" id="authors" name="authors" required 
                                           placeholder="Comma-separated list of authors (e.g., John Doe, Jane Smith)">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="abstract" class="form-label">Abstract</label>
                                    <textarea class="form-control" id="abstract" name="abstract" rows="4" 
                                              placeholder="Brief description of the document"></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="group" class="form-label">Working Group (Optional)</label>
                                    <select class="form-select" id="group" name="group">
                                        <option value="">Select a Working Group</option>
                                        <option value="httpbis">HTTP</option>
                                        <option value="quic">QUIC</option>
                                        <option value="tls">TLS</option>
                                        <option value="dnsop">DNSOP</option>
                                        <option value="rtgwg">RTGWG</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="file" class="form-label">Document File *</label>
                                    <input type="file" class="form-control" id="file" name="file" required 
                                           accept=".pdf,.txt,.xml,.doc,.docx">
                                    <div class="form-text">Supported formats: PDF, TXT, XML, DOC, DOCX (max 16MB)</div>
                                </div>
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="terms" required>
                                        <label class="form-check-label" for="terms">
                                            I agree to the <a href="#" target="_blank">MLTF submission terms</a>
                                        </label>
                                    </div>
                                </div>
                                
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                    <button type="submit" class="btn btn-primary">Submit Draft</button>
                                    <a href="/" class="btn btn-secondary">Cancel</a>
                                </div>
                            </form>
                        </div>
                        
                        <!-- From Ordinal Tab -->
                        <div class="tab-pane fade" id="ordinal" role="tabpanel">
                            <form method="POST" id="ordinalForm">
                                <input type="hidden" name="sourceType" value="ordinal">
                                <input type="hidden" name="ordinalContentUrl" id="ordinalContentUrl">
                                <input type="hidden" name="ordinalContentType" id="ordinalContentType">
                                <input type="hidden" name="inscriptionNumber" id="inscriptionNumber">
                                <input type="hidden" name="blockHeight" id="blockHeight">
                                <input type="hidden" name="inscriptionTimestamp" id="inscriptionTimestamp">
                                
                                <div class="mb-3">
                                    <label for="ordinalId" class="form-label">Inscription ID *</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" id="ordinalId" name="ordinalId" required 
                                               placeholder="Enter Bitcoin Ordinal inscription ID">
                                        <button class="btn btn-outline-secondary" type="button" id="previewBtn">
                                            <i class="bi bi-eye"></i> Preview
                                        </button>
                                    </div>
                                    <div class="form-text">Enter the inscription ID from ordinals.com</div>
                                </div>
                                
                                <!-- Preview Area -->
                                <div id="ordinalPreview" class="mb-3" style="display: none;">
                                    <div class="card">
                                        <div class="card-header">
                                            <h6 class="mb-0">Ordinal Preview</h6>
                                        </div>
                                        <div class="card-body">
                                            <div id="previewLoading" style="display: none;">
                                                <div class="text-center">
                                                    <div class="spinner-border text-primary" role="status">
                                                        <span class="visually-hidden">Loading...</span>
                                                    </div>
                                                    <p class="mt-2">Loading ordinal content...</p>
                                                </div>
                                            </div>
                                            <div id="previewError" class="alert alert-danger" style="display: none;"></div>
                                            <div id="previewContent"></div>
                                            <div id="previewMetadata" class="mt-3" style="display: none;">
                                                <hr>
                                                <h6>Metadata:</h6>
                                                <ul class="list-unstyled small">
                                                    <li><strong>Inscription ID:</strong> <span id="metaInscriptionId"></span></li>
                                                    <li><strong>Inscription Number:</strong> <span id="metaInscriptionNumber"></span></li>
                                                    <li><strong>Block Height:</strong> <span id="metaBlockHeight"></span></li>
                                                    <li><strong>Timestamp:</strong> <span id="metaTimestamp"></span></li>
                                                    <li><strong>Content Type:</strong> <span id="metaContentType"></span></li>
                                                    <li><strong>Content Size:</strong> <span id="metaContentSize"></span></li>
                                                </ul>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalTitle" class="form-label">Document Title *</label>
                                    <input type="text" class="form-control" id="ordinalTitle" name="title" required 
                                           placeholder="Enter the document title">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalAuthors" class="form-label">Authors *</label>
                                    <input type="text" class="form-control" id="ordinalAuthors" name="authors" required 
                                           placeholder="Comma-separated list of authors">
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalAbstract" class="form-label">Abstract</label>
                                    <textarea class="form-control" id="ordinalAbstract" name="abstract" rows="4" 
                                              placeholder="Brief description of the document"></textarea>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="ordinalGroup" class="form-label">Working Group (Optional)</label>
                                    <select class="form-select" id="ordinalGroup" name="group">
                                        <option value="">Select a Working Group</option>
                                        <option value="httpbis">HTTP</option>
                                        <option value="quic">QUIC</option>
                                        <option value="tls">TLS</option>
                                        <option value="dnsop">DNSOP</option>
                                        <option value="rtgwg">RTGWG</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="ordinalTerms" required>
                                        <label class="form-check-label" for="ordinalTerms">
                                            I agree to the <a href="#" target="_blank">MLTF submission terms</a>
                                        </label>
                                    </div>
                                </div>
                                
                                <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                                    <button type="submit" class="btn btn-primary" id="ordinalSubmitBtn" disabled>Submit Draft</button>
                                    <a href="/" class="btn btn-secondary">Cancel</a>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Submission Guidelines</h5>
                </div>
                <div class="card-body">
                    <h6>File Requirements:</h6>
                    <ul class="small">
                        <li>PDF format preferred</li>
                        <li>Maximum 16MB file size</li>
                        <li>Use standard MLTF formatting</li>
                    </ul>
                    
                    <h6>Ordinal Requirements:</h6>
                    <ul class="small">
                        <li>Content must be < 50KB</li>
                        <li>Supported: Images, Text, Markdown, HTML</li>
                        <li>Valid inscription ID required</li>
                    </ul>
                    
                    <h6>Content Requirements:</h6>
                    <ul class="small">
                        <li>Clear, descriptive title</li>
                        <li>Complete author information</li>
                        <li>Abstract describing the work</li>
                        <li>Proper MLTF document structure</li>
                    </ul>
                    
                    <h6>Review Process:</h6>
                    <ul class="small">
                        <li>Initial technical review</li>
                        <li>Working group consideration</li>
                        <li>IESG review (if applicable)</li>
                        <li>Publication decision</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Ordinal preview functionality
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔨 BUILD """ + str(BUILD_NUMBER) + """ - Ordinals Module Loaded');
    
    const previewBtn = document.getElementById('previewBtn');
    const ordinalIdInput = document.getElementById('ordinalId');
    const ordinalPreview = document.getElementById('ordinalPreview');
    const previewLoading = document.getElementById('previewLoading');
    const previewError = document.getElementById('previewError');
    const previewContent = document.getElementById('previewContent');
    const previewMetadata = document.getElementById('previewMetadata');
    const ordinalSubmitBtn = document.getElementById('ordinalSubmitBtn');
    
    let previewData = null;
    
    previewBtn.addEventListener('click', async function() {
        const inscriptionId = ordinalIdInput.value.trim();
        
        if (!inscriptionId) {
            alert('Please enter an inscription ID');
            return;
        }
        
        // Show preview area and loading
        ordinalPreview.style.display = 'block';
        previewLoading.style.display = 'block';
        previewError.style.display = 'none';
        previewContent.innerHTML = '';
        previewMetadata.style.display = 'none';
        ordinalSubmitBtn.disabled = true;
        
        try {
            const response = await fetch('/api/ordinal/preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ inscriptionId })
            });
            
            const data = await response.json();
            
            previewLoading.style.display = 'none';
            
            if (!data.success) {
                previewError.textContent = data.error || 'Failed to load ordinal';
                previewError.style.display = 'block';
                return;
            }
            
            // Store preview data
            previewData = data;
            
            // Populate hidden fields
            document.getElementById('ordinalContentUrl').value = data.contentUrl;
            document.getElementById('ordinalContentType').value = data.contentType;
            document.getElementById('inscriptionNumber').value = data.inscriptionNumber || '';
            document.getElementById('blockHeight').value = data.blockHeight || '';
            document.getElementById('inscriptionTimestamp').value = data.timestamp || '';
            
            // Display content based on type
            displayOrdinalContent(data);
            
            // Display metadata
            displayMetadata(data);
            
            // Enable submit button
            ordinalSubmitBtn.disabled = false;
            
        } catch (error) {
            previewLoading.style.display = 'none';
            previewError.textContent = 'Error: ' + error.message;
            previewError.style.display = 'block';
        }
    });
    
    function displayOrdinalContent(data) {
        const contentType = data.contentType;
        const contentUrl = data.contentUrl;
        
        console.log('=== displayOrdinalContent DEBUG ===');
        console.log('contentType:', contentType);
        console.log('contentUrl:', contentUrl);
        console.log('startsWith image:', contentType.startsWith('image/'));
        console.log('includes text/plain:', contentType.includes('text/plain'));
        console.log('includes text/javascript:', contentType.includes('text/javascript'));
        console.log('includes application/json:', contentType.includes('application/json'));
        console.log('includes text/markdown:', contentType.includes('text/markdown'));
        console.log('includes text/html:', contentType.includes('text/html'));
        
        if (contentType.startsWith('image/')) {
            console.log('→ RENDERING AS IMAGE');
            // Display image
            previewContent.innerHTML = `<img src="${contentUrl}" class="img-fluid" alt="Ordinal content" style="max-height: 400px;">`;
        } else if (contentType.includes('text/plain') || contentType.includes('text/javascript') || contentType.includes('application/json')) {
            console.log('→ RENDERING AS TEXT/PLAIN (checking for markdown)');
            // Display plain text (handles charset parameters), but check if it's actually markdown
            fetch(contentUrl)
                .then(res => {
                    console.log('Fetch response status:', res.status);
                    return res.text();
                })
                .then(text => {
                    console.log('Text content length:', text.length);
                    console.log('First 100 chars:', text.substring(0, 100));
                    
                    // Check if text looks like markdown
                    const markdownPatterns = [
                        /^#{1,6}\s+.+$/m,              // Headers: # Header
                        /\[.+\]\(.+\)/,                // Links: [text](url)
                        /!\[.*\]\(.+\)/,               // Images: ![alt](url)
                        /^\s*[-*+]\s+.+$/m,            // Unordered lists
                        /^\s*\d+\.\s+.+$/m,            // Ordered lists
                        /```[\s\S]*?```/,              // Code blocks
                        /^\s*>\s+.+$/m,                // Blockquotes
                        /\*\*.+?\*\*/,                 // Bold
                        /__(.+?)__/,                   // Bold (alt)
                        /\*.+?\*/,                     // Italic
                        /_(.+?)_/                      // Italic (alt)
                    ];
                    
                    const looksLikeMarkdown = markdownPatterns.some(pattern => pattern.test(text));
                    
                    if (looksLikeMarkdown) {
                        console.log('→ DETECTED MARKDOWN in text/plain, converting...');
                        // Treat as markdown
                        fetch('/api/ordinal/convert-markdown', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ markdown: text })
                        })
                        .then(res => {
                            console.log('✅ Markdown API response status:', res.status);
                            return res.json();
                        })
                        .then(result => {
                            console.log('✅ Markdown API result:', result);
                            if (result.success) {
                                console.log('✅ HTML length:', result.html.length);
                                console.log('📄 HTML first 500 chars:', result.html.substring(0, 500));
                                // Fix relative image URLs
                                let html = result.html;
                                const beforeFix = html;
                                html = html.replace(/src="\/content\//g, 'src="https://ordinals.com/content/');
                                html = html.replace(/src='\/content\//g, "src='https://ordinals.com/content/");
                                if (html !== beforeFix) {
                                    console.log('✅ FIXED relative image URLs in frontend');
                                    console.log('📄 Fixed HTML first 500 chars:', html.substring(0, 500));
                                } else {
                                    console.log('⚠️  No relative URLs found to fix in frontend');
                                }
                                previewContent.innerHTML = `<div class="border p-3" style="max-height: 400px; overflow-y: auto;">${html}</div>`;
                                console.log('✅ HTML injected into DOM');
                            } else {
                                console.error('❌ Markdown conversion failed:', result.error);
                                // Fallback to plain text
                                previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                            }
                        })
                        .catch(err => {
                            console.error('❌ Error calling markdown API:', err);
                            // Fallback to plain text
                            previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                        });
                    } else {
                        console.log('→ DISPLAYING AS PLAIN TEXT');
                        previewContent.innerHTML = `<pre class="border p-3" style="max-height: 400px; overflow-y: auto;">${escapeHtml(text)}</pre>`;
                    }
                })
                .catch(err => {
                    console.error('Error fetching text:', err);
                    previewContent.innerHTML = `<div class="alert alert-danger">Error loading text: ${err.message}</div>`;
                });
        } else if (contentType.includes('text/markdown')) {
            console.log('→ RENDERING AS MARKDOWN');
            // Display markdown (convert to HTML)
            fetch(contentUrl)
                .then(res => res.text())
                .then(markdown => {
                    return fetch('/api/ordinal/convert-markdown', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ markdown })
                    });
                })
                .then(res => res.json())
                .then(result => {
                    if (result.success) {
                        // Fix relative image URLs to ordinals.com
                        let html = result.html;
                        html = html.replace(/src="\/content\//g, 'src="https://ordinals.com/content/');
                        html = html.replace(/src='\/content\//g, "src='https://ordinals.com/content/");
                        previewContent.innerHTML = `<div class="border p-3" style="max-height: 400px; overflow-y: auto;">${html}</div>`;
                    }
                });
        } else if (contentType.includes('text/html')) {
            console.log('→ RENDERING AS HTML');
            // Display HTML in sandboxed iframe
            previewContent.innerHTML = `<iframe src="${contentUrl}" sandbox="allow-same-origin" style="width: 100%; height: 400px; border: 1px solid var(--card-border);"></iframe>`;
        } else {
            console.log('→ UNSUPPORTED TYPE');
            previewContent.innerHTML = `<div class="alert alert-info">Content type: ${contentType}<br>Cannot preview this content type.</div>`;
        }
    }
    
    function displayMetadata(data) {
        document.getElementById('metaInscriptionId').textContent = data.inscriptionId;
        document.getElementById('metaInscriptionNumber').textContent = data.inscriptionNumber || 'N/A';
        document.getElementById('metaBlockHeight').textContent = data.blockHeight || 'N/A';
        document.getElementById('metaTimestamp').textContent = data.timestamp || 'N/A';
        document.getElementById('metaContentType').textContent = data.contentType;
        document.getElementById('metaContentSize').textContent = formatBytes(data.contentSize);
        previewMetadata.style.display = 'block';
    }
    
    function formatBytes(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
</script>
"""

@app.before_request
def deployment_safety_check():
    """Block data modifications during deployment"""
    if DEPLOYMENT_MODE and request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        # Allow deployment endpoints and static files
        if (request.path.startswith('/_deploy/') or
            request.path.startswith('/static/') or
            request.path in ['/login/', '/logout/']):
            return
        # Block all other data modifications
        print(f"🚨 BLOCKED {request.method} {request.path} - Deployment mode active")
        from flask import jsonify
        return jsonify({'error': 'Data modifications disabled during deployment'}), 403

def calculate_pages_and_words(file_path, filename, max_size_mb=50, timeout_seconds=30):
    """
    Calculate pages and words from a file.
    Returns: (pages, words) tuple
    Defaults to (1, 0) if calculation fails
    
    Security features:
    - File size limit (default 50MB)
    - Processing timeout (default 30s)
    - Safe error handling
    """
    try:
        # Check file size (security: prevent memory exhaustion)
        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            print(f"[WARNING] File too large: {file_size} bytes (max {max_size_bytes})")
            return (1, 0)
        
        _, ext = os.path.splitext(filename.lower())
        words = 0
        pages = 1
        
        # Use signal for timeout (Unix-like systems only)
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("File processing timeout")
        
        # Set timeout alarm (if supported)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
        
        try:
            if ext in ['.txt', '.xml']:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                words = len(content.split())
                pages = max(1, (words + 499) // 500)  # ~500 words per page
                
            elif ext == '.docx' and DOCX_SUPPORT:
                doc = docx.Document(file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = max(1, (words + 499) // 500)
                
            elif ext == '.pdf' and PDF_SUPPORT:
                reader = PyPDF2.PdfReader(file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = len(reader.pages) if reader.pages else max(1, (words + 499) // 500)
        finally:
            # Cancel timeout alarm
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
        
        return (pages, words)
        
    except TimeoutError:
        print(f"[WARNING] File processing timeout for {filename}")
        return (1, 0)
    except Exception as e:
        print(f"[WARNING] Failed to calculate pages/words for {filename}: {e}")
        return (1, 0)  # Default fallback

@app.route('/submit/', methods=['GET', 'POST'])
@require_auth
def submit_draft():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Generate working group options dynamically
    group_options = '<option value="">Select a Working Group</option>'
    for group in GROUPS:
        group_options += f'<option value="{group["acronym"]}">{group["name"]}</option>'

    # Replace the hardcoded options in the template (multiple occurrences for both tabs)
    submit_template = SUBMIT_TEMPLATE
    for _ in range(2):  # Replace in both upload and ordinal tabs
        submit_template = submit_template.replace(
            '''<option value="">Select a Working Group</option>
                                        <option value="httpbis">HTTP</option>
                                        <option value="quic">QUIC</option>
                                        <option value="tls">TLS</option>
                                        <option value="dnsop">DNSOP</option>
                                        <option value="rtgwg">RTGWG</option>''',
            group_options,
            1  # Replace only one occurrence at a time
        )

    if request.method == 'POST':
        # Get common fields
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        source_type = request.form.get('sourceType', 'file').strip()
        
        # Process authors (comma-separated)
        authors_list = [a.strip() for a in authors.split(',') if a.strip()]
        
        # Generate submission ID
        import random
        import string
        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Handle based on source type
        if source_type == 'ordinal':
            # Ordinal submission
            ordinal_id = request.form.get('ordinalId', '').strip()
            ordinal_content_url = request.form.get('ordinalContentUrl', '').strip()
            ordinal_content_type = request.form.get('ordinalContentType', '').strip()
            inscription_number = request.form.get('inscriptionNumber', '').strip()
            block_height = request.form.get('blockHeight', '').strip()
            inscription_timestamp = request.form.get('inscriptionTimestamp', '').strip()
            
            # Validation
            if not title or not authors or not ordinal_id:
                flash('Title, authors, and inscription ID are required', 'error')
                return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER)
            
            if not ordinal_content_url:
                flash('Please preview the ordinal before submitting', 'error')
                return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER)
            
            # Fetch ordinal content and calculate pages/words
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                    # Removed Accept-Encoding to avoid compression issues that cause wrong word counts
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=30)
                response.raise_for_status()
                content_text = response.text
                
                # Calculate pages and words from text
                word_count = len(content_text.split())
                chars_per_page = 3000
                page_count = max(1, (len(content_text) + chars_per_page - 1) // chars_per_page)
            except Exception as e:
                app.logger.error(f"Failed to fetch ordinal content for pages/words: {e}")
                # Use defaults if fetch fails
                page_count = 1
                word_count = 0
            
            # Create submission record with ordinal data
            current_user_info = get_current_user()
            app.logger.info(f"📝 CREATING SUBMISSION:")
            app.logger.info(f"   current_user_info: {current_user_info}")
            app.logger.info(f"   submitted_by will be: {current_user_info['name']}")
            
            # Get doc_type from form (default to 'draft')
            doc_type = request.form.get('doc_type', 'draft').strip() or 'draft'
            if doc_type not in ['draft', 'rfc']:
                doc_type = 'draft'
            
            submission = Submission(
                id=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                submitted_by=current_user_info['name'],
                sourceType='ordinal',
                doc_type=doc_type,
                ordinalId=ordinal_id,
                ordinalContentUrl=ordinal_content_url,
                ordinalContentType=ordinal_content_type,
                inscriptionNumber=int(inscription_number) if inscription_number else None,
                blockHeight=int(block_height) if block_height else None,
                inscriptionTimestamp=datetime.strptime(inscription_timestamp.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S') if inscription_timestamp else None,
                pages=page_count,
                words=word_count
            )
            
        else:
            # File upload submission
            file = request.files.get('file')
            
            # Validation
            if not title or not authors or not file:
                flash('Title, authors, and file are required', 'error')
                return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER)
            
            # Security: Check file size (max 50MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                flash(f'File too large. Maximum size is 50MB. Your file is {file_size / (1024*1024):.1f}MB.', 'error')
                return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER)
            
            # Save file
            filename = f"{submission_id}-{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Calculate pages and words
            pages, words = calculate_pages_and_words(file_path, filename)
            
            # Create submission record with file data
            submission = Submission(
                id=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                filename=filename,
                file_path=file_path,
                submitted_by=get_current_user()['name'],
                sourceType='file',
                pages=pages,
                words=words
            )
        
        # ML numbers are assigned only when submissions are approved, not on submission
        # submission.ml_number will remain None until approval
        
        # Save to database
        db.session.add(submission)
        db.session.commit()

        # Log the action
        source_desc = f"from ordinal {submission.ordinalId}" if source_type == 'ordinal' else "via file upload"
        add_to_document_history(f"draft-{submission_id}", "submitted", get_current_user()['name'], f"New draft submitted {source_desc}: {title}")

        flash('Draft submitted successfully!', 'success')
        return redirect(f'/submit/status/{submission_id}/')

    return BASE_TEMPLATE.format(title="Submit Internet-Draft - MLTF", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER)

@app.route('/submit/revision/<draft_name>/', methods=['GET', 'POST'])
@require_auth
def submit_revision(draft_name):
    """Submit a new revision of an existing draft"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    
    # Find the current draft
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    # If not found in DRAFTS, try to find as a submission
    submission = None
    if not draft:
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission and submission.status == 'approved':
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': ', '.join(submission.authors) if isinstance(submission.authors, list) else submission.authors,
                'abstract': submission.abstract or '',
                'group': submission.group or '',
                'rev': submission.revision_number or '00',
                'ml_number': submission.ml_number,
            }
        elif submission:
            flash('Cannot create revision of unapproved submission', 'error')
            return redirect(f'/submit/status/{submission.id}/')
    
    if not draft:
        flash('Draft not found', 'error')
        return redirect('/doc/all/')
    
    # Determine display ID (ML-Draft-XXX or internal ID)
    display_id = draft.get('ml_number', draft_name) or draft_name
    
    # Calculate new revision number
    current_rev = int(draft.get('rev', '00'))
    new_rev = f"{current_rev + 1:02d}"
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        what_changed = request.form.get('what_changed', '').strip()
        source_type = request.form.get('sourceType', 'file').strip()
        
        # Process authors
        authors_list = [a.strip() for a in authors.split(',') if a.strip()]
        
        # Generate submission ID
        import random
        import string
        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Handle based on source type
        if source_type == 'ordinal':
            # Ordinal submission
            ordinal_id = request.form.get('ordinalId', '').strip()
            ordinal_content_url = request.form.get('ordinalContentUrl', '').strip()
            ordinal_content_type = request.form.get('ordinalContentType', '').strip()
            inscription_number = request.form.get('inscriptionNumber', '').strip()
            block_height = request.form.get('blockHeight', '').strip()
            inscription_timestamp = request.form.get('inscriptionTimestamp', '').strip()
            
            # Validation
            if not title or not authors or not ordinal_id:
                flash('Title, authors, and inscription ID are required', 'error')
                return redirect(f'/submit/revision/{draft_name}/')
            
            if not ordinal_content_url:
                flash('Please preview the ordinal before submitting', 'error')
                return redirect(f'/submit/revision/{draft_name}/')
            
            # Fetch ordinal content and calculate pages/words
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=30)
                response.raise_for_status()
                content_text = response.text
                
                word_count = len(content_text.split())
                chars_per_page = 3000
                page_count = max(1, (len(content_text) + chars_per_page - 1) // chars_per_page)
            except Exception as e:
                app.logger.error(f"Failed to fetch ordinal content: {e}")
                page_count = 1
                word_count = 0
            
            # Create revision submission with ordinal data
            submission = Submission(
                id=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                submitted_by=get_current_user()['name'],
                sourceType='ordinal',
                doc_type='draft',
                ordinalId=ordinal_id,
                ordinalContentUrl=ordinal_content_url,
                ordinalContentType=ordinal_content_type,
                inscriptionNumber=int(inscription_number) if inscription_number else None,
                blockHeight=int(block_height) if block_height else None,
                inscriptionTimestamp=datetime.strptime(inscription_timestamp.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S') if inscription_timestamp else None,
                pages=page_count,
                words=word_count,
                # Revision fields
                parent_draft_name=draft_name,
                revision_number=new_rev,
                what_changed=what_changed,
                is_revision=True
            )
        else:
            # File upload submission
            file = request.files.get('file')
            
            # Validation
            if not title or not authors or not file:
                flash('Title, authors, and file are required', 'error')
                return redirect(f'/submit/revision/{draft_name}/')
            
            # Security: Check file size (max 50MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            max_size = 50 * 1024 * 1024
            if file_size > max_size:
                flash(f'File too large. Maximum size is 50MB.', 'error')
                return redirect(f'/submit/revision/{draft_name}/')
            
            # Save file
            filename = f"{submission_id}-{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Calculate pages and words
            pages, words = calculate_pages_and_words(file_path, filename)
            
            # Create revision submission with file data
            submission = Submission(
                id=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                filename=filename,
                file_path=file_path,
                submitted_by=get_current_user()['name'],
                sourceType='file',
                pages=pages,
                words=words,
                # Revision fields
                parent_draft_name=draft_name,
                revision_number=new_rev,
                what_changed=what_changed,
                is_revision=True
            )
        
        # Save to database
        db.session.add(submission)
        db.session.commit()
        
        # Log the action
        source_desc = f"from ordinal {submission.ordinalId}" if source_type == 'ordinal' else "via file upload"
        change_desc = f" Changes: {what_changed[:100]}" if what_changed else ""
        add_to_document_history(
            draft_name,
            "revision_submitted",
            get_current_user()['name'],
            f"Revision {new_rev} submitted {source_desc}.{change_desc}"
        )
        
        flash(f'Revision {new_rev} submitted successfully!', 'success')
        return redirect(f'/submit/status/{submission_id}/')
    
    # GET: Show form with pre-populated data
    # Generate working group options
    group_options = '<option value="">Select a Working Group</option>'
    for g in GROUPS:
        selected = 'selected' if g['acronym'] == draft.get('group', '') else ''
        group_options += f'<option value="{g["acronym"]}" {selected}>{g["name"]}</option>'
    
    revision_form = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{draft_name}</a></li>
                <li class="breadcrumb-item active">Submit Revision</li>
            </ol>
        </nav>
        
        <h1>Submit New Revision</h1>
        <p class="lead">Submit a new revision of {draft_name}</p>
        
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            <strong>Current Revision:</strong> {draft.get('rev', '00')} → <strong>New Revision:</strong> {new_rev}
        </div>
        
        <form method="POST" enctype="multipart/form-data" id="revisionForm">
            <div class="mb-3">
                <label class="form-label">Draft Name</label>
                <input type="text" class="form-control" value="{display_id}" disabled>
                <input type="hidden" name="draft_name" value="{draft_name}">
                <small class="form-text text-muted">This field cannot be changed for revisions</small>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Title *</label>
                <input type="text" class="form-control" name="title" value="{draft.get('title', '')}" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Authors *</label>
                <input type="text" class="form-control" name="authors" value="{draft.get('authors', '')}" required>
                <small class="form-text text-muted">Comma-separated list</small>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Abstract</label>
                <textarea class="form-control" name="abstract" rows="4">{draft.get('abstract', '')}</textarea>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Working Group</label>
                <select class="form-control" name="group">
                    {group_options}
                </select>
            </div>
            
            <div class="mb-3">
                <label class="form-label">What changed since the last revision?</label>
                <textarea class="form-control" name="what_changed" rows="3" 
                          placeholder="Example: Clarified workgroup role in determining rough consensus; added glossary; no change to core governance principles."></textarea>
                <small class="form-text text-muted">
                    Optional but recommended. Briefly describe substantive changes so reviewers and future readers 
                    can understand what evolved and why. Not required for minor or editorial edits.
                </small>
            </div>
            
            <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item">
                    <a class="nav-link active" data-bs-toggle="tab" href="#upload" onclick="document.getElementById('sourceType').value='file'">Upload File</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#ordinal" onclick="document.getElementById('sourceType').value='ordinal'">Bitcoin Ordinal</a>
                </li>
            </ul>
            
            <div class="tab-content mt-3">
                <div id="upload" class="tab-pane active">
                    <div class="mb-3">
                        <label class="form-label">Upload Document *</label>
                        <input type="file" class="form-control" name="file" accept=".txt,.pdf,.xml,.docx">
                        <small class="form-text text-muted">Supported formats: TXT, PDF, XML, DOCX</small>
                    </div>
                </div>
                
                <div id="ordinal" class="tab-pane">
                    <div class="mb-3">
                        <label class="form-label">Inscription ID *</label>
                        <input type="text" class="form-control" name="ordinalId" id="ordinalId" 
                               placeholder="e.g., 6fb976ab49dcec017f1e201e84395983204ae1a7c2abf7ced0a85d692e442799i0">
                        <small class="form-text text-muted">The unique inscription ID from Bitcoin</small>
                    </div>
                    
                    <div class="mb-3">
                        <button type="button" class="btn btn-secondary" onclick="previewOrdinal()">
                            <i class="fas fa-eye me-1"></i>Preview Ordinal
                        </button>
                    </div>
                    
                    <div id="ordinalPreview" class="mb-3" style="display: none;">
                        <div class="card">
                            <div class="card-header">
                                <h6>Ordinal Preview</h6>
                            </div>
                            <div class="card-body">
                                <div id="ordinalContent"></div>
                                <input type="hidden" name="ordinalContentUrl" id="ordinalContentUrl">
                                <input type="hidden" name="ordinalContentType" id="ordinalContentType">
                                <input type="hidden" name="inscriptionNumber" id="inscriptionNumber">
                                <input type="hidden" name="blockHeight" id="blockHeight">
                                <input type="hidden" name="inscriptionTimestamp" id="inscriptionTimestamp">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <input type="hidden" name="sourceType" value="file" id="sourceType">
            
            <div class="mt-4">
                <button type="submit" class="btn btn-success btn-lg">
                    <i class="fas fa-upload me-2"></i>Submit Revision
                </button>
                <a href="/doc/draft/{draft_name}/" class="btn btn-secondary btn-lg ms-2">Cancel</a>
            </div>
        </form>
    </div>
    
    <script>
    async function previewOrdinal() {{
        const inscriptionId = document.getElementById('ordinalId').value.trim();
        if (!inscriptionId) {{
            alert('Please enter an inscription ID');
            return;
        }}
        
        // Show loading
        const preview = document.getElementById('ordinalPreview');
        const content = document.getElementById('ordinalContent');
        content.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading ordinal...</div>';
        preview.style.display = 'block';
        
        try {{
            // Use our API endpoint to fetch ordinal metadata
            const response = await fetch('/api/ordinal/preview', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{ inscriptionId }})
            }});
            
            const data = await response.json();
            
            if (!data.success) {{
                content.innerHTML = `<div class="alert alert-danger">Error: ${{data.error}}</div>`;
                return;
            }}
            
            // Fill in hidden form fields
            document.getElementById('ordinalContentUrl').value = data.contentUrl;
            document.getElementById('ordinalContentType').value = data.contentType;
            document.getElementById('inscriptionNumber').value = data.inscriptionNumber || '';
            document.getElementById('blockHeight').value = data.blockHeight || '';
            document.getElementById('inscriptionTimestamp').value = data.timestamp || '';
            
            // Fetch and display content
            const contentResponse = await fetch(data.contentUrl);
            const contentText = await contentResponse.text();
            
            // Check if it's markdown
            const isMarkdown = data.contentType.includes('markdown') || data.contentType.includes('text/plain');
            
            if (isMarkdown) {{
                // Convert markdown to HTML
                const convertResponse = await fetch('/api/ordinal/convert-markdown', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ markdown: contentText }})
                }});
                
                const convertData = await convertResponse.json();
                
                if (convertData.success) {{
                    content.innerHTML = `
                        <div class="alert alert-info">
                            <strong>Preview:</strong> Inscription #${{data.inscriptionNumber}} | 
                            Block: ${{data.blockHeight}} | 
                            Size: ${{(data.contentSize / 1024).toFixed(2)}} KB
                        </div>
                        <div class="document-content" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 1em; line-height: 1.6; max-height: 600px; overflow-y: auto; padding: 20px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--input-bg);">
                            ${{convertData.html}}
                        </div>
                    `;
                }} else {{
                    content.innerHTML = `<pre style="max-height: 400px; overflow-y: auto;">${{contentText.substring(0, 2000)}}</pre>`;
                }}
            }} else {{
                content.innerHTML = `<pre style="max-height: 400px; overflow-y: auto;">${{contentText.substring(0, 2000)}}</pre>`;
            }}
            
        }} catch (error) {{
            content.innerHTML = `<div class="alert alert-danger">Error loading ordinal: ${{error.message}}</div>`;
        }}
    }}
    </script>
    """
    
    return BASE_TEMPLATE.format(title=f"Submit Revision - {draft_name}", theme=current_theme, user_menu=user_menu, content=revision_form, build_number=BUILD_NUMBER)

SUBMISSION_STATUS_TEMPLATE = """
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item"><a href="/submit/">Submit Draft</a></li>
            <li class="breadcrumb-item active">Submission Status</li>
        </ol>
    </nav>
    
    <h1>Submission Status</h1>
    <p class="lead">Track your Internet-Draft submission</p>

    <div id="flash-messages"></div>
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>
                        Submission Details
                        {% if is_revision %}
                        <span class="badge bg-success ms-2">Revision {{ revision_number }}</span>
                        {% endif %}
                    </h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submission ID:</strong></div>
                        <div class="col-sm-9"><code>{{ submission.id }}</code></div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Status:</strong></div>
                        <div class="col-sm-9">
                            <span class="badge bg-primary">{{ submission_status_title }}</span>
                            {% if is_ordinal %}
                            <span class="badge bg-info ms-2"><i class="bi bi-coin"></i> Ordinal</span>
                            {% else %}
                            <span class="badge bg-secondary ms-2"><i class="bi bi-file-earmark"></i> File</span>
                            {% endif %}
                        </div>
                    </div>
                    {% if is_revision %}
                    <div class="alert alert-info mb-3">
                        <strong><i class="fas fa-code-branch me-2"></i>This is a revision</strong><br>
                        Revision <strong>{{ revision_number }}</strong> of
                        <a href="/doc/draft/{{ parent_draft_name }}/">{{ parent_draft_name }}</a>
                    </div>
                    {% endif %}
                    {% if what_changed %}
                    <div class="card mb-3">
                        <div class="card-header">
                            <strong>What changed (submitter's explanation)</strong>
                        </div>
                        <div class="card-body">
                            <p class="mb-0">{{ what_changed }}</p>
                        </div>
                    </div>
                    {% endif %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Title:</strong></div>
                        <div class="col-sm-9">{{ submission_title }}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Authors:</strong></div>
                        <div class="col-sm-9">{{ submission_authors_joined }}</div>
                    </div>
                    {% if ml_number %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>ML Number:</strong></div>
                        <div class="col-sm-9"><code>{{ ml_number }}</code></div>
                    </div>
                    {% endif %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Draft ID:</strong></div>
                        <div class="col-sm-9"><code>{{ submission_id }}</code></div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submitted:</strong></div>
                        <div class="col-sm-9">{{ submission_submitted_at }}</div>
                    </div>
                    {% if is_file %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>File:</strong></div>
                        <div class="col-sm-9">
                            <code>{{ submission_filename }}</code>
                            <a href="/download/{{ submission_id }}" class="btn btn-sm btn-outline-primary ms-2">Download</a>
                        </div>
                    </div>
                    {% endif %}
                    {% if submission_abstract %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Abstract:</strong></div>
                        <div class="col-sm-9">{{ submission_abstract }}</div>
                    </div>
                    {% endif %}

                    {% if is_ordinal %}
                    <h6 class="mt-4">Ordinal Metadata</h6>
                    <div class="card mb-3" style="background-color: var(--bg-secondary);">
                        <div class="card-body">
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Inscription ID:</strong></div>
                                <div class="col-sm-8">
                                    <a href="https://ordinals.com/inscription/{{ ordinal_id }}" target="_blank" class="text-decoration-none" style="color: var(--accent-color);">
                                        <code style="font-size: 0.85em;">{{ ordinal_id_short }}</code>
                                    </a>
                                </div>
                            </div>
                            {% if inscription_number %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Inscription Number:</strong></div>
                                <div class="col-sm-8">{{ inscription_number }}</div>
                            </div>
                            {% endif %}
                            {% if block_height %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Block Height:</strong></div>
                                <div class="col-sm-8">{{ block_height }}</div>
                            </div>
                            {% endif %}
                            {% if inscription_timestamp %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Timestamp:</strong></div>
                                <div class="col-sm-8">{{ inscription_timestamp }}</div>
                            </div>
                            {% endif %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Content Type:</strong></div>
                                <div class="col-sm-8"><code>{{ ordinal_content_type }}</code></div>
                            </div>
                            <div class="row">
                                <div class="col-sm-12">
                                    <a href="https://ordinals.com/inscription/{{ ordinal_id }}" target="_blank" class="btn btn-sm btn-outline-primary">
                                        <i class="bi bi-box-arrow-up-right"></i> View on Ordinals.com
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endif %}

                    <h6 class="mt-4">Content Preview</h6>
                    {% if content_preview_html %}
                    <div class="border rounded p-3" style="background-color: var(--input-bg); border-color: var(--input-border);">
                        {{ content_preview_html|safe }}
                    </div>
                    {% else %}
                    <div class="border rounded p-3" style="background-color: var(--input-bg); border-color: var(--input-border);">
                        <pre class="mb-0" style="font-size: 0.9em; max-height: 400px; overflow-y: auto; color: var(--text-primary);">{{ file_content }}</pre>
                    </div>
                    {% endif %}

                    {% if is_submitted and is_admin %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Actions:</strong></div>
                        <div class="col-sm-9">
                            <form method="POST" action="/submit/approve/{{ submission_id }}" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">Approve & Publish</button>
                            </form>
                            <form method="POST" action="/submit/reject/{{ submission_id }}" style="display: inline; margin-left: 10px;">
                                <button type="submit" class="btn btn-danger btn-sm">Reject</button>
                            </form>
                        </div>
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5>Review Timeline</h5>
                </div>
                <div class="card-body">
                    <div class="timeline">
                        <div class="timeline-item">
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Submitted</h6>
                                <p class="text-muted small">{{ submission_submitted_at }}</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            {% if is_approved_or_rejected %}
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">
                                    {% if is_approved %}Completed{% else %}Rejected{% endif %}
                                    {% if submission_approved_at %}
                                    - {{ submission_approved_at }}
                                    {% elif submission_rejected_at %}
                                    - {{ submission_rejected_at }}
                                    {% endif %}
                                </p>
                            </div>
                            {% else %}
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">In Progress</p>
                            </div>
                            {% endif %}
                        </div>
                        {% if is_approved %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-primary"></div>
                            <div class="timeline-content">
                                <h6>Published</h6>
                                <p class="text-muted small">Available in document repository</p>
                            </div>
                        </div>
                        {% else %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Working Group Review</h6>
                                <p class="text-muted small">Pending initial approval</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>MLSG Review</h6>
                                <p class="text-muted small">Pending working group review</p>
                            </div>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Actions</h5>
                </div>
                <div class="card-body">
                    <a href="/submit/" class="btn btn-primary w-100 mb-2">Submit Another Draft</a>
                    <a href="/doc/all/" class="btn btn-outline-secondary w-100 mb-2">View All Documents</a>
                    <a href="/" class="btn btn-outline-secondary w-100">Back to Home</a>
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5>Need Help?</h5>
                </div>
                <div class="card-body">
                    <p class="small">If you have questions about your submission:</p>
                    <ul class="small">
                        <li>Check the <a href="#" target="_blank">submission guidelines</a></li>
                        <li>Contact the <a href="mailto:draft@metalayer.org">MLTF Secretariat</a></li>
                        <li>Join the <a href="#" target="_blank">MLTF discussion list</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.timeline {
    position: relative;
    padding-left: 30px;
}

.timeline-item {
    position: relative;
    margin-bottom: 20px;
}

.timeline-marker {
    position: absolute;
    left: -25px;
    top: 5px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 2px #dee2e6;
}

.timeline-content h6 {
    margin-bottom: 5px;
    font-weight: 600;
}

.timeline-content p {
    margin-bottom: 0;
}
</style>
"""

@app.route('/submit/status/')
@require_auth
def submission_status():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Get user's submissions
    user_name = get_current_user()['name']
    submissions = Submission.query.filter_by(submitted_by=user_name).order_by(Submission.submitted_at.desc()).all()

    # Format submissions for template
    submissions_html = ""
    for submission in submissions:
        status_badge = {
            'submitted': 'badge bg-warning text-dark',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger',
            'published': 'badge bg-info'
        }.get(submission.status, 'badge bg-secondary')
        
        # Get source type
        source_type = getattr(submission, 'sourceType', 'file')
        source_badge = '<span class="badge bg-info ms-2"><i class="bi bi-coin"></i> Ordinal</span>' if source_type == 'ordinal' else '<span class="badge bg-secondary ms-2"><i class="bi bi-file-earmark"></i> File</span>'
        
        # Get revision info
        is_revision = getattr(submission, 'is_revision', False)
        revision_number = getattr(submission, 'revision_number', '')
        parent_draft_name = getattr(submission, 'parent_draft_name', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''
        
        # Get source info (inscription number or filename)
        if source_type == 'ordinal':
            inscription_number = getattr(submission, 'inscriptionNumber', None)
            ordinal_id = getattr(submission, 'ordinalId', None)
            if inscription_number:
                source_info = f'<p class="mb-2"><strong>Inscription:</strong> #{inscription_number}</p>'
            elif ordinal_id:
                shortened_id = shorten_inscription_id(ordinal_id, 8)
                source_info = f'<p class="mb-2"><strong>Inscription:</strong> <a href="https://ordinals.com/inscription/{ordinal_id}" target="_blank" class="text-decoration-none"><code>{shortened_id}</code></a></p>'
            else:
                source_info = ''
        else:
            filename = getattr(submission, 'filename', None)
            source_info = f'<p class="mb-2"><strong>File:</strong> {filename}</p>' if filename else '<p class="mb-2 text-muted"><em>No file</em></p>'

        submissions_html += f"""
        <div class="submission-item">
            <div class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <a href="/submit/status/{submission.id}/" class="text-decoration-none">
                            {submission.title}
                        </a>
                    </h6>
                    <div>
                        <span class="{status_badge}">{submission.status.title()}</span>
                        {source_badge}
                        {revision_badge}
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-8">
                            <p class="mb-2"><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                            <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                            <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')}</p>
                            {source_info}
                            {f'<p class="mb-2"><strong>Abstract:</strong> {submission.abstract[:100]}...</p>' if submission.abstract else ''}
                        </div>
                        <div class="col-md-4 text-end">
                            <a href="/submit/status/{submission.id}/" class="btn btn-sm btn-primary me-2">View Details</a>
                            <a href="/doc/draft/{submission.id}/" class="btn btn-sm btn-outline-primary">View Draft</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/submit/">Submit Draft</a></li>
                <li class="breadcrumb-item active">My Submissions</li>
            </ol>
        </nav>

        <h1>My Submissions</h1>

        {f'<div class="alert alert-info">You have {len(submissions)} submission(s).</div>' if submissions else '<div class="alert alert-info">You have no submissions yet.</div>'}

        {submissions_html}

        <div class="mt-4">
            <a href="/submit/" class="btn btn-primary">Submit Another Draft</a>
            <a href="/" class="btn btn-secondary ms-2">Back to Home</a>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(title="My Submissions - MLTF", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/submit/status/<submission_id>/')
@require_auth
def submission_detail(submission_id):
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    current_user = get_current_user()

    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        return "Submission not found", 404

    # Check if user owns this submission or is admin
    app.logger.info(f"🔐 ACCESS CHECK:")
    app.logger.info(f"   submission.submitted_by: {submission.submitted_by}")
    app.logger.info(f"   current_user['name']: {current_user['name']}")
    app.logger.info(f"   current_user.get('role'): {current_user.get('role')}")
    app.logger.info(f"   Match: {submission.submitted_by == current_user['name']}")
    
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        app.logger.warning(f"❌ ACCESS DENIED!")
        return "Access denied", 403
    
    app.logger.info(f"✅ ACCESS GRANTED")

    # Handle content preview based on source type
    file_content = "File preview not available"
    content_preview_html = ""
    source_type = getattr(submission, 'sourceType', 'file')
    
    print(f"=== BACKEND DEBUG: submission_detail ===")
    print(f"source_type: {source_type}")
    
    if source_type == 'ordinal':
        # Ordinal content - generate preview HTML
        ordinal_content_type = getattr(submission, 'ordinalContentType', '')
        ordinal_content_url = getattr(submission, 'ordinalContentUrl', '')
        
        print(f"ordinal_content_type: {ordinal_content_type}")
        print(f"ordinal_content_url: {ordinal_content_url}")
        
        if ordinal_content_type.startswith('image/'):
            print("→ Rendering as image")
            content_preview_html = f'<img src="{ordinal_content_url}" class="img-fluid" style="max-height: 400px;" alt="Ordinal content">'
        elif 'text/plain' in ordinal_content_type or 'text/javascript' in ordinal_content_type or 'application/json' in ordinal_content_type or 'application/javascript' in ordinal_content_type:
            print("→ Rendering as text/plain or text/javascript or application/json")
            # Fetch and display text-based content (handles charset parameters)
            try:
                import markdown2
                import bleach
                import re
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                text_content = response.text
                print(f"Text content length: {len(text_content)}")
                print(f"First 100 chars: {text_content[:100]}")
                
                # Check if content is markdown
                is_markdown = False
                if 'text/plain' in ordinal_content_type:
                    # Detect markdown patterns
                    markdown_patterns = [
                        r'^#{1,6}\s+.+$',  # Headers
                        r'\*\*.+\*\*',      # Bold
                        r'\*.+\*',          # Italic
                        r'^\s*[-*+]\s+',    # Lists
                        r'^\s*\d+\.\s+',    # Numbered lists
                        r'\[.+\]\(.+\)',    # Links
                        r'!\[.*\]\(.+\)'    # Images
                    ]
                    for pattern in markdown_patterns:
                        if re.search(pattern, text_content, re.MULTILINE):
                            is_markdown = True
                            print(f"→ DETECTED MARKDOWN (pattern: {pattern})")
                            break
                
                if is_markdown:
                    # Convert markdown to HTML
                    html_content = markdown2.markdown(text_content, extras=['fenced-code-blocks', 'tables', 'break-on-newline'])
                    
                    # Sanitize HTML
                    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                  'ul', 'ol', 'li', 'a', 'img', 'code', 'pre', 'blockquote', 'table',
                                  'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div', 'span']
                    allowed_attrs = {'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'title', 'width', 'height']}
                    html_content = bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
                    
                    # Fix relative image URLs to point to ordinals.com
                    html_content = re.sub(
                        r'src="(/content/[^"]+)"',
                        r'src="https://ordinals.com\1"',
                        html_content
                    )
                    
                    content_preview_html = f'<div class="border p-3" style="max-height: 400px; overflow-y: auto;">{html_content}</div>'
                    file_content = ""  # Clear file_content since we're using content_preview_html
                else:
                    # Display as plain text
                    if len(text_content) > 2000:
                        file_content = text_content[:2000] + "..."
                    else:
                        file_content = text_content
                print(f"file_content set, length: {len(file_content) if file_content else 0}")
            except Exception as e:
                print(f"ERROR fetching text content: {e}")
                file_content = "Error loading ordinal text content"
        elif 'text/markdown' in ordinal_content_type:
            # Fetch, convert, and display markdown
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                markdown_text = response.text
                if MARKDOWN_SUPPORT:
                    html_content = markdown2.markdown(
                        markdown_text,
                        extras=['fenced-code-blocks', 'tables', 'break-on-newline']
                    )
                    content_preview_html = f'<div class="border p-3" style="max-height: 400px; overflow-y: auto;">{html_content}</div>'
                else:
                    file_content = markdown_text[:2000] + ("..." if len(markdown_text) > 2000 else "")
            except:
                file_content = "Error loading ordinal markdown content"
        elif 'text/html' in ordinal_content_type:
            print("→ Rendering as HTML iframe")
            # Display HTML in iframe (handles charset parameters)
            content_preview_html = f'<iframe src="{ordinal_content_url}" sandbox="allow-same-origin" style="width: 100%; height: 400px; border: 1px solid var(--card-border);"></iframe>'
        else:
            print(f"→ UNSUPPORTED content type")
            file_content = f"Ordinal content type: {ordinal_content_type}\\nPreview not available for this content type."
    
    elif submission.file_path and os.path.exists(submission.file_path):
        # File upload - extract text for preview
        _, ext = os.path.splitext(submission.filename.lower())

        try:
            if ext in ['.txt', '.xml']:
                # Text-based files can be previewed directly
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    # Limit preview to first 2000 characters
                    if len(content) > 2000:
                        file_content = content[:2000] + "..."
                    else:
                        file_content = content

            elif ext == '.docx':
                # Extract text from DOCX files
                from docx import Document
                doc = Document(submission.file_path)
                content = ""
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content += paragraph.text + "\n"

                # Also check tables for content
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content += cell.text + "\n"

                if content.strip():
                    # Limit preview to first 2000 characters
                    if len(content) > 2000:
                        file_content = content[:2000] + "..."
                    else:
                        file_content = content
                else:
                    file_content = "DOCX file appears to be empty or contains no extractable text."

            elif ext == '.pdf':
                # For PDFs, use embedded viewer instead of text extraction
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                
                # Create an embedded PDF viewer
                content_preview_html = f'''
                <div class="pdf-viewer-container">
                    <div class="alert alert-info mb-3">
                        <i class="bi bi-file-pdf"></i> PDF Document ({file_size_kb:.1f} KB) - 
                        <a href="/download/{submission.id}" class="alert-link">Download PDF</a> for best viewing experience
                    </div>
                    <iframe src="/view/{submission.id}" 
                            type="application/pdf" 
                            style="width: 100%; height: 600px; border: 1px solid var(--card-border);"
                            title="PDF Preview">
                        <p>Your browser does not support PDF preview. 
                           <a href="/download/{submission.id}">Download the PDF</a> to view it.</p>
                    </iframe>
                </div>
                '''
                file_content = ""  # Clear file_content since we're using content_preview_html

            elif ext == '.doc':
                # Legacy DOC files - show file info
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                file_content = f"Legacy DOC file ({file_size_kb:.1f} KB)\\nText extraction not supported for legacy .doc format.\\nPlease convert to .docx for text preview."

            else:
                # Unknown file type
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                file_content = f"Unsupported file type: {ext} ({file_size_kb:.1f} KB)\\nPreview not available."

        except Exception as e:
            file_size = os.path.getsize(submission.file_path)
            file_size_kb = file_size / 1024
            file_content = f"Error extracting text from {ext[1:].upper()} file ({file_size_kb:.1f} KB): {str(e)}"

    # Use Flask's Jinja2 render_template_string properly - BEST PRACTICE
    # Prepare template variables
    template_vars = {
        'submission': submission,
        'current_user': current_user,
        'file_content': file_content,
        'content_preview_html': content_preview_html,
        'submission_id': submission.id,
        'submission_status': submission.status,
        'submission_status_title': submission.status.title(),
        'submission_title': submission.title or '',
        'submission_abstract': submission.abstract or '',
        'submission_authors': submission.authors,
        'submission_authors_joined': ', '.join(submission.authors) if submission.authors else '',
        'submission_draft_name': getattr(submission, 'draft_name', submission.id) or '',
        'submission_submitted_at': submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if submission.submitted_at else '',
        'submission_filename': submission.filename or '',
        'submission_approved_at': submission.approved_at.strftime('%Y-%m-%d %H:%M:%S') if submission.approved_at else '',
        'submission_rejected_at': submission.rejected_at.strftime('%Y-%m-%d %H:%M:%S') if submission.rejected_at else '',
        'is_admin': current_user and (current_user.get('role') in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']),
        'is_approved': submission.status == 'approved',
        'is_rejected': submission.status == 'rejected',
        'is_approved_or_rejected': submission.status in ['approved', 'rejected'],
        'is_submitted': submission.status == 'submitted',
        # Ordinal-specific fields
        'source_type': source_type,
        'is_ordinal': source_type == 'ordinal',
        'is_file': source_type == 'file',
        'ordinal_id': getattr(submission, 'ordinalId', ''),
        'ordinal_id_short': shorten_inscription_id(getattr(submission, 'ordinalId', ''), 8),
        'ordinal_content_url': getattr(submission, 'ordinalContentUrl', ''),
        'ordinal_content_type': getattr(submission, 'ordinalContentType', ''),
        'inscription_number': getattr(submission, 'inscriptionNumber', None),
        'block_height': getattr(submission, 'blockHeight', None),
        'inscription_timestamp': getattr(submission, 'inscriptionTimestamp', None),
        'ml_number': submission.ml_number,
        # Revision fields
        'is_revision': getattr(submission, 'is_revision', False),
        'parent_draft_name': getattr(submission, 'parent_draft_name', ''),
        'revision_number': getattr(submission, 'revision_number', ''),
        'what_changed': getattr(submission, 'what_changed', '')
    }
    
    # Render the submission status template using Flask's Jinja2 engine
    # This properly handles all conditionals and preserves HTML structure
    rendered_content = render_template_string(SUBMISSION_STATUS_TEMPLATE, **template_vars)
    
    # Now use the rendered content in BASE_TEMPLATE (which uses Python .format())
    return BASE_TEMPLATE.format(title=f"Submission {submission.id} - MLTF", theme=current_theme, user_menu=user_menu, content=rendered_content, build_number=BUILD_NUMBER)

LOGIN_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Sign In</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>

                    <!-- Single Web3Auth Sign In Button -->
                    <div class="mb-4 text-center">
                        <p class="text-muted mb-3">Connect your account to continue</p>
                        <button type="button" class="btn btn-primary btn-lg" id="web3auth-signin-btn" onclick="loginWithWeb3Auth()">
                            <svg width="20" height="20" class="me-2" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;">
                                <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 18c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z"/>
                            </svg>
                            Sign In with Web3Auth
                        </button>
                        <p class="text-muted mt-3 small">Sign in with Google, Twitter, Email, or connect your wallet</p>
                    </div>

                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Web3Auth Integration
let web3auth = null;

// Function to load script dynamically
function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = () => resolve();
        script.onerror = (e) => reject(e);
        document.head.appendChild(script);
    });
}

// Initialize Web3Auth after ensuring scripts are loaded
async function initWeb3Auth() {
    try {
        // Load Web3 first
        await loadScript('https://cdn.jsdelivr.net/npm/web3@1.10.0/dist/web3.min.js');

        // Load Web3Auth Modal
        await loadScript('https://unpkg.com/@web3auth/modal@10.13.1/dist/modal.umd.min.js');

        // Wait for Web3Auth to be available
        await new Promise(resolve => {
            const checkWeb3Auth = () => {
                if (window.Modal && window.Modal.Web3Auth) {
                    resolve();
                } else {
                    setTimeout(checkWeb3Auth, 100);
                }
            };
            checkWeb3Auth();
        });

        const Web3AuthConstructor = window.Modal.Web3Auth;

        const web3AuthConfig = {
            clientId: "BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk",
            web3AuthNetwork: 'sapphire_devnet',
            chainConfig: {
                chainNamespace: 'eip155',
                chainId: '0x1',
                rpcTarget: 'https://rpc.ankr.com/eth',
                displayName: 'Ethereum Mainnet',
                blockExplorerUrl: 'https://etherscan.io',
                ticker: 'ETH',
                tickerName: 'Ethereum',
            },
            // Disable modal for direct provider login
            modal: false,
            uiConfig: {
                theme: 'dark',
                loginMethodsOrder: ['google', 'twitter', 'email_passwordless', 'wallet'],
                defaultLanguage: 'en',
            },
            // Force account selection for Google OAuth
            loginConfig: {
                google: {
                    verifier: 'web3auth-google-sapphire-devnet',
                    typeOfLogin: 'google',
                    clientId: 'BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk',
                    // Force account selection and re-authentication
                    extraLoginOptions: {
                        prompt: 'login select_account',
                        access_type: 'offline'
                    },
                    // Also try query parameters
                    queryParameters: {
                        prompt: 'login select_account',
                        access_type: 'offline'
                    }
                }
            },
        };

        web3auth = new Web3AuthConstructor(web3AuthConfig);
        await web3auth.init();

        console.log('Web3Auth initialized successfully');

    } catch (error) {
        console.error('Web3Auth initialization failed:', error);
    }
}

async function loginWithWeb3Auth(buttonType) {
    if (!web3auth) {
        alert("Web3Auth not initialized. Please refresh the page.");
        return;
    }

    try {
        // Update button to show loading
        const btn = document.getElementById(buttonType + '-login-btn');
        if (btn) {
            btn.innerHTML = 'Connecting...';
        }

        // Connect to Web3Auth with specific login provider
        let loginProvider = null;
        if (buttonType === 'google') loginProvider = 'google';
        else if (buttonType === 'twitter') loginProvider = 'twitter';
        else if (buttonType === 'email') loginProvider = 'email_passwordless';
        else if (buttonType === 'wallet') loginProvider = 'wallet';

        // Connect directly to provider with forced auth
        console.log("Connecting directly to:", loginProvider);
        const web3authProvider = await web3auth.connect({
            loginProvider,
            extraLoginOptions: {
                prompt: 'login select_account',
                access_type: 'offline'
            }
        });

        if (web3authProvider) {
            // Get user info
            const userInfo = await web3auth.getUserInfo();

            // Get wallet address for wallet logins
            let walletAddress = null;
            try {
                const web3 = new Web3(web3authProvider);
                const accounts = await web3.eth.getAccounts();
                walletAddress = accounts[0];
            } catch (walletError) {
                console.log("No wallet address available:", walletError.message);
            }

            // Determine login type
            let loginType = 'unknown';
            if (userInfo.groupedAuthConnectionId) {
                if (userInfo.groupedAuthConnectionId.includes('google')) {
                    loginType = 'google';
                } else if (userInfo.groupedAuthConnectionId.includes('twitter')) {
                    loginType = 'twitter';
                } else if (userInfo.groupedAuthConnectionId.includes('email')) {
                    loginType = 'email';
                } else if (userInfo.groupedAuthConnectionId.includes('wallet')) {
                    loginType = 'wallet';
                }
            } else if (walletAddress) {
                loginType = 'wallet';
            }

            // Send user data to backend
            const requestData = {
                verifierId: userInfo.verifierId || userInfo.groupedAuthConnectionId || `user_${Date.now()}`,
                typeOfLogin: loginType,
                email: userInfo.email,
                name: userInfo.name,
                profileImage: userInfo.profileImage,
                oauthName: userInfo.name,
                evmAddress: walletAddress
            };

            const response = await fetch('/api/auth/web3auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            if (response.ok) {
                // Update button to show final success
                if (btn) {
                    btn.innerHTML = 'Success! Redirecting...';
                }
                // Redirect after a short delay
                setTimeout(() => {
                    window.location.href = '/';
                }, 1000);
            } else {
                const error = await response.json().catch(() => ({}));
                alert('Login failed: ' + (error.error || 'Unknown error'));

                // Reset button
                if (btn) {
                    if (buttonType === 'google') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>Continue with Google';
                    else if (buttonType === 'twitter') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/></svg>Continue with X (Twitter)';
                    else if (buttonType === 'email') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>Continue with Email';
                    else if (buttonType === 'wallet') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M21 7.28V5c0-1.1-.9-2-2-2H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-2.28c.59-.35 1-.98 1-1.72V9c0-.74-.41-1.37-1-1.72zM20 9v6h-7V9h7zM5 7h14v10H5V7z"/><circle cx="16" cy="12" r="1.5"/></svg>Connect Wallet';
                }
            }
        }
    } catch (error) {
        console.error('Web3Auth login error:', error);
        alert('Login failed: ' + error.message);

        // Reset button
        const btn = document.getElementById(buttonType + '-login-btn');
        if (btn) {
            if (buttonType === 'google') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>Continue with Google';
            else if (buttonType === 'twitter') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/></svg>Continue with X (Twitter)';
            else if (buttonType === 'email') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>Continue with Email';
            else if (buttonType === 'wallet') btn.innerHTML = '<svg width="18" height="18" class="me-2" viewBox="0 0 24 24" fill="currentColor"><path d="M21 7.28V5c0-1.1-.9-2-2-2H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-2.28c.59-.35 1-.98 1-1.72V9c0-.74-.41-1.37-1-1.72zM20 9v6h-7V9h7zM5 7h14v10H5V7z"/><circle cx="16" cy="12" r="1.5"/></svg>Connect Wallet';
        }
    }
}

// Initialize Web3Auth when page loads
document.addEventListener('DOMContentLoaded', () => {
    initWeb3Auth();
});
</script>
"""

REGISTER_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Create Account</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required minlength="6">
                        </div>
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Create Account</button>
                        </div>
                    </form>
                    
                    <hr>
                    <div class="text-center">
                        <p class="mb-0">Already have an account? <a href="/login/">Sign in</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

PROFILE_TEMPLATE = """
<div class="container mt-4">
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">User Profile</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <!-- Profile Information -->
                    <h5>Profile Information</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_profile">
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" value="{current_user_name}" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" value="{current_user_email}" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" value="{session_user}" readonly>
                        </div>
                        <button type="submit" class="btn btn-primary">Update Profile</button>
                    </form>
                    
                    <hr>
                    
                    <!-- Password Change -->
                    <h5>Change Password</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_password">
                        <div class="mb-3">
                            <label for="old_password" class="form-label">Current Password</label>
                            <input type="password" class="form-control" id="old_password" name="old_password" required>
                        </div>
                        <div class="mb-3">
                            <label for="new_password" class="form-label">New Password</label>
                            <input type="password" class="form-control" id="new_password" name="new_password" required minlength="6">
                        </div>
                        <button type="submit" class="btn btn-warning">Change Password</button>
                    </form>

                    <hr>

                    <!-- Theme Preferences -->
                    <h5>Theme Preferences</h5>
                    <form method="POST">
                        <input type="hidden" name="action" value="update_theme">
                        <div class="mb-3">
                            <label class="form-label">Preferred Theme</label>
                            <select class="form-select" name="theme" id="theme-select">
                                <option value="light" {light_selected}>Light Mode</option>
                                <option value="dark" {dark_selected}>Dark Mode</option>
                                <option value="auto" {auto_selected}>Auto (System)</option>
                            </select>
                            <div class="form-text">Choose your preferred theme. Auto will follow your system's preference.</div>
                        </div>
                        <button type="submit" class="btn btn-secondary">Save Theme Preference</button>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Account Status</h5>
                </div>
                <div class="card-body">
                    <p><strong>Username:</strong> {session_user}</p>
                    <p><strong>Name:</strong> {current_user_name}</p>
                    <p><strong>Email:</strong> {current_user_email}</p>
                    <p><strong>Status:</strong> <span class="badge bg-success">Active</span></p>
                </div>
            </div>
        </div>
    </div>
</div>
"""

# Authentication routes
@app.route('/login/', methods=['GET'])
def login():
    """Redirect to home and trigger Web3Auth modal"""
    return redirect(url_for('home') + '?show_login=1')

@app.route('/logout/')
def logout():
    """User logout"""
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/register/', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        
        # Check if username or email already exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists.', 'error')
            else:
                flash('Email already registered.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            # Create new user in database
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                name=name,
                email=email,
                role='user',  # Default role
                theme='dark'  # Default theme
            )
            db.session.add(new_user)
            db.session.commit()

            session['user'] = username
            flash(f'Account created successfully! Welcome, {name}!', 'success')
            return redirect(url_for('home'))
    
    # Generate user menu for register page
    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/login/">Sign In</a>
    </div>
    """
    return render_template_string(BASE_TEMPLATE.format(title="Register - MLTF", theme="light", user_menu=user_menu, content=REGISTER_TEMPLATE, build_number=BUILD_NUMBER))

# Ordinals API routes
@app.route('/api/ordinal/preview', methods=['POST'])
def preview_ordinal():
    """Preview ordinal content and fetch metadata"""
    try:
        data = request.get_json()
        inscription_id = data.get('inscriptionId', '').strip()
        
        if not inscription_id:
            return jsonify({'success': False, 'error': 'Inscription ID is required'}), 400
        
        # Validate inscription ID format (basic validation)
        if len(inscription_id) < 10 or not all(c.isalnum() or c in 'i-_' for c in inscription_id):
            return jsonify({'success': False, 'error': 'Invalid inscription ID format'}), 400
        
        # Build content URL
        content_url = f"https://ordinals.com/content/{inscription_id}"
        
        # Check size and content type with HEAD request
        try:
            # Add headers to avoid 403 errors from ordinals.com
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Connection': 'keep-alive'
                # Removed Accept-Encoding to avoid compression issues
            }
            
            head_response = requests.head(content_url, headers=headers, timeout=10, allow_redirects=True)
            
            if head_response.status_code == 404:
                return jsonify({'success': False, 'error': 'Inscription not found'}), 404
            
            if head_response.status_code == 403:
                return jsonify({
                    'success': False, 
                    'error': 'Access denied by ordinals.com. The inscription exists but cannot be accessed from the server. You can view it directly at: ' + content_url
                }), 403
            
            if head_response.status_code != 200:
                return jsonify({'success': False, 'error': f'Failed to fetch inscription (status: {head_response.status_code})'}), 400
            
            # Get content length
            content_length = int(head_response.headers.get('Content-Length', 0))
            max_size = 50 * 1024  # 50KB
            
            # If HEAD doesn't return Content-Length, try a GET request with streaming
            if content_length == 0:
                try:
                    get_response = requests.get(content_url, headers=headers, timeout=10, stream=True)
                    # Read just enough to check size
                    content_chunk = get_response.raw.read(max_size + 1)
                    content_length = len(content_chunk)
                    content_type = get_response.headers.get('Content-Type', 'unknown').lower()
                except:
                    # If we can't determine size, allow it but note it
                    content_length = 1  # Set to non-zero to proceed
            
            if content_length > max_size:
                size_kb = content_length / 1024
                return jsonify({
                    'success': False, 
                    'error': f'Content too large: {size_kb:.1f}KB (max 50KB)'
                }), 400
            
            # Get content type
            content_type = head_response.headers.get('Content-Type', 'unknown').lower()
            
            # Check if supported type
            supported_types = [
                'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 
                'image/svg+xml', 'image/webp',
                'text/plain', 'text/markdown', 'text/html', 'text/javascript',
                'application/json', 'application/javascript'
            ]
            
            is_supported = any(st in content_type for st in supported_types)
            
            if not is_supported:
                return jsonify({
                    'success': False,
                    'error': f'Unsupported content type: {content_type}. Supported: images, text, markdown, HTML'
                }), 400
            
            # Fetch metadata from ordinals.com HTML (JSON API is disabled on public instance - returns 406)
            inscription_number = None
            block_height = None
            timestamp = None
            
            try:
                import re
                
                # Fetch HTML page
                page_url = f"https://ordinals.com/inscription/{inscription_id}"
                page_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                app.logger.info(f"🔍 Scraping metadata from HTML: {page_url}")
                
                page_response = requests.get(page_url, headers=page_headers, timeout=10)
                app.logger.info(f"📡 HTML Response status: {page_response.status_code}")
                
                if page_response.status_code == 200:
                    html = page_response.text
                    
                    # Extract inscription number from title: <title>Inscription 117530382</title>
                    number_match = re.search(r'<title>Inscription (\d+)</title>', html)
                    if number_match:
                        inscription_number = int(number_match.group(1))
                        app.logger.info(f"   ✅ Inscription number: {inscription_number}")
                    
                    # Extract block height: <dt>height</dt><dd><a href=/block/933535>933535</a></dd>
                    height_match = re.search(r'<dt>height</dt>\s*<dd><a[^>]*>(\d+)</a></dd>', html)
                    if height_match:
                        block_height = int(height_match.group(1))
                        app.logger.info(f"   ✅ Block height: {block_height}")
                    
                    # Extract timestamp: <dt>timestamp</dt><dd><time>2026-01-23 15:15:43 UTC</time></dd>
                    time_match = re.search(r'<dt>timestamp</dt>\s*<dd><time[^>]*>([^<]+)</time></dd>', html)
                    if time_match:
                        timestamp = time_match.group(1).strip()
                        app.logger.info(f"   ✅ Timestamp: {timestamp}")
                    
                    app.logger.info(f"✅ Metadata scraped: number={inscription_number}, height={block_height}, time={timestamp}")
                else:
                    app.logger.warning(f"⚠️  HTML fetch failed ({page_response.status_code})")
            except Exception as e:
                app.logger.error(f"❌ Error scraping metadata: {e}")
                import traceback
                app.logger.error(traceback.format_exc())
                pass  # Metadata fetch failed, continue without it
            
            return jsonify({
                'success': True,
                'contentUrl': content_url,
                'contentType': content_type,
                'contentSize': content_length,
                'inscriptionId': inscription_id,
                'inscriptionNumber': inscription_number,
                'blockHeight': block_height,
                'timestamp': timestamp
            })
            
        except requests.Timeout:
            return jsonify({'success': False, 'error': 'Request timed out. Please try again.'}), 408
        except requests.ConnectionError:
            return jsonify({'success': False, 'error': 'Ordinals service unavailable. Please try again later.'}), 503
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to fetch content: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Ordinal preview error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/ordinal/convert-markdown', methods=['POST'])
def convert_markdown():
    """Convert markdown to HTML with sanitization"""
    try:
        data = request.get_json()
        markdown_text = data.get('markdown', '')
        
        app.logger.info(f"📝 MARKDOWN CONVERSION REQUEST")
        app.logger.info(f"   Input length: {len(markdown_text)} chars")
        app.logger.info(f"   First 200 chars: {markdown_text[:200]}")
        
        if not markdown_text:
            return jsonify({'success': False, 'error': 'No markdown provided'}), 400
        
        if MARKDOWN_SUPPORT:
            app.logger.info(f"   ✅ Markdown support enabled")
            
            # Pre-process markdown to handle figure tags with images
            import re
            
            # Convert markdown images inside figure tags to HTML img tags with img-fluid class
            def replace_figure_image(match):
                full_match = match.group(0)
                alt_text = match.group(1) if match.group(1) else ''
                image_url = match.group(2)
                caption = match.group(3) if len(match.groups()) >= 3 and match.group(3) else ''
                
                # Build the HTML
                html = '<figure class="figure">\n'
                html += f'  <img src="{image_url}" alt="{alt_text}" class="img-fluid figure-img">\n'
                if caption:
                    html += f'  <figcaption class="figure-caption"><small>{caption}</small></figcaption>\n'
                html += '</figure>'
                return html
            
            # Pattern to match: <figure>\n![alt](url)\n<figcaption>caption</figcaption>\n</figure>
            markdown_text = re.sub(
                r'<figure[^>]*>\s*!\[([^\]]*)\]\(([^\)]+)\)\s*(?:<figcaption[^>]*>([^<]+)</figcaption>)?\s*</figure>',
                replace_figure_image,
                markdown_text,
                flags=re.MULTILINE | re.DOTALL
            )
            
            # Convert markdown to HTML using markdown2 (without break-on-newline to avoid extra line breaks)
            html_content = markdown2.markdown(
                markdown_text,
                extras=['fenced-code-blocks', 'tables']
            )
            app.logger.info(f"   📄 Converted HTML length: {len(html_content)} chars")
            app.logger.info(f"   📄 HTML first 300 chars: {html_content[:300]}")
            
            # Fix image URLs BEFORE sanitization
            # 1. Fix relative /content/ URLs
            html_content = re.sub(
                r'src="(/content/[^"]+)"',
                r'src="https://ordinals.com\1"',
                html_content
            )
            
            # 2. Fix bare inscription IDs (64-char hex + 'i' + number)
            html_content = re.sub(
                r'src="(?:[^"]*/)??([a-f0-9]{64}i\d+)"',
                r'src="https://ordinals.com/content/\1"',
                html_content
            )
            
            # 3. Add img-fluid class to all img tags that don't already have it
            html_content = re.sub(
                r'<img(?![^>]*class=)([^>]*)>',
                r'<img class="img-fluid"\1>',
                html_content
            )
            
            app.logger.info(f"   📄 After URL fixes - First 500 chars: {html_content[:500]}")
            
            # Sanitize HTML to prevent XSS
            allowed_tags = [
                'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img',
                'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'figure', 'figcaption', 'small'
            ]
            allowed_attrs = {
                'a': ['href', 'title'],
                'img': ['src', 'alt', 'title', 'class'],
                'code': ['class'],
                'figure': ['class'],
                'figcaption': ['class']
            }
            
            html_content = bleach.clean(
                html_content,
                tags=allowed_tags,
                attributes=allowed_attrs,
                strip=True
            )
            app.logger.info(f"   🧹 Sanitized HTML length: {len(html_content)} chars")
            app.logger.info(f"   📄 Sanitized HTML first 500 chars: {html_content[:500]}")
        else:
            # Fallback: simple HTML escape and line breaks
            import html
            html_content = html.escape(markdown_text).replace('\n', '<br>')
        
        return jsonify({'success': True, 'html': html_content})
        
    except Exception as e:
        print(f"Markdown conversion error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Conversion failed'}), 500

# Web3Auth API routes
@app.route('/api/auth/web3auth', methods=['POST'])
def web3auth_login():
    """Web3Auth login endpoint"""
    # Rate limiting: 10 requests per 5 minutes per IP
    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')
    if not check_rate_limit(f"web3auth_{client_ip}", max_requests=10, window_seconds=300):
        return jsonify({'error': 'Rate limit exceeded. Try again later.'}), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        verifierId = data.get('verifierId')
        typeOfLogin = data.get('typeOfLogin')
        email = data.get('email')
        name = data.get('name')
        profileImage = data.get('profileImage')
        evmAddress = data.get('evmAddress')
        solanaAddress = data.get('solanaAddress')

        if not verifierId:
            return jsonify({'error': 'verifierId required'}), 400

        # Check if user exists in database
        user = User.query.filter_by(web3authVerifierId=verifierId).first()

        # If not found by verifierId, check by email
        if not user and email:
            user = User.query.filter_by(email=email).first()

        # If user exists, update their Web3Auth info
        if user:
            # Update existing user with new Web3Auth data
            user.web3authVerifierId = verifierId
            user.typeOfLogin = typeOfLogin
            if name:
                user.displayName = name
                user.displayNameSetAt = datetime.utcnow()
                user.oauthName = name
            if profileImage:
                user.profileImage = profileImage
            if evmAddress:
                user.evmAddress = evmAddress
            if solanaAddress:
                user.solanaAddress = solanaAddress
            db.session.commit()
        else:
            # Create new user
            # Generate handle (use email or wallet address)
            existing_handles = db.session.query(User.username).all()
            existing_handles = [handle[0] for handle in existing_handles]
            if typeOfLogin == 'wallet' and evmAddress:
                # For wallet login, generate handle from wallet address
                short_address = f"{evmAddress[:6]}...{evmAddress[-4:]}"
                handle = f"wallet_{short_address}"
                counter = 1
                while handle in existing_handles:
                    handle = f"wallet_{short_address}_{counter}"
                    counter += 1
            else:
                # For social login, generate from email
                base_handle = email.split('@')[0] if email else 'user'
                base_handle = re.sub(r'[^a-zA-Z0-9_]', '', base_handle)
                if len(base_handle) < 3:
                    base_handle = 'user'
                handle = base_handle
                counter = 1
                while handle in existing_handles:
                    handle = f"{base_handle}{counter}"
                    counter += 1

            # Create user
            user = User(
                web3authVerifierId=verifierId,
                typeOfLogin=typeOfLogin,
                displayName=name if name else None,
                displayNameSetAt=datetime.utcnow() if name else None,
                oauthName=name,
                email=email,
                profileImage=profileImage,
                evmAddress=evmAddress,
                solanaAddress=solanaAddress,
                username=handle,
                handle=handle,
                role='user',
                theme='dark'
            )
            db.session.add(user)
            db.session.commit()

        # Create session
        session['user'] = user.username
        session['theme'] = user.theme

        # Return user data (excluding sensitive info)
        user_data = {
            'id': user.id,
            'username': user.username,
            'displayName': user.displayName,
            'oauthName': user.oauthName,
            'email': user.email,
            'profileImage': user.profileImage,
            'evmAddress': user.evmAddress,
            'typeOfLogin': user.typeOfLogin,
            'theme': user.theme
        }

        # Return sanitized user data (exclude sensitive fields)
        safe_user_data = {
            'id': user.id,
            'username': user.username,
            'displayName': user.displayName,
            'oauthName': user.oauthName,
            'email': user.email,
            'profileImage': user.profileImage,
            'evmAddress': user.evmAddress,
            'solanaAddress': user.solanaAddress,
            'typeOfLogin': user.typeOfLogin,
            'theme': user.theme
        }

        return jsonify({'success': True, 'user': safe_user_data})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Web3Auth login error: {e}")
        print(f"Traceback: {error_details}")
        print(f"Request data: {data if 'data' in locals() else 'N/A'}")
        db.session.rollback()
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500


@app.route('/api/user/me', methods=['GET'])
def get_user_profile():
    """Get current user profile"""
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_data = {
        'id': user.id,
        'username': user.username,
        'displayName': user.displayName,
        'displayNameSetAt': user.displayNameSetAt.isoformat() if user.displayNameSetAt else None,
        'oauthName': user.oauthName,
        'email': user.email,
        'profileImage': user.profileImage,
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'typeOfLogin': user.typeOfLogin,
        'theme': user.theme
    }

    # Return sanitized user data (exclude sensitive fields)
    safe_user_data = {
        'id': user.id,
        'username': user.username,
        'displayName': user.displayName,
        'displayNameSetAt': user.displayNameSetAt.isoformat() if user.displayNameSetAt else None,
        'oauthName': user.oauthName,
        'email': user.email,
        'profileImage': user.profileImage,
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'typeOfLogin': user.typeOfLogin,
        'theme': user.theme
    }

    return jsonify({'user': safe_user_data})

@app.route('/api/user/display-name', methods=['PUT'])
def update_display_name():
    """Update user display name"""
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data or 'displayName' not in data:
        return jsonify({'error': 'Display name required'}), 400

    displayName = data['displayName'].strip()

    # Validation
    if not displayName:
        return jsonify({'error': 'Display name cannot be empty'}), 400

    if len(displayName) > 50:
        return jsonify({'error': 'Display name must be 50 characters or less'}), 400

    # Optional: Check for allowed characters
    import re
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', displayName):
        return jsonify({'error': 'Display name can only contain letters, numbers, spaces, hyphens, and underscores'}), 400

    # Update user
    user.displayName = displayName
    user.displayNameSetAt = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'user': {
        'id': user.id,
        'displayName': user.displayName,
        'displayNameSetAt': user.displayNameSetAt.isoformat()
    }})

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API logout endpoint"""
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/profile/', methods=['GET', 'POST'])
@require_auth
def profile():
    """User profile management"""
    current_user = get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action')
        user = User.query.filter_by(username=session['user']).first()

        if action == 'update_password':
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            
            if check_password_hash(user.password_hash, old_password):
                if len(new_password) >= 6:
                    user.password_hash = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Password updated successfully!', 'success')
                else:
                    flash('New password must be at least 6 characters.', 'error')
            else:
                flash('Current password is incorrect.', 'error')
        
        elif action == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            
            # Check if email is already taken by another user
            existing_email = User.query.filter(User.email == email, User.username != session['user']).first()
            if existing_email:
                flash('Email already registered to another account.', 'error')
            else:
                if name:
                    user.name = name
                if email:
                    user.email = email
                db.session.commit()
                flash('Profile updated successfully!', 'success')

        elif action == 'update_theme':
            theme = request.form.get('theme', 'dark').strip()
            if theme in ['light', 'dark', 'auto']:
                user.theme = theme
                db.session.commit()
                session['theme'] = theme  # Update session immediately
                flash('Theme preference updated successfully!', 'success')
            else:
                flash('Invalid theme selection.', 'error')
    
    # Generate user menu
    user_menu = generate_user_menu()
    
    current_theme = current_user.get('theme', 'dark')
    light_selected = 'selected' if current_theme == 'light' else ''
    dark_selected = 'selected' if current_theme == 'dark' else ''
    auto_selected = 'selected' if current_theme == 'auto' else ''
    
    profile_content = PROFILE_TEMPLATE.format(
        current_user_name=current_user['name'],
        current_user_email=current_user['email'],
        current_user_theme=current_theme,
        light_selected=light_selected,
        dark_selected=dark_selected,
        auto_selected=auto_selected,
        session_user=session['user']
    )
    return render_template_string(BASE_TEMPLATE.format(title="Profile - MLTF", theme=current_theme, user_menu=user_menu, content=profile_content, build_number=BUILD_NUMBER))

@app.route('/admin/')
@require_role('admin')
def admin_dashboard():
    user_menu = generate_user_menu()

    # Enhanced admin statistics
    total_users = User.query.count()
    total_groups = len(GROUPS)
    total_submissions = Submission.query.count()
    approved_drafts = PublishedDraft.query.count()
    pending_chairs = WorkingGroupChair.query.filter_by(approved=False).count()

    # Recent activity and alerts
    pending_submissions = Submission.query.filter_by(status='submitted').count()
    recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    # Get most active drafts (by comment count or views if we had them)
    # For now, just show recent submissions as proxy
    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(10).all()

    # Most active users (by login frequency - simplified)
    active_users = User.query.order_by(User.last_login.desc()).limit(10).all()

    # Build recent activity feed
    activity_html = ""
    for submission in recent_submissions[:3]:  # Show last 3 submissions
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-file-alt me-1"></i>
                New submission: <strong>{submission.title[:50]}...</strong>
                by {submission.submitted_by}
                <span class="float-end">{submission.submitted_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    for user in recent_users[:2]:  # Show last 2 new users
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-user-plus me-1"></i>
                New user: <strong>{user.name}</strong> ({user.email})
                <span class="float-end">{user.created_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    # Build alerts section
    alerts_html = ""
    if pending_submissions > 0:
        alerts_html += f"""
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>{pending_submissions}</strong> draft submission(s) pending review
            <a href="/admin/submissions/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_chairs > 0:
        alerts_html += f"""
        <div class="alert alert-info alert-dismissible fade show" role="alert">
            <i class="fas fa-users me-2"></i>
            <strong>{pending_chairs}</strong> working group chair(s) pending approval
            <a href="/group/" class="alert-link">Manage chairs</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <!-- Alerts Section -->
        <div id="admin-alerts" class="mb-4">
            {alerts_html}
        </div>

        <div class="row">
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h1>Admin Dashboard</h1>
                    <div>
                        <a href="/admin/users/" class="btn btn-outline-primary me-2">Manage Users</a>
                        <a href="/admin/chairs/" class="btn btn-outline-warning me-2">Manage Chairs</a>
                        <a href="/admin/submissions/" class="btn btn-outline-success">Review Submissions</a>
                    </div>
                </div>

                <!-- Statistics Cards -->
                <div class="row mb-4">
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-primary mb-1">{total_users}</h4>
                                <p class="mb-0 small">Total Users</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-success mb-1">{total_groups}</h4>
                                <p class="mb-0 small">Working Groups</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-warning mb-1">{total_submissions}</h4>
                                <p class="mb-0 small">Total Submissions</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-info mb-1">{approved_drafts}</h4>
                                <p class="mb-0 small">Published Drafts</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-danger mb-1">{pending_submissions}</h4>
                                <p class="mb-0 small">Pending Review</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-secondary mb-1">{pending_chairs}</h4>
                                <p class="mb-0 small">Pending Chairs</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <!-- Recent Activity -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Recent Activity</h5>
                                <span class="badge bg-primary">Live</span>
                            </div>
                            <div class="card-body">
                                {activity_html}
                                <hr>
                                <a href="/admin/activity/" class="btn btn-sm btn-outline-primary">View All Activity</a>
                            </div>
                        </div>
                    </div>

                    <!-- Quick Actions -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Quick Actions</h5>
                            </div>
                            <div class="card-body">
                                <div class="d-grid gap-2">
                                    <a href="/admin/submissions/" class="btn btn-success">
                                        <i class="fas fa-check-circle me-2"></i>Review Submissions ({pending_submissions} pending)
                                    </a>
                                    <a href="/admin/users/" class="btn btn-primary">
                                        <i class="fas fa-users me-2"></i>Manage Users ({total_users} total)
                                    </a>
                                    <a href="/group/" class="btn btn-info">
                                        <i class="fas fa-users-cog me-2"></i>Manage Working Groups ({pending_chairs} pending chairs)
                                    </a>
                                    <a href="/admin/analytics/" class="btn btn-secondary">
                                        <i class="fas fa-chart-bar me-2"></i>View Analytics
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Content Management Section -->
                <div class="row mt-4">
                    <div class="col-12">
                        <h3 class="mb-3">Content Management</h3>
                    </div>
                </div>

                <div class="row">
                    <!-- Most Active Drafts -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Draft Submissions</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <a href="/doc/draft/{draft.id}/" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{draft.title[:40]}...</strong>
                                            <br><small class="text-muted">by {draft.submitted_by} • {draft.submitted_at.strftime('%m/%d')}</small>
                                        </div>
                                        <span class="badge bg-{'warning' if draft.status == 'submitted' else 'success'}">{draft.status}</span>
                                    </a>
                                    ''' for draft in active_drafts[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Active Users -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent User Activity</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <div class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{user.name}</strong>
                                            <br><small class="text-muted">{user.email} • {user.role}</small>
                                        </div>
                                        <small class="text-muted">
                                            {user.last_login.strftime('%m/%d %H:%M') if user.last_login else 'Never logged in'}
                                        </small>
                                    </div>
                                    ''' for user in active_users[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Admin Dashboard - MLTF",
        theme=get_current_user().get('theme', 'dark'),
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)

@app.route('/admin/users/')
@require_role('admin')
def admin_users():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Get all users with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.name.contains(search),
                User.email.contains(search)
            )
        )

    if role_filter:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    total_users = query.count()

    # Build user rows
    user_rows = ""
    for user in users.items:
        role_badge = {
            'admin': 'badge bg-danger',
            'editor': 'badge bg-warning',
            'user': 'badge bg-secondary'
        }.get(user.role, 'badge bg-secondary')

        last_login = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'

        user_rows += f"""
        <tr>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="{role_badge}">{user.role.title()}</span></td>
            <td>{user.theme.title()}</td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{last_login}</td>
            <td>
                <div class="btn-group btn-group-sm" role="group">
                    <div class="dropdown">
                        <button class="btn btn-outline-primary btn-sm dropdown-toggle" type="button" id="roleDropdown{user.username}" data-bs-toggle="dropdown" aria-expanded="false" data-bs-offset="0,4">
                            <i class="fas fa-user-edit"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="roleDropdown{user.username}">
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'user'); return false;">User</a></li>
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'editor'); return false;">Editor</a></li>
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'admin'); return false;">Admin</a></li>
                        </ul>
                    </div>
                    <button class="btn btn-outline-danger btn-sm ms-1" onclick="deleteUser('{user.username}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
        """

    # Role filter options
    role_options = f"""
    <option value="">All Roles</option>
    <option value="admin" {'selected' if role_filter == 'admin' else ''}>Admin</option>
    <option value="editor" {'selected' if role_filter == 'editor' else ''}>Editor</option>
    <option value="user" {'selected' if role_filter == 'user' else ''}>User</option>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">User Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>User Management</h1>
            <div>
                <span class="badge bg-info me-2">Total: {total_users} users</span>
            </div>
        </div>

        <!-- Filters and Search -->
        <div class="card mb-4">
            <div class="card-body">
                <form method="GET" class="row g-3">
                    <div class="col-md-6">
                        <label for="search" class="form-label">Search Users</label>
                        <input type="text" class="form-control" id="search" name="search"
                               value="{search}" placeholder="Name, username, or email">
                    </div>
                    <div class="col-md-4">
                        <label for="role" class="form-label">Filter by Role</label>
                        <select class="form-select" id="role" name="role">
                            {role_options}
                        </select>
                    </div>
                    <div class="col-md-2 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary me-2">
                            <i class="fas fa-search me-1"></i>Filter
                        </button>
                        <a href="/admin/users/" class="btn btn-outline-secondary">
                            <i class="fas fa-times"></i>
                        </a>
                    </div>
                </form>
            </div>
        </div>

        <!-- Users Table -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Users ({users.total} total)</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Theme</th>
                                <th>Joined</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {user_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Pagination -->
        {f'''
        <nav aria-label="User pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not users.has_prev else ""}"><a class="page-link" href="?page={users.prev_num}&search={search}&role={role_filter}">Previous</a></li>' if users.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == users.page else ""}"><a class="page-link" href="?page={i}&search={search}&role={role_filter}">{i}</a></li>' for i in users.iter_pages()])}
                {f'<li class="page-item {"disabled" if not users.has_next else ""}"><a class="page-link" href="?page={users.next_num}&search={search}&role={role_filter}">Next</a></li>' if users.has_next else ''}
            </ul>
        </nav>
        ''' if users.pages > 1 else ''}
        </div>

    <script>
        function changeRole(username, newRole) {{
            console.log('Changing role for', username, 'to', newRole);
            
            fetch('/admin/users/' + username + '/role', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ role: newRole }})
            }})
            .then(response => {{
                console.log('Response status:', response.status);
                return response.json();
            }})
            .then(data => {{
                console.log('Response data:', data);
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error: ' + (data.message || 'Unknown error'));
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error updating role: ' + error.message);
            }});
        }}

        function deleteUser(username) {{
            if (confirm("Are you sure you want to delete user " + username + "? This action cannot be undone.")) {{
                console.log('Deleting user:', username);
                fetch('/admin/users/' + username + '/delete', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }}
                }})
                .then(response => {{
                    console.log('Delete response status:', response.status);
                    return response.json();
                }})
                .then(data => {{
                    console.log('Delete response data:', data);
                    if (data.success) {{
                        // Just reload without alert
                        location.reload();
                    }} else {{
                        alert('Error: ' + (data.message || 'Unknown error'));
                    }}
                }})
                .catch(error => {{
                    console.error('Error:', error);
                    alert('Error deleting user: ' + error.message);
                }});
            }}
        }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title="User Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)

@app.route('/admin/users/<username>/role', methods=['POST'])
@require_role('admin')
def change_user_role(username):
    data = request.get_json()
    new_role = data.get('role', '')

    if new_role not in ['user', 'editor', 'admin']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Prevent admin from demoting themselves
    current_admin = get_current_user()
    if user.id == current_admin['id'] and new_role != 'admin':
        return jsonify({'success': False, 'message': 'Cannot change your own admin role'}), 400

    user.role = new_role
    db.session.commit()

    # Log the action
    add_to_document_history(f"user-{user.id}", "role_changed", current_admin['name'],
                           f"Changed {user.name}'s role to {new_role}")

    return jsonify({'success': True, 'message': f'Role changed to {new_role}'})

@app.route('/admin/users/<username>/delete', methods=['POST'])
@require_role('admin')
def delete_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    # Prevent admin from deleting themselves
    current_admin = get_current_user()
    if user.id == current_admin['id']:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400

    # Log before deletion
    add_to_document_history(f"user-{user.id}", "user_deleted", current_admin['name'],
                           f"Deleted user {user.name} ({user.email})")

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'User deleted successfully'})

@app.route('/admin/submissions/')
@require_role('admin')
def admin_submissions():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Get submissions with filters
    status_filter = request.args.get('status', 'submitted')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Submission.query

    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    submissions = query.order_by(Submission.submitted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    # Build submission cards
    submission_cards = ""
    for submission in submissions.items:
        status_badge = {
            'submitted': 'badge bg-warning text-dark',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger',
            'published': 'badge bg-info'
        }.get(submission.status, 'badge bg-secondary')

        # Get revision info
        is_revision = getattr(submission, 'is_revision', False)
        revision_number = getattr(submission, 'revision_number', '')
        parent_draft_name = getattr(submission, 'parent_draft_name', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''

        # Get source info (file or ordinal)
        source_type = getattr(submission, 'sourceType', 'file')
        if source_type == 'ordinal':
            inscription_number = getattr(submission, 'inscriptionNumber', None)
            ordinal_id = getattr(submission, 'ordinalId', None)
            block_height = getattr(submission, 'blockHeight', None)
            if inscription_number:
                source_info = f'<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span> Inscription #{inscription_number}'
                if block_height:
                    source_info += f' (Block {block_height})'
            elif ordinal_id:
                source_info = f'<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span> {ordinal_id[:16]}...'
            else:
                source_info = '<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span>'
        else:
            file_size = "N/A"
            if submission.file_path and os.path.exists(submission.file_path):
                file_size = f"{os.path.getsize(submission.file_path) / 1024:.1f} KB"
            source_info = f'<span class="badge bg-secondary"><i class="bi bi-file-earmark"></i> File</span> {submission.filename} ({file_size})'

        action_buttons = ""
        if submission.status == 'submitted':
            action_buttons = f"""
            <button class="btn btn-success btn-sm me-2" onclick="approveSubmission('{submission.id}')">
                <i class="fas fa-check me-1"></i>Approve
            </button>
            <button class="btn btn-danger btn-sm me-2" onclick="rejectSubmission('{submission.id}')">
                <i class="fas fa-times me-1"></i>Reject
            </button>
            <button class="btn btn-info btn-sm" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            """
        elif submission.status == 'approved':
            action_buttons = f"""
            <button class="btn btn-info btn-sm me-2" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            <button class="btn btn-warning btn-sm" onclick="unapproveSubmission('{submission.id}')">
                <i class="fas fa-undo me-1"></i>Unapprove
            </button>
            """

        # Add revision context if this is a revision
        revision_context = ""
        if is_revision and parent_draft_name:
            revision_context = f'<p class="mb-2"><strong>Revision of:</strong> <a href="/doc/draft/{parent_draft_name}/" class="text-decoration-none">{parent_draft_name}</a></p>'

        submission_cards += f"""
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <a href="/doc/draft/{submission.id}/" class="text-decoration-none">
                        {submission.title}
                    </a>
                </h6>
                <div>
                    <span class="{status_badge}">{submission.status.title()}</span>
                    {revision_badge}
                </div>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-8">
                        <p class="mb-2"><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                        <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                        <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')} by {submission.submitted_by}</p>
                        <p class="mb-2"><strong>Source:</strong> {source_info}</p>
                        {revision_context}
                        {f'<p class="mb-2"><strong>Abstract:</strong> {submission.abstract[:200]}...</p>' if submission.abstract else ''}
                    </div>
                    <div class="col-md-4">
                        <div class="d-grid gap-2">
                            <a href="/doc/draft/{submission.id}/" class="btn btn-outline-primary btn-sm">
                                <i class="fas fa-eye me-1"></i>View Draft
                            </a>
                            {action_buttons}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    # Status filter options
    status_options = f"""
    <option value="all" {'selected' if status_filter == 'all' else ''}>All Submissions</option>
    <option value="submitted" {'selected' if status_filter == 'submitted' else ''}>Pending Review</option>
    <option value="approved" {'selected' if status_filter == 'approved' else ''}>Approved</option>
    <option value="rejected" {'selected' if status_filter == 'rejected' else ''}>Rejected</option>
    <option value="published" {'selected' if status_filter == 'published' else ''}>Published</option>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Submission Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Submission Management</h1>
            <div>
                <select class="form-select form-select-sm" onchange="changeStatusFilter(this.value)">
                    {status_options}
                </select>
            </div>
        </div>

        <!-- Statistics -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{Submission.query.filter_by(status='submitted').count()}</h4>
                        <p class="mb-0 small">Pending Review</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{Submission.query.filter_by(status='approved').count()}</h4>
                        <p class="mb-0 small">Approved</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-danger">{Submission.query.filter_by(status='rejected').count()}</h4>
                        <p class="mb-0 small">Rejected</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{Submission.query.filter_by(status='published').count()}</h4>
                        <p class="mb-0 small">Published as RFC</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Submissions -->
        <div id="submissions-container">
            {submission_cards}
        </div>

        <!-- Pagination -->
        {f'''
        <nav aria-label="Submission pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not submissions.has_prev else ""}"><a class="page-link" href="?page={submissions.prev_num}&status={status_filter}">Previous</a></li>' if submissions.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == submissions.page else ""}"><a class="page-link" href="?page={i}&status={status_filter}">{i}</a></li>' for i in submissions.iter_pages()])}
                {f'<li class="page-item {"disabled" if not submissions.has_next else ""}"><a class="page-link" href="?page={submissions.next_num}&status={status_filter}">Next</a></li>' if submissions.has_next else ''}
            </ul>
        </nav>
        ''' if submissions.pages > 1 else ''}
    </div>

    <script>
        function changeStatusFilter(status) {{
            window.location.href = '?status=' + status;
        }}

        function approveSubmission(submissionId) {{
            if (confirm('Approve this draft submission? It will be marked as approved and ready for publication.')) {{
                updateSubmissionStatus(submissionId, 'approved');
            }}
        }}

        function rejectSubmission(submissionId) {{
            const reason = prompt('Reason for rejection (optional):');
            updateSubmissionStatus(submissionId, 'rejected', reason);
        }}

        function unapproveSubmission(submissionId) {{
            if (confirm('Remove approval for this submission?')) {{
                updateSubmissionStatus(submissionId, 'submitted');
            }}
        }}

        function publishAsRFC(submissionId) {{
            const rfcNumber = prompt('Enter RFC number:');
            if (rfcNumber && confirm('Publish as RFC ' + rfcNumber + '?')) {{
                updateSubmissionStatus(submissionId, 'published', null, rfcNumber);
            }}
        }}

        function updateSubmissionStatus(submissionId, status, reason = null, rfcNumber = null) {{
            const data = {{ status: status }};
            if (reason) data.reason = reason;
            if (rfcNumber) data.rfc_number = rfcNumber;

                fetch('/admin/submissions/' + submissionId + '/status', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify(data)
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error updating submission status');
            }});
        }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title="Submission Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)

@app.route('/admin/submissions/<submission_id>/status', methods=['POST'])
@require_role('admin')
def update_submission_status(submission_id):
    data = request.get_json()
    new_status = data.get('status', '')
    reason = data.get('reason', '')
    rfc_number = data.get('rfc_number', '')

    if new_status not in ['submitted', 'approved', 'rejected', 'published']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400

    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        return jsonify({'success': False, 'message': 'Submission not found'}), 404

    old_status = submission.status
    submission.status = new_status

    # Assign ML number when approving
    if new_status == 'approved' and not submission.ml_number:
        # Check if this is a revision
        is_revision = getattr(submission, 'is_revision', False)
        parent_draft_name = getattr(submission, 'parent_draft_name', '')
        
        if is_revision and parent_draft_name:
            # This is a revision - find the parent draft and use its ML number
            parent_submission = Submission.query.filter_by(id=parent_draft_name).first()
            if parent_submission and parent_submission.ml_number:
                # Use the parent's ML number for the revision
                submission.ml_number = parent_submission.ml_number
                submission.approved_at = datetime.utcnow()
                app.logger.info(f"✅ Revision {submission_id} inherits ML number {parent_submission.ml_number} from parent {parent_draft_name} via admin status update")
            else:
                app.logger.warning(f"⚠️ Parent draft {parent_draft_name} not found or has no ML number, assigning new ML number")
                try:
                    doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                    ml_number = get_next_ml_number(doc_type)
                    submission.ml_number = ml_number
                    submission.approved_at = datetime.utcnow()
                    app.logger.info(f"✅ Assigned new ML number {ml_number} to revision {submission_id} via admin status update")
                except Exception as e:
                    app.logger.error(f"❌ Failed to assign ML number to revision {submission_id} via admin status update: {e}")
        else:
            # This is a new draft - assign a new ML number
            try:
                doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                ml_number = get_next_ml_number(doc_type)
                submission.ml_number = ml_number
                submission.approved_at = datetime.utcnow()
                app.logger.info(f"✅ Assigned ML number {ml_number} to submission {submission_id} via admin status update")
            except Exception as e:
                app.logger.error(f"❌ Failed to assign ML number to submission {submission_id} via admin status update: {e}")
            # Continue with status change even if ML assignment fails

    if new_status == 'rejected' and reason:
        submission.rejected_at = datetime.utcnow()

    if new_status == 'published' and rfc_number:
        # Create a published RFC record
        published_draft = PublishedDraft(
            name=f"rfc{rfc_number}",
            title=submission.title,
            authors=submission.authors,
            group=submission.group,
            status='published',
            date=datetime.utcnow().strftime('%Y-%m-%d'),
            abstract=submission.abstract,
            submission_id=submission.id
        )
        db.session.add(published_draft)

    db.session.commit()

    # Log the action
    admin_user = get_current_user()
    action_details = f"Changed status from {old_status} to {new_status}"
    if reason:
        action_details += f" - Reason: {reason}"
    if rfc_number:
        action_details += f" - Published as RFC {rfc_number}"

    add_to_document_history(f"submission-{submission.id}", "status_changed",
                           admin_user['name'], action_details)

    return jsonify({'success': True, 'message': f'Status updated to {new_status}'})

def get_next_ml_number(doc_type='draft'):
    """Get the next ML number (ML-Draft-001 or ML-RFC-001)
    
    Args:
        doc_type: 'draft' or 'rfc'
    
    Returns:
        str: ML-Draft-001, ML-RFC-001, etc.
    """
    # Find the highest existing ML number for this document type
    prefix = f"ML-{doc_type.capitalize()}-"
    max_ml = db.session.query(db.func.max(Submission.ml_number)).filter(
        Submission.ml_number.like(f"{prefix}%")
    ).scalar()
    
    if max_ml:
        # Extract number from ML-Draft-XXX or ML-RFC-XXX format
        try:
            current_num = int(max_ml.split('-')[-1])
            next_num = current_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    # Use 3 digits for 1-999, 4 digits for 1000+
    if next_num < 1000:
        return f"{prefix}{next_num:03d}"
    else:
        return f"{prefix}{next_num:04d}"

@app.route('/submit/approve/<submission_id>', methods=['POST'])
@require_role('admin')
def approve_submission(submission_id):
    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        flash('Submission not found', 'error')
        return redirect('/admin/submissions/')

    # Check if this is a revision
    is_revision = getattr(submission, 'is_revision', False)
    parent_draft_name = getattr(submission, 'parent_draft_name', '')
    
    if is_revision and parent_draft_name:
        # This is a revision - find the parent draft and use its ML number
        parent_submission = Submission.query.filter_by(id=parent_draft_name).first()
        if parent_submission and parent_submission.ml_number:
            # Use the parent's ML number for the revision
            submission.ml_number = parent_submission.ml_number
            app.logger.info(f"✅ Revision {submission_id} inherits ML number {parent_submission.ml_number} from parent {parent_draft_name}")
        else:
            app.logger.warning(f"⚠️ Parent draft {parent_draft_name} not found or has no ML number")
            # Assign a new ML number as fallback
            if not submission.ml_number:
                try:
                    doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                    ml_number = get_next_ml_number(doc_type)
                    submission.ml_number = ml_number
                    app.logger.info(f"✅ Assigned new ML number {ml_number} to revision {submission_id}")
                except Exception as e:
                    app.logger.error(f"❌ Failed to assign ML number to revision {submission_id}: {e}")
    else:
        # This is a new draft - assign ML number if not already assigned
        if not submission.ml_number:
            try:
                doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                ml_number = get_next_ml_number(doc_type)
                submission.ml_number = ml_number
                app.logger.info(f"✅ Assigned ML number {ml_number} to submission {submission_id}")
            except Exception as e:
                app.logger.error(f"❌ Failed to assign ML number to submission {submission_id}: {e}")
                # Continue with approval even if ML assignment fails
    
    submission.status = 'approved'
    submission.approved_at = datetime.utcnow()
    
    try:
        db.session.commit()
        app.logger.info(f"✅ Successfully approved submission {submission_id}")
    except Exception as e:
        app.logger.error(f"❌ Failed to commit approval for submission {submission_id}: {e}")
        db.session.rollback()
        flash(f'Failed to approve submission: {str(e)}', 'error')
        return redirect('/admin/submissions/')

    # Log the action
    admin_user = get_current_user()
    action_desc = f"Approved revision {submission.revision_number} of {parent_draft_name}" if is_revision else f"Approved submission: {submission.title}"
    add_to_document_history(f"submission-{submission.id}", "approved", admin_user['name'], action_desc)

    flash_msg = f'Revision {submission.id} approved successfully! ML number: {submission.ml_number}' if is_revision else f'Submission {submission.id} approved successfully! Assigned ML number: {submission.ml_number}'
    flash(flash_msg, 'success')
    return redirect(f'/submit/status/{submission_id}/')

@app.route('/submit/reject/<submission_id>', methods=['POST'])
@require_role('admin')
def reject_submission(submission_id):
    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        flash('Submission not found', 'error')
        return redirect('/admin/submissions/')

    submission.status = 'rejected'
    submission.rejected_at = datetime.utcnow()
    db.session.commit()

    # Log the action
    admin_user = get_current_user()
    add_to_document_history(f"submission-{submission.id}", "rejected", admin_user['name'],
                           f"Rejected submission: {submission.title}")

    flash(f'Submission {submission.id} rejected!', 'warning')
    return redirect(f'/submit/status/{submission_id}/')

@app.route('/view/<submission_id>')
@require_auth
def view_submission(submission_id):
    """View a submission file inline (for PDFs and other viewable files)"""
    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        return "Submission not found", 404

    # Check if user owns this submission or is admin
    current_user = get_current_user()
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        return "Access denied", 403

    if not submission.file_path or not os.path.exists(submission.file_path):
        return "File not found", 404

    # Serve file inline (not as attachment) for viewing in browser
    return send_file(submission.file_path, as_attachment=False, download_name=submission.filename)

@app.route('/download/<submission_id>')
@require_auth
def download_submission(submission_id):
    """Download a submission file"""
    submission = Submission.query.filter_by(id=submission_id).first()
    if not submission:
        return "Submission not found", 404

    # Check if user owns this submission or is admin
    current_user = get_current_user()
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        return "Access denied", 403

    if not submission.file_path or not os.path.exists(submission.file_path):
        return "File not found", 404

    return send_file(submission.file_path, as_attachment=True, download_name=submission.filename)

@app.route('/admin/analytics/')
@require_role('admin')
def admin_analytics():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    # Most active drafts (recent submissions)
    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(20).all()

    # Most active users (by recent logins and submissions)
    active_users = User.query.order_by(User.last_login.desc()).limit(20).all()

    # User role distribution
    role_stats = db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all()
    role_data = {role: count for role, count in role_stats}

    # Submission status distribution
    status_stats = db.session.query(Submission.status, db.func.count(Submission.id)).group_by(Submission.status).all()
    status_data = {status: count for status, count in status_stats}

    # Recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_users = User.query.filter(User.created_at >= thirty_days_ago).count()
    recent_submissions = Submission.query.filter(Submission.submitted_at >= thirty_days_ago).count()

    # Build active drafts table
    draft_rows = ""
    for i, draft in enumerate(active_drafts, 1):
        draft_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <a href="/doc/draft/{draft.id}/" class="text-decoration-none">
                    {draft.title[:60]}{'...' if len(draft.title) > 60 else ''}
                </a>
            </td>
            <td>{', '.join(draft.authors[:2])}{'...' if len(draft.authors) > 2 else ''}</td>
            <td>{draft.group or 'None'}</td>
            <td>{draft.submitted_at.strftime('%Y-%m-%d')}</td>
            <td><span class="badge bg-{ 'warning' if draft.status == 'submitted' else 'success' if draft.status == 'approved' else 'danger' if draft.status == 'rejected' else 'info'}">{draft.status}</span></td>
        </tr>
        """

    # Build active users table
    user_rows = ""
    for i, user in enumerate(active_users, 1):
        user_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="badge bg-{ 'danger' if user.role == 'admin' else 'warning' if user.role == 'editor' else 'secondary'}">{user.role.title()}</span></td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'}</td>
        </tr>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Analytics</li>
            </ol>
        </nav>

        <h1 class="mb-4">Analytics Dashboard</h1>

        <!-- Overview Stats -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{recent_users}</h4>
                        <p class="mb-0 small">New Users (30 days)</p>
        </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{recent_submissions}</h4>
                        <p class="mb-0 small">New Submissions (30 days)</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{len(active_drafts)}</h4>
                        <p class="mb-0 small">Total Submissions</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{len(active_users)}</h4>
                        <p class="mb-0 small">Registered Users</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- Most Active Drafts -->
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Drafts</h5>
                        <small class="text-muted">Recent submissions and activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Title</th>
                                        <th>Authors</th>
                                        <th>Group</th>
                                        <th>Date</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {draft_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Most Active Users -->
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Users</h5>
                        <small class="text-muted">Users by recent login activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Joined</th>
                                        <th>Last Login</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {user_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Distribution Charts (Text-based) -->
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>User Role Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Admin:</strong> {role_data.get('admin', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(role_data.get('admin', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Editor:</strong> {role_data.get('editor', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(role_data.get('editor', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>User:</strong> {role_data.get('user', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-secondary" style="width: {(role_data.get('user', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Submission Status Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Submitted:</strong> {status_data.get('submitted', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(status_data.get('submitted', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Approved:</strong> {status_data.get('approved', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-success" style="width: {(status_data.get('approved', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Published:</strong> {status_data.get('published', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-info" style="width: {(status_data.get('published', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Rejected:</strong> {status_data.get('rejected', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(status_data.get('rejected', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </div>
        """
    
    return BASE_TEMPLATE.format(
        title="Analytics - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)

@app.route('/admin/chairs/')
@require_auth
def admin_chairs():
    current_user = get_current_user()
    current_theme = session.get('theme', 'dark')

    # Generate user menu
    user_menu = generate_user_menu()

    # Get statistics
    total_chairs = len(WORKING_GROUP_CHAIRS)
    approved_chairs = len([c for c in WORKING_GROUP_CHAIRS.values() if c['approved']])
    pending_chairs = total_chairs - approved_chairs

    # Build chair list
    chair_list = ""
    for chair_id, chair_data in WORKING_GROUP_CHAIRS.items():
        status_badge = 'success' if chair_data['approved'] else 'warning'
        status_text = 'Active' if chair_data['approved'] else 'Pending'
        chair_list += f"""
        <tr>
            <td>{chair_data['chair_name']}</td>
            <td>{chair_data.get('chair_email', 'N/A')}</td>
            <td><code>{chair_data['group_acronym']}</code></td>
            <td><span class="badge bg-{status_badge}">{status_text}</span></td>
            <td>{chair_data['set_at'].strftime('%Y-%m-%d')}</td>
            <td>
                <a href="/admin/chairs/{chair_id}/approve" class="btn btn-sm btn-outline-success" onclick="return confirm('Approve this chair?')">Approve</a>
                <a href="/admin/chairs/{chair_id}/delete" class="btn btn-sm btn-outline-danger" onclick="return confirm('Delete this chair?')">Delete</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Chair Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="mb-1">Chair Management</h1>
                <p class="text-muted mb-0">Manage working group chairs across all groups</p>
            </div>
            <a href="/admin/chairs/add" class="btn btn-primary">
                <i class="fas fa-plus me-2"></i>Add New Chair
            </a>
        </div>

        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{total_chairs}</h4>
                        <small class="text-muted">Total Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{approved_chairs}</h4>
                        <small class="text-muted">Active Chairs</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{pending_chairs}</h4>
                        <small class="text-muted">Pending Approval</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Chairs Table -->
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Working Group Chairs</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Group</th>
                                <th>Status</th>
                                <th>Added</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {chair_list if chair_list else '<tr><td colspan="6" class="text-center text-muted py-4">No chairs found. <a href="/admin/chairs/add">Add the first chair</a>.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Chair Management - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)

@app.route('/admin/chairs/add', methods=['GET', 'POST'])
@require_auth
def add_chair():
    current_user = get_current_user()
    current_theme = session.get('theme', 'dark')

    # Generate user menu
    user_menu = generate_user_menu()

    if request.method == 'POST':
        chair_name = request.form.get('chair_name', '').strip()
        chair_email = request.form.get('chair_email', '').strip()
        group_acronym = request.form.get('group_acronym', '').strip()
        approved = request.form.get('approved') == 'on'

        if not chair_name or not group_acronym:
            flash('Chair name and group are required', 'error')
        else:
            # Check if chair already exists
            for chair_data in WORKING_GROUP_CHAIRS.values():
                if chair_data['group_acronym'] == group_acronym and chair_data['chair_name'] == chair_name:
                    flash('Chair already exists in this group', 'error')
                    break
            else:
                # Add new chair
                chair_id = str(uuid.uuid4())
                WORKING_GROUP_CHAIRS[chair_id] = {
                    'chair_name': chair_name,
                    'chair_email': chair_email,
                    'group_acronym': group_acronym,
                    'approved': approved,
                    'set_at': datetime.utcnow()
                }
                flash('Chair added successfully', 'success')
                return redirect('/admin/chairs/')

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item"><a href="/admin/chairs/">Chair Management</a></li>
                <li class="breadcrumb-item active">Add Chair</li>
            </ol>
        </nav>

        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Add New Chair</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="chair_name" class="form-label">Chair Name *</label>
                                <input type="text" class="form-control" id="chair_name" name="chair_name" required>
                            </div>
                            <div class="mb-3">
                                <label for="chair_email" class="form-label">Email</label>
                                <input type="email" class="form-control" id="chair_email" name="chair_email">
                            </div>
                            <div class="mb-3">
                                <label for="group_acronym" class="form-label">Working Group *</label>
                                <input type="text" class="form-control" id="group_acronym" name="group_acronym" required>
                            </div>
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="approved" name="approved">
                                    <label class="form-check-label" for="approved">
                                        Approved (Active Chair)
                                    </label>
                                </div>
                            </div>
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary">Add Chair</button>
                                <a href="/admin/chairs/" class="btn btn-secondary">Cancel</a>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Add Chair - MLTF",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)

@app.route('/admin/chairs/<chair_id>/approve')
@require_auth
def approve_chair(chair_id):
    if chair_id in WORKING_GROUP_CHAIRS:
        WORKING_GROUP_CHAIRS[chair_id]['approved'] = True
        flash('Chair approved successfully', 'success')
    else:
        flash('Chair not found', 'error')
    return redirect('/admin/chairs/')

@app.route('/admin/chairs/<chair_id>/delete')
@require_auth
def delete_chair(chair_id):
    if chair_id in WORKING_GROUP_CHAIRS:
        del WORKING_GROUP_CHAIRS[chair_id]
        flash('Chair deleted successfully', 'success')
    else:
        flash('Chair not found', 'error')
    return redirect('/admin/chairs/')

# Routes
@app.route('/')
def home():
    # Generate user menu
    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'dark'  # Default to dark
    user_menu = generate_user_menu()
    
    # Count documents: DRAFTS + approved/published submissions
    doc_count = len(DRAFTS) + Submission.query.filter(Submission.status.in_(['approved', 'published'])).count()
    
    return BASE_TEMPLATE.format(title="MLTF", theme=current_theme, user_menu=user_menu, content=f"""
    
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <p class="lead">Welcome to the Governance Hub for the Meta-Layer Task Force!</p>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Documents</h5>
                            </div>
                            <div class="card-body">
                                <p>View the latest MLTF documents including drafts, RFCs, and other standards.</p>
                                <a href="/doc/all/" class="btn btn-primary">View All Documents</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Working Groups</h5>
                            </div>
                            <div class="card-body">
                                <p>Browse MLTF working groups and their activities.</p>
                                <a href="/group/" class="btn btn-primary">View Working Groups</a>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Meetings</h5>
                            </div>
                            <div class="card-body">
                                <p>Information about MLTF meetings and sessions.</p>
                                <a href="/meeting/" class="btn btn-primary">View Meetings</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>People</h5>
                            </div>
                            <div class="card-body">
                                <p>Directory of MLTF participants and contributors.</p>
                                <a href="/person/" class="btn btn-primary">View People</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Quick Stats</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Documents:</strong> {doc_count}</p>
                        <p><strong>Working Groups:</strong> {len(GROUPS)}</p>
                        <p><strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """, build_number=BUILD_NUMBER)

@app.route('/doc/active/')
def active_documents():
    """Show active documents (alias for all documents)"""
    return all_documents()

@app.route('/doc/all/')
def all_documents():
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    
    # Get all documents: published drafts + approved/published submissions
    all_docs = []
    
    # Add published drafts from DRAFTS list
    all_docs.extend(DRAFTS)
    
    # Add approved/published submissions from database
    # Exclude revisions - we only want to show the original draft or the latest approved revision
    approved_submissions = Submission.query.filter(
        Submission.status.in_(['approved', 'published']),
        Submission.is_revision == False  # Only show non-revision submissions
    ).all()
    
    # For each approved submission, check if there's a newer approved revision
    for submission in approved_submissions:
        # Check if there's an approved revision for this draft
        latest_revision = Submission.query.filter(
            Submission.parent_draft_name == submission.id,
            Submission.is_revision == True,
            Submission.status.in_(['approved', 'published'])
        ).order_by(Submission.revision_number.desc()).first()
        
        # Use the latest approved revision if it exists, otherwise use the original
        display_submission = latest_revision if latest_revision else submission
        
        # Use stored pages and words values (calculated on submission)
        pages = display_submission.pages if display_submission.pages else 1
        words = display_submission.words if display_submission.words else 0
        
        # Get revision info for display
        is_revision = getattr(display_submission, 'is_revision', False)
        revision_number = getattr(display_submission, 'revision_number', '')
        
        all_docs.append({
            'name': display_submission.id,
            'title': display_submission.title,
            'authors': display_submission.authors if isinstance(display_submission.authors, list) else [display_submission.authors] if display_submission.authors else [],
            'group': display_submission.group or 'N/A',
            'status': display_submission.status,
            'rev': revision_number if is_revision else '00',
            'pages': pages,
            'words': words,
            'date': display_submission.submitted_at.strftime('%Y-%m-%d') if display_submission.submitted_at else '',
            'abstract': display_submission.abstract or '',
            'ml_number': display_submission.ml_number,
            'is_revision': is_revision,
            'revision_number': revision_number
        })
    
    docs_html = ""
    for draft in all_docs:
        display_id = draft.get('ml_number') or draft['name']
        is_revision = draft.get('is_revision', False)
        revision_number = draft.get('revision_number', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''
        
        docs_html += f"""
        <div class="col-md-6 document-card">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title document-title">
                        <a href="/doc/draft/{draft['name']}/">{display_id}</a>
                        {revision_badge}
                    </h5>
                    <p class="card-text">{draft['title']}</p>
                    <div class="document-meta">
                        <span class="badge bg-secondary status-badge">{draft['status']}</span>
                        <span class="ms-2">Rev: {draft['rev']}</span>
                        <span class="ms-2">{draft['pages']} pages</span>
                        <span class="ms-2">{draft['words']} words</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Authors: {', '.join(draft['authors']) if draft['authors'] else 'N/A'}<br>
                            Group: {draft['group']}<br>
                            Date: {draft['date']}
                        </small>
                    </div>
                    <div class="mt-2">
                        <a href="/doc/draft/{draft['name']}/comments/" class="btn btn-sm btn-outline-primary">Comments</a>
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-sm btn-outline-secondary">History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-sm btn-outline-info">Revisions</a>
                    </div>
                </div>
            </div>
        </div>
        """
    
    content = f"""
    <div class="container mt-4">
        <h1>All Documents</h1>
        <p>Showing {len(all_docs)} documents</p>
        
        <div class="row">
            {docs_html}
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(title="All Documents - MLTF", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/doc/draft/<path:draft_name>.txt')
def draft_text(draft_name):
    """Serve draft content as plain text"""
    # First try to find in DRAFTS (published documents)
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    # If not found in DRAFTS, try to find as a submission ID
    submission = None
    if not draft:
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission:
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'abstract': submission.abstract or 'Abstract not available for this draft.',
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
            }
    
    if not draft:
        return "Document not found", 404
    
    # Load document content
    document_content = "Document content not available."
    
    # Try to get content from submission file first
    if submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
            elif ext == '.docx':
                from docx import Document
                doc = Document(submission.file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content_parts.append(cell.text)
                document_content = '\n\n'.join(content_parts)
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                document_content = '\n\n'.join(content_parts)
                # Clean up PDF text
                import re
                document_content = re.sub(r'\n+', '\n', document_content)
                document_content = re.sub(r' +', ' ', document_content)
            else:
                document_content = f"Document content cannot be displayed for {ext.upper()} files. Please download to view."
        except Exception as e:
            document_content = f"Error loading document content: {str(e)}"
    
    # If no submission content, try to get from DRAFTS data
    elif draft and 'name' in draft:
        # Generate text content from draft data
        document_content = f"""INTERNET-DRAFT                                               {', '.join(draft.get('authors', []))}
Intended status: Informational                            Meta-Layer Initiative
Expires: {draft.get('date', 'TBD')}                                      {draft.get('date', 'TBD')}


{draft.get('title', 'Document Title')}


Abstract

{draft.get('abstract', 'Abstract not available.')}


1. Introduction

This document describes {draft.get('title', 'the subject matter')}.

The content of this draft is currently being developed and will be available
in the full document once published.

2. Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions
of BCP 78 and BCP 79.

Meta-Layer Drafts are working documents of the Meta-Layer Task Force
(MLTF). These documents represent proposals and specifications for the
Meta-Layer ecosystem. The list of current Meta-Layer Drafts is available
in the MLTF datatracker.

Internet-Drafts are draft documents valid for a maximum of six months and
may be updated, replaced, or obsoleted by other documents at any time. It is
inappropriate to use Internet-Drafts as reference material or to cite them
other than as "work in progress."

This Internet-Draft will expire on {draft.get('date', 'TBD')}.


3. References

[MLTF] MLTF Datatracker, https://rfc.themetalayer.org/

Authors' Addresses

{chr(10).join([f'{author} <email@example.com>' for author in draft.get('authors', [])])}

Meta-Layer Initiative
"""
    
    # Return as plain text
    from flask import Response
    return Response(document_content, mimetype='text/plain; charset=utf-8')

@app.route('/doc/draft/<draft_name>/')
def draft_detail(draft_name):
    # First try to find in DRAFTS (published documents)
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)

    # If not found in DRAFTS, try to find as a submission ID or ML number
    submission = None
    if not draft:
        # Try to find by submission ID first
        submission = Submission.query.filter_by(id=draft_name).first()
        
        # If not found by ID, try to find by ML number
        if not submission:
            submission = Submission.query.filter_by(ml_number=draft_name).first()
        if submission:
            # Calculate pages and words for ordinals
            source_type = getattr(submission, 'sourceType', 'file')
            pages_count = 1
            words_count = 0
            ordinal_content_url = getattr(submission, 'ordinalContentUrl', None)
            ordinal_content_type = getattr(submission, 'ordinalContentType', '')
            
            if source_type == 'ordinal':
                # Fetch ordinal content to calculate words and pages
                
                if ordinal_content_url and ('text/' in ordinal_content_type or 'application/json' in ordinal_content_type):
                    try:
                        import requests
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            text_content = response.text
                            words_count = len(text_content.split())
                            # Estimate pages (assuming ~500 words per page)
                            pages_count = max(1, (words_count + 499) // 500)
                    except Exception as e:
                        app.logger.warning(f"Failed to fetch ordinal content for word/page count: {e}")
                        # Keep defaults
                        pass
            
            # Create a draft-like object from the submission
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'abstract': submission.abstract or 'Abstract not available for this draft.',
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'rev': '00',  # Default revision for submissions
                'pages': pages_count,
                'words': words_count,
                'stream': 'mltf',  # Default stream
                'ml_number': submission.ml_number,
                # Ordinal metadata
                'sourceType': source_type,
                'ordinalId': getattr(submission, 'ordinalId', None),
                'inscriptionNumber': getattr(submission, 'inscriptionNumber', None),
                'blockHeight': getattr(submission, 'blockHeight', None),
                'inscriptionTimestamp': getattr(submission, 'inscriptionTimestamp', None),
                'ordinalContentType': ordinal_content_type,
                # Revision metadata
                'is_revision': getattr(submission, 'is_revision', False),
                'revision_number': getattr(submission, 'revision_number', ''),
                'parent_draft_name': getattr(submission, 'parent_draft_name', '')
            }

    if not draft:
        return "Document not found", 404
    
    # Load full document content
    document_content = "Document content not available."
    calculated_pages = draft.get('pages', 1)
    calculated_words = draft.get('words', 0)

    # Try to get content from ordinal first
    if submission and draft.get('sourceType') == 'ordinal':
        ordinal_content_url = getattr(submission, 'ordinalContentUrl', None)
        ordinal_content_type = getattr(submission, 'ordinalContentType', '')
        
        if ordinal_content_url and ('text/' in ordinal_content_type or 'application/json' in ordinal_content_type):
            try:
                import requests
                import markdown2
                import bleach
                import re
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    raw_content = response.text
                    # Calculate words and pages from ordinal text
                    words = len(raw_content.split())
                    calculated_pages = max(1, (words + 499) // 500)
                    calculated_words = words
                    # Update draft with calculated values
                    draft['pages'] = calculated_pages
                    draft['words'] = calculated_words
                    
                    # Check if content is markdown
                    is_markdown = False
                    if 'text/plain' in ordinal_content_type or 'text/markdown' in ordinal_content_type:
                        # Detect markdown patterns
                        markdown_patterns = [
                            r'^#{1,6}\s+.+$',  # Headers
                            r'\*\*.+\*\*',      # Bold
                            r'\*.+\*',          # Italic
                            r'^\s*[-*+]\s+',    # Lists
                            r'^\s*\d+\.\s+',    # Numbered lists
                            r'\[.+\]\(.+\)',    # Links
                            r'!\[.*\]\(.+\)'    # Images
                        ]
                        for pattern in markdown_patterns:
                            if re.search(pattern, raw_content, re.MULTILINE):
                                is_markdown = True
                                break
                    
                    if is_markdown:
                        # Pre-process markdown: convert images inside figure tags to HTML with img-fluid class
                        # This must happen BEFORE markdown2 conversion
                        processed_content = re.sub(
                            r'<figure[^>]*>\s*!\[([^\]]*)\]\(([^)]+)\)',
                            lambda m: f'<figure><img src="{m.group(2)}" alt="{m.group(1)}" class="img-fluid" />',
                            raw_content
                        )
                        
                        # Convert markdown to HTML
                        html_content = markdown2.markdown(processed_content, extras=['fenced-code-blocks', 'tables'])
                        
                        # Fix image URLs: handle both /content/ paths and bare inscription IDs
                        # First, fix /content/ paths
                        html_content = re.sub(
                            r'src="(/content/[^"]+)"',
                            r'src="https://ordinals.com\1"',
                            html_content
                        )
                        # Then, fix bare inscription IDs or paths with inscription IDs
                        html_content = re.sub(
                            r'src="(?:[^"]*/)??([a-f0-9]{64}i\d+)"',
                            r'src="https://ordinals.com/content/\1"',
                            html_content
                        )
                        
                        # Sanitize HTML - allow figure, figcaption, small tags and class attribute
                        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                      'ul', 'ol', 'li', 'a', 'img', 'code', 'pre', 'blockquote', 'table',
                                      'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div', 'span',
                                      'figure', 'figcaption', 'small']
                        allowed_attrs = {
                            'a': ['href', 'title', 'target'],
                            'img': ['src', 'alt', 'title', 'class'],
                            'figure': ['class'],
                            'figcaption': ['class']
                        }
                        html_content = bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
                        
                        document_content = html_content
                    else:
                        # Display as plain text
                        document_content = raw_content
            except Exception as e:
                app.logger.warning(f"Failed to fetch ordinal content for display: {e}")
                document_content = f"Error loading ordinal content: {str(e)}"
        elif ordinal_content_url and ordinal_content_type.startswith('image/'):
            document_content = f'<img src="{ordinal_content_url}" class="img-fluid" style="max-width: 100%;" alt="Ordinal image content">'
        else:
            document_content = f"Ordinal content type: {ordinal_content_type}\nPreview not available for this content type."
    
    # Try to get content from submission file
    elif submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
                # Calculate words and pages from text
                words = len(document_content.split())
                # Estimate pages (assuming ~500 words per page)
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.docx':
                from docx import Document
                doc = Document(submission.file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content_parts.append(cell.text)
                document_content = '\n\n'.join(content_parts)
                # Calculate words and pages
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.pdf':
                # For PDFs, extract metadata but display with embedded viewer
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                # Get page count and estimate words
                calculated_pages = len(reader.pages) if reader.pages else 1
                # Estimate words (roughly 250-300 words per page for PDFs)
                calculated_words = calculated_pages * 275
                
                # Create embedded PDF viewer for display
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                document_content = f'''
<div class="pdf-viewer-container">
    <div class="alert alert-info mb-3">
        <i class="bi bi-file-pdf"></i> PDF Document ({calculated_pages} pages, ~{calculated_words} words, {file_size_kb:.1f} KB)
    </div>
    <iframe src="/view/{draft_name}" 
            type="application/pdf" 
            style="width: 100%; height: 800px; border: 1px solid var(--card-border); border-radius: 4px;"
            title="PDF Document Viewer">
        <p>Your browser does not support PDF preview. 
           <a href="/download/{draft_name}">Download the PDF</a> to view it.</p>
    </iframe>
</div>
'''
            else:
                document_content = f"Document content cannot be displayed for {ext.upper()} files. Please download to view."
        except Exception as e:
            document_content = f"Error loading document content: {str(e)}"
        # Update draft with calculated values
        if submission:
            draft['pages'] = calculated_pages
            draft['words'] = calculated_words

    # If no submission content, try to get from DRAFTS data
    elif draft and 'name' in draft:
        # For demo purposes, generate some sample content based on the draft
        document_content = f"""INTERNET-DRAFT                                               {', '.join(draft.get('authors', []))}
Intended status: Informational                            Meta-Layer Initiative
Expires: {draft.get('date', 'TBD')}                                      {draft.get('date', 'TBD')}


{draft.get('title', 'Document Title')}


Abstract

{draft.get('abstract', 'Abstract not available.')}


1. Introduction

This document describes {draft.get('title', 'the subject matter')}.

The content of this draft is currently being developed and will be available
in the full document once published.

2. Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions
of BCP 78 and BCP 79.

Meta-Layer Drafts are working documents of the Meta-Layer Task Force
(MLTF). These documents represent proposals and specifications for the
Meta-Layer ecosystem. The list of current Meta-Layer Drafts is available
in the MLTF datatracker.

Internet-Drafts are draft documents valid for a maximum of six months and
may be updated, replaced, or obsoleted by other documents at any time. It is
inappropriate to use Internet-Drafts as reference material or to cite them
other than as "work in progress."

This Internet-Draft will expire on {draft.get('date', 'TBD')}.


3. References

[MLTF] MLTF Datatracker, https://rfc.themetalayer.org/

Authors' Addresses

{chr(10).join([f'{author} <email@example.com>' for author in draft.get('authors', [])])}

Meta-Layer Initiative
"""

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    # Show ML number only if approved, otherwise show submission ID
    if draft.get('status') == 'approved' and draft.get('ml_number'):
        display_id = draft.get('ml_number')
    else:
        display_id = draft['name']
    # Check if this is a revision
    is_revision = draft.get('is_revision', False)
    revision_number = draft.get('revision_number', '')
    revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''
    
    # Determine content styling based on source type
    if draft.get('sourceType') == 'ordinal':
        content_style = "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 1em; line-height: 1.6;"
    else:
        content_style = "font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.4; white-space: pre-wrap;"
    
    content = f"""
    <div class="container mt-4">
        <h1>{display_id} {revision_badge}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Information</h5>
                    </div>
                    <div class="card-body">
                        <table class="table" style="color: var(--text-primary) !important;">
                            <tr><td style="color: var(--text-secondary) !important;"><strong>ID:</strong></td><td style="color: var(--text-primary) !important;">{display_id}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Title:</strong></td><td style="color: var(--text-primary) !important;">{draft['title']}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Status:</strong></td><td style="color: var(--text-primary) !important;"><span class="badge bg-secondary">{draft['status']}</span></td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Authors:</strong></td><td style="color: var(--text-primary) !important;">{', '.join(draft['authors'])}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Group:</strong></td><td style="color: var(--text-primary) !important;">{draft['group'] or 'N/A'}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Date:</strong></td><td style="color: var(--text-primary) !important;">{draft['date']}</td></tr>
                            {f'<tr><td colspan="2" style="padding-top: 15px;"><hr style="border-color: var(--border-color);"></td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Source:</strong></td><td style="color: var(--text-primary) !important;"><span class="badge bg-info"><i class="bi bi-coin"></i> Bitcoin Ordinal</span></td></tr>' if draft.get('sourceType') == 'ordinal' else f'<tr><td style="color: var(--text-secondary) !important;"><strong>Revision:</strong></td><td style="color: var(--text-primary) !important;">{draft["rev"]}</td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Pages:</strong></td><td style="color: var(--text-primary) !important;">{draft["pages"]}</td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Words:</strong></td><td style="color: var(--text-primary) !important;">{draft["words"]}</td></tr>'}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Inscription #:</strong></td><td style="color: var(--text-primary) !important;">{draft["inscriptionNumber"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('inscriptionNumber') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Block Height:</strong></td><td style="color: var(--text-primary) !important;">{draft["blockHeight"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('blockHeight') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Timestamp:</strong></td><td style="color: var(--text-primary) !important;">{draft["inscriptionTimestamp"].strftime("%Y-%m-%d %H:%M UTC") if draft.get("inscriptionTimestamp") else "N/A"}</td></tr>' if draft.get('sourceType') == 'ordinal' else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Content Type:</strong></td><td style="color: var(--text-primary) !important;">{draft["ordinalContentType"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('ordinalContentType') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Inscription ID:</strong></td><td style="color: var(--text-primary) !important;"><a href="https://ordinals.com/inscription/{draft["ordinalId"]}" target="_blank" class="text-decoration-none" style="color: var(--accent-color) !important;"><code style="font-family: monospace; font-size: 0.85em;">{shorten_inscription_id(draft["ordinalId"], 8)}</code></a></td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('ordinalId') else ''}
                        </table>
                    </div>
                </div>
                
                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Abstract</h5>
                    </div>
                    <div class="card-body">
                        <p>{draft.get('abstract', 'Abstract not available for this draft.')}</p>
                    </div>
                </div>

                <!-- Full Document Content -->
                <div class="card mt-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">Document Content</h5>
                        <div>
                            {'' if draft.get('sourceType') == 'ordinal' else f'''
                            <a href="/download/{draft['name']}" class="btn btn-sm btn-outline-primary" target="_blank">
                                <i class="fas fa-download me-1"></i>Download
                            </a>
                            <a href="/doc/draft/{draft['name']}.txt" class="btn btn-sm btn-outline-secondary" target="_blank">
                                <i class="fas fa-external-link-alt me-1"></i>View TXT
                            </a>
                            '''}
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="document-content" style="{content_style} background-color: var(--input-bg) !important; color: var(--text-primary) !important; padding: 20px; border-radius: 8px; max-height: 800px; overflow-y: auto; border: 1px solid var(--input-border);">
{document_content}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Actions</h5>
                    </div>
                    <div class="card-body">
                        {f'<a href="/doc/draft/{draft["name"]}/comments/" class="btn btn-primary w-100 mb-2">View Comments ({Comment.query.filter_by(draft_name=draft_name).count()})</a>' if draft.get('status') == 'approved' else ''}
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-secondary w-100 mb-2">View History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-info w-100 mb-2">View Revisions</a>
                        {f'<a href="/submit/revision/{draft["name"]}/" class="btn btn-success w-100 mb-2"><i class="fas fa-plus me-1"></i>Submit New Revision</a>' if current_user and draft.get('status') == 'approved' else ''}
                        {'' if draft.get('sourceType') == 'ordinal' else f'<a href="/download/{draft["name"]}" class="btn btn-outline-primary w-100 mb-2">Download Document</a>'}
                        {'<form method="post" action="/doc/draft/' + draft['name'] + '/follow/" style="display: inline;" class="mb-2"><select name="notification_level" class="form-select form-select-sm mb-1"><option value="all">All changes & comments</option><option value="significant">Significant changes only</option><option value="major">Major changes only</option><option value="comments">Comments only</option><option value="none">No notifications</option></select><button type="submit" class="btn btn-success w-100"><i class="fas fa-bell me-1"></i>Follow Document</button></form>' if current_user and draft.get('status') == 'approved' and not is_user_following_draft(draft_name, current_user) else ''}
                        {'<form method="post" action="/doc/draft/' + draft['name'] + '/unfollow/" style="display: inline;" class="mb-2"><button type="submit" class="btn btn-warning w-100"><i class="fas fa-bell-slash me-1"></i>Unfollow Document</button></form>' if current_user and draft.get('status') == 'approved' and is_user_following_draft(draft_name, current_user) else ''}
                        {get_notification_controls(draft_name, current_user) if current_user and draft.get('status') == 'approved' and is_user_following_draft(draft_name, current_user) else ''}
                        {'' if not current_user else ''}
                    </div>
                </div>
                
                {f'''<div class="card mt-3">
                    <div class="card-header">
                        <h5>Quick Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/doc/draft/{draft['name']}/comments/">
                            <div class="mb-3">
                                <textarea class="form-control" name="comment" rows="3" placeholder="Add a quick comment..." required></textarea>
                    </div>
                            <button type="submit" class="btn btn-success btn-sm w-100">Post Comment</button>
                        </form>
        </div>
    </div>''' if draft.get('status') == 'approved' else ''}
    
                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Related Documents</h5>
                    </div>
                <div class="card-body">
                        <p>Related documents would appear here in the real datatracker.</p>
                    </div>
                    </div>
                </div>
            </div>
        </div>
        """
    
    # Add document_content to the template
    content = content.replace('{document_content}', document_content)

    # Use ML number for title if approved and available, otherwise use draft name (submission ID)
    if draft.get('status') == 'approved' and draft.get('ml_number'):
        title_id = draft.get('ml_number')
    else:
        title_id = draft['name']
    return BASE_TEMPLATE.format(title=f"{title_id} - MLTF", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/doc/draft/<draft_name>/comments/', methods=['GET', 'POST'])
@require_auth
def draft_comments(draft_name):
    # First try to find in DRAFTS (published documents)
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    # If not found in DRAFTS, try to find as a submission ID
    submission = None
    if not draft:
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission:
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'ml_number': submission.ml_number
            }
    
    if not draft:
        return "Document not found", 404
    
    # Get display ID (ML number if available, otherwise draft name)
    display_id = draft.get('ml_number') or draft_name

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    current_user = get_current_user()

    # Handle new comment submission
    if request.method == 'POST':
        action = request.form.get('action', 'comment')
        
        if action == 'comment':
            comment_text = request.form.get('comment', '').strip()
            if comment_text:
                # Create new comment in database
                new_comment = Comment(
                    draft_name=draft_name,
                    text=comment_text,
                    author=current_user['name']
                )
                db.session.add(new_comment)
                db.session.commit()
                
                # Add to document history
                add_to_document_history(draft_name, 'Comment added', current_user['name'], f'Added comment: {comment_text[:50]}...')
                
                flash('Comment added successfully!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Please enter a comment.', 'error')
        
        elif action == 'like':
            comment_id = request.form.get('comment_id')
            if comment_id:
                liked = toggle_comment_like(draft_name, comment_id, current_user['name'])
                action_text = 'liked' if liked else 'unliked'
                flash(f'Comment {action_text}!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Invalid comment ID.', 'error')
        
        elif action == 'reply':
            parent_comment_id = request.form.get('parent_comment_id')
            reply_text = request.form.get('reply_text', '').strip()
            if reply_text and parent_comment_id:
                add_comment_reply(draft_name, parent_comment_id, reply_text, current_user)
                flash('Reply added successfully!', 'success')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Please enter a reply.', 'error')
    
        elif action == 'edit':
            comment_id = request.form.get('comment_id')
            new_text = request.form.get('new_text', '').strip()
            if comment_id and new_text:
                comment = Comment.query.filter_by(id=int(comment_id)).first()
                if comment and comment.author == current_user['name']:
                    # Check time limit
                    time_diff = datetime.utcnow() - comment.timestamp
                    time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
                    if time_diff <= time_limit and not comment.is_deleted:
                        # Store original text if first edit
                        if not comment.original_text:
                            comment.original_text = comment.text
                        comment.text = new_text
                        comment.edited_at = datetime.utcnow()
                        db.session.commit()
                        flash('Comment updated successfully!', 'success')
                    else:
                        flash('Edit time limit has expired.', 'error')
                else:
                    flash('You can only edit your own comments.', 'error')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Invalid comment or empty text.', 'error')
        
        elif action == 'delete':
            comment_id = request.form.get('comment_id')
            if comment_id:
                comment = Comment.query.filter_by(id=int(comment_id)).first()
                if comment and comment.author == current_user['name']:
                    # Check time limit
                    time_diff = datetime.utcnow() - comment.timestamp
                    time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
                    if time_diff <= time_limit and not comment.is_deleted:
                        comment.is_deleted = True
                        comment.text = '[Deleted]'
                        db.session.commit()
                        flash('Comment deleted successfully!', 'success')
                    else:
                        flash('Delete time limit has expired.', 'error')
                else:
                    flash('You can only delete your own comments.', 'error')
                return redirect(f'/doc/draft/{draft_name}/comments/')
            else:
                flash('Invalid comment ID.', 'error')

    # Get comments for this draft and build comment tree
    all_comments = build_comment_tree(draft_name)

    # Render the comment tree with nested replies
    comments_html = render_comment_tree(all_comments, draft_name)

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">Comments</li>
            </ol>
        </nav>
        
        <h1>Comments for {display_id}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary me-2">History</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>
        
        <div class="row">
            <div class="col-md-8">
                <h3>Comments ({len(all_comments)})</h3>
                <div id="flash-messages"></div>
                {comments_html}
                
                <div class="card mt-4">
                    <div class="card-header">
                        <h5>Add a Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="comment" class="form-label">Your Comment</label>
                                <textarea class="form-control" id="comment" name="comment" rows="4" placeholder="Enter your comment here..." required></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary">Submit Comment</button>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Info</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Last Updated:</strong> {draft['date']}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function toggleLike(commentId) {{
            // Create a form to submit the like action
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';

            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'like';

            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;

            form.appendChild(actionInput);
            form.appendChild(commentIdInput);
            document.body.appendChild(form);
            form.submit();
        }}
        
        function toggleReply(commentId) {{
            // Find the reply form for this comment
            const replyForm = document.getElementById('reply-form-' + commentId);
            if (replyForm) {{
                // Toggle visibility
                if (replyForm.style.display === 'none' || replyForm.style.display === '') {{
                replyForm.style.display = 'block';
            }} else {{
                replyForm.style.display = 'none';
            }}
            }}
        }}

        function editComment(commentId) {{
            const commentCard = document.getElementById('comment-' + commentId);
            if (!commentCard) return;
            
            // Find the comment text element
            const commentText = commentCard.querySelector('p.mb-2');
            if (!commentText) return;
            
            const currentText = commentText.textContent.trim();
            
            // Create edit form
            const editForm = document.createElement('form');
            editForm.method = 'POST';
            editForm.style.marginTop = '10px';
            
            const textarea = document.createElement('textarea');
            textarea.className = 'form-control';
            textarea.name = 'new_text';
            textarea.rows = 3;
            textarea.value = currentText;
            textarea.required = true;
            
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'edit';
            
            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;
            
            const buttonDiv = document.createElement('div');
            buttonDiv.className = 'd-flex gap-2 mt-2';
            
            const saveBtn = document.createElement('button');
            saveBtn.type = 'submit';
            saveBtn.className = 'btn btn-sm btn-primary';
            saveBtn.textContent = 'Save';
            
            const cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'btn btn-sm btn-secondary';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.onclick = function() {{
                commentText.style.display = 'block';
                editForm.remove();
            }};
            
            buttonDiv.appendChild(saveBtn);
            buttonDiv.appendChild(cancelBtn);
            
            editForm.appendChild(actionInput);
            editForm.appendChild(commentIdInput);
            editForm.appendChild(textarea);
            editForm.appendChild(buttonDiv);
            
            // Hide original text and show edit form
            commentText.style.display = 'none';
            commentText.parentNode.insertBefore(editForm, commentText.nextSibling);
        }}

        function deleteComment(commentId) {{
            if (!confirm('Are you sure you want to delete this comment? This action cannot be undone.')) {{
                return;
            }}
            
            // Create a form to submit the delete action
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';
            
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'delete';
            
            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;
            
            form.appendChild(actionInput);
            form.appendChild(commentIdInput);
            document.body.appendChild(form);
            form.submit();
        }}
    </script>
"""

    return BASE_TEMPLATE.format(title=f"Comments - {draft_name}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/doc/draft/<draft_name>/history/')
def draft_history(draft_name):
    # First try to find in DRAFTS (published documents)
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    # If not found in DRAFTS, try to find as a submission ID
    submission = None
    if not draft:
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission:
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'ml_number': submission.ml_number,
            }
    
    if not draft:
        return "Document not found", 404
    
    # Determine display ID (ML-Draft-XXX or internal ID)
    display_id = draft.get('ml_number', draft_name) or draft_name
    
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    # Get history for this draft
    history = DocumentHistory.query.filter_by(draft_name=draft_name).order_by(DocumentHistory.timestamp.desc()).all()
    
    history_html = ""
    if history:
        for entry in history:
            history_html += f"""
            <div class="card mb-3">
                        <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge bg-primary">{entry.action}</span>
                        <small class="text-muted">{entry.timestamp.strftime('%Y-%m-%d %H:%M')}</small>
                            </div>
                    <p class="mb-1"><strong>User:</strong> {entry.user}</p>
                    <p class="mb-0">{entry.details}</p>
                        </div>
                    </div>
            """
    else:
        history_html = """
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            No history available for this draft.
        </div>
        """
    
    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">History</li>
            </ol>
        </nav>
        
        <h1>History for {display_id}</h1>
        <p class="lead">{draft['title']}</p>
        
        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>

                {history_html}
            </div>
    """

    return BASE_TEMPLATE.format(title=f"History - {display_id}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/doc/draft/<draft_name>/follow/', methods=['POST'])
def follow_draft(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to follow documents.', 'error')
        return redirect(url_for('draft_detail', draft_name=draft_name))

    # Check if already following
    existing_follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if existing_follow:
        flash('You are already following this document.', 'info')
    else:
        # Get notification level from form, default to 'all'
        notification_level = request.form.get('notification_level', 'all')
        follow = UserFollow(
            user_id=current_user['id'],
            draft_name=draft_name,
            notification_level=notification_level
        )
        db.session.add(follow)
        db.session.commit()
        level_desc = UserFollow.NOTIFICATION_LEVELS.get(notification_level, 'All changes and comments')
        flash(f'You are now following this document with {level_desc.lower()} notifications.', 'success')

    return redirect(url_for('draft_detail', draft_name=draft_name))

@app.route('/doc/draft/<draft_name>/unfollow/', methods=['POST'])
def unfollow_draft(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to unfollow documents.', 'error')
        return redirect(url_for('draft_detail', draft_name=draft_name))

    follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash('You have stopped following this document.', 'success')
    else:
        flash('You were not following this document.', 'info')

    return redirect(url_for('draft_detail', draft_name=draft_name))

@app.route('/doc/draft/<draft_name>/update-notification/', methods=['POST'])
def update_notification_level(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to update notification settings.', 'error')
        return redirect(url_for('draft_detail', draft_name=draft_name))

    follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if not follow:
        flash('You are not following this document.', 'error')
        return redirect(url_for('draft_detail', draft_name=draft_name))

    notification_level = request.form.get('notification_level', 'all')
    if notification_level in UserFollow.NOTIFICATION_LEVELS:
        follow.notification_level = notification_level
        db.session.commit()
        level_desc = UserFollow.NOTIFICATION_LEVELS[notification_level]
        flash(f'Notification level updated to: {level_desc}', 'success')
    else:
        flash('Invalid notification level.', 'error')

    return redirect(url_for('draft_detail', draft_name=draft_name))

@app.route('/doc/draft/<draft_name>/revisions/')
def draft_revisions(draft_name):
    current_user = get_current_user()
    # First try to find in DRAFTS (published documents)
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    # If not found in DRAFTS, try to find as a submission ID
    submission = None
    original_submission_id = None
    if not draft:
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission:
            # Determine the original submission ID
            # If this submission is a revision, use its parent_draft_name
            # Otherwise, this IS the original
            if getattr(submission, 'is_revision', False) and getattr(submission, 'parent_draft_name', ''):
                original_submission_id = submission.parent_draft_name
            else:
                original_submission_id = submission.id
            
            # For the revisions page, just show the requested draft as-is
            # Don't try to find the "latest" - show what was requested
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'rev': getattr(submission, 'revision_number', '00') or '00',
                'pages': submission.pages or 1,
                'words': submission.words or 0,
                'is_revision': getattr(submission, 'is_revision', False),
                'parent_draft_name': getattr(submission, 'parent_draft_name', ''),
                'original_submission_id': original_submission_id,  # Always the true original
                'ml_number': submission.ml_number,
            }
    
    if not draft:
        return "Document not found", 404
    
    # Determine display ID (ML-Draft-XXX or internal ID)
    display_id = draft.get('ml_number', draft_name) or draft_name

    # Calculate pages and words from document content if it's a submission
    calculated_pages = draft.get('pages', 1)
    calculated_words = draft.get('words', 0)
    
    if submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
                # Calculate words and pages from text
                words = len(document_content.split())
                # Estimate pages (assuming ~500 words per page)
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.docx':
                from docx import Document
                doc = Document(submission.file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content_parts.append(cell.text)
                document_content = '\n\n'.join(content_parts)
                # Calculate words and pages
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                document_content = '\n\n'.join(content_parts)
                # Clean up PDF text
                import re
                document_content = re.sub(r'\n+', '\n', document_content)
                document_content = re.sub(r' +', ' ', document_content)
                # Calculate words and pages
                words = len(document_content.split())
                calculated_pages = len(reader.pages) if reader.pages else max(1, (words + 499) // 500)
                calculated_words = words
        except Exception as e:
            # If calculation fails, keep default values
            pass
        
        # Update draft with calculated values
        draft['pages'] = calculated_pages
        draft['words'] = calculated_words

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    # Get the original submission ID to find all revisions
    original_id = draft.get('original_submission_id', draft['name'])
    
    # Get the original submission for display
    original_submission = Submission.query.filter_by(id=original_id).first()
    
    # Find all approved/published revisions for this draft
    all_revisions = Submission.query.filter(
        Submission.parent_draft_name == original_id,
        Submission.is_revision == True,
        Submission.status.in_(['approved', 'published'])
    ).order_by(Submission.revision_number.desc()).all()
    
    # Build revision list HTML - include ALL revisions (current and historical)
    revisions_list_html = ""
    for rev in all_revisions:
        status_badge_class = {
            'submitted': 'bg-warning text-dark',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'published': 'bg-info'
        }.get(rev.status, 'bg-secondary')
        
        what_changed = getattr(rev, 'what_changed', '')
        what_changed_html = f'<p class="mb-2"><strong>What changed:</strong> {what_changed}</p>' if what_changed else ''
        
        # Check if this is the current revision
        is_current = (rev.id == draft['name'])
        current_badge = '<span class="badge bg-primary ms-2">Current</span>' if is_current else ''
        
        revisions_list_html += f"""
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <a href="/doc/draft/{rev.id}/" class="text-decoration-none">Revision {rev.revision_number}</a>
                    {current_badge}
                </h6>
                <span class="badge {status_badge_class}">{rev.status.title()}</span>
            </div>
            <div class="card-body">
                <p class="mb-2"><strong>Published:</strong> {rev.approved_at.strftime('%Y-%m-%d') if rev.approved_at and rev.status == 'approved' else (rev.submitted_at.strftime('%Y-%m-%d') if rev.submitted_at else 'N/A')}</p>
                <p class="mb-2"><strong>Pages:</strong> {rev.pages or 1} | <strong>Words:</strong> {rev.words or 0}</p>
                {what_changed_html}
            </div>
        </div>
        """
    
    # Show revision history
    revisions_html = f"""
                <h4>Revision History</h4>
                {revisions_list_html if revisions_list_html else '<p class="text-muted">No revisions yet.</p>'}
                
                <div class="card mt-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            <a href="/doc/draft/{original_id}/" class="text-decoration-none">Original Version (Rev 00)</a>
                        </h6>
                        <span class="badge bg-success">Approved</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-2"><strong>Published:</strong> {original_submission.approved_at.strftime('%Y-%m-%d') if original_submission and original_submission.approved_at else (original_submission.submitted_at.strftime('%Y-%m-%d') if original_submission and original_submission.submitted_at else draft['date'])}</p>
                        <p class="mb-0"><strong>Pages:</strong> {original_submission.pages if original_submission else 1} | <strong>Words:</strong> {original_submission.words if original_submission else 0}</p>
                    </div>
                </div>

    <div class="alert alert-info mt-3">
        <i class="fas fa-info-circle me-2"></i>
        Detailed revision history and diff viewing would be implemented in a full datatracker system.
            </div>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">Revisions</li>
            </ol>
        </nav>

        <h1>Revisions for {display_id}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            {f'<a href="/submit/revision/{draft_name}/" class="btn btn-success me-2"><i class="fas fa-plus me-1"></i>Submit New Revision</a>' if current_user and draft.get('status') == 'approved' else ''}
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary">History</a>
        </div>

        {revisions_html}
    </div>
    """

    return BASE_TEMPLATE.format(title=f"Revisions - {display_id}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)

@app.route('/group/')
def groups():
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark') if get_current_user() else 'light'
    groups_html = ""
    for group in GROUPS:
        # Get chair information from database
        all_chairs = WorkingGroupChair.query.filter_by(group_acronym=group['acronym']).all()
        if all_chairs:
            chair_names = []
            for chair in all_chairs:
                chair_name = chair.chair_name
                if not chair.approved:
                    chair_name += " (Pending)"
                chair_names.append(chair_name)
            chair_display = ", ".join(chair_names)
        else:
            chair_display = "TBD"

        groups_html += f"""
        <div class="col-md-6">
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">
                        <a href="/group/{group['acronym']}/">{group['acronym']}</a>
                    </h5>
                    <p class="card-text">{group['name']}</p>
                    <div class="document-meta">
                        <span class="badge bg-primary">{group['type']}</span>
                        <span class="badge bg-success ms-2">{group['state']}</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Chair: {chair_display}<br>
                            {group['description']}
                        </small>
                    </div>
                </div>
            </div>
        </div>
        """

    # Get theme from session or user preference
    current_theme = session.get('theme', 'dark')

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
                <h1 class="mb-4">Working Groups</h1>
                <p class="lead mb-4">Browse the Meta-Layer Desirable Properties working groups.</p>

                <div class="row">
                    {groups_html}
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Working Groups - MLTF",
        theme=current_theme,
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)
@app.route('/group/<acronym>/')
def group_detail(acronym):
    """Display individual working group details"""
    # Find the group - handle both full acronyms and short forms (DP1, DP2, etc.)
    group = None
    full_acronym = acronym  # Default to the URL parameter

    for g in GROUPS:
        if g['acronym'] == acronym:
            group = g
            full_acronym = g['acronym']
            break
        # Also check for short form (dp1 -> dp1-federated-auth, DP1 -> dp1-federated-auth)
        if acronym.lower().startswith('dp') and g['acronym'].startswith(acronym.lower() + '-'):
            group = g
            full_acronym = g['acronym']
            break

    if not group:
        return f"Working group '{acronym}' not found. Available: {[g['acronym'] for g in GROUPS]}", 404

    user_menu = generate_user_menu()
    current_user = get_current_user()

    # Check if user is already a member
    is_member = False
    if current_user:
        membership = WorkingGroupMember.query.filter_by(
            group_acronym=full_acronym,
            user_name=current_user['name']
        ).first()
        is_member = membership is not None

    # Get chair information using the full acronym
    all_chairs = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).all()
    if all_chairs:
        approved_chairs = [chair.chair_name for chair in all_chairs if chair.approved]
        pending_chairs = [chair.chair_name for chair in all_chairs if not chair.approved]

        if approved_chairs:
            chair_name = ", ".join(approved_chairs)
            if pending_chairs:
                chair_name += f" (Pending: {', '.join(pending_chairs)})"
        else:
            chair_name = f"Pending: {', '.join(pending_chairs)}"
        chair_approved = len(approved_chairs) > 0
    else:
        chair_name = "TBD"
        chair_approved = False

    join_button = ""
    if current_user and not is_member:
        join_button = f'<button class="btn btn-primary" onclick="joinGroup(\'{full_acronym}\')">Join Working Group</button>'
    elif current_user and is_member:
        join_button = '<span class="badge bg-success">Member</span> <button class="btn btn-outline-danger btn-sm ms-2" onclick="leaveGroup(\'{full_acronym}\')">Leave</button>'

    # Admin chair management
    chair_management = ""
    if current_user and current_user.get('role') == 'admin':
        # Get all chairs for this group
        all_chairs = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).all()

        # Create options for the multi-select dropdown
        chair_options = ""
        selected_chairs = []
        for chair in all_chairs:
            chair_display = chair.chair_name
            if not chair.approved:
                chair_display += " (Pending)"
            chair_options += f'<option value="{chair.id}" {"selected" if chair.approved else ""}>{chair_display}</option>'
            if chair.approved:
                selected_chairs.append(chair.chair_name)

        # Convert selected chairs to JSON for JavaScript
        selected_chairs_json = json.dumps(selected_chairs)

        chair_management = f'''
        <div class="mt-4 p-3 border rounded">
            <h5>Chair Management</h5>
            <div class="mb-3">
                <label class="form-label">Current Chairs:</label>
                <select multiple class="form-select" id="chair-select-{full_acronym}" size="4">
                    {chair_options}
                </select>
                <div class="form-text">Select multiple chairs using Ctrl+Click (Cmd+Click on Mac)</div>
            </div>
            <div class="d-flex gap-2">
                <input type="text" id="new-chair-input-{full_acronym}" class="form-control" placeholder="Add new chair name">
                <button type="button" class="btn btn-success" onclick="addChair('{full_acronym}')">Add Chair</button>
                <button type="button" class="btn btn-warning" onclick="updateChairs('{full_acronym}')">Update Chairs</button>
        </div>
            <div class="mt-2">
                <small class="text-muted">Current approved chairs: {", ".join(selected_chairs) if selected_chairs else "None"}</small>
            </div>
        </div>
        '''

    # Get theme from session or user preference
    current_theme = session.get('theme', current_user.get('theme', 'dark') if current_user else 'dark')

    content = f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                        <li class="breadcrumb-item"><a href="/group/">Working Groups</a></li>
                        <li class="breadcrumb-item active">{group['name']}</li>
            </ol>
        </nav>
        
                <div class="card mb-4">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <h1 class="card-title mb-2">{group['name']}</h1>
                                <p class="text-muted mb-3">{group['acronym'].upper()}</p>
                                <p class="card-text">{group['description']}</p>
                            </div>
                            <div class="text-end">
                                {join_button}
                            </div>
                        </div>
                    </div>
                </div>
        
        <div class="row">
            <div class="col-md-8">
                        <div class="card mb-4">
                            <div class="card-header">
                                <h5 class="mb-0">About</h5>
                </div>
                            <div class="card-body">
                                <p>{group['description']}</p>
            </div>
                        </div>
                    </div>
            <div class="col-md-4">
                        <div class="card mb-4">
                    <div class="card-header">
                                <h5 class="mb-0">Leadership</h5>
                    </div>
                    <div class="card-body">
                                <p><strong>Chair:</strong> {chair_name}</p>
                                {'<span class="badge bg-warning">Pending Approval</span>' if not chair_approved and chair_name != "TBD" else ''}
                            </div>
                        </div>

                        {chair_management}
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function joinGroup(acronym) {{
        fetch(`/group/${{acronym}}/join`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }}
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error joining group: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error joining group');
        }});
    }}

    function leaveGroup(acronym) {{
        fetch(`/group/${{acronym}}/leave`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }}
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error leaving group: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error leaving group');
        }});
    }}

    function addChair(acronym) {{
        const input = document.getElementById(`new-chair-input-${{acronym}}`);
        const chairName = input.value.trim();
        if (!chairName) {{
            alert('Please enter a chair name');
            return;
        }}

        fetch(`/group/${{acronym}}/add_chair`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ chair_name: chairName }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error adding chair: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error adding chair');
        }});
    }}

    function updateChairs(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const selectedOptions = Array.from(select.selectedOptions);
        const chairIds = selectedOptions.map(option => parseInt(option.value));

        fetch(`/group/${{acronym}}/update_chairs`, {{
            method: 'POST',
            headers: {{
                'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ chair_ids: chairIds }})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error updating chairs: ' + data.message);
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error updating chairs');
        }});
    }}

    function removeChair(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const selectedOptions = Array.from(select.selectedOptions);

        if (selectedOptions.length === 0) {{
            alert('Please select chairs to remove');
            return;
        }}

        if (confirm('Are you sure you want to remove ' + selectedOptions.length + ' chair(s)?')) {{
            const chairIds = selectedOptions.map(option => parseInt(option.value));

            fetch(`/group/${{acronym}}/remove_chairs`, {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                }},
                body: JSON.stringify({{ chair_ids: chairIds }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    alert('Error removing chairs: ' + data.message);
                }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error removing chairs');
            }});
        }}
    }}
    </script>
    """

    return BASE_TEMPLATE.format(
        title=f"{group['name']} - MLTF",
        theme=current_theme,
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)

@app.route('/group/<acronym>/join', methods=['POST'])
@require_auth
def join_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    # Check if already a member
    existing = WorkingGroupMember.query.filter_by(
        group_acronym=acronym,
        user_name=current_user['name']
    ).first()

    if existing:
        return jsonify({'success': False, 'message': 'Already a member'}), 400

    # Add membership
    membership = WorkingGroupMember(
        group_acronym=acronym,
        user_name=current_user['name']
    )
    db.session.add(membership)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Joined successfully'})

@app.route('/group/<acronym>/leave', methods=['POST'])
@require_auth
def leave_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    # Remove membership
    membership = WorkingGroupMember.query.filter_by(
        group_acronym=acronym,
        user_name=current_user['name']
    ).first()

    if not membership:
        return jsonify({'success': False, 'message': 'Not a member'}), 400

    db.session.delete(membership)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Left successfully'})

@app.route('/group/<acronym>/add_chair', methods=['POST'])
@require_role('admin')
def add_group_chair(acronym):
    data = request.get_json()
    chair_name = data.get('chair_name', '').strip()
    if not chair_name:
        return jsonify({'success': False, 'message': 'Chair name required'}), 400

    # Check if chair already exists
    existing = WorkingGroupChair.query.filter_by(group_acronym=acronym, chair_name=chair_name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Chair already exists'}), 400

    # Add new chair (unapproved)
    chair = WorkingGroupChair(
        group_acronym=acronym,
        chair_name=chair_name,
        approved=False
    )
    db.session.add(chair)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair added successfully'})

@app.route('/group/<acronym>/update_chairs', methods=['POST'])
@require_role('admin')
def update_group_chairs(acronym):
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    # Mark all chairs as unapproved first
    WorkingGroupChair.query.filter_by(group_acronym=acronym).update({'approved': False})

    # Approve selected chairs
    if chair_ids:
        WorkingGroupChair.query.filter(
            WorkingGroupChair.group_acronym == acronym,
            WorkingGroupChair.id.in_(chair_ids)
        ).update({'approved': True})

    db.session.commit()

    return jsonify({'success': True, 'message': 'Chairs updated successfully'})

@app.route('/group/<acronym>/remove_chairs', methods=['POST'])
@require_role('admin')
def remove_group_chairs(acronym):
    data = request.get_json()
    chair_ids = data.get('chair_ids', [])

    if not chair_ids:
        return jsonify({'success': False, 'message': 'No chairs selected'}), 400

    # Remove selected chairs
    WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == acronym,
        WorkingGroupChair.id.in_(chair_ids)
    ).delete()

    db.session.commit()

    return jsonify({'success': True, 'message': 'Chairs removed successfully'})

@app.route('/person/')
def people():
    """People directory - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    content = """
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center">
                    <i class="fas fa-user-friends fa-4x text-muted mb-4"></i>
                    <h1 class="mb-3">People Directory</h1>
                    <p class="lead text-muted mb-4">Coming Soon</p>
                    <p class="mb-4">We're building a comprehensive directory of MLTF participants and contributors. This feature will help you connect with other members of the community.</p>
                    <a href="/" class="btn btn-primary">Return to Home</a>
        </div>
            </div>
        </div>
        </div>
        """
    
    return BASE_TEMPLATE.format(
        title="People Directory - MLTF",
        theme=session.get('theme', 'dark'),
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)

@app.route('/meeting/')
def meetings():
    """Meetings - coming soon"""
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    content = """
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center">
                    <i class="fas fa-calendar fa-4x text-muted mb-4"></i>
                    <h1 class="mb-3">Meetings</h1>
                    <p class="lead text-muted mb-4">Coming Soon</p>
                    <p class="mb-4">Information about upcoming MLTF meetings and sessions will be available here. Stay tuned for announcements about our first events.</p>
                    <a href="/" class="btn btn-primary">Return to Home</a>
                </div>
            </div>
        </div>
    </div>
    """

    return BASE_TEMPLATE.format(
        title="Meetings - MLTF",
        theme=session.get('theme', 'dark'),
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)

# Deployment API endpoint (development only)
@app.route('/_deploy/reload', methods=['POST'])
def reload_app():
    """Reload the application - development only"""
    if not IS_DEVELOPMENT:
        return jsonify({'error': 'Not available in production'}), 403
    
    # Clear Python cache
    import shutil
    cache_dirs = []
    for root, dirs, files in os.walk(os.path.dirname(os.path.abspath(__file__))):
        if '__pycache__' in dirs:
            cache_dirs.append(os.path.join(root, '__pycache__'))
        for file in files:
            if file.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, file))
                except:
                    pass
    
    for cache_dir in cache_dirs:
        try:
            shutil.rmtree(cache_dir)
        except:
            pass
    
    # Touch the file to trigger reload if using file watcher
    # For systemd, we'll return a signal to restart
    return jsonify({
        'status': 'success',
        'message': 'Cache cleared. Service restart required.',
        'restart_command': 'systemctl --user restart datatracker-dev.service'
    })

@app.route('/_deploy/status', methods=['GET'])
def deployment_status():
    """Check deployment status - comprehensive status endpoint"""
    import subprocess
    from datetime import datetime
    
    # Get git info
    git_branch = 'unknown'
    git_commit = 'unknown'
    git_commit_short = 'unknown'
    try:
        result = subprocess.run(['git', 'branch', '--show-current'], 
                               capture_output=True, text=True, timeout=2, cwd=os.path.dirname(os.path.abspath(__file__)))
        if result.returncode == 0:
            git_branch = result.stdout.strip() or 'unknown'
    except:
        pass
    
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                               capture_output=True, text=True, timeout=2, cwd=os.path.dirname(os.path.abspath(__file__)))
        if result.returncode == 0:
            git_commit = result.stdout.strip() or 'unknown'
            git_commit_short = git_commit[:8] if len(git_commit) > 8 else git_commit
    except:
        pass
    
    # Check service status
    service_name = f'datatracker{"-dev" if IS_DEVELOPMENT else ""}.service'
    service_active = None
    try:
        result = subprocess.run(['systemctl', '--user', 'is-active', service_name],
                               capture_output=True, text=True, timeout=2)
        service_active = result.returncode == 0
    except:
        pass
    
    # Check database
    db_exists = os.path.exists(DB_PATH)
    db_size = 0
    if db_exists:
        try:
            db_size = os.path.getsize(DB_PATH)
        except:
            pass
    
    status = {
        'environment': ENV,
        'port': PORT,
        'database': {
            'path': DB_PATH,
            'exists': db_exists,
            'size_bytes': db_size,
            'size_mb': round(db_size / 1024 / 1024, 2) if db_size > 0 else 0
        },
        'git': {
            'branch': git_branch,
            'commit': git_commit,
            'commit_short': git_commit_short
        },
        'service': {
            'name': service_name,
            'active': service_active
        },
        'deployed_at': datetime.now().isoformat(),
        'version': '2026-01-17-v2'
    }

    return jsonify(status)

@app.route('/_deploy/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    import subprocess
    
    # Check database connection
    db_healthy = False
    try:
        db.session.execute(db.text('SELECT 1'))
        db_healthy = True
    except:
        pass
    
    # Check service status
    service_name = f'datatracker{"-dev" if IS_DEVELOPMENT else ""}.service'
    service_healthy = None
    try:
        result = subprocess.run(['systemctl', '--user', 'is-active', service_name],
                               capture_output=True, text=True, timeout=2)
        service_healthy = result.returncode == 0
    except:
        pass
    
    overall_healthy = db_healthy and (service_healthy is True)
    
    return jsonify({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'database': 'connected' if db_healthy else 'disconnected',
        'service': 'active' if service_healthy else 'inactive',
        'timestamp': datetime.now().isoformat()
    }), 200 if overall_healthy else 503

@app.route('/_deploy/test', methods=['GET'])
def deployment_test():
    """Show a visible test page"""
    return f"""
    <html>
    <head><title>Deployment Test</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1 style="color: red;">🚨 DEPLOYMENT TEST PAGE 🚨</h1>
        <div style="background-color: #ffcccc; border: 3px solid red; padding: 20px; margin: 20px 0; border-radius: 10px;">
            <h2 style="color: red;">If you can see this page, the deployment worked!</h2>
            <p><strong>Environment:</strong> {ENV}</p>
            <p><strong>Port:</strong> {PORT}</p>
            <p><strong>Database:</strong> {DB_PATH}</p>
            <p><strong>Time:</strong> {__import__('datetime').datetime.now()}</p>
        </div>
        <p><a href="/">← Back to main site</a></p>
    </body>
    </html>
    """

if __name__ == '__main__':
    # Initialize deployment safety checks
    init_deployment_safety()
    # Initialize database on startup
    init_db()
    print(f"🚀 Starting MLTF Datatracker - BUILD {BUILD_NUMBER}")
    print(f"Environment: {ENV} mode on port {PORT}")
    print(f"Database: {DB_PATH}")
    # Disable reloader when running under systemd (detected by systemd environment)
    # The reloader can cause hanging in systemd services
    use_reloader = DEBUG and not os.environ.get('INVOCATION_ID')  # systemd sets INVOCATION_ID
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG, use_reloader=use_reloader)

