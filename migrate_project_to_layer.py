#!/usr/bin/env python3
"""
Migration: Project → Layer

Renames:
- table project → layer
- table project_member → layer_member  
- table project_admin → layer_admin
- column project_id → layer_id in all tables

Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_project_to_layer.py [--dry-run] [--db path]
"""
import os
import sys
import shutil
from datetime import datetime

def get_db_path():
    """Get dev DB path - same as config for dev."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instance = os.path.join(script_dir, 'instance_dev')
    return os.path.join(instance, 'datatracker_dev.db')

def run_migration(db_path, dry_run=False):
    import sqlite3
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Backup
    backup_path = f"{db_path}.backup_pre_layer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()
    
    try:
        if dry_run:
            print("[DRY RUN] Would execute: ALTER TABLE project RENAME TO layer")
            print("[DRY RUN] Would rename project_member, project_admin, and project_id→layer_id in all tables")
            conn.close()
            return True
        
        # 1. Rename project table to layer
        cursor.execute("ALTER TABLE project RENAME TO layer")
        conn.commit()
        print("✅ Renamed table project → layer")
        
        # 2. Fix superseded_by_id FK in layer (references self)
        # SQLite: the column stays; FK target is now layer
        # No change needed - table rename updates the reference
        
        # 3. Rename project_member → layer_member, project_id → layer_id
        cursor.execute("ALTER TABLE project_member RENAME TO layer_member")
        conn.commit()
        cursor.execute("ALTER TABLE layer_member RENAME COLUMN project_id TO layer_id")
        conn.commit()
        print("✅ Renamed project_member → layer_member, project_id → layer_id")
        
        # 4. Rename project_admin → layer_admin, project_id → layer_id
        cursor.execute("ALTER TABLE project_admin RENAME TO layer_admin")
        conn.commit()
        cursor.execute("ALTER TABLE layer_admin RENAME COLUMN project_id TO layer_id")
        conn.commit()
        print("✅ Renamed project_admin → layer_admin, project_id → layer_id")
        
        # 5. Tables with project_id that reference layer (formerly project)
        tables_to_rename_col = [
            'submission',
            'inscription_order', 
            'role_image',
            'badge_cycle',
            'one_time_badge',
            'waitlist',
            'working_group',  # Workgroup model uses __tablename__ = 'working_group'
            'cluster',
            'role',
            'claim',
            'badge',
            'vote',
        ]
        
        for table in tables_to_rename_col:
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [c[1] for c in cursor.fetchall()]
            if 'project_id' in cols:
                cursor.execute(f"ALTER TABLE {table} RENAME COLUMN project_id TO layer_id")
                conn.commit()
                print(f"✅ {table}: project_id → layer_id")
            elif 'project_id' not in cols and table != 'layer':
                print(f"⚠️  {table}: no project_id column (skipping)")
        
        # 6. email_unsubscribe - if exists
        try:
            cursor.execute("PRAGMA table_info(email_unsubscribe)")
            cols = [c[1] for c in cursor.fetchall()]
            if 'project_id' in cols:
                cursor.execute("ALTER TABLE email_unsubscribe RENAME COLUMN project_id TO layer_id")
                conn.commit()
                print(f"✅ email_unsubscribe: project_id → layer_id")
        except sqlite3.OperationalError:
            pass  # Table may not exist
        
        # 7. Unique constraints and indexes - SQLite keeps old names
        # unique_project_member -> will need manual fix if we want unique_layer_member
        # For now the constraint still works (same columns, different name)
        
        conn.execute("PRAGMA foreign_keys = ON")
        print("\n✅ Migration complete. Restart the app and run code updates.")
        return True
        
    except sqlite3.OperationalError as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        if 'RENAME COLUMN' in str(e):
            print("   SQLite 3.35+ required for RENAME COLUMN. Check: sqlite3 --version")
        return False
    finally:
        conn.close()

def main():
    dry_run = '--dry-run' in sys.argv
    db_path = get_db_path()
    for i, arg in enumerate(sys.argv):
        if arg == '--db' and i + 1 < len(sys.argv):
            db_path = sys.argv[i + 1]
            break
    
    print(f"Database: {db_path}")
    if dry_run:
        print("DRY RUN - no changes will be made")
    
    success = run_migration(db_path, dry_run)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
