#!/usr/bin/env python3
"""
Create RoleImage and RoleImageVote tables in the database
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import RoleImage, RoleImageVote

def create_tables():
    """Create the RoleImage and RoleImageVote tables"""
    with app.app_context():
        print("Creating role_image and role_image_vote tables...")
        
        # Create tables
        db.create_all()
        
        print("✅ Tables created successfully!")
        
        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'role_image' in tables:
            print("✅ role_image table exists")
        else:
            print("❌ role_image table NOT found")
            
        if 'role_image_vote' in tables:
            print("✅ role_image_vote table exists")
        else:
            print("❌ role_image_vote table NOT found")

if __name__ == '__main__':
    create_tables()
