#!/usr/bin/env python3
"""
UUID + public_id Migration (Phase 2 & 3 of UUID + Layer Migration Plan)

Adds public_id (UUID) to all major entities. Backfills existing rows.
Enables canonical UUID-based URLs: /p/<uuid>, /layer/<uuid>, /draft/<uuid>, etc.

Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_uuid.py [--dry-run] [--db path]

Tables migrated (in order):
- user, layer, submission, badge, vote (already have public_id in model; ensure DB has it)
- claim, role, working_group, role_image, cluster, badge_cycle, one_time_badge
"""
import os
import sys
import shutil
from datetime import datetime
from uuid import uuid4


def get_db_path():
    """Get dev DB path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instance = os.path.join(script_dir, 'instance_dev')
    return os.path.join(instance, 'datatracker_dev.db')


def run_migration(db_path, dry_run=False):
    import sqlite3

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    # Backup
    backup_path = f"{db_path}.backup_pre_uuid_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tables that need public_id. Order: no FK dependencies on public_id.
    tables = [
        'user', 'layer', 'submission', 'badge', 'vote',
        'claim', 'role', 'working_group', 'role_image',
        'cluster', 'badge_cycle', 'one_time_badge',
        'guild', 'ballot',  # ballot/claim may need it for future routes
    ]

    for table_name in tables:
        try:
            cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        except sqlite3.OperationalError:
            print(f"⏭️  Table {table_name} does not exist, skipping")
            continue

        try:
            cursor.execute(f"SELECT public_id FROM {table_name} LIMIT 1")
            print(f"✅ {table_name}: public_id already exists")
        except sqlite3.OperationalError:
            if dry_run:
                print(f"[DRY RUN] Would add public_id to {table_name}")
                continue
            print(f"🔄 Adding public_id to {table_name}...")
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN public_id VARCHAR(36)")
            conn.commit()

            # PK column is 'id' for all our tables
            pk_col = 'id'

            cursor.execute(f"SELECT {pk_col} FROM {table_name} WHERE public_id IS NULL")
            rows = cursor.fetchall()
            for row in rows:
                cursor.execute(
                    f"UPDATE {table_name} SET public_id = ? WHERE {pk_col} = ?",
                    (str(uuid4()), row[0])
                )
            conn.commit()
            print(f"   ✅ Backfilled {len(rows)} rows")

            try:
                cursor.execute(f"CREATE UNIQUE INDEX idx_{table_name}_public_id ON {table_name}(public_id)")
                conn.commit()
                print(f"   ✅ Created unique index")
            except sqlite3.OperationalError:
                pass

    conn.close()
    print("\n✅ UUID migration complete")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add public_id (UUID) to major entities')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--db', default=None, help='Database path (default: instance_dev/datatracker_dev.db)')
    args = parser.parse_args()
    db_path = args.db or get_db_path()
    ok = run_migration(db_path, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
