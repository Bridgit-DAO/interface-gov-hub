"""Transactional evidence workflow. All reads apply authoritative membership and policy.

No vector/graph copies or generated-answer cache in this increment. Revocation and
retirement therefore take effect on the next query without projection lag.
"""
from datetime import date, datetime
import hashlib
import re

from flask import abort, current_app, g, has_request_context
from sqlalchemy import or_, select
from extensions import db
from models import Layer, LayerMember
from models.community_intelligence import CIOrganization, CIMembership, CIProgram, CISource, CIClaim, CIAudit
from services.community_extraction import MAX_BYTES, SUPPORTED, ExtractionError, extract

ROLES = {'administrator', 'steward', 'contributor'}
LIFECYCLES = {'unknown', 'planned', 'active', 'paused', 'completed', 'discontinued'}


def enabled(layer_id):
    return layer_id in current_app.config.get('COMMUNITY_INTELLIGENCE_LAYERS', ())


def require_layer(layer_id, user):
    if not user:
        abort(401)
    # Even global/layer administrators must be active members for this feature.
    if not enabled(layer_id) or not LayerMember.query.filter_by(
            layer_id=layer_id, user_id=user['id'], status='active').first():
        abort(404)
    return db.session.get(Layer, layer_id)


def membership(org_id, user_id):
    return db.session.get(CIMembership, (org_id, user_id))


def require_org(org_id, user_id, *, steward=False, administrator=False):
    member = membership(org_id, user_id)
    if not member:
        abort(404)
    if administrator and member.role != 'administrator':
        abort(403)
    if steward and member.role not in {'administrator', 'steward'}:
        abort(403)
    return member


