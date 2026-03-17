#!/usr/bin/env python3
"""
Migration: Add EventLog table (GOV-HUB-3 Rule 3)

Creates append-only event_log table for governance events.
Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_event_log.py [--dry-run] [--db path]
"""
import os
import sys
import shutil
from datetime import datetime


def get_db_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instance = os.path.join(script_dir, 'instance_dev')
    return os.path.join(instance, 'datatracker_dev.db')


def run_migration(db_path, dry_run=False):
    import sqlite3

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    backup_path = f"{db_path}.backup_pre_event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_log'")
        if cursor.fetchone():
            print("✅ event_log table already exists")
            conn.close()
            return True

        if dry_run:
            print("[DRY RUN] Would create event_log table")
            conn.close()
            return True

        cursor.execute("""
            CREATE TABLE event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type VARCHAR(50) NOT NULL,
                actor_type VARCHAR(30),
                actor_id VARCHAR(50),
                subject_type VARCHAR(30),
                subject_id VARCHAR(50),
                layer_id VARCHAR(50),
                payload_json TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (layer_id) REFERENCES layer(id)
            )
        """)
        conn.commit()
        print("✅ Created event_log table")

        cursor.execute("CREATE INDEX idx_event_log_event_type ON event_log(event_type)")
        conn.commit()
        cursor.execute("CREATE INDEX idx_event_log_layer_id ON event_log(layer_id)")
        conn.commit()
        cursor.execute("CREATE INDEX idx_event_log_created_at ON event_log(created_at)")
        conn.commit()
        cursor.execute("CREATE INDEX idx_event_log_layer_created ON event_log(layer_id, created_at)")
        conn.commit()
        print("✅ Created indexes")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

    print("\n✅ EventLog migration complete")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add event_log table')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--db', default=None, help='Database path')
    args = parser.parse_args()
    db_path = args.db or get_db_path()
    ok = run_migration(db_path, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
