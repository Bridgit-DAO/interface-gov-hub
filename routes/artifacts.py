"""Artifacts API: artifacts, relations, support/opposition, opportunities, quests, monuments."""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import (
    Layer, LayerMember, Artifact, ArtifactRelation, Submission, Quest, QuestSubmission, Monument,
)
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.artifact import get_artifact_by_ref, _ensure_artifact_for_submission
from services.events import emit_event
from services.knowledge_layer import (
    apply_knowledge_patch,
    public_schema_dict,
    validate_knowledge_for_create,
)

bp = Blueprint('artifacts', __name__, url_prefix='/api')

ARTIFACT_RELATION_TYPES = frozenset([
    'builds_on', 'references', 'supports', 'opposes', 'amends', 'implements', 'awarded_for'
])


def _artifact_lineage(artifact_id, depth=3):
    """Compute ancestors and descendants for lineage. Returns (ancestors, descendants)."""
    art = Artifact.query.get(artifact_id)
    if not art:
        return [], []
    seen_a, seen_d = {artifact_id}, {artifact_id}
    ancestors, descendants = [], []

    def _node(a, rel_type, d):
        return {'id': a.id, 'public_ref': a.public_ref, 'title': (a.title or a.public_ref or a.id)[:60], 'relation_type': rel_type, 'depth': d}

    frontier_a = [(artifact_id, 0)]
    for aid, d in frontier_a:
        if d >= depth:
            continue
        inc = ArtifactRelation.query.filter(
            ArtifactRelation.to_object_type == 'artifact',
            ArtifactRelation.to_object_id == aid,
        ).all()
        for r in inc:
            if r.from_object_type == 'artifact' and r.from_object_id not in seen_a:
                seen_a.add(r.from_object_id)
                a = Artifact.query.get(r.from_object_id)
                if a:
                    ancestors.append(_node(a, r.relation_type, d + 1))
                    frontier_a.append((r.from_object_id, d + 1))

    frontier_d = [(artifact_id, 0)]
    for aid, d in frontier_d:
        if d >= depth:
            continue
        out = ArtifactRelation.query.filter(
            ArtifactRelation.from_object_type == 'artifact',
            ArtifactRelation.from_object_id == aid,
        ).all()
        for r in out:
            if r.to_object_type == 'artifact' and r.to_object_id not in seen_d:
                seen_d.add(r.to_object_id)
                a = Artifact.query.get(r.to_object_id)
                if a:
                    descendants.append(_node(a, r.relation_type, d + 1))
                    frontier_d.append((r.to_object_id, d + 1))

    return ancestors, descendants


@bp.route('/layers/<layer_id>/artifact-relations/', methods=['POST'])
@require_auth
def create_artifact_relation(layer_id):
    """Create a typed link between artifacts."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    from_type = data.get('from_object_type')
    from_id = data.get('from_object_id')
    to_type = data.get('to_object_type')
    to_id = data.get('to_object_id')
    relation_type = data.get('relation_type')
    if not all([from_type, from_id, to_type, to_id, relation_type]):
        return jsonify({'error': 'from_object_type, from_object_id, to_object_type, to_object_id, relation_type required'}), 400
    if relation_type not in ARTIFACT_RELATION_TYPES:
        return jsonify({'error': f'relation_type must be one of: {sorted(ARTIFACT_RELATION_TYPES)}'}), 400
    Layer.query.get_or_404(layer_id)
    rel = ArtifactRelation(
        from_object_type=from_type,
        from_object_id=str(from_id),
        to_object_type=to_type,
        to_object_id=str(to_id),
        relation_type=relation_type,
        created_by_user_id=current_user['id'],
    )
    db.session.add(rel)
    db.session.flush()
    emit_event('artifact_linked', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact_relation', subject_id=rel.id, layer_id=layer_id,
               payload={'from': f'{from_type}:{from_id}', 'to': f'{to_type}:{to_id}', 'relation_type': relation_type})
    db.session.commit()
    return jsonify({
        'id': rel.id,
        'from_object_type': rel.from_object_type,
        'from_object_id': rel.from_object_id,
        'to_object_type': rel.to_object_type,
        'to_object_id': rel.to_object_id,
        'relation_type': rel.relation_type,
        'created_at': rel.created_at.isoformat() if rel.created_at else None,
    }), 201


@bp.route('/artifacts/<artifact_id>/support/', methods=['POST'])
@require_auth
def add_support(artifact_id):
    """Create a support artifact and link to proposal."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    proposal = Artifact.query.get_or_404(artifact_id)
    if not proposal.layer_id:
        return jsonify({'error': 'Artifact has no layer'}), 400
    data = request.get_json() or {}
    title = (data.get('title') or '').strip() or f"Support for {proposal.title or 'proposal'}"
    summary = (data.get('summary') or '').strip() or None
    support = Artifact(
        layer_id=proposal.layer_id,
        creator_user_id=current_user['id'],
        artifact_type='support',
        title=title,
        summary=summary,
        status='published',
    )
    db.session.add(support)
    db.session.flush()
    rel = ArtifactRelation(
        from_object_type='artifact',
        from_object_id=support.id,
        to_object_type='artifact',
        to_object_id=artifact_id,
        relation_type='supports',
        created_by_user_id=current_user['id'],
    )
    db.session.add(rel)
    emit_event('artifact_created', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=support.id, layer_id=proposal.layer_id,
               payload={'artifact_type': 'support', 'proposal_id': artifact_id})
    emit_event('artifact_linked', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact_relation', subject_id=rel.id, layer_id=proposal.layer_id,
               payload={'from': f'artifact:{support.id}', 'to': f'artifact:{artifact_id}', 'relation_type': 'supports'})
    db.session.commit()
    return jsonify({
        'artifact': {'id': support.id, 'title': support.title, 'summary': support.summary},
        'relation': {'id': rel.id, 'relation_type': 'supports'},
    }), 201


