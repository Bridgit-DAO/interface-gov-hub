#!/usr/bin/env python3
"""Port approved/published documents from production DB to dev (submissions, artifacts, tags, files).

Makes the dev document catalog match prod (including ML-Draft-029, prod titles, ordinal metadata).

Does NOT replace dev users or non-approved submissions.

Usage:
  python3 scripts/port_prod_documents_to_dev.py --dry-run
  python3 scripts/port_prod_documents_to_dev.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEV_ROOT = Path(__file__).resolve().parents[1]
PROD_ROOT = Path('/home/ubuntu/gov-hub-prod')
DEV_DB = DEV_ROOT / 'instance_dev' / 'datatracker_dev.db'
PROD_DB = PROD_ROOT / 'instance' / 'datatracker.db'
UPLOAD_FOLDER = Path('/home/ubuntu/data-tracker/uploads')

APPROVED_STATUSES = ('approved', 'published')


def backup_dev_db() -> Path:
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = DEV_DB.with_name(f'{DEV_DB.stem}.backup_pre_prod_doc_port_{ts}{DEV_DB.suffix}')
    shutil.copy2(DEV_DB, dest)
    return dest


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    return col in table_columns(conn, table)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def copy_rows(
    prod: sqlite3.Connection,
    dev: sqlite3.Connection,
    table: str,
    where_sql: str,
    params: tuple,
    *,
    replace: bool = True,
) -> int:
    if not table_exists(prod, table) or not table_exists(dev, table):
        return 0
    prod_cols = table_columns(prod, table)
    dev_cols = table_columns(dev, table)
    cols = [c for c in prod_cols if c in dev_cols]
    if not cols:
        return 0
    col_sql = ', '.join(f'"{c}"' if c == 'group' else c for c in cols)
    placeholders = ', '.join('?' for _ in cols)
    verb = 'INSERT OR REPLACE' if replace else 'INSERT OR IGNORE'
    rows = prod.execute(
        f'SELECT {col_sql} FROM "{table}" WHERE {where_sql}',
        params,
    ).fetchall()
    for row in rows:
        dev.execute(
            f'{verb} INTO "{table}" ({col_sql}) VALUES ({placeholders})',
            row,
        )
    return len(rows)


def prod_approved_submission_ids(prod: sqlite3.Connection) -> list[str]:
    rows = prod.execute(
        f"""
        SELECT id FROM submission
        WHERE status IN ({','.join('?' * len(APPROVED_STATUSES))})
        """,
        APPROVED_STATUSES,
    ).fetchall()
    return [r[0] for r in rows]


def dev_approved_submission_ids(dev: sqlite3.Connection) -> list[str]:
    rows = dev.execute(
        f"""
        SELECT id FROM submission
        WHERE status IN ({','.join('?' * len(APPROVED_STATUSES))})
        """,
        APPROVED_STATUSES,
    ).fetchall()
    return [r[0] for r in rows]


def artifact_ids_for_submissions(conn: sqlite3.Connection, sub_ids: list[str]) -> list[str]:
    if not sub_ids:
        return []
    ph = ','.join('?' * len(sub_ids))
    rows = conn.execute(
        f'SELECT DISTINCT artifact_id FROM submission WHERE artifact_id IS NOT NULL AND id IN ({ph})',
        sub_ids,
    ).fetchall()
    return [r[0] for r in rows if r[0]]


def delete_dev_catalog(dev: sqlite3.Connection, sub_ids: list[str], art_ids: list[str]) -> None:
    if sub_ids:
        ph = ','.join('?' * len(sub_ids))
        if table_exists(dev, 'layer_tag_link'):
            dev.execute(
                f"DELETE FROM layer_tag_link WHERE subject_type='submission' AND subject_id IN ({ph})",
                sub_ids,
            )
        if table_exists(dev, 'comment'):
            dev.execute(
                f'DELETE FROM comment WHERE draft_name IN ({ph})',
                sub_ids,
            )
        if table_exists(dev, 'document_history'):
            dev.execute(
                f'DELETE FROM document_history WHERE draft_name IN ({ph})',
                sub_ids,
            )
        if table_exists(dev, 'dp_proposal'):
            if _column_exists(dev, 'dp_proposal', 'submission_id'):
                dev.execute(
                    f'DELETE FROM dp_proposal WHERE submission_id IN ({ph})',
                    sub_ids,
                )
            elif _column_exists(dev, 'dp_proposal', 'draft_id'):
                dev.execute(
                    f'DELETE FROM dp_proposal WHERE draft_id IN ({ph})',
                    sub_ids,
                )

    if art_ids:
        ph = ','.join('?' * len(art_ids))
        if table_exists(dev, 'layer_tag_link'):
            dev.execute(
                f"DELETE FROM layer_tag_link WHERE subject_type='artifact' AND subject_id IN ({ph})",
                art_ids,
            )
        if table_exists(dev, 'comment'):
            dev.execute(
                f'DELETE FROM comment WHERE artifact_id IN ({ph})',
                art_ids,
            )
        dev.execute(f'DELETE FROM artifact WHERE id IN ({ph})', art_ids)

    if sub_ids:
        ph = ','.join('?' * len(sub_ids))
        dev.execute(f'DELETE FROM submission WHERE id IN ({ph})', sub_ids)


def copy_upload_files(prod: sqlite3.Connection, sub_ids: list[str], *, dry_run: bool) -> int:
    if not UPLOAD_FOLDER.is_dir():
        return 0
    ph = ','.join('?' * len(sub_ids))
    rows = prod.execute(
        f'SELECT file_path, filename FROM submission WHERE id IN ({ph}) AND file_path IS NOT NULL AND file_path != ""',
        sub_ids,
    ).fetchall()
    copied = 0
    for file_path, filename in rows:
        src = Path(file_path)
        if not src.is_file():
            # try basename in shared uploads
            if filename:
                alt = UPLOAD_FOLDER / filename
                if alt.is_file():
                    src = alt
                else:
                    continue
            else:
                continue
        dest = UPLOAD_FOLDER / src.name
        if dry_run:
            copied += 1
            continue
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dest)
        copied += 1
    return copied


def port_document_history(prod: sqlite3.Connection, dev: sqlite3.Connection, sub_ids: list[str]) -> int:
    if not table_exists(prod, 'document_history') or not sub_ids:
        return 0
    ph = ','.join('?' * len(sub_ids))
    # Also match draft_name values for those submissions
    draft_names = [
        r[0]
        for r in prod.execute(
            f'SELECT draft_name FROM submission WHERE id IN ({ph}) AND draft_name IS NOT NULL',
            sub_ids,
        ).fetchall()
        if r[0]
    ]
    keys = list(set(sub_ids + draft_names))
    ph2 = ','.join('?' * len(keys))
    return copy_rows(prod, dev, 'document_history', f'draft_name IN ({ph2})', tuple(keys))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not PROD_DB.is_file():
        raise SystemExit(f'Prod DB not found: {PROD_DB}')
    if not DEV_DB.is_file():
        raise SystemExit(f'Dev DB not found: {DEV_DB}')

    if not args.dry_run:
        backup = backup_dev_db()
        print(f'✅ Dev backup: {backup}')

    prod = sqlite3.connect(f'file:{PROD_DB}?mode=ro', uri=True)
    dev = sqlite3.connect(DEV_DB)
    prod.row_factory = sqlite3.Row
    try:
        prod_sub_ids = prod_approved_submission_ids(prod)
        prod_art_ids = artifact_ids_for_submissions(prod, prod_sub_ids)
        dev_sub_ids = dev_approved_submission_ids(dev)
        dev_art_ids = artifact_ids_for_submissions(dev, dev_sub_ids)

        print(f'Prod approved submissions: {len(prod_sub_ids)}')
        print(f'Prod linked artifacts: {len(prod_art_ids)}')
        print(f'Dev approved to replace: {len(dev_sub_ids)}')

        prod_ml = prod.execute(
            f"""
            SELECT DISTINCT ml_number FROM submission
            WHERE status IN ({','.join('?' * len(APPROVED_STATUSES))}) AND ml_number IS NOT NULL
            ORDER BY ml_number
            """,
            APPROVED_STATUSES,
        ).fetchall()
        print(f'Prod ML numbers: {[r[0] for r in prod_ml]}')

        if args.dry_run:
            files = copy_upload_files(prod, prod_sub_ids, dry_run=True)
            print(f'Would copy ~{files} upload file(s)')
            print('Dry run — no DB changes')
            return

        delete_dev_catalog(dev, dev_sub_ids, dev_art_ids)

        n_sub = copy_rows(
            prod,
            dev,
            'submission',
            f'status IN ({",".join("?" * len(APPROVED_STATUSES))})',
            APPROVED_STATUSES,
        )
        n_art = 0
        if prod_art_ids:
            ph = ','.join('?' * len(prod_art_ids))
            n_art = copy_rows(prod, dev, 'artifact', f'id IN ({ph})', tuple(prod_art_ids))

        # Tags: layer_tag rows used by prod links, then links
        if table_exists(prod, 'layer_tag_link') and prod_sub_ids:
            phs = ','.join('?' * len(prod_sub_ids))
            tag_ids = set()
            for row in prod.execute(
                f"""
                SELECT DISTINCT tag_id FROM layer_tag_link
                WHERE (subject_type='submission' AND subject_id IN ({phs}))
                """,
                prod_sub_ids,
            ):
                tag_ids.add(row[0])
            if prod_art_ids:
                pha = ','.join('?' * len(prod_art_ids))
                for row in prod.execute(
                    f"""
                    SELECT DISTINCT tag_id FROM layer_tag_link
                    WHERE subject_type='artifact' AND subject_id IN ({pha})
                    """,
                    prod_art_ids,
                ):
                    tag_ids.add(row[0])
            if tag_ids and table_exists(prod, 'layer_tag'):
                pht = ','.join('?' * len(tag_ids))
                copy_rows(prod, dev, 'layer_tag', f'id IN ({pht})', tuple(tag_ids), replace=True)
            # submission links
            copy_rows(
                prod,
                dev,
                'layer_tag_link',
                f"subject_type='submission' AND subject_id IN ({phs})",
                prod_sub_ids,
            )
            if prod_art_ids:
                pha = ','.join('?' * len(prod_art_ids))
                copy_rows(
                    prod,
                    dev,
                    'layer_tag_link',
                    f"subject_type='artifact' AND subject_id IN ({pha})",
                    tuple(prod_art_ids),
                )

        n_hist = port_document_history(prod, dev, prod_sub_ids)
        n_files = copy_upload_files(prod, prod_sub_ids, dry_run=False)

        dev.commit()
        print(f'✅ Inserted {n_sub} submissions, {n_art} artifacts')
        print(f'✅ History rows: {n_hist}, files copied: {n_files}')

        # Verify
        dev_sub_after = dev_approved_submission_ids(dev)
        dev_ml = dev.execute(
            f"""
            SELECT DISTINCT ml_number FROM submission
            WHERE status IN ({','.join('?' * len(APPROVED_STATUSES))}) AND ml_number IS NOT NULL
            ORDER BY ml_number
            """,
            APPROVED_STATUSES,
        ).fetchall()
        print(f'Dev approved after: {len(dev_sub_after)} families: {len(dev_ml)}')
        print(f'Dev ML numbers: {[r[0] for r in dev_ml]}')
    finally:
        prod.close()
        dev.close()


if __name__ == '__main__':
    main()
