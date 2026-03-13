#!/usr/bin/env python3
"""
Migration: Add Quest, QuestSubmission, and Monument tables (GOV-HUB-3 Phase 2)

Creates quest, quest_submission, monument tables.
Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_quest_monument.py [--dry-run] [--db path]
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

    backup_path = f"{db_path}.backup_pre_quest_monument_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Create quest table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quest'")
        if cursor.fetchone():
            print("✅ quest table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create quest table")
            else:
                cursor.execute("""
                    CREATE TABLE quest (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        public_id VARCHAR(36) UNIQUE NOT NULL,
                        layer_id VARCHAR(50) NOT NULL,
                        creator_user_id INTEGER,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        quest_type VARCHAR(50) DEFAULT 'contribution',
                        difficulty VARCHAR(20) DEFAULT 'medium',
                        status VARCHAR(20) DEFAULT 'open',
                        acceptance_criteria TEXT,
                        due_date DATETIME,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME,
                        FOREIGN KEY (layer_id) REFERENCES layer(id),
                        FOREIGN KEY (creator_user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_quest_layer_id ON quest(layer_id)")
                cursor.execute("CREATE INDEX idx_quest_status ON quest(status)")
                cursor.execute("CREATE INDEX idx_quest_created_at ON quest(created_at)")
                conn.commit()
                print("✅ Created quest table")

        # 2. Create quest_submission table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quest_submission'")
        if cursor.fetchone():
            print("✅ quest_submission table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create quest_submission table")
            else:
                cursor.execute("""
                    CREATE TABLE quest_submission (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        quest_id INTEGER NOT NULL,
                        artifact_id VARCHAR(36),
                        submitter_user_id INTEGER NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending_review',
                        review_notes TEXT,
                        reviewed_at DATETIME,
                        reviewed_by_user_id INTEGER,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (quest_id) REFERENCES quest(id),
                        FOREIGN KEY (artifact_id) REFERENCES artifact(id),
                        FOREIGN KEY (submitter_user_id) REFERENCES user(id),
                        FOREIGN KEY (reviewed_by_user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_quest_submission_quest_id ON quest_submission(quest_id)")
                cursor.execute("CREATE INDEX idx_quest_submission_status ON quest_submission(status)")
                conn.commit()
                print("✅ Created quest_submission table")

        # 3. Create monument table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='monument'")
        if cursor.fetchone():
            print("✅ monument table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create monument table")
            else:
                cursor.execute("""
                    CREATE TABLE monument (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        public_id VARCHAR(36) UNIQUE NOT NULL,
                        layer_id VARCHAR(50) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        monument_type VARCHAR(50) DEFAULT 'reference',
                        steward_user_id INTEGER,
                        uri VARCHAR(500),
                        provenance TEXT,
                        status VARCHAR(20) DEFAULT 'active',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME,
                        FOREIGN KEY (layer_id) REFERENCES layer(id),
                        FOREIGN KEY (steward_user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_monument_layer_id ON monument(layer_id)")
                cursor.execute("CREATE INDEX idx_monument_status ON monument(status)")
                conn.commit()
                print("✅ Created monument table")

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
