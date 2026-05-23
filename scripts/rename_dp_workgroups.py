#!/usr/bin/env python3
"""Rename DP workgroups to 'DP{n} - {Title}' and strip Working Group suffixes."""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from services.groups import DP_DESCRIPTIONS, format_dp_display_name, strip_workgroup_suffix

DEFAULT_DB = REPO_ROOT / 'instance_dev' / 'datatracker_dev.db'


def resolve_display_name(acronym: str, current_name: str) -> str:
    if acronym in DP_DESCRIPTIONS:
        title = DP_DESCRIPTIONS[acronym]['title']
        return format_dp_display_name(acronym, title)
    if extract_dp := format_dp_display_name(acronym, current_name):
        if extract_dp != strip_workgroup_suffix(current_name):
            return extract_dp
    return strip_workgroup_suffix(current_name)


def main(db_path: Path = DEFAULT_DB) -> int:
    if not db_path.exists():
        print(f'Database not found: {db_path}')
        return 1

    backup = db_path.with_suffix(
        f'.backup_pre_dp_rename_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.db'
    )
    shutil.copy2(db_path, backup)
    print(f'Backup: {backup}')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT id, acronym, name FROM working_group ORDER BY acronym')
    rows = cur.fetchall()

    updated = 0
    for row in rows:
        acronym = row['acronym'] or ''
        old_name = row['name'] or ''
        new_name = resolve_display_name(acronym, old_name)
        if new_name == old_name:
            continue
        cur.execute(
            'UPDATE working_group SET name = ? WHERE id = ?',
            (new_name, row['id']),
        )
        print(f'  {acronym}: {old_name!r} -> {new_name!r}')
        updated += 1

    conn.commit()
    conn.close()
    print(f'Updated {updated} workgroup name(s).')
    return 0


if __name__ == '__main__':
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    raise SystemExit(main(path))
