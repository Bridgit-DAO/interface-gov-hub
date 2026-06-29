#!/usr/bin/env python3
"""Clear image_url on all workgroups."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import app
from extensions import db
from services.workgroup_links import clear_all_workgroup_images


def main() -> int:
    with app.app_context():
        stats = clear_all_workgroup_images()
        if stats['cleared']:
            db.session.commit()
        print(f"Cleared {stats['cleared']} workgroup image(s); {stats['already_empty']} already had none.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
