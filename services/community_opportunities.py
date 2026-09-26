"""Private opportunity tracking, bound to the exact reviewed evidence version."""
import hashlib
import json
from datetime import datetime
from flask import abort, g
from extensions import db
from models.community_intelligence import CIOpportunity
from services import community_intelligence as ci, community_rooms as rooms


def snapshots(rows):
    return sorted([dict(claim_id=c.id, source_id=s.id, source_revision=s.revision,
                        program_id=p.id, program_revision=p.revision) for c, s, p in rows],
                  key=lambda e: e['claim_id'])


def fingerprint(evidence):
    return hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()


def current_rows(layer_id, user_id, data):
    ids = data.get('claim_ids')
    if not isinstance(ids, list) or len(ids) != 2 or not all(isinstance(i, str) for i in ids) or len(set(ids)) != 2:
        abort(400, description='Select exactly one reviewed need and offer.')
    rows = ci.evidence_query(layer_id, user_id, shared_only=True).filter(ci.CIClaim.id.in_(ids)).all()
    if len(rows) != 2:
        abort(404)
    a, b = rows
    if ({a[0].kind, b[0].kind} != {'need', 'offer'} or not a[0].topic
            or a[0].topic.casefold() != (b[0].topic or '').casefold()
            or a[1].organization_id == b[1].organization_id):
        abort(400, description='Select complementary evidence from different organizations with the same topic.')
    # Require the versions the user actually reviewed, not silently updated evidence.
    if data.get('evidence') != snapshots(rows):
        abort(409, description='Suggestion changed. Refresh before saving it.')
    return rows


def describe(item, user_id):
    rows = rooms.evidence_for(item, user_id)
    if rows is None:
        return dict(id=item.id, stale=True, title='Opportunity needs refreshed evidence')
    g.ci_read_opportunities = getattr(g, 'ci_read_opportunities', set()) | {item.id}
    need = next(row for row in rows if row[0].kind == 'need')
    return dict(id=item.id, stale=False, title='Explore ' + need[0].topic,
                status=item.status, revision=item.revision, updated_at=item.updated_at.isoformat(),
                evidence=item.evidence, citations=[ci.evidence_dict(*row) for row in rows])


def save(layer_id, user_id, data):
    rows = current_rows(layer_id, user_id, data)
    rooms.lock_evidence(rows)
    evidence = snapshots(rows)
    item = CIOpportunity.query.filter_by(layer_id=layer_id, user_id=user_id,
                                         fingerprint=fingerprint(evidence)).first()
    if item is None:
        if CIOpportunity.query.filter_by(layer_id=layer_id, user_id=user_id).count() >= 200:
            abort(409, description='Your pilot tracker reached its 200-record limit.')
        item = CIOpportunity(layer_id=layer_id, user_id=user_id, evidence=evidence,
                             fingerprint=fingerprint(evidence), status='saved')
        db.session.add(item)
        db.session.flush()
    return item


def change(item, user_id, data):
    state = data.get('status')
    if state not in ('saved', 'exploring', 'dismissed'):
        abort(400, description='Choose saved, exploring or dismissed.')
    rows = rooms.evidence_for(item, user_id)
    if rows is None:
        abort(409, description='Evidence changed. Save a current suggestion instead.')
    rooms.lock_evidence(rows)
    ci.advance(CIOpportunity, item, data.get('revision'))
    item.status = state
    item.updated_at = datetime.utcnow()
    return item
