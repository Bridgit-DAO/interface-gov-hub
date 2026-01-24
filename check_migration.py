#!/usr/bin/env python3
import sqlite3
import sys

db_path = '/home/ubuntu/datatracker/instance_dev/datatracker.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check submission table columns
    cursor.execute("PRAGMA table_info(submission)")
    columns = cursor.fetchall()
    
    column_names = [col[1] for col in columns]
    
    ordinal_columns = [
        'sourceType', 'ordinalId', 'ordinalContentUrl', 'ordinalContentType',
        'inscriptionNumber', 'blockHeight', 'inscriptionTimestamp'
    ]
    
    print("=== Submission Table Schema ===")
    print(f"Total columns: {len(column_names)}")
    print()
    
    print("Ordinal columns status:")
    for col in ordinal_columns:
        status = "✅ Present" if col in column_names else "❌ Missing"
        print(f"  {col}: {status}")
    
    missing = [col for col in ordinal_columns if col not in column_names]
    
    print()
    if missing:
        print(f"❌ MIGRATION NEEDED - Missing columns: {', '.join(missing)}")
        sys.exit(1)
    else:
        print("✅ ALL ORDINAL COLUMNS PRESENT - Migration successful!")
        sys.exit(0)
        
except Exception as e:
    print(f"Error: {e}")
    sys.exit(2)
finally:
    if conn:
        conn.close()