@bp.route('/artifacts/<artifact_id>/opposition/', methods=['POST'])
@require_auth
def add_opposition(artifact_id):
    """Create an opposition artifact and link to proposal."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    proposal = Artifact.query.get_or_404(artifact_id)
    if not proposal.layer_id:
        return jsonify({'error': 'Artifact has no layer'}), 400
    data = request.get_json() or {}
    title = (data.get('title') or '').strip() or f"Opposition to {proposal.title or 'proposal'}"
    summary = (data.get('summary') or '').strip() or None
    opposition = Artifact(
        layer_id=proposal.layer_id,
        creator_user_id=current_user['id'],
        artifact_type='opposition',
        title=title,
        summary=summary,
        status='published',
    )
    db.session.add(opposition)
    db.session.flush()
    rel = ArtifactRelation(
        from_object_type='artifact',
        from_object_id=opposition.id,
        to_object_type='artifact',
        to_object_id=artifact_id,
        relation_type='opposes',
        created_by_user_id=current_user['id'],
    )
    db.session.add(rel)
    emit_event('artifact_created', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=opposition.id, layer_id=proposal.layer_id,
               payload={'artifact_type': 'opposition', 'proposal_id': artifact_id})
    emit_event('artifact_linked', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact_relation', subject_id=rel.id, layer_id=proposal.layer_id,
               payload={'from': f'artifact:{opposition.id}', 'to': f'artifact:{artifact_id}', 'relation_type': 'opposes'})
    db.session.commit()
    return jsonify({
        'artifact': {'id': opposition.id, 'title': opposition.title, 'summary': opposition.summary},
        'relation': {'id': rel.id, 'relation_type': 'opposes'},
    }), 201


@bp.route('/layers/<layer_id>/opportunities/', methods=['GET'])
def layer_opportunities(layer_id):
    """Drafts missing support or opposition, open quests."""
    Layer.query.get_or_404(layer_id)
    artifacts = Artifact.query.filter_by(layer_id=layer_id, artifact_type='submission').all()
    missing_support = []
    missing_opposition = []
    for a in artifacts:
        incoming = ArtifactRelation.query.filter(
            ArtifactRelation.to_object_type == 'artifact',
            ArtifactRelation.to_object_id == a.id,
        ).all()
        has_support = any(r.relation_type == 'supports' for r in incoming)
        has_opposition = any(r.relation_type == 'opposes' for r in incoming)
        sub = Submission.query.filter_by(artifact_id=a.id).first()
        draft_id = sub.id if sub else a.id
        layer = Layer.query.get(layer_id)
        layer_slug = layer.slug if layer else layer_id
        item = {'id': a.id, 'title': a.title or 'Untitled', 'draft_id': draft_id, 'layer_slug': layer_slug}
        if not has_support:
            missing_support.append(item)
        if not has_opposition:
            missing_opposition.append(item)
    open_quests = []
    try:
        for q in Quest.query.filter_by(layer_id=layer_id, status='open').order_by(Quest.created_at.desc()).limit(20):
            open_quests.append({
                'id': q.id, 'public_id': q.public_id, 'title': q.title,
                'quest_type': q.quest_type, 'difficulty': q.difficulty,
            })
    except Exception:
        pass
    return jsonify({
        'missing_support': missing_support,
        'missing_opposition': missing_opposition,
        'open_quests': open_quests,
    }), 200


@bp.route('/layers/<layer_id>/quests/', methods=['GET', 'POST'])
def layer_quests(layer_id):
    """List or create quests for a layer."""
    Layer.query.get_or_404(layer_id)
    if request.method == 'GET':
        status_filter = request.args.get('status') or 'open'
        q = Quest.query.filter_by(layer_id=layer_id)
        if status_filter:
            q = q.filter(Quest.status == status_filter)
        quests = q.order_by(Quest.created_at.desc()).all()
        return jsonify({
            'quests': [{
                'id': q.id, 'public_id': q.public_id, 'title': q.title, 'description': q.description,
                'quest_type': q.quest_type, 'difficulty': q.difficulty, 'status': q.status,
                'acceptance_criteria': q.acceptance_criteria,
                'due_date': q.due_date.isoformat() if q.due_date else None,
                'created_at': q.created_at.isoformat() if q.created_at else None,
            } for q in quests]
        }), 200
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    quest = Quest(
        layer_id=layer_id,
        creator_user_id=current_user.get('id'),
        title=data.get('title') or 'Untitled Quest',
        description=data.get('description'),
        quest_type=data.get('quest_type', 'contribution'),
        difficulty=data.get('difficulty', 'medium'),
        status='open',
        acceptance_criteria=data.get('acceptance_criteria'),
    )
    db.session.add(quest)
    db.session.flush()
    emit_event('quest_created', actor_type='user', actor_id=current_user.get('id'),
               subject_type='quest', subject_id=str(quest.id), layer_id=layer_id,
               payload={'title': quest.title})
    db.session.commit()
    return jsonify({
        'quest': {
            'id': quest.id, 'public_id': quest.public_id, 'title': quest.title,
            'description': quest.description, 'quest_type': quest.quest_type,
            'difficulty': quest.difficulty, 'status': quest.status,
        }
    }), 201


@bp.route('/quests/<quest_id>/submit/', methods=['POST'])
@require_auth
def quest_submit(quest_id):
    """Submit an artifact for a quest."""
    quest = Quest.query.get_or_404(quest_id)
    if quest.status != 'open':
        return jsonify({'error': 'Quest is not open for submissions'}), 400
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    artifact_id = data.get('artifact_id')
    if not artifact_id:
        return jsonify({'error': 'artifact_id required'}), 400
    Artifact.query.get_or_404(artifact_id)
    qs = QuestSubmission(
        quest_id=quest_id,
        artifact_id=artifact_id,
        submitter_user_id=current_user.get('id'),
        status='pending_review',
    )
    db.session.add(qs)
    db.session.commit()
    return jsonify({
        'quest_submission': {'id': qs.id, 'status': qs.status, 'artifact_id': artifact_id},
    }), 201


@bp.route('/layers/<layer_id>/monuments/', methods=['GET', 'POST'])
def layer_monuments(layer_id):
    """List or create monuments for a layer."""
    Layer.query.get_or_404(layer_id)
    if request.method == 'GET':
        status_filter = request.args.get('status') or 'active'
        monuments = Monument.query.filter_by(layer_id=layer_id).filter(
            Monument.status == status_filter
        ).order_by(Monument.created_at.desc()).all()
        return jsonify({
            'monuments': [{
                'id': m.id, 'public_id': m.public_id, 'title': m.title, 'description': m.description,
                'monument_type': m.monument_type, 'steward_user_id': m.steward_user_id,
                'uri': m.uri, 'provenance': m.provenance, 'status': m.status,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            } for m in monuments]
        }), 200
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    monument = Monument(
        layer_id=layer_id,
        title=data.get('title') or 'Untitled Monument',
        description=data.get('description'),
        monument_type=data.get('monument_type', 'reference'),
        steward_user_id=current_user.get('id'),
        uri=data.get('uri'),
        provenance=data.get('provenance'),
        status='active',
    )
    db.session.add(monument)
    db.session.flush()
    emit_event('monument_created', actor_type='user', actor_id=current_user.get('id'),
               subject_type='monument', subject_id=str(monument.id), layer_id=layer_id,
               payload={'title': monument.title})
    db.session.commit()
    return jsonify({
        'monument': {'id': monument.id, 'public_id': monument.public_id, 'title': monument.title},
    }), 201


@bp.route('/monuments/<monument_id>/', methods=['GET'])
def monument_detail(monument_id):
    """Get a single monument."""
    m = Monument.query.get_or_404(monument_id)
    return jsonify({
        'id': m.id, 'public_id': m.public_id, 'title': m.title, 'description': m.description,
        'monument_type': m.monument_type, 'steward_user_id': m.steward_user_id,
        'uri': m.uri, 'provenance': m.provenance, 'status': m.status, 'layer_id': m.layer_id,
        'created_at': m.created_at.isoformat() if m.created_at else None,
    }), 200


@bp.route('/monuments/<monument_id>/link-artifact/', methods=['POST'])
@require_auth
def monument_link_artifact(monument_id):
    """Link a monument to an artifact via ArtifactRelation."""
    monument = Monument.query.get_or_404(monument_id)
    if monument.status != 'active':
        return jsonify({'error': 'Monument is not active'}), 400
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    artifact_id = data.get('artifact_id')
    if not artifact_id:
        return jsonify({'error': 'artifact_id required'}), 400
    Artifact.query.get_or_404(artifact_id)
    relation_type = data.get('relation_type', 'references')
    rel = ArtifactRelation(
        from_object_type='monument',
        from_object_id=str(monument.public_id),
        to_object_type='artifact',
        to_object_id=artifact_id,
        relation_type=relation_type,
        created_by_user_id=current_user.get('id'),
    )
    db.session.add(rel)
    db.session.commit()
    return jsonify({
        'relation': {'id': rel.id, 'relation_type': relation_type, 'artifact_id': artifact_id},
    }), 201


@bp.route('/knowledge-layer/schema/', methods=['GET'])
def knowledge_layer_schema():
    """Feature flags + contribution-type matrix for client pickers (artifact_contribution_schema.md)."""
    return jsonify(public_schema_dict(current_app.config)), 200


@bp.route('/artifacts/<artifact_id>/', methods=['GET'])
def get_artifact(artifact_id):
    """Get artifact for modal."""
    art = Artifact.query.get_or_404(artifact_id)
    return jsonify(art.to_dict())


@bp.route('/artifacts/<artifact_id>/', methods=['PATCH'])
@require_auth
def update_artifact(artifact_id):
    """Update artifact. Layer member or admin."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    art = Artifact.query.get_or_404(artifact_id)
    if art.layer_id:
        layer = Layer.query.get(art.layer_id)
        if layer and not is_layer_admin(layer, current_user):
            member = LayerMember.query.filter_by(layer_id=art.layer_id, user_id=current_user['id'], status='active').first()
            if not member:
                return jsonify({'error': 'Not a layer member'}), 403
    data = request.get_json() or {}
    old_status = art.status
    old_kf = getattr(art, 'knowledge_form', None)
    for field in ('title', 'summary', 'body', 'uri', 'artifact_type', 'artifact_subtype', 'status', 'source_language', 'current_language'):
        if field in data:
            setattr(art, field, data[field] if data[field] is not None else None)
    kerr = apply_knowledge_patch(art, data, current_app.config)
    if kerr:
        return jsonify({'error': '; '.join(kerr)}), 400
    art.updated_at = datetime.utcnow()
    new_kf = getattr(art, 'knowledge_form', None)
    if old_kf != new_kf:
        if new_kf:
            emit_event(
                'contribution_type_set',
                actor_type='user',
                actor_id=current_user['id'],
                subject_type='artifact',
                subject_id=art.id,
                layer_id=art.layer_id,
                payload={
                    'knowledge_form': new_kf,
                    'source': 'edit',
                    'previous': old_kf,
                },
            )
        else:
            emit_event(
                'contribution_type_cleared',
                actor_type='user',
                actor_id=current_user['id'],
                subject_type='artifact',
                subject_id=art.id,
                layer_id=art.layer_id,
                payload={'previous': old_kf},
            )
    emit_event('artifact_updated', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=art.id, layer_id=art.layer_id,
               payload={'updated_fields': list(data.keys())})
    if 'status' in data and old_status != art.status:
        emit_event('artifact_status_changed', actor_type='user', actor_id=current_user['id'],
                   subject_type='artifact', subject_id=art.id, layer_id=art.layer_id,
                   payload={'old_status': old_status, 'new_status': art.status})
    db.session.commit()
    return jsonify({'success': True, 'artifact': art.to_dict()})


