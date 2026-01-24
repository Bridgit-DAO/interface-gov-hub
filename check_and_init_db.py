#!/usr/bin/env python3
import sqlite3
import sys

db_path = '/home/ubuntu/datatracker/instance_dev/datatracker.db'

print(f"Checking database: {db_path}")
print()

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"Tables in database: {len(tables)}")
    for table in tables:
        print(f"  - {table[0]}")
        
        # Show column count for each table
        cursor.execute(f"PRAGMA table_info({table[0]})")
        cols = cursor.fetchall()
        print(f"    Columns: {len(cols)}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
