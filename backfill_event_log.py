#!/usr/bin/env python3
"""
Backfill EventLog with historical events from existing data.

Creates member_joined, member_removed, role_claimed, badge_*, vote_started,
vote_closed, ballot_cast events from LayerMember, Claim, Badge, Vote, Ballot.

Run from gov-hub-dev root. Safe to run multiple times (skips existing).
Usage: python backfill_event_log.py [--dry-run] [--db path]
"""
import os
import sys
import json
from datetime import datetime

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Must set FLASK_ENV before importing app
os.environ.setdefault('FLASK_ENV', 'development')


def run_backfill(dry_run=False):
    from app import app
    from extensions import db
    from models import (
        EventLog, LayerMember, Claim, Badge, Vote, Ballot,
        VoteEligibilitySnapshot
    )

    with app.app_context():
        existing = set()
        if not dry_run:
            for row in EventLog.query.with_entities(EventLog.event_type, EventLog.subject_type, EventLog.subject_id).all():
                existing.add((row.event_type, row.subject_type, str(row.subject_id)))

        count = 0

        # 1. member_joined from LayerMember (active, has joined_at)
        for m in LayerMember.query.filter_by(status='active').filter(LayerMember.joined_at.isnot(None)).all():
            key = ('member_joined', 'layer_member', str(m.id))
            if key in existing:
                continue
            evt = EventLog(
                event_type='member_joined',
                actor_type='user',
                actor_id=str(m.user_id),
                subject_type='layer_member',
                subject_id=str(m.id),
                layer_id=m.layer_id,
                payload_json=json.dumps({'user_id': m.user_id, 'role': m.role}),
                created_at=m.joined_at or datetime.utcnow()
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 2. member_removed from LayerMember (left, has left_at)
        for m in LayerMember.query.filter_by(status='left').filter(LayerMember.left_at.isnot(None)).all():
            key = ('member_removed', 'layer_member', str(m.id))
            if key in existing:
                continue
            evt = EventLog(
                event_type='member_removed',
                actor_type='user',
                actor_id=str(m.user_id),
                subject_type='layer_member',
                subject_id=str(m.id),
                layer_id=m.layer_id,
                payload_json=json.dumps({'user_id': m.user_id}),
                created_at=m.left_at
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 3. role_claimed from Claim (active)
        for c in Claim.query.filter_by(status='active').all():
            key = ('role_claimed', 'claim', str(c.id))
            if key in existing:
                continue
            ts = c.approved_at or c.created_at or datetime.utcnow()
            evt = EventLog(
                event_type='role_claimed',
                actor_type='user',
                actor_id=str(c.claimant_id),
                subject_type='claim',
                subject_id=str(c.id),
                layer_id=c.layer_id,
                payload_json=json.dumps({'role_id': c.role_id, 'status': c.status}),
                created_at=ts
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 4. badge events from Badge
        for b in Badge.query.all():
            if b.status in ('approved', 'issued'):
                key = ('badge_approved', 'badge', str(b.id))
                ts = b.approved_at or b.created_at or datetime.utcnow()
                evt_type = 'badge_approved'
            elif b.status == 'denied':
                key = ('badge_rejected', 'badge', str(b.id))
                ts = b.approved_at or datetime.utcnow()
                evt_type = 'badge_rejected'
            else:
                key = ('badge_nominated', 'badge', str(b.id))
                ts = b.created_at or datetime.utcnow()
                evt_type = 'badge_nominated'
            if key in existing:
                continue
            evt = EventLog(
                event_type=evt_type,
                actor_type='user',
                actor_id=str(b.requested_by_id),
                subject_type='badge',
                subject_id=str(b.id),
                layer_id=b.layer_id,
                payload_json=json.dumps({'badge_type': b.badge_type, 'status': b.status}),
                created_at=ts
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 5. vote_started from Vote (active or closed)
        for v in Vote.query.filter(Vote.status.in_(['active', 'closed'])).all():
            key = ('vote_started', 'vote', str(v.id))
            if key in existing:
                continue
            # Use start_at as proxy for activation time
            ts = v.start_at or v.created_at or datetime.utcnow()
            eligible_count = VoteEligibilitySnapshot.query.filter_by(vote_id=v.id, is_eligible=True).count()
            evt = EventLog(
                event_type='vote_started',
                actor_type='user',
                actor_id=str(v.created_by_id),
                subject_type='vote',
                subject_id=str(v.id),
                layer_id=v.layer_id,
                payload_json=json.dumps({'title': v.title, 'eligible_count': eligible_count}),
                created_at=ts
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 6. vote_closed from Vote (closed)
        for v in Vote.query.filter_by(status='closed').filter(Vote.closed_at.isnot(None)).all():
            key = ('vote_closed', 'vote', str(v.id))
            if key in existing:
                continue
            ballots = Ballot.query.filter_by(vote_id=v.id).all()
            evt = EventLog(
                event_type='vote_closed',
                actor_type='system',
                subject_type='vote',
                subject_id=str(v.id),
                layer_id=v.layer_id,
                payload_json=json.dumps({'result': v.result, 'votes_cast': len(ballots)}),
                created_at=v.closed_at
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        # 7. ballot_cast from Ballot
        for b in Ballot.query.all():
            key = ('ballot_cast', 'ballot', str(b.id))
            if key in existing:
                continue
            vote = Vote.query.get(b.vote_id)
            evt = EventLog(
                event_type='ballot_cast',
                actor_type='user',
                actor_id=str(b.person_id),
                subject_type='ballot',
                subject_id=str(b.id),
                layer_id=vote.layer_id if vote else None,
                payload_json=json.dumps({'vote_id': b.vote_id, 'choice': b.choice}),
                created_at=b.cast_at or datetime.utcnow()
            )
            if not dry_run:
                db.session.add(evt)
            count += 1

        if not dry_run and count > 0:
            db.session.commit()

        return count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Backfill EventLog from existing data')
    parser.add_argument('--dry-run', action='store_true', help='Show count without inserting')
    parser.add_argument('--db', default=None, help='Database path (unused; uses app config)')
    args = parser.parse_args()
    count = run_backfill(dry_run=args.dry_run)
    print(f"{'[DRY RUN] Would insert ' if args.dry_run else ''}{count} events")
    sys.exit(0)


if __name__ == '__main__':
    main()
