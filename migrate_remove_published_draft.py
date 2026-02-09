#!/usr/bin/env python3
"""
Migration script to remove PublishedDraft table and add rfc_number to submission table.

This migration:
1. Adds rfc_number column to submission table
2. Drops the published_draft table (currently unused, 0 records)
3. Updates schema to match new unified data model

Run this on both dev and production databases after deploying code changes.
"""

import sqlite3
import sys
import os
from datetime import datetime

def migrate_database(db_path):
    """Migrate database to remove PublishedDraft table"""
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Create backup first
    backup_path = f"{db_path}.backup.remove_published_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"📦 Creating backup: {backup_path}")
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backup created successfully")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if rfc_number column already exists
        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'rfc_number' not in columns:
            print("➕ Adding rfc_number column to submission table...")
            cursor.execute("""
                ALTER TABLE submission 
                ADD COLUMN rfc_number INTEGER
            """)
            print("✅ rfc_number column added")
        else:
            print("ℹ️  rfc_number column already exists")
        
        # Check if published_draft table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='published_draft'
        """)
        
        if cursor.fetchone():
            # Check if table has any data
            cursor.execute("SELECT COUNT(*) FROM published_draft")
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"⚠️  WARNING: published_draft table has {count} records!")
                print("   These records will be lost. Press Ctrl+C to cancel, or Enter to continue...")
                input()
            
            print("🗑️  Dropping published_draft table...")
            cursor.execute("DROP TABLE published_draft")
            print("✅ published_draft table dropped")
        else:
            print("ℹ️  published_draft table doesn't exist (already removed)")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print(f"   Backup saved at: {backup_path}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        print(f"   Database unchanged. Backup at: {backup_path}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("PublishedDraft Table Removal Migration")
    print("=" * 60)
    print()
    
    # Determine which database to migrate
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default to dev database
        db_path = "/home/ubuntu/datatracker/instance_dev/datatracker_dev.db"
    
    print(f"Target database: {db_path}")
    print()
    
    success = migrate_database(db_path)
    
    if success:
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print("✅ rfc_number column added to submission table")
        print("✅ published_draft table removed")
        print("\nNext steps:")
        print("1. Restart the application")
        print("2. Verify admin dashboard shows correct counts")
        print("3. Test publishing a draft to RFC status")
        sys.exit(0)
    else:
        print("\n❌ Migration failed. Please review errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
