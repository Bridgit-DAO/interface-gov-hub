#!/usr/bin/env python3
"""
Migration: Add Artifact and ArtifactRelation tables (GOV-HUB-3)

Creates artifact (central knowledge object) and artifact_relation (typed links).
Run from gov-hub-dev root. Backs up DB first.
Usage: python migrate_artifact.py [--dry-run] [--db path]
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

    backup_path = f"{db_path}.backup_pre_artifact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Create artifact table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact'")
        if cursor.fetchone():
            print("✅ artifact table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create artifact table")
            else:
                cursor.execute("""
                    CREATE TABLE artifact (
                        id VARCHAR(36) PRIMARY KEY,
                        public_id VARCHAR(36) UNIQUE NOT NULL,
                        layer_id VARCHAR(50),
                        creator_user_id INTEGER,
                        artifact_type VARCHAR(50) NOT NULL,
                        title VARCHAR(255),
                        summary TEXT,
                        uri VARCHAR(500),
                        status VARCHAR(20) DEFAULT 'draft',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (layer_id) REFERENCES layer(id),
                        FOREIGN KEY (creator_user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_artifact_layer_id ON artifact(layer_id)")
                cursor.execute("CREATE INDEX idx_artifact_artifact_type ON artifact(artifact_type)")
                cursor.execute("CREATE INDEX idx_artifact_created_at ON artifact(created_at)")
                conn.commit()
                print("✅ Created artifact table")

        # 2. Create artifact_relation table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_relation'")
        if cursor.fetchone():
            print("✅ artifact_relation table already exists")
        else:
            if dry_run:
                print("[DRY RUN] Would create artifact_relation table")
            else:
                cursor.execute("""
                    CREATE TABLE artifact_relation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        from_object_type VARCHAR(50) NOT NULL,
                        from_object_id VARCHAR(100) NOT NULL,
                        to_object_type VARCHAR(50) NOT NULL,
                        to_object_id VARCHAR(100) NOT NULL,
                        relation_type VARCHAR(50) NOT NULL,
                        created_by_user_id INTEGER,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (created_by_user_id) REFERENCES user(id)
                    )
                """)
                conn.commit()
                cursor.execute("CREATE INDEX idx_artifact_relation_from ON artifact_relation(from_object_type, from_object_id)")
                cursor.execute("CREATE INDEX idx_artifact_relation_to ON artifact_relation(to_object_type, to_object_id)")
                cursor.execute("CREATE INDEX idx_artifact_relation_type ON artifact_relation(relation_type)")
                conn.commit()
                print("✅ Created artifact_relation table")

        # 3. Add artifact_id to submission (nullable, for linking)
        cursor.execute("PRAGMA table_info(submission)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'artifact_id' not in cols:
            if dry_run:
                print("[DRY RUN] Would add artifact_id to submission")
            else:
                cursor.execute("ALTER TABLE submission ADD COLUMN artifact_id VARCHAR(36)")
                cursor.execute("CREATE INDEX idx_submission_artifact_id ON submission(artifact_id)")
                conn.commit()
                print("✅ Added artifact_id to submission")

        # 4. Add artifact_id to vote (nullable, keep submission_id for backward compat)
        cursor.execute("PRAGMA table_info(vote)")
        vote_cols = [r[1] for r in cursor.fetchall()]
        if 'artifact_id' not in vote_cols:
            if dry_run:
                print("[DRY RUN] Would add artifact_id to vote")
            else:
                cursor.execute("ALTER TABLE vote ADD COLUMN artifact_id VARCHAR(36)")
                cursor.execute("CREATE INDEX idx_vote_artifact_id ON vote(artifact_id)")
                conn.commit()
                print("✅ Added artifact_id to vote")

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
