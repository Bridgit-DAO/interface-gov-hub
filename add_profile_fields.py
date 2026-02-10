#!/usr/bin/env python3
"""Add profile fields to user table and statement/nominator fields to working_group_chair table"""

import sqlite3
import sys

def add_profile_fields():
    # Connect to database
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add fields to user table
        print("Adding profile fields to user table...")
        
        # Check if fields already exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'banner_image' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN banner_image VARCHAR(500)")
            print("  ✓ Added banner_image")
        else:
            print("  - banner_image already exists")
            
        if 'headline' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN headline VARCHAR(200)")
            print("  ✓ Added headline")
        else:
            print("  - headline already exists")
            
        if 'bio' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN bio TEXT")
            print("  ✓ Added bio")
        else:
            print("  - bio already exists")
            
        if 'social_links' not in columns:
            cursor.execute("ALTER TABLE user ADD COLUMN social_links TEXT")  # JSON string
            print("  ✓ Added social_links")
        else:
            print("  - social_links already exists")
        
        # Add fields to working_group_chair table
        print("\nAdding nomination fields to working_group_chair table...")
        
        cursor.execute("PRAGMA table_info(working_group_chair)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'statement' not in columns:
            cursor.execute("ALTER TABLE working_group_chair ADD COLUMN statement TEXT")
            print("  ✓ Added statement")
        else:
            print("  - statement already exists")
            
        if 'nominated_by_user_id' not in columns:
            cursor.execute("ALTER TABLE working_group_chair ADD COLUMN nominated_by_user_id INTEGER REFERENCES user(id)")
            print("  ✓ Added nominated_by_user_id")
        else:
            print("  - nominated_by_user_id already exists")
            
        if 'is_self_nomination' not in columns:
            cursor.execute("ALTER TABLE working_group_chair ADD COLUMN is_self_nomination BOOLEAN DEFAULT 1")
            print("  ✓ Added is_self_nomination")
        else:
            print("  - is_self_nomination already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    add_profile_fields()
