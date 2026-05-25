#!/usr/bin/env python3
"""
Database Migration Script for Web3Auth Schema Updates
Run this to add new Web3Auth fields to existing database

SAFEGUARDS:
- Shows which environment will be affected
- Requires explicit confirmation for production
- Creates backup before any changes
- Verifies backup integrity
"""

import os
import sys
from pathlib import Path
import shutil
from datetime import datetime

# Add current directory to path so we can import the Flask app
sys.path.insert(0, str(Path(__file__).parent))

def get_environment_info():
    """Get current environment information"""
    flask_env = os.environ.get('FLASK_ENV', 'production')
    instance_dir = Path(__file__).parent / ('instance_dev' if flask_env == 'development' else 'instance')
    db_path = instance_dir / 'datatracker.db'
    env_name = 'DEVELOPMENT' if flask_env == 'development' else 'PRODUCTION'

    return {
        'env': flask_env,
        'env_name': env_name,
        'db_path': db_path,
        'instance_dir': instance_dir
    }

def create_backup(db_path):
    """Create a backup of the database"""
    backup_dir = Path(__file__).parent / 'backups'
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'migration-backup-{timestamp}.db'

    print(f"📦 Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Verify backup
    if backup_path.stat().st_size > 0:
        print("✅ Backup created and verified")
        return backup_path
    else:
        print("❌ Backup creation failed!")
        return None

def confirm_production_operation(env_info):
    """Require explicit confirmation for production operations"""
    if env_info['env_name'] == 'PRODUCTION':
        print("\n" + "="*60)
        print("🚨 PRODUCTION ENVIRONMENT DETECTED")
        print("="*60)
        print(f"Database: {env_info['db_path']}")
        print("This operation will modify PRODUCTION data!")
        print("="*60)

        response = input("\nType 'YES' to confirm production operation: ").strip()
        if response != 'YES':
            print("Operation cancelled.")
            return False

        print("✅ Production operation confirmed")
        return True

    return True

from app import app
from extensions import db
from models import User

def migrate_database():
    """Add new Web3Auth columns to existing database"""

    env_info = get_environment_info()

    print(f"\n🔍 ENVIRONMENT CHECK")
    print(f"Environment: {env_info['env_name']}")
    print(f"Database: {env_info['db_path']}")
    print(f"Exists: {env_info['db_path'].exists()}")

    # Require confirmation for production
    if not confirm_production_operation(env_info):
        return

    # Create backup
    if env_info['db_path'].exists():
        backup_path = create_backup(env_info['db_path'])
        if not backup_path:
            print("❌ Backup failed - aborting migration")
            return
    else:
        print("⚠️  No existing database found - creating new one")

    with app.app_context():
        # Check current schema
        print("\n🔍 Checking current database schema...")
        try:
            # Try to query existing users to see current schema
            users = User.query.limit(1).all()
            print(f"Found {len(users)} users in database")
        except Exception as e:
            print(f"Database schema issue: {e}")
            if env_info['env_name'] == 'PRODUCTION':
                print("❌ PRODUCTION DATABASE ERROR - Refusing to recreate")
                print("Please restore from backup and contact administrator")
                return
            else:
                print("Recreating database with new schema...")

                # Drop all tables and recreate
                db.drop_all()
                db.create_all()

                print("Database recreated successfully!")
                return

        # Check if new columns exist by trying to access them
        try:
            # Try to access new fields on a user
            if users:
                user = users[0]
                # Try to access new fields
                verifier_id = getattr(user, 'web3authVerifierId', None)
                display_name = getattr(user, 'displayName', None)
                handle = getattr(user, 'handle', None)
                if all([verifier_id is not None, display_name is not None, handle is not None]):
                    print("✅ New schema fields already exist - no migration needed")
                    return
        except Exception as e:
            print(f"New schema fields missing: {e}")

        print("\n🛠️  Adding new Web3Auth columns to existing database...")

        if env_info['env_name'] == 'PRODUCTION':
            print("⚠️  PRODUCTION ENVIRONMENT - Using SAFE migration approach")

            # For production, use a safer approach
            print("This would use a proper migration tool like Alembic in production")
            print("For now, please contact administrator for production schema changes")
            return

        # For SQLite, we need to recreate the table with new schema
        # This is a simplified approach - in production you'd use proper migrations

        # Get existing user data
        existing_users = []
        for user in User.query.all():
            existing_users.append({
                'id': user.id,
                'username': user.username,
                'password_hash': user.password_hash,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'theme': user.theme,
                'created_at': user.created_at,
                'last_login': user.last_login,
            })

        print(f"📊 Preserving {len(existing_users)} existing users")

        # Drop and recreate tables
        db.drop_all()
        db.create_all()

        # Restore user data with default values for new fields
        for user_data in existing_users:
            user = User(
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                name=user_data['name'],
                email=user_data['email'],
                role=user_data['role'],
                theme=user_data['theme'],
                created_at=user_data['created_at'],
                last_login=user_data['last_login'],
                # New fields with defaults
                web3authVerifierId=None,
                typeOfLogin=None,
                displayName=None,
                displayNameSetAt=None,
                oauthName=None,
                profileImage=None,
                evmAddress=None,
                solanaAddress=None,
                handle=user_data['username'],  # Default handle to username
            )
            db.session.add(user)

        db.session.commit()
        print(f"✅ Migrated {len(existing_users)} users successfully!")

if __name__ == '__main__':
    migrate_database()
    print("Migration complete!")