@bp.route('/layers/<layer_id>/artifacts/', methods=['GET'])
def list_layer_artifacts(layer_id):
    """List artifacts for a layer. Optional ?knowledge_form= when filters enabled."""
    Layer.query.get_or_404(layer_id)
    q = Artifact.query.filter_by(layer_id=layer_id)
    kf = request.args.get('knowledge_form')
    if kf and current_app.config.get('KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED', True):
        q = q.filter(Artifact.knowledge_form == kf.strip().lower())
    arts = q.order_by(Artifact.created_at.desc()).limit(100).all()
    return jsonify({'artifacts': [a.to_dict() for a in arts]}), 200


@bp.route('/layers/<layer_id>/artifacts/', methods=['POST'])
@require_auth
def create_artifact(layer_id):
    """Create standalone artifact."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    layer = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(layer, current_user):
        member = LayerMember.query.filter_by(layer_id=layer_id, user_id=current_user['id'], status='active').first()
        if not member:
            return jsonify({'error': 'Not a layer member'}), 403
    data = request.get_json() or {}
    atype = data.get('artifact_type', 'proposal')
    kform, kscaf, kerrs = validate_knowledge_for_create(
        atype,
        data.get('knowledge_form'),
        data.get('knowledge_scaffold'),
        current_app.config,
    )
    if kerrs:
        return jsonify({'error': '; '.join(kerrs)}), 400
    art = Artifact(
        layer_id=layer_id,
        creator_user_id=current_user['id'],
        artifact_type=atype,
        artifact_subtype=data.get('artifact_subtype'),
        title=data.get('title', '').strip() or None,
        summary=data.get('summary') or None,
        body=data.get('body') or None,
        uri=data.get('uri') or None,
        status=data.get('status', 'draft'),
        source_language=data.get('source_language'),
        current_language=data.get('current_language'),
        knowledge_form=kform,
        knowledge_scaffold=kscaf,
    )
    db.session.add(art)
    db.session.flush()
    emit_event('artifact_created', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=art.id, layer_id=layer_id,
               payload={'artifact_type': art.artifact_type})
    if kform:
        emit_event(
            'contribution_type_set',
            actor_type='user',
            actor_id=current_user['id'],
            subject_type='artifact',
            subject_id=art.id,
            layer_id=layer_id,
            payload={'knowledge_form': kform, 'source': 'create', 'previous': None},
        )
    db.session.commit()
    return jsonify({'success': True, 'artifact': art.to_dict()}), 201


@bp.route('/submissions/<submission_id>/ensure-artifact/', methods=['POST'])
@require_auth
def ensure_submission_artifact(submission_id):
    """Ensure artifact exists for submission. Creates if missing."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    sub = Submission.query.get_or_404(submission_id)
    if sub.layer_id:
        layer = Layer.query.get(sub.layer_id)
        if layer and not is_layer_admin(layer, current_user):
            member = LayerMember.query.filter_by(layer_id=sub.layer_id, user_id=current_user['id'], status='active').first()
            if not member:
                return jsonify({'error': 'Not a layer member'}), 403
    _ensure_artifact_for_submission(sub)
    db.session.commit()
    art = Artifact.query.get(sub.artifact_id)
    return jsonify({'success': True, 'artifact': art.to_dict(), 'artifact_id': art.id})


