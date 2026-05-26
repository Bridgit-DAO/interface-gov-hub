#!/usr/bin/env python3
"""Apply config/product_rollout.json to the current database (dev or prod)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from services.product_rollout_seed import ensure_product_rollout_seeded, load_rollout_json


def main():
    force = '--force' in sys.argv
    app = create_app()
    with app.app_context():
        written = ensure_product_rollout_seeded(force=force)
        cfg = load_rollout_json()
        action = 'Updated' if written else 'Already present (use --force to overwrite)'
        print(f'{action} product_rollout from config/product_rollout.json')
        for k in sorted(cfg.keys()):
            print(f'  {k}: {cfg[k]}')


if __name__ == '__main__':
    main()
