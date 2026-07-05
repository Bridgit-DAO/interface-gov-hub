#!/usr/bin/env python3
"""Renumber ML-Draft-* by document family creation order (first submission)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from extensions import db
from services.ml_numbering import (
    apply_ml_renumber_plan,
    build_ml_renumber_plan,
    is_ml_numbering_sealed,
    seal_ml_numbering,
)


def main(dry_run: bool = False, force: bool = False, seal: bool = False) -> None:
    app = create_app()
    with app.app_context():
        if is_ml_numbering_sealed() and not force:
            print('ML numbering is SEALED – no changes made.')
            print('Pass --force to renumber anyway, or --seal after a successful renumber.')
            return

        plan = build_ml_renumber_plan()
        changes = [p for p in plan if p['changes']]

        print(f'Active document families: {len(plan)}')
        print(f'Families needing renumber: {len(changes)}')
        print('Order: earliest submission in each family (creation order)\n')
        for entry in plan:
            arrow = '→' if entry['changes'] else '='
            when = entry.get('first_submitted_at') or '?'
            print(
                f"  {entry['old_ml'] or '(none)':14} {arrow} {entry['new_ml']}  "
                f"[{when}]  {entry['title'][:50]}"
            )

        if not changes:
            print('\nAlready in creation order – nothing to do.')
            if seal and not dry_run:
                seal_ml_numbering(note='sealed after verify (no changes needed)')
                print('Sealed ML numbering.')
            return

        if dry_run:
            print('\nDry run – no changes saved.')
            db.session.rollback()
            return

        updated = apply_ml_renumber_plan(plan, force=force)
        db.session.commit()
        print(f'\nDone. Renumbered {updated} document families ({len(plan)} total).')

        if seal:
            seal_ml_numbering(note='sealed after creation-order renumber')
            print('Sealed ML numbering – numbers will not change on restart or init_db.')


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    seal = '--seal' in sys.argv
    if dry:
        print('Dry run – no changes will be saved.\n')
    main(dry_run=dry, force=force, seal=seal)
