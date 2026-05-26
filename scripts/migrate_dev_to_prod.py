#!/usr/bin/env python3
"""Migrate dev database and assets to production.

- Backs up production DB before any write
- Copies dev DB as the new production base (schema + dev data)
- Preserves production-only real users (by email / web3authVerifierId)
- Removes seeded fake users (@example.com, test accounts)
- Copies static DP images into prod tree

Usage:
  python3 scripts/migrate_dev_to_prod.py --dry-run
  python3 scripts/migrate_dev_to_prod.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_DB = REPO_ROOT / 'instance_dev' / 'datatracker_dev.db'
PROD_DB = Path('/home/ubuntu/gov-hub-prod/instance/datatracker.db')
DEV_STATIC_DP = REPO_ROOT / 'static' / 'images' / 'dp'
PROD_STATIC_DP = Path('/home/ubuntu/gov-hub-prod/static/images/dp')
PRODUCT_ROLLOUT_JSON = REPO_ROOT / 'config' / 'product_rollout.json'

FAKE_USERNAMES = frozenset({
    'john', 'jane', 'shiftshapr', 'test', 'testuser', 'user1', 'user2',
})

USER_CHILD_TABLES = [
    ('user_linked_account', 'user_id'),
    ('user_event_subscription', 'user_id'),
    ('user_notification', 'user_id'),
    ('email_unsubscribe', 'user_id'),
    ('layer_admin', 'user_id'),
    ('layer_member', 'user_id'),
    ('layer_invitation', 'inviter_id'),
    ('layer_invitation', 'invitee_id'),
    ('working_group_member', 'user_id'),
    ('working_group_chair', 'user_id'),
    ('working_group_chair', 'nominated_by_user_id'),
    ('workgroup_member_request', 'user_id'),
    ('coordinator_request', 'user_id'),
    ('guild_membership', 'user_id'),
    ('waitlist_entry', 'user_id'),
    ('role_image_vote', 'user_id'),
    ('vote_candidate', 'user_id'),
    ('inscription_order', 'user_id'),
    ('brick', 'user_id'),
    ('brick_message', 'user_id'),
    ('bridge_session', 'user_id'),
    ('hypothesis_account', 'user_id'),
    ('quest_submission', 'submitter_user_id'),
    ('quest_submission', 'reviewed_by_user_id'),
    ('artifact', 'creator_user_id'),
    ('artifact_collection', 'creator_user_id'),
    ('artifact_relation', 'created_by_user_id'),
    ('artifact_tag', 'created_by_user_id'),
    ('artifact_tag_link', 'created_by_user_id'),
    ('guild_artifact_link', 'created_by_user_id'),
    ('guild_layer_link', 'created_by_user_id'),
    ('guild_quest_link', 'created_by_user_id'),
    ('monument', 'steward_user_id'),
    ('quest', 'creator_user_id'),
    ('comment', 'author_user_id'),
    ('working_group', 'coordinator_id'),
]


def is_fake_user(row: sqlite3.Row) -> bool:
    username = (row['username'] or '').strip().lower()
    email = (row['email'] or '').strip().lower()
    if username in FAKE_USERNAMES:
        return True
    if email.endswith('@example.com'):
        return True
    return False


def user_identity(row: sqlite3.Row) -> str | None:
    email = (row['email'] or '').strip().lower()
    if email and email != '-':
        return f'email:{email}'
    verifier = (row['web3authVerifierId'] or '').strip().lower()
    if verifier:
        return f'web3:{verifier}'
    username = (row['username'] or '').strip().lower()
    return f'user:{username}' if username else None


def backup_prod_db() -> Path:
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    dest = PROD_DB.with_name(f'{PROD_DB.stem}.backup_pre_dev_migrate_{ts}{PROD_DB.suffix}')
    shutil.copy2(PROD_DB, dest)
    return dest


def copy_static_dp_images() -> int:
    if not DEV_STATIC_DP.is_dir():
        return 0
    PROD_STATIC_DP.mkdir(parents=True, exist_ok=True)
    count = 0
    for src in DEV_STATIC_DP.glob('dp*.png'):
        dest = PROD_STATIC_DP / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        count += 1
    return count


def merge_prod_only_users(prod_backup: Path, target: Path) -> list[str]:
    """Insert real prod users missing from target (after dev copy)."""
    prod = sqlite3.connect(f'file:{prod_backup}?mode=ro', uri=True)
    prod.row_factory = sqlite3.Row
    dev = sqlite3.connect(target)
    dev.row_factory = sqlite3.Row

    try:
        target_cols = [c[1] for c in dev.execute('PRAGMA table_info(user)').fetchall()]
        existing = {}
        for row in dev.execute('SELECT * FROM user').fetchall():
            key = user_identity(row)
            if key:
                existing[key] = row['id']
            existing[f"user:{(row['username'] or '').lower()}"] = row['id']

        added: list[str] = []
        for row in prod.execute('SELECT * FROM user').fetchall():
            if is_fake_user(row):
                continue
            ident = user_identity(row)
            if ident and ident in existing:
                continue
            username_key = f"user:{(row['username'] or '').lower()}"
            if username_key in existing:
                continue

            new_id = str(uuid4())
            values = {col: row[col] if col in row.keys() else None for col in target_cols}
            values['id'] = new_id
            if 'public_id' in target_cols and not values.get('public_id'):
                values['public_id'] = str(uuid4())

            col_sql = ', '.join(f'"{c}"' if c == 'group' else c for c in target_cols)
            placeholders = ', '.join('?' for _ in target_cols)
            dev.execute(
                f'INSERT INTO user ({col_sql}) VALUES ({placeholders})',
                [values[c] for c in target_cols],
            )
            added.append(row['username'] or new_id)
        dev.commit()
        return added
    finally:
        prod.close()
        dev.close()


def remove_fake_users(target: Path) -> list[str]:
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    try:
        fake_rows = [r for r in conn.execute('SELECT * FROM user').fetchall() if is_fake_user(r)]
        removed = [r['username'] for r in fake_rows]
        fake_ids = [r['id'] for r in fake_rows]
        if not fake_ids:
            return []

        for table, col in USER_CHILD_TABLES:
            if not _table_exists(conn, table):
                continue
            if not _column_exists(conn, table, col):
                continue
            for uid in fake_ids:
                conn.execute(f'DELETE FROM "{table}" WHERE "{col}" = ?', (uid,))

        for uid in fake_ids:
            conn.execute('DELETE FROM user WHERE id = ?', (uid,))
        conn.commit()
        return removed
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
    return col in cols


def sync_product_rollout(dev_db: Path, prod_db: Path) -> None:
    """Copy dev site_config.product_rollout JSON to prod, else config/product_rollout.json."""
    dev_conn = sqlite3.connect(dev_db)
    row = dev_conn.execute(
        "SELECT value FROM site_config WHERE key='product_rollout'"
    ).fetchone()
    dev_conn.close()

    if row and (row[0] or '').strip():
        payload = row[0]
        source = 'dev DB site_config'
    elif PRODUCT_ROLLOUT_JSON.is_file():
        payload = json.dumps(json.loads(PRODUCT_ROLLOUT_JSON.read_text()), sort_keys=True)
        source = str(PRODUCT_ROLLOUT_JSON)
    else:
        raise RuntimeError(
            'product_rollout missing in dev DB and config/product_rollout.json not found'
        )

    prod_conn = sqlite3.connect(prod_db)
    existing = prod_conn.execute(
        "SELECT key FROM site_config WHERE key='product_rollout'"
    ).fetchone()
    if existing:
        prod_conn.execute(
            "UPDATE site_config SET value=? WHERE key='product_rollout'",
            (payload,),
        )
    else:
        prod_conn.execute(
            "INSERT INTO site_config (key, value) VALUES ('product_rollout', ?)",
            (payload,),
        )
    prod_conn.commit()
    prod_conn.close()
    print(f'Synced product_rollout to prod (from {source}).')


def migrate(*, dry_run: bool) -> int:
    if not DEV_DB.is_file():
        print(f'Dev DB not found: {DEV_DB}', file=sys.stderr)
        return 1
    if not PROD_DB.is_file():
        print(f'Prod DB not found: {PROD_DB}', file=sys.stderr)
        return 1

    prod_users = sqlite3.connect(f'file:{PROD_DB}?mode=ro', uri=True)
    prod_users.row_factory = sqlite3.Row
    prod_real = [r['username'] for r in prod_users.execute('SELECT * FROM user') if not is_fake_user(r)]
    prod_users.close()

    dev_users = sqlite3.connect(f'file:{DEV_DB}?mode=ro', uri=True)
    dev_users.row_factory = sqlite3.Row
    dev_fake = [r['username'] for r in dev_users.execute('SELECT * FROM user') if is_fake_user(r)]
    dev_users.close()

    print(f'Production real users to preserve: {len(prod_real)} → {", ".join(sorted(prod_real))}')
    print(f'Dev fake users to remove after copy: {", ".join(sorted(dev_fake))}')

    if dry_run:
        print('[dry-run] Would backup prod, copy dev DB, merge prod-only users, remove fakes, copy DP images.')
        return 0

    backup_path = backup_prod_db()
    print(f'Prod DB backup: {backup_path}')

    shutil.copy2(DEV_DB, PROD_DB)
    print(f'Copied dev DB → {PROD_DB}')

    added = merge_prod_only_users(backup_path, PROD_DB)
    if added:
        print(f'Merged prod-only users: {", ".join(added)}')
    else:
        print('No prod-only users needed merging.')

    removed = remove_fake_users(PROD_DB)
    print(f'Removed fake users: {", ".join(removed) if removed else "(none)"}')

    dp_count = copy_static_dp_images()
    print(f'Copied {dp_count} DP image(s) to {PROD_STATIC_DP}/')

    sync_product_rollout(DEV_DB, PROD_DB)

    final = sqlite3.connect(PROD_DB)
    final.row_factory = sqlite3.Row
    remaining = [r['username'] for r in final.execute('SELECT username FROM user ORDER BY username')]
    final.close()
    print(f'Final production users ({len(remaining)}): {", ".join(remaining)}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == '__main__':
    raise SystemExit(main())