def text_field(data, key, limit=200, *, optional=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (not optional and not value.strip()):
        abort(400, description=f'{key} must be text between 1 and {limit} characters.')
    return value.strip()


def date_field(data, key):
    raw = data.get(key)
    if raw in (None, ''):
        return None
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        abort(400, description=f'{key} must be an ISO date or empty.')


def audit(org_id, actor, target, action, revision):
    db.session.add(CIAudit(organization_id=org_id, actor_id=actor, target_id=target,
                           action=action, revision=revision))


def advance(model, row, revision):
    if type(revision) is not int:
        abort(400, description='An integer revision is required.')
    count = model.query.filter_by(id=row.id, revision=revision).update(
        {'revision': revision + 1}, synchronize_session=False)
    if count != 1:
        abort(409, description='This item changed. Refresh before reviewing it.')
    db.session.refresh(row)


def visible_sources(layer_id, user_id, *, shared_only=False):
    # Permission predicate executes before title, count, passages or metadata leave SQL.
    owned = select(CIMembership.organization_id).where(CIMembership.user_id == user_id)
    policy = CISource.visibility == 'layer'
    if not shared_only:
        policy = or_(policy, CISource.organization_id.in_(owned))
    return CISource.query.filter(CISource.layer_id == layer_id,
                                 CISource.state != 'withdrawn', policy)


def track_evidence(source, program=None):
    """Capture dependencies for the delivery-time policy/revision check."""
    if has_request_context():
        if not hasattr(g, 'ci_dependencies'):
            g.ci_dependencies = {}
        if program is None:
            program = db.session.get(CIProgram, source.program_id)
        g.ci_dependencies[source.id] = (source.revision, program.id, program.revision)


def source_for(layer_id, user_id, source_id, *, steward=False):
    source = visible_sources(layer_id, user_id).filter_by(id=source_id).first_or_404()
    if steward:
        require_org(source.organization_id, user_id, steward=True)
    track_evidence(source)
    return source


def source_dict(source, user_id):
    track_evidence(source)
    member = membership(source.organization_id, user_id)
    can_review = bool(member and member.role in {'administrator', 'steward'})
    program = db.session.get(CIProgram, source.program_id)
    org = db.session.get(CIOrganization, source.organization_id)
    return dict(id=source.id, organization_id=org.id, organization=org.name,
                program_id=program.id, program=program.name, lifecycle=program.lifecycle,
                program_revision=program.revision, title=source.title,
                visibility=source.visibility, state=source.state, revision=source.revision,
                captured_at=source.created_at.isoformat(),
                published_date=source.published_date.isoformat() if source.published_date else None,
                warning=source.warning, error=source.error, attempts=source.attempts,
                can_review=can_review, extractor=source.extractor_version)


def claim_dict(claim):
    return dict(id=claim.id, locator=claim.locator, evidence=claim.evidence,
                statement=claim.statement, standing=claim.standing, kind=claim.kind,
                topic=claim.topic, reviewed_at=claim.reviewed_at.isoformat() if claim.reviewed_at else None)


def submit_source(layer_id, user_id, program_id, title, content, extension, published_date=None):
    program = CIProgram.query.filter_by(id=program_id, layer_id=layer_id).first_or_404()
    require_org(program.organization_id, user_id)
    if extension not in SUPPORTED or not content or len(content) > MAX_BYTES:
        abort(400, description='Supported files: TXT, MD, PDF, DOCX, PNG, JPEG; maximum 5 MB.')
    digest = hashlib.sha256(content).hexdigest()
    # A removed contribution cannot be reintroduced in another program or layer.
    tombstone = CISource.query.filter_by(organization_id=program.organization_id,
                                        digest=digest, state='withdrawn').first()
    if tombstone:
        abort(409, description='This contribution was removed. Reintroduction is blocked.')
    prior = CISource.query.filter_by(organization_id=program.organization_id,
                                   layer_id=layer_id, program_id=program_id, digest=digest).first()
    if prior:
        return prior, False
    source = CISource(organization_id=program.organization_id, layer_id=layer_id,
                      program_id=program_id, title=title, original=content, digest=digest,
                      media_type=extension, submitted_by=user_id, published_date=published_date)
    db.session.add(source)
    db.session.flush()
    audit(source.organization_id, user_id, source.id, 'source.received', source.revision)
    return source, True


def process_source(source_id):
    """One durable queue job. CAS prevents retry/withdrawal races from recreating data.

    Extraction runs outside the transaction. A crashed processing job can be
    explicitly retried by a steward. No outbound network is available here.
    """
    source = db.session.get(CISource, source_id)
    if not source or source.state != 'queued' or not enabled(source.layer_id):
        db.session.rollback()
        return False
    revision = source.revision
    content, extension = source.original, source.media_type
    won = CISource.query.filter_by(id=source_id, revision=revision, state='queued').update(
        {'state': 'processing', 'revision': revision + 1, 'attempts': CISource.attempts + 1},
        synchronize_session=False)
    db.session.commit()
    if not won:
        return False
    try:
        passages, warnings = extract(content, extension)
        error = None
    except ExtractionError as exc:
        passages, warnings, error = [], [], str(exc)
    except Exception:
        passages, warnings, error = [], [], 'Extraction failed. Inspect the worker configuration and retry.'
    won = CISource.query.filter_by(id=source_id, revision=revision + 1, state='processing').update(
        {'state': 'failed' if error else 'needs_review', 'revision': revision + 2,
         'warning': '\n'.join(warnings), 'error': error}, synchronize_session=False)
    if not won:
        db.session.rollback()
        return False
    for locator, evidence in passages:
        db.session.add(CIClaim(source_id=source_id, locator=locator, evidence=evidence, statement=evidence))
    source = db.session.get(CISource, source_id, populate_existing=True)
    audit(source.organization_id, None, source.id,
          'extraction.failed' if error else 'extraction.completed', revision + 2)
    db.session.commit()
    return True


def review(source, user_id, data):
    advance(CISource, source, data.get('revision'))
    if source.state not in {'needs_review', 'ready'}:
        abort(409, description='Source is not ready for review.')
    decisions = data.get('decisions')
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 200:
        abort(400, description='Provide 1 to 200 review decisions.')
    seen = set()
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get('id'), str):
            abort(400, description='Invalid decision.')
        if decision['id'] in seen:
            abort(400, description='Duplicate decision.')
        seen.add(decision['id'])
        claim = CIClaim.query.filter_by(id=decision['id'], source_id=source.id).first_or_404()
        if not isinstance(decision.get('standing'), str) or decision['standing'] not in {'confirmed', 'rejected', 'disputed'}:
            abort(400, description='Choose confirmed, rejected or disputed.')
        kind = decision.get('kind', claim.kind)
        if not isinstance(kind, str) or kind not in {'description', 'need', 'offer'}:
            abort(400, description='Invalid claim kind.')
        statement = text_field(decision, 'statement', 2000) if 'statement' in decision else claim.statement
        topic = text_field(decision, 'topic', 100, optional=True) if 'topic' in decision else claim.topic
        claim.statement, claim.standing, claim.kind, claim.topic = statement, decision['standing'], kind, topic
        claim.reviewed_by, claim.reviewed_at = user_id, datetime.utcnow()
    db.session.flush()
    source.state = 'needs_review' if CIClaim.query.filter_by(source_id=source.id, standing='proposed').first() else 'ready'
    audit(source.organization_id, user_id, source.id, 'changes.reviewed', source.revision)


