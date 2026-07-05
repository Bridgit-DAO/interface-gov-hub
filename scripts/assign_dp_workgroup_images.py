#!/usr/bin/env python3
"""Copy DP pictogram images into static/ and assign image_url on DP workgroups."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import app
from extensions import db
from services.workgroup_links import sync_all_dp_workgroup_images

DEFAULT_SOURCE = Path('/home/ubuntu/.cursor/projects/home-ubuntu/assets/dp-icons')
STATIC_DP_DIR = REPO_ROOT / 'static' / 'images' / 'dp'
EXTRACT_SCRIPT = REPO_ROOT / 'scripts' / 'extract_dp_icons.py'


def copy_dp_images(source_dir: Path = DEFAULT_SOURCE) -> list[Path]:
    """Build icon-only PNGs from card slices, written to static/images/dp/."""
    import subprocess

    if not EXTRACT_SCRIPT.is_file():
        raise FileNotFoundError(f'Missing extract script: {EXTRACT_SCRIPT}')
    subprocess.run([sys.executable, str(EXTRACT_SCRIPT)], check=True)
    return sorted(STATIC_DP_DIR.glob('dp*.png'))


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
        print('Dry run – no database changes will be saved.')
    if force:
        print('Force – overwriting existing image_url values.')
    raise SystemExit(main(dry_run=dry, force=force, source_dir=source))
