#!/usr/bin/env python3
"""
Migration: Add requires_election to Role, fix Vote for role elections (GOV-HUB-3)

- Adds requires_election to role table
- Makes vote.submission_id nullable (for election votes)
- Fixes vote.role_id: INTEGER -> VARCHAR(50) to match role.id
- Requires SQLite 3.35+ for DROP COLUMN
Usage: python migrate_vote_role_election.py [--dry-run] [--db path]
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

    backup_path = f"{db_path}.backup_pre_vote_role_election_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Add requires_election to role
        cursor.execute("PRAGMA table_info(role)")
        role_cols = [r[1] for r in cursor.fetchall()]
        if 'requires_election' not in role_cols:
            if dry_run:
                print("[DRY RUN] Would add role.requires_election")
            else:
                cursor.execute("ALTER TABLE role ADD COLUMN requires_election INTEGER DEFAULT 0")
                conn.commit()
                print("✅ Added role.requires_election")
        else:
            print("✅ role.requires_election already exists")

        # 2. Make vote.submission_id nullable (SQLite: recreate table or use table copy)
        # SQLite doesn't support ALTER COLUMN. We use a workaround: add submission_id_new, copy, drop old, rename.
        cursor.execute("PRAGMA table_info(vote)")
        vote_cols = {r[1]: r[2] for r in cursor.fetchall()}
        # Check if submission_id has NOT NULL - we need to recreate to make nullable
        cursor.execute("PRAGMA table_info(vote)")
        for r in cursor.fetchall():
            if r[1] == 'submission_id' and r[3] == 1:  # notnull=1
                # Need to make nullable - recreate table
                if dry_run:
                    print("[DRY RUN] Would make vote.submission_id nullable")
                else:
                    cursor.execute("""
                        CREATE TABLE vote_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            public_id VARCHAR(36) UNIQUE NOT NULL,
                            layer_id VARCHAR(50) NOT NULL,
                            submission_id VARCHAR(8),
                            artifact_id VARCHAR(36),
                            created_by_id INTEGER NOT NULL,
                            title VARCHAR(255) NOT NULL,
                            description TEXT,
                            start_at DATETIME NOT NULL,
                            end_at DATETIME NOT NULL,
                            quorum_count INTEGER NOT NULL,
                            win_threshold REAL NOT NULL DEFAULT 0.5,
                            status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
                            result VARCHAR(20),
                            result_summary TEXT,
                            vote_type VARCHAR(20) DEFAULT 'approval',
                            role_id VARCHAR(50),
                            seats INTEGER DEFAULT 1,
                            created_at DATETIME,
                            closed_at DATETIME,
                            FOREIGN KEY (layer_id) REFERENCES layer(id),
                            FOREIGN KEY (submission_id) REFERENCES submission(id),
                            FOREIGN KEY (artifact_id) REFERENCES artifact(id),
                            FOREIGN KEY (created_by_id) REFERENCES user(id),
                            FOREIGN KEY (role_id) REFERENCES role(id)
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO vote_new SELECT id, public_id, layer_id, submission_id, artifact_id,
                            created_by_id, title, description, start_at, end_at, quorum_count, win_threshold,
                            status, result, result_summary,
                            COALESCE(vote_type,'approval'), role_id, COALESCE(seats,1), created_at, closed_at
                        FROM vote
                    """)
                    cursor.execute("DROP TABLE vote")
                    cursor.execute("ALTER TABLE vote_new RENAME TO vote")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_vote_layer_id ON vote(layer_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_vote_status ON vote(status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_vote_vote_type ON vote(vote_type)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS ix_vote_role_id ON vote(role_id)")
                    conn.commit()
                    print("✅ Made vote.submission_id nullable, fixed role_id to VARCHAR(50)")
                break
        else:
            # Check role_id type - if INTEGER, fix it
            if vote_cols.get('role_id') == 'INTEGER':
                if dry_run:
                    print("[DRY RUN] Would fix vote.role_id to VARCHAR(50)")
                else:
                    try:
                        cursor.execute("ALTER TABLE vote DROP COLUMN role_id")
                        conn.commit()
                    except sqlite3.OperationalError:
                        pass  # Might not support DROP COLUMN
                    try:
                        cursor.execute("ALTER TABLE vote ADD COLUMN role_id VARCHAR(50) REFERENCES role(id)")
                        conn.commit()
                        print("✅ Fixed vote.role_id to VARCHAR(50)")
                    except sqlite3.OperationalError as e:
                        print(f"Note: role_id alter: {e}")
            else:
                print("✅ vote.role_id already correct or no change needed")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--db', help='Database path')
    args = parser.parse_args()
    db_path = args.db or get_db_path()
    ok = run_migration(db_path, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