def withdraw(source, user_id, revision):
    advance(CISource, source, revision)
    CIClaim.query.filter_by(source_id=source.id).delete(synchronize_session=False)
    # Remove persisted discussion copies that may quote this source, too.
    from models.community_intelligence import CIRoom, CIRoomMessage, CIAction
    for room in CIRoom.query.filter_by(layer_id=source.layer_id).all():
        if any(e['source_id'] == source.id for e in room.evidence):
            CIRoomMessage.query.filter_by(room_id=room.id).delete(synchronize_session=False)
            CIAction.query.filter_by(room_id=room.id).delete(synchronize_session=False)
            room.title = 'Discussion evidence removed'
    source.original, source.warning, source.error = None, None, None
    source.title, source.visibility, source.state = 'Removed contribution', 'private', 'withdrawn'
    audit(source.organization_id, user_id, source.id, 'contribution.withdrawn', source.revision)


def evidence_query(layer_id, user_id, *, history=False, shared_only=False):
    sources = visible_sources(layer_id, user_id, shared_only=shared_only).with_entities(CISource.id)
    query = db.session.query(CIClaim, CISource, CIProgram).join(
        CISource, CIClaim.source_id == CISource.id).join(CIProgram, CISource.program_id == CIProgram.id).filter(
        CISource.id.in_(sources), CIClaim.standing == 'confirmed',
        CISource.state.in_(['ready', 'needs_review']))
    if not history:
        query = query.filter(CIProgram.lifecycle == 'active')
    return query


def evidence_dict(claim, source, program):
    track_evidence(source, program)
    return dict(claim_id=claim.id, statement=claim.statement, evidence=claim.evidence,
                source_id=source.id, title=source.title, locator=claim.locator,
                organization_id=source.organization_id,
                organization=db.session.get(CIOrganization, source.organization_id).name,
                program=program.name, lifecycle=program.lifecycle, standing='organization-confirmed',
                source_revision=source.revision, program_revision=program.revision,
                captured_at=source.created_at.isoformat(),
                published_date=source.published_date.isoformat() if source.published_date else None,
                reviewed_at=claim.reviewed_at.isoformat() if claim.reviewed_at else None)


def answer(layer_id, user_id, question, *, history=False):
    tokens = list(dict.fromkeys(re.findall(r'\w{3,}', question.lower())))[:12]
    stop = {'the', 'and', 'what', 'who', 'can', 'does', 'have', 'with', 'are', 'for'}
    tokens = [token for token in tokens if token not in stop]
    query = evidence_query(layer_id, user_id, history=history)
    if not tokens:
        rows = []
    else:
        query = query.filter(or_(*(CIClaim.statement.ilike('%' + t + '%') for t in tokens)))
        rows = query.order_by(CIClaim.reviewed_at.desc(), CIClaim.id).limit(12).all()
    return dict(mode='evidence-retrieval', historical=history,
                answer='Reviewed evidence matching your question.' if rows else
                       'No matching reviewed evidence is documented in the accessible knowledge. This does not establish that no one is doing the work.',
                limitation='Keyword retrieval, not a model-generated answer. No Hermes or semantic inference is configured.',
                citations=[evidence_dict(*row) for row in rows])


def opportunities(layer_id, user_id):
    """Draft suggestions from explicitly reviewed need/offer tags shared to this layer.

    Computed afresh so retirement, corrections and withdrawal remove dependencies.
    No claims of capacity, partnership or commitment are inferred.
    """
    rows = evidence_query(layer_id, user_id, shared_only=True).filter(
        CIClaim.kind.in_(['need', 'offer']), CIClaim.topic.isnot(None), CIClaim.topic != '').order_by(
        CIClaim.reviewed_at.desc(), CIClaim.id).limit(200).all()
    out = []
    for need in rows:
        if need[0].kind != 'need':
            continue
        for offer in rows:
            if (offer[0].kind != 'offer' or need[1].organization_id == offer[1].organization_id
                    or need[0].topic.casefold() != offer[0].topic.casefold()):
                continue
            from services.community_opportunities import snapshots
            out.append(dict(evidence=snapshots([need, offer]), id=f'{need[0].id}:{offer[0].id}', title=f'Explore {need[0].topic}',
                            status='rule-based suggestion', audience='layer',
                            explanation='A reviewed need and offer share a steward-selected topic.',
                            unknowns=['Current capacity and willingness', 'Timing, geography and conditions'],
                            first_step='Ask the participating stewards whether a short scoping conversation would help.',
                            citations=[evidence_dict(*need), evidence_dict(*offer)]))
            if len(out) == 20:
                return out
    return out
