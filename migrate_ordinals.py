#!/usr/bin/env python3
"""
Database migration script for Ordinals integration
Adds columns to support ordinal inscriptions as draft sources
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path):
    """Add ordinals support columns to the database"""
    
    print(f"Migrating database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_needed = []
        
        # Define new columns
        new_columns = {
            'sourceType': "ALTER TABLE submission ADD COLUMN sourceType TEXT DEFAULT 'file'",
            'ordinalId': "ALTER TABLE submission ADD COLUMN ordinalId TEXT",
            'inscriptionNumber': "ALTER TABLE submission ADD COLUMN inscriptionNumber INTEGER",
            'blockHeight': "ALTER TABLE submission ADD COLUMN blockHeight INTEGER",
            'inscriptionTimestamp': "ALTER TABLE submission ADD COLUMN inscriptionTimestamp DATETIME",
            'ordinalContentUrl': "ALTER TABLE submission ADD COLUMN ordinalContentUrl TEXT",
            'ordinalContentType': "ALTER TABLE submission ADD COLUMN ordinalContentType TEXT"
        }
        
        # Check which columns need to be added
        for col_name, sql in new_columns.items():
            if col_name not in columns:
                migrations_needed.append((col_name, sql))
        
        if not migrations_needed:
            print("✅ Database already up to date - no migration needed")
            return True
        
        # Execute migrations
        print(f"Adding {len(migrations_needed)} new columns...")
        for col_name, sql in migrations_needed:
            print(f"  - Adding column: {col_name}")
            cursor.execute(sql)
        
        # Update existing records to have sourceType='file'
        cursor.execute("UPDATE submission SET sourceType='file' WHERE sourceType IS NULL")
        
        conn.commit()
        print(f"✅ Successfully added {len(migrations_needed)} columns")
        
        # Verify migration
        cursor.execute("PRAGMA table_info(submission)")
        new_columns_list = [col[1] for col in cursor.fetchall()]
        print(f"\nSubmission table now has {len(new_columns_list)} columns:")
        for col in ['sourceType', 'ordinalId', 'inscriptionNumber', 'blockHeight', 
                    'inscriptionTimestamp', 'ordinalContentUrl', 'ordinalContentType']:
            status = "✓" if col in new_columns_list else "✗"
            print(f"  {status} {col}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def main():
    """Migrate both dev and production databases"""
    
    print("=" * 60)
    print("Ordinals Integration - Database Migration")
    print("=" * 60)
    print()
    
    # Migrate dev database
    dev_db = "/home/ubuntu/datatracker/instance_dev/datatracker_dev.db"
    print("1. Migrating DEV database...")
    dev_success = migrate_database(dev_db)
    print()
    
    # Migrate production database
    prod_db = "/home/ubuntu/datatracker/instance/datatracker.db"
    print("2. Migrating PRODUCTION database...")
    
    # Backup production database first
    if os.path.exists(prod_db):
        backup_path = f"/home/ubuntu/datatracker/backups/datatracker_prod_before_ordinals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        print(f"   Creating backup: {backup_path}")
        import shutil
        shutil.copy2(prod_db, backup_path)
        print(f"   ✅ Backup created")
    
    prod_success = migrate_database(prod_db)
    print()
    
    # Summary
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"DEV database:        {'✅ Success' if dev_success else '❌ Failed'}")
    print(f"PRODUCTION database: {'✅ Success' if prod_success else '❌ Failed'}")
    print()
    
    if dev_success and prod_success:
        print("✅ All migrations completed successfully!")
        print()
        print("Next steps:")
        print("1. Restart dev service: systemctl --user restart datatracker-dev.service")
        print("2. Test ordinals integration on dev")
        print("3. Restart prod service: systemctl --user restart datatracker.service")
        return 0
    else:
        print("❌ Some migrations failed. Please check errors above.")
        return 1

if __name__ == "__main__":
    exit(main())
