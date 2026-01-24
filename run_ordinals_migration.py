#!/usr/bin/env python3
"""
Standalone script to add ordinals support columns to the submission table
"""
import sqlite3
import sys
import os

# Determine which database to use
if len(sys.argv) > 1 and sys.argv[1] == 'prod':
    db_path = '/home/ubuntu/datatracker/instance/datatracker.db'
    env = 'PRODUCTION'
else:
    db_path = '/home/ubuntu/datatracker/instance_dev/datatracker.db'
    env = 'DEVELOPMENT'

print(f"=== Ordinals Migration Script ({env}) ===")
print(f"Database: {db_path}")
print()

if not os.path.exists(db_path):
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if ordinals columns exist
    print("1. Checking current schema...")
    cursor.execute("PRAGMA table_info(submission)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"   Current columns: {len(columns)}")
    
    ordinals_columns = {
        'sourceType': ('TEXT', 'file'),
        'ordinalId': ('TEXT', None),
        'ordinalContentUrl': ('TEXT', None),
        'ordinalContentType': ('TEXT', None),
        'inscriptionNumber': ('INTEGER', None),
        'blockHeight': ('INTEGER', None),
        'inscriptionTimestamp': ('DATETIME', None)
    }
    
    print()
    print("2. Checking ordinals columns...")
    missing_columns = []
    for col_name in ordinals_columns.keys():
        if col_name in columns:
            print(f"   ✅ {col_name} - already exists")
        else:
            print(f"   ❌ {col_name} - missing")
            missing_columns.append(col_name)
    
    if not missing_columns:
        print()
        print("✅ All ordinals columns already exist!")
        conn.close()
        sys.exit(0)
    
    print()
    print(f"3. Adding {len(missing_columns)} missing columns...")
    added_columns = []
    
    for col_name, (col_type, default_value) in ordinals_columns.items():
        if col_name not in columns:
            try:
                if default_value:
                    sql = f"ALTER TABLE submission ADD COLUMN {col_name} {col_type} DEFAULT '{default_value}'"
                else:
                    sql = f"ALTER TABLE submission ADD COLUMN {col_name} {col_type}"
                
                print(f"   Executing: {sql}")
                cursor.execute(sql)
                added_columns.append(col_name)
                print(f"   ✅ Added {col_name}")
            except Exception as e:
                print(f"   ❌ Failed to add {col_name}: {e}")
    
    if added_columns:
        conn.commit()
        print()
        print(f"✅ Successfully added {len(added_columns)} columns:")
        for col in added_columns:
            print(f"   - {col}")
    
    # Verify
    print()
    print("4. Verifying...")
    cursor.execute("PRAGMA table_info(submission)")
    new_columns = [col[1] for col in cursor.fetchall()]
    
    all_present = all(col in new_columns for col in ordinals_columns.keys())
    
    if all_present:
        print(f"   ✅ All ordinals columns verified present")
        print(f"   Total columns now: {len(new_columns)}")
    else:
        print(f"   ⚠️  Some columns still missing")
    
    conn.close()
    
    print()
    print("=== Migration Complete ===")
    print()
    print("Next steps:")
    print("  1. Restart the service: bash /home/ubuntu/datatracker/force-restart-dev.sh")
    print("  2. Test by submitting a new ordinal")
    
    sys.exit(0 if all_present else 1)
    
except Exception as e:
    print(f"❌ Error during migration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(2)
