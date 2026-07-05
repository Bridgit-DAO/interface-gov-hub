#!/usr/bin/env python3
"""Trim stored DP proposal passages to changed sentences only (backfill)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from services.dp_proposals import retrim_all_dp_proposals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would change without committing',
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        stats = retrim_all_dp_proposals(dry_run=args.dry_run)
        print(f"Total proposals: {stats['total']}")
        print(f"Updated: {stats['updated']}")
        print(f"Unchanged (already trimmed): {stats['unchanged']}")
        print(f"Skipped: {stats['skipped']}")
        if stats['errors']:
            print('Errors:')
            for item in stats['errors']:
                print(f"  {item['id']}: {item['error']}")
        if args.dry_run:
            print('\nDry run – no changes saved.')
        else:
            print('\nCommitted.')


if __name__ == '__main__':
    main()
