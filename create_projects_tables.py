#!/usr/bin/env python3
"""
Create Projects, Workgroups, Guilds, Roles, Claims, and Badges tables
"""
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from extensions import db
from models import (
    Layer, Workgroup, Guild, GuildMembership, GuildInvitation,
    Cluster, Role, Claim, Badge, StatusChange
)

def create_tables():
    """Create all Projects/Workgroups/Guilds/Roles tables"""
    with app.app_context():
        print("Creating Projects, Workgroups, Guilds, and Roles system tables...")
        
        # Create tables
        db.create_all()
        
        print("✅ Tables created successfully!")
        
        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'layer', 'working_group', 'guild', 'guild_membership', 'guild_invitation',
            'cluster', 'role', 'claim', 'badge', 'status_change'
        ]
        
        for table in expected_tables:
            if table in tables:
                print(f"✅ {table} table exists")
            else:
                print(f"❌ {table} table NOT found")
        
        print("\n📊 Summary:")
        print(f"Total tables in database: {len(tables)}")
        print(f"Expected new tables: {len(expected_tables)}")
        print(f"Found: {sum(1 for t in expected_tables if t in tables)}/{len(expected_tables)}")

if __name__ == '__main__':
    create_tables()
