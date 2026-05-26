#!/usr/bin/env python3
"""Link DP workgroups ↔ DP draft submissions (both directions)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from extensions import db
from services.workgroup_links import sync_all_dp_submission_groups, sync_all_dp_workgroup_documents


def main(dry_run: bool = False, force: bool = False):
    with app.app_context():
        wg_stats = sync_all_dp_workgroup_documents(force=force)
        sub_stats = sync_all_dp_submission_groups(force=force)
        if dry_run:
            db.session.rollback()
        elif wg_stats['updated'] or sub_stats['updated']:
            db.session.commit()

        print(
            f"Workgroups: updated {wg_stats['updated']}, skipped {wg_stats['skipped']}, "
            f"missing draft {wg_stats['missing_draft']}, not DP {wg_stats['not_dp']}."
        )
        print(
            f"Documents: updated {sub_stats['updated']}, skipped {sub_stats['skipped']}, "
            f"missing workgroup {sub_stats['missing_wg']}, not DP {sub_stats['not_dp']}."
        )


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    force = '--force' in sys.argv
    if dry:
        print('Dry run — no changes will be saved.')
    if force:
        print('Force — overwriting existing links.')
    main(dry_run=dry, force=force)
