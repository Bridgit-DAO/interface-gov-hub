#!/usr/bin/env python3
"""
One-off migration: rewrite bridge.relationship to claim-centric canonical strings.

Maps:
  contradicts -> contradicted_by
  supports    -> supported_by
  related     -> related_to
  extends     -> related_to
  timeline    -> related_to
(cites unchanged)

Run from gov-hub-dev root. Backs up DB first (unless --dry-run).
Usage:
  python migrate_bridge_relationship_labels.py [--dry-run] [--db PATH]
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from config import DB_PATH as CONFIG_DB_PATH
except ImportError:
    CONFIG_DB_PATH = os.path.join(SCRIPT_DIR, "instance_dev", "datatracker_dev.db")

# (old_value, new_value) – one old string per UPDATE for clear reporting
PAIR_UPDATES = (
    ("contradicts", "contradicted_by"),
    ("supports", "supported_by"),
)

# Multiple legacy values -> one canonical
RELATED_TO_LEGACY = ("related", "extends", "timeline")


def default_db_path():
    return CONFIG_DB_PATH


def run_migration(db_path: str, dry_run: bool) -> bool:
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    backup_path = (
        f"{db_path}.backup_pre_bridge_rel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bridge'"
        )
        if not cursor.fetchone():
            print("❌ Table 'bridge' does not exist – nothing to migrate.")
            return False

        total_changes = 0

        for old, new in PAIR_UPDATES:
            cursor.execute(
                "SELECT COUNT(*) FROM bridge WHERE relationship = ?", (old,)
            )
            n = cursor.fetchone()[0]
            if n:
                print(f"  {'Would update' if dry_run else 'Updating'} {n} row(s): {old!r} -> {new!r}")
                if not dry_run:
                    cursor.execute(
                        "UPDATE bridge SET relationship = ? WHERE relationship = ?",
                        (new, old),
                    )
                    total_changes += cursor.rowcount

        placeholders = ",".join("?" * len(RELATED_TO_LEGACY))
        cursor.execute(
            f"SELECT COUNT(*) FROM bridge WHERE relationship IN ({placeholders})",
            RELATED_TO_LEGACY,
        )
        n = cursor.fetchone()[0]
        if n:
            print(
                f"  {'Would update' if dry_run else 'Updating'} {n} row(s): "
                f"{RELATED_TO_LEGACY} -> 'related_to'"
            )
            if not dry_run:
                cursor.execute(
                    f"UPDATE bridge SET relationship = 'related_to' "
                    f"WHERE relationship IN ({placeholders})",
                    RELATED_TO_LEGACY,
                )
                total_changes += cursor.rowcount

        if dry_run:
            conn.rollback()
            print("[DRY RUN] No writes performed.")
        else:
            conn.commit()
            print(f"✅ Migration committed ({total_changes} rows updated).")

        # Sanity: show any relationship values still not in canonical set
        canonical = frozenset(
            {"cites", "contradicted_by", "supported_by", "related_to"}
        )
        cursor.execute(
            "SELECT DISTINCT relationship FROM bridge ORDER BY relationship"
        )
        distinct = [r[0] for r in cursor.fetchall()]
        odd = [r for r in distinct if r not in canonical]
        if odd:
            print(
                "⚠️  Non-canonical relationship values still present (review manually):",
                odd,
            )
        elif distinct:
            print(f"✅ Distinct relationships now: {distinct}")

        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite bridge.relationship legacy strings to canonical labels."
    )
    parser.add_argument(
        "--db",
        default=default_db_path(),
        help=f"SQLite database path (default: from config or {CONFIG_DB_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts only; do not write or backup",
    )
    args = parser.parse_args()

    print(f"Database: {args.db}")
    ok = run_migration(args.db, args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
