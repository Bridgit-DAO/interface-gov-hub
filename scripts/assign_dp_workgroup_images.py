#!/usr/bin/env python3
"""Copy DP card images into static/ and assign image_url on DP workgroups."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import app
from extensions import db
from services.groups import DP_ABBREVIATIONS
from services.workgroup_links import sync_all_dp_workgroup_images

DEFAULT_SOURCE = Path('/home/ubuntu/.cursor/projects/home-ubuntu/assets/dp-icons')
STATIC_DP_DIR = REPO_ROOT / 'static' / 'images' / 'dp'


def copy_dp_images(source_dir: Path = DEFAULT_SOURCE) -> list[Path]:
    """Copy DP{n}_{Abbr}.png assets to static/images/dp/dp{n}.png."""
    if not source_dir.is_dir():
        raise FileNotFoundError(f'DP icon source directory not found: {source_dir}')

    STATIC_DP_DIR.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []

    for dp_num, abbr in sorted(DP_ABBREVIATIONS.items()):
        src = source_dir / f'DP{dp_num}_{abbr}.png'
        if not src.is_file():
            raise FileNotFoundError(f'Missing source image: {src}')
        dest = STATIC_DP_DIR / f'dp{dp_num}.png'
        shutil.copy2(src, dest)
        copied.append(dest)

    return copied


def main(dry_run: bool = False, force: bool = False, source_dir: Path = DEFAULT_SOURCE) -> int:
    copied = copy_dp_images(source_dir)
    print(f'Copied {len(copied)} image(s) to {STATIC_DP_DIR}/')

    with app.app_context():
        stats = sync_all_dp_workgroup_images(force=force)
        if dry_run:
            db.session.rollback()
        elif stats['updated']:
            db.session.commit()

        print(
            f"Workgroups: updated {stats['updated']}, skipped {stats['skipped']}, "
            f"missing image {stats['missing_image']}, not DP {stats['not_dp']}."
        )

    return 0


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    source = Path(sys.argv[sys.argv.index('--source') + 1]) if '--source' in sys.argv else DEFAULT_SOURCE
    if dry:
        print('Dry run — no database changes will be saved.')
    if force:
        print('Force — overwriting existing image_url values.')
    raise SystemExit(main(dry_run=dry, force=force, source_dir=source))
