#!/usr/bin/env python3
"""
DEV ONLY: Remove a duplicate revision row and optionally renumber the survivor.

Gov Hub has no admin UI for revision deletion. This script mirrors the cascade
logic in scripts/port_prod_documents_to_dev.py (delete_dev_catalog).

Usage (dry-run first):
  python scripts/dev_cleanup_duplicate_revision.py \\
    --db instance_dev/datatracker_dev.db \\
    --delete-id 3ce47b0a-78ed-4745-b6fb-b88d97f6d4da \\
    --renumber-id 48353820-046d-4ad9-8fc4-01d68c5667b6 \\
    --new-revision 03 \\
    --dry-run

Requires explicit --execute to write changes. Always backs up the DB first.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def backup_db(db_path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    dest = db_path.with_suffix(f'.backup_pre_rev_cleanup_{ts}.db')
    shutil.copy2(db_path, dest)
    return dest


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
    return column in cols


def fetch_submission(conn: sqlite3.Connection, sub_id: str) -> dict | None:
    row = conn.execute(
        'SELECT id, title, ml_number, revision_number, content_hash, file_path, status '
        'FROM submission WHERE id = ?',
        (sub_id,),
    ).fetchone()
    if not row:
        return None
    keys = ('id', 'title', 'ml_number', 'revision_number', 'content_hash', 'file_path', 'status')
    return dict(zip(keys, row))


def delete_submission_cascade(conn: sqlite3.Connection, sub_id: str) -> None:
    if table_exists(conn, 'layer_tag_link'):
        conn.execute(
            "DELETE FROM layer_tag_link WHERE subject_type='submission' AND subject_id = ?",
            (sub_id,),
        )
    if table_exists(conn, 'comment'):
        conn.execute('DELETE FROM comment WHERE submission_id = ?', (sub_id,))
        conn.execute('DELETE FROM comment WHERE draft_name = ?', (sub_id,))
    if table_exists(conn, 'document_history'):
        conn.execute('DELETE FROM document_history WHERE draft_name = ?', (sub_id,))
    if table_exists(conn, 'dp_proposal'):
        if column_exists(conn, 'dp_proposal', 'submission_id'):
            conn.execute('DELETE FROM dp_proposal WHERE submission_id = ?', (sub_id,))
    conn.execute('DELETE FROM submission WHERE id = ?', (sub_id,))


def main() -> int:
    parser = argparse.ArgumentParser(description='DEV: delete duplicate revision row')
    parser.add_argument('--db', required=True, help='Path to SQLite database (DEV only)')
    parser.add_argument('--delete-id', required=True, help='Submission UUID to delete')
    parser.add_argument('--renumber-id', help='Survivor submission UUID to renumber')
    parser.add_argument('--new-revision', help='New revision_number for survivor (e.g. 03)')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without writing')
    parser.add_argument('--execute', action='store_true', help='Apply changes (implies not dry-run)')
    args = parser.parse_args()

    if 'instance_dev' not in args.db and 'dev' not in Path(args.db).name.lower():
        print('ERROR: Refusing to run outside a DEV database path.', file=sys.stderr)
        return 1

    if not args.execute and not args.dry_run:
        print('Pass --dry-run or --execute', file=sys.stderr)
        return 1

    db_path = Path(args.db)
    if not db_path.is_file():
        print(f'ERROR: DB not found: {db_path}', file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    victim = fetch_submission(conn, args.delete_id)
    if not victim:
        print(f'ERROR: delete-id not found: {args.delete_id}', file=sys.stderr)
        return 1

    survivor = None
    if args.renumber_id:
        survivor = fetch_submission(conn, args.renumber_id)
        if not survivor:
            print(f'ERROR: renumber-id not found: {args.renumber_id}', file=sys.stderr)
            return 1
        if victim['ml_number'] != survivor['ml_number']:
            print('ERROR: delete and renumber rows must share ml_number', file=sys.stderr)
            return 1
        if args.new_revision:
            conflict = conn.execute(
                'SELECT id FROM submission WHERE ml_number = ? AND revision_number = ? AND id NOT IN (?, ?)',
                (victim['ml_number'], args.new_revision, args.delete_id, args.renumber_id),
            ).fetchone()
            if conflict:
                print(f'ERROR: revision {args.new_revision} already taken by {conflict[0]}', file=sys.stderr)
                return 1

    print('=== Planned actions ===')
    print(f"Delete: {victim['id']} rev {victim['revision_number']} ({victim['title']})")
    print(f"  content_hash: {victim['content_hash']}")
    print(f"  file_path: {victim['file_path']}")
    if survivor and args.new_revision:
        print(f"Renumber: {survivor['id']} rev {survivor['revision_number']} -> {args.new_revision}")

    if args.dry_run and not args.execute:
        print('\nDry run — no changes written.')
        return 0

    backup = backup_db(db_path)
    print(f'\nBackup: {backup}')

    try:
        delete_submission_cascade(conn, args.delete_id)
        if survivor and args.new_revision:
            conn.execute(
                'UPDATE submission SET revision_number = ? WHERE id = ?',
                (args.new_revision, args.renumber_id),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    victim_file = victim.get('file_path')
    if victim_file and Path(victim_file).is_file():
        Path(victim_file).unlink(missing_ok=True)
        print(f'Removed upload file: {victim_file}')

    print('Done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
