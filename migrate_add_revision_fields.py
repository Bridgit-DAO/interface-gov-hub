#!/usr/bin/env python3
"""
Migration: Add revision fields to Submission table
"""

import os
import sys
import sqlite3

# Determine which database to use
if len(sys.argv) > 1 and sys.argv[1] == '--dev':
    DB_PATH = 'instance_dev/datatracker_dev.db'
    print("🔧 Using DEV database")
else:
    DB_PATH = 'instance/datatracker.db'
    print("🔧 Using PRODUCTION database")

def migrate():
    """Add revision fields to submission table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    # Backup database
    backup_path = f"{DB_PATH}.backup.revision_fields"
    import shutil
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup created: {backup_path}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]
        
        fields_to_add = []
        if 'parent_draft_name' not in columns:
            fields_to_add.append(('parent_draft_name', 'TEXT'))
        if 'revision_number' not in columns:
            fields_to_add.append(('revision_number', 'TEXT'))
        if 'what_changed' not in columns:
            fields_to_add.append(('what_changed', 'TEXT'))
        if 'is_revision' not in columns:
            fields_to_add.append(('is_revision', 'INTEGER DEFAULT 0'))
        
        if not fields_to_add:
            print("✅ All revision fields already exist")
            return True
        
        # Add new columns
        for field_name, field_type in fields_to_add:
            sql = f"ALTER TABLE submission ADD COLUMN {field_name} {field_type}"
            print(f"   Adding column: {field_name}")
            cursor.execute(sql)
        
        conn.commit()
        print(f"✅ Added {len(fields_to_add)} revision fields to submission table")
        
        # Verify
        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"✅ Verified columns: {', '.join(['parent_draft_name', 'revision_number', 'what_changed', 'is_revision'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRATION: Add Revision Fields to Submission Table")
    print("=" * 60)
    
    success = migrate()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("\nNew fields added:")
        print("  - parent_draft_name: Link to parent draft")
        print("  - revision_number: e.g., '01', '02'")
        print("  - what_changed: Description of changes")
        print("  - is_revision: Boolean flag")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
