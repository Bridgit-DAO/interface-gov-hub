#!/usr/bin/env python3
"""
Backfill: Create Artifacts for existing Submissions and link Votes (GOV-HUB-3)

Run after migrate_artifact.py. Creates one Artifact per Submission, links
submission.artifact_id, and sets vote.artifact_id from submission.artifact_id.

Uses FLASK_ENV=development by default (instance_dev/datatracker_dev.db).
Usage: python backfill_artifact.py [--dry-run]
"""
import os
import sys


def run_backfill(dry_run=False):
    # Import inside function so we can set env before loading app
    os.environ.setdefault('FLASK_ENV', 'development')  # use instance_dev/datatracker_dev.db
    from app import app
    from extensions import db
    from models import Artifact, Submission, Vote

    with app.app_context():
        submissions = Submission.query.filter(Submission.artifact_id.is_(None)).all()
        created = 0
        for s in submissions:
            if dry_run:
                print(f"[DRY RUN] Would create Artifact for Submission {s.id}: {s.title[:50]}...")
                created += 1
                continue
            art = Artifact(
                layer_id=s.layer_id,
                creator_user_id=None,  # submitted_by is string; no user_id mapping
                artifact_type='submission',
                title=s.title or f"Draft {s.id}",
                summary=s.abstract,
                uri=None,
                status=s.status or 'submitted',
                created_at=s.submitted_at,
            )
            db.session.add(art)
            db.session.flush()  # get art.id
            s.artifact_id = art.id
            created += 1
        if not dry_run and created:
            db.session.commit()
            print(f"✅ Created {created} Artifacts for Submissions")

        # Backfill Vote.artifact_id from Submission.artifact_id
        votes = Vote.query.filter(Vote.artifact_id.is_(None), Vote.submission_id.isnot(None)).all()
        updated = 0
        for v in votes:
            if v.submission and v.submission.artifact_id:
                if dry_run:
                    print(f"[DRY RUN] Would set Vote {v.id} artifact_id={v.submission.artifact_id}")
                else:
                    v.artifact_id = v.submission.artifact_id
                updated += 1
        if not dry_run and updated:
            db.session.commit()
            print(f"✅ Updated {updated} Votes with artifact_id")

        if dry_run:
            print(f"[DRY RUN] Would create {created} Artifacts, update {updated} Votes")
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run_backfill(dry_run=args.dry_run)
    sys.exit(0)


if __name__ == '__main__':
    main()
