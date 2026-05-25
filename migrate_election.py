#!/usr/bin/env python3
"""
Migration: Add VoteCandidate and election fields (GOV-HUB-3 Phase 2.4)

Adds vote_candidate table, vote_type/role_id/seats to vote.
Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_election.py [--dry-run] [--db path]
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

    backup_path = f"{db_path}.backup_pre_election_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def add_col(table, col, spec):
        cursor.execute("PRAGMA table_info({})".format(table))
        if col not in [r[1] for r in cursor.fetchall()]:
            if dry_run:
                print(f"[DRY RUN] Would add {table}.{col}")
            else:
                cursor.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, col, spec))
                conn.commit()
                print("✅ Added {}.{}".format(table, col))
        else:
            print("✅ {}.{} already exists".format(table, col))

    try:
        # 1. Add vote_type, role_id, seats to vote
        add_col("vote", "vote_type", "VARCHAR(20) DEFAULT 'approval'")
        add_col("vote", "role_id", "INTEGER")
        add_col("vote", "seats", "INTEGER DEFAULT 1")

        # 2. Create vote_candidate table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vote_candidate'")
        if cursor.fetchone():
            print("✅ vote_candidate table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create vote_candidate table")
            else:
                cursor.execute("""
                    CREATE TABLE vote_candidate (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        vote_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        display_name VARCHAR(255),
                        display_order INTEGER DEFAULT 0,
                        status VARCHAR(20) DEFAULT 'approved',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (vote_id) REFERENCES vote(id),
                        FOREIGN KEY (user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_vote_candidate_vote_id ON vote_candidate(vote_id)")
                conn.commit()
                print("✅ Created vote_candidate table")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
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