@bp.route('/artifacts/<artifact_id>/relations/', methods=['GET'])
def artifact_relations(artifact_id):
    """List typed relations for an artifact (incoming and outgoing)."""
    Artifact.query.get_or_404(artifact_id)
    outgoing = ArtifactRelation.query.filter(
        ArtifactRelation.from_object_type == 'artifact',
        ArtifactRelation.from_object_id == artifact_id,
    ).order_by(ArtifactRelation.created_at.desc()).all()
    incoming = ArtifactRelation.query.filter(
        ArtifactRelation.to_object_type == 'artifact',
        ArtifactRelation.to_object_id == artifact_id,
    ).order_by(ArtifactRelation.created_at.desc()).all()

    def _row(r, direction):
        return {
            'id': r.id,
            'direction': direction,
            'from_object_type': r.from_object_type,
            'from_object_id': r.from_object_id,
            'to_object_type': r.to_object_type,
            'to_object_id': r.to_object_id,
            'relation_type': r.relation_type,
            'created_at': r.created_at.isoformat() if r.created_at else None,
        }
    return jsonify({
        'outgoing': [_row(r, 'outgoing') for r in outgoing],
        'incoming': [_row(r, 'incoming') for r in incoming],
    }), 200


@bp.route('/artifacts/<artifact_id>/lineage/', methods=['GET'])
def artifact_lineage(artifact_id):
    """Lineage API: ancestors and descendants for governance graph."""
    art = Artifact.query.get_or_404(artifact_id)
    depth = min(int(request.args.get('depth', 3)), 5)
    ancestors, descendants = _artifact_lineage(artifact_id, depth)
    return jsonify({
        'artifact': {'id': art.id, 'public_ref': art.public_ref, 'title': art.title},
        'ancestors': ancestors,
        'descendants': descendants,
    }), 200
