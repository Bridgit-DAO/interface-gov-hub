#!/usr/bin/env python3
"""Copy all production submissions (documents) into dev, assigned to the Metaweb layer.

Usage (from gov-hub-dev):
  python scripts/migrate_prod_documents_to_dev.py
  python scripts/migrate_prod_documents_to_dev.py --dry-run

Backs up instance_dev/datatracker_dev.db before writing.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
PROD_DB = Path('/home/ubuntu/gov-hub-prod/instance/datatracker.db')
DEV_DB = REPO_ROOT / 'instance_dev' / 'datatracker_dev.db'
METAWEB_SLUG = 'the-metaweb'

# Columns present in both DBs (prod schema subset)
SHARED_COLUMNS = [
    'id', 'title', 'authors', 'abstract', 'group', 'filename', 'file_path',
    'draft_name', 'status', 'submitted_at', 'submitted_by', 'approved_at',
    'rejected_at', 'ml_number', 'sourceType', 'ordinalId', 'ordinalContentUrl',
    'ordinalContentType', 'inscriptionNumber', 'blockHeight', 'inscriptionTimestamp',
    'doc_type', 'pages', 'words', 'parent_draft_name', 'revision_number',
    'what_changed', 'is_revision', 'rfc_number',
]

DEV_EXTRA_DEFAULTS = {
    'inscription_order_id': None,
    'artifact_id': None,
    'displayBodySource': 'file',
    'displayOrdinalId': None,
    'displayOrdinalContentUrl': None,
    'displayOrdinalContentType': None,
    'displaySwitchedAt': None,
    'displaySwitchedBy': None,
}


def _row_dict(row) -> dict:
    return dict(row)


def backup_dev_db() -> Path:
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DEV_DB.with_name(f'{DEV_DB.stem}.backup_pre_doc_migrate_{ts}{DEV_DB.suffix}')
    shutil.copy2(DEV_DB, dest)
    return dest


def get_metaweb_layer_id(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT id FROM layer WHERE slug = ? LIMIT 1",
        (METAWEB_SLUG,),
    ).fetchone()
    if not row:
        raise SystemExit(f'Metaweb layer not found in dev (slug={METAWEB_SLUG!r})')
    return row[0]


def normalize_draft_name(row: dict) -> str | None:
    dn = (row.get('draft_name') or '').strip()
    if dn:
        return dn
    sid = (row.get('id') or '').strip()
    return sid or None


def migrate(*, dry_run: bool) -> None:
    if not PROD_DB.is_file():
        raise SystemExit(f'Production DB not found: {PROD_DB}')
    if not DEV_DB.is_file():
        raise SystemExit(f'Dev DB not found: {DEV_DB}')

    prod = sqlite3.connect(f'file:{PROD_DB}?mode=ro', uri=True)
    prod.row_factory = sqlite3.Row
    dev = sqlite3.connect(DEV_DB)
    dev.row_factory = sqlite3.Row

    try:
        metaweb_id = get_metaweb_layer_id(dev)
        print(f'Metaweb layer: {METAWEB_SLUG} → {metaweb_id}')

        prod_rows = prod.execute('SELECT * FROM submission ORDER BY is_revision ASC, submitted_at ASC').fetchall()
        print(f'Production submissions: {len(prod_rows)}')

        if dry_run:
            print('[dry-run] Would backup dev DB, replace submissions/comments, import prod rows.')
            for row in prod_rows:
                d = _row_dict(row)
                dn = normalize_draft_name(d)
                src = d.get('sourceType') or 'file'
                fp = 'yes' if d.get('file_path') else 'no'
                print(f"  {d['id']:10} {d.get('status',''):10} {src:8} file={fp} draft_name={dn}")
            return

        backup_path = backup_dev_db()
        print(f'Dev DB backup: {backup_path}')

        dev.execute('DELETE FROM comment')
        dev.execute('DELETE FROM submission')
        dev.commit()

        inserted = 0
        for row in prod_rows:
            src = _row_dict(row)
            draft_name = normalize_draft_name(src)
            public_id = str(uuid4())
            values = {col: src[col] if col in src.keys() else None for col in SHARED_COLUMNS}
            values['draft_name'] = draft_name
            values['public_id'] = public_id
            values['layer_id'] = metaweb_id
            values.update(DEV_EXTRA_DEFAULTS)

            cols = list(values.keys())
            placeholders = ', '.join('?' for _ in cols)
            col_sql = ', '.join(f'"{c}"' if c == 'group' else c for c in cols)
            dev.execute(
                f'INSERT INTO submission ({col_sql}) VALUES ({placeholders})',
                [values[c] for c in cols],
            )
            inserted += 1

        # Prod comments (integer ids) → dev (text ids), draft_name unchanged
        prod_comments = prod.execute('SELECT * FROM comment ORDER BY id').fetchall()
        for crow in prod_comments:
            c = _row_dict(crow)
            dev.execute(
                '''INSERT INTO comment (id, draft_name, text, author, timestamp, parent_id,
                   edited_at, is_deleted, original_text, artifact_id, author_user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    str(uuid4()),
                    c.get('draft_name'),
                    c.get('text'),
                    c.get('author'),
                    c.get('timestamp'),
                    None,  # parent_id remapped below if needed — prod uses int chain; flat here
                    c.get('edited_at'),
                    c.get('is_deleted'),
                    c.get('original_text'),
                    None,
                    None,
                ),
            )

        dev.commit()
        on_metaweb = dev.execute(
            'SELECT COUNT(*) FROM submission WHERE layer_id = ?',
            (metaweb_id,),
        ).fetchone()[0]
        comment_count = dev.execute('SELECT COUNT(*) FROM comment').fetchone()[0]
        print(f'Inserted {inserted} submissions ({on_metaweb} on Metaweb layer)')
        print(f'Inserted {comment_count} comments')
    finally:
        prod.close()
        dev.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
