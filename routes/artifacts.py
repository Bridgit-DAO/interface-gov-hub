"""Artifacts API: artifacts, relations, support/opposition, opportunities, quests, monuments."""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import (
    Layer,
    LayerMember,
    Artifact,
    ArtifactRelation,
    Submission,
    Quest,
    QuestSubmission,
    Monument,
    GuildArtifactLink,
    GuildQuestLink,
    Comment,
)
from services.access_policy import (
    can_user_submit_quest,
    normalize_join_policy_quest,
    normalize_listing_visibility,
    quest_listing_visible,
)
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin, is_site_moderation_staff
from services.artifact import get_artifact_by_ref, _ensure_artifact_for_submission
from services.events import emit_event
from services.knowledge_layer import (
    apply_knowledge_patch,
    canonical_knowledge_form,
    public_schema_dict,
    validate_knowledge_for_create,
)
from services.artifact_tags import (
    tags_enabled,
    tag_filters_enabled,
    parse_tag_slugs,
    list_layer_tags,
    set_artifact_tags,
    apply_tag_filter,
    artifact_to_dict,
    enrich_artifact_dicts,
)

bp = Blueprint('artifacts', __name__, url_prefix='/api')

ARTIFACT_RELATION_TYPES = frozenset([
    'builds_on', 'references', 'supports', 'opposes', 'amends', 'implements', 'awarded_for'
])

# Site moderation staff (admin/editor) may PATCH these keys without layer membership (see update_artifact).
_STAFF_KNOWLEDGE_ONLY_PATCH_KEYS = frozenset({'knowledge_form', 'knowledge_scaffold'})


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
    from services.layer_features import get_effective_features

    layer = Layer.query.get(layer_id)
    if get_effective_features(layer).get('quests', True):
        viewer = get_current_user()
        try:
            for q in Quest.query.filter_by(layer_id=layer_id, status='open').order_by(Quest.created_at.desc()).limit(20):
                if not quest_listing_visible(q, viewer):
                    continue
                open_quests.append({
                    'id': q.id, 'public_id': q.public_id, 'title': q.title,
                    'quest_type': q.quest_type, 'difficulty': q.difficulty,
                    'listing_visibility': getattr(q, 'listing_visibility', 'public'),
                    'join_policy': getattr(q, 'join_policy', 'open'),
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
        viewer = get_current_user()
        visible = [q for q in quests if quest_listing_visible(q, viewer)]
        return jsonify({
            'quests': [{
                'id': q.id, 'public_id': q.public_id, 'title': q.title, 'description': q.description,
                'quest_type': q.quest_type, 'difficulty': q.difficulty, 'status': q.status,
                'acceptance_criteria': q.acceptance_criteria,
                'due_date': q.due_date.isoformat() if q.due_date else None,
                'listing_visibility': getattr(q, 'listing_visibility', 'public'),
                'join_policy': getattr(q, 'join_policy', 'open'),
                'created_at': q.created_at.isoformat() if q.created_at else None,
            } for q in visible]
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
        listing_visibility=normalize_listing_visibility(data.get('listing_visibility')),
        join_policy=normalize_join_policy_quest(data.get('join_policy')),
    )
    db.session.add(quest)
    db.session.flush()
    emit_event('quest_created', actor_type='user', actor_id=current_user.get('id'),
               subject_type='quest', subject_id=str(quest.id), layer_id=layer_id,
               payload={'title': quest.title})
    db.session.commit()
    return jsonify({'quest': quest.to_dict()}), 201


@bp.route('/quests/<quest_id>/', methods=['PATCH'])
@require_auth
def update_quest(quest_id):
    """Update quest metadata (layer admin or quest creator)."""
    quest = Quest.query.get_or_404(quest_id)
    layer = Layer.query.get_or_404(quest.layer_id)
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if quest.creator_user_id != user.get('id') and not is_layer_admin(layer, user):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json() or {}
    if 'title' in data and (data.get('title') or '').strip():
        quest.title = data['title'].strip()
    if 'description' in data:
        quest.description = data['description']
    if 'quest_type' in data:
        quest.quest_type = data['quest_type']
    if 'difficulty' in data:
        quest.difficulty = data['difficulty']
    if 'status' in data and data['status'] in ('open', 'closed', 'completed'):
        quest.status = data['status']
    if 'acceptance_criteria' in data:
        quest.acceptance_criteria = data['acceptance_criteria']
    if 'listing_visibility' in data:
        quest.listing_visibility = normalize_listing_visibility(data.get('listing_visibility'))
    if 'join_policy' in data:
        quest.join_policy = normalize_join_policy_quest(data.get('join_policy'))
    quest.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'quest': quest.to_dict()})


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
    ok, err = can_user_submit_quest(quest, current_user)
    if not ok:
        return jsonify({'error': err or 'Forbidden'}), 403
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
    payload = artifact_to_dict(art) if tags_enabled(current_app.config) else art.to_dict()
    sub = Submission.query.filter_by(artifact_id=art.id).first()
    if sub:
        payload['submission_id'] = sub.id
    return jsonify(payload)


@bp.route('/artifacts/<artifact_id>/guild-links/', methods=['GET'])
def list_artifact_guild_links(artifact_id):
    """Guild sponsorship / co-author / review links for this artifact (Unified Phase I)."""
    art = Artifact.query.get(artifact_id)
    if not art:
        art = Artifact.query.filter_by(public_id=artifact_id).first()
    if not art:
        return jsonify({'error': 'Artifact not found'}), 404
    rows = GuildArtifactLink.query.filter_by(artifact_id=art.id).all()
    out = []
    for row in rows:
        d = row.to_dict()
        g = row.guild
        if g:
            d['guild'] = {
                'id': g.id,
                'name': g.name,
                'slug': g.slug,
                'image_url': g.image_url,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/quests/<quest_id>/guild-links/', methods=['GET'])
def list_quest_guild_links(quest_id):
    """Guild links for a quest (Unified Phase I)."""
    quest = Quest.query.get(quest_id)
    if not quest:
        return jsonify({'error': 'Quest not found'}), 404
    rows = GuildQuestLink.query.filter_by(quest_id=quest.id).all()
    out = []
    for row in rows:
        d = row.to_dict()
        g = row.guild
        if g:
            d['guild'] = {
                'id': g.id,
                'name': g.name,
                'slug': g.slug,
                'image_url': g.image_url,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/artifacts/<artifact_id>/', methods=['PATCH'])
@require_auth
def update_artifact(artifact_id):
    """Update artifact. Layer member or admin."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    art = Artifact.query.get_or_404(artifact_id)
    data = request.get_json(silent=True) or {}
    if art.layer_id:
        layer = Layer.query.get(art.layer_id)
        if layer and not is_layer_admin(layer, current_user):
            member = LayerMember.query.filter_by(layer_id=art.layer_id, user_id=current_user['id'], status='active').first()
            if not member:
                staff_knowledge_only = (
                    is_site_moderation_staff(current_user)
                    and set(data.keys()).issubset(_STAFF_KNOWLEDGE_ONLY_PATCH_KEYS)
                )
                if not staff_knowledge_only:
                    return jsonify({'error': 'Not a layer member'}), 403
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
        _layer = Layer.query.get(art.layer_id) if art.layer_id else None
        _others_artifact = (
            _layer
            and (not art.creator_user_id or art.creator_user_id != current_user['id'])
            and (
                is_layer_admin(_layer, current_user)
                or is_site_moderation_staff(current_user)
            )
        )
        _src = 'moderation' if _others_artifact else 'edit'
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
                    'source': _src,
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
                payload={'previous': old_kf, 'source': _src},
            )
    emit_event('artifact_updated', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=art.id, layer_id=art.layer_id,
               payload={'updated_fields': list(data.keys())})
    if 'status' in data and old_status != art.status:
        emit_event('artifact_status_changed', actor_type='user', actor_id=current_user['id'],
                   subject_type='artifact', subject_id=art.id, layer_id=art.layer_id,
                   payload={'old_status': old_status, 'new_status': art.status})
    if tags_enabled(current_app.config) and ('tag_slugs' in data or 'tags' in data):
        raw_tags = data.get('tag_slugs', data.get('tags'))
        try:
            added, removed = set_artifact_tags(art, raw_tags or [], current_user['id'])
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        for slug in added:
            emit_event(
                'artifact_tag_added',
                actor_type='user',
                actor_id=current_user['id'],
                subject_type='artifact',
                subject_id=art.id,
                layer_id=art.layer_id,
                payload={'tag_slug': slug},
            )
        for slug in removed:
            emit_event(
                'artifact_tag_removed',
                actor_type='user',
                actor_id=current_user['id'],
                subject_type='artifact',
                subject_id=art.id,
                layer_id=art.layer_id,
                payload={'tag_slug': slug},
            )
    db.session.commit()
    payload = artifact_to_dict(art) if tags_enabled(current_app.config) else art.to_dict()
    return jsonify({'success': True, 'artifact': payload})


@bp.route('/layers/<layer_id>/artifact-tags/', methods=['GET'])
def list_layer_artifact_tags(layer_id):
    """List tags defined on a layer (with artifact counts)."""
    Layer.query.get_or_404(layer_id)
    if not tags_enabled(current_app.config):
        return jsonify({'tags': [], 'enabled': False}), 200
    return jsonify({
        'tags': list_layer_tags(layer_id, with_counts=True),
        'enabled': True,
    }), 200


@bp.route('/layers/<layer_id>/artifacts/', methods=['GET'])
def list_layer_artifacts(layer_id):
    """List artifacts for a layer. Optional ?knowledge_form=, ?tags=, ?tags_any=."""
    Layer.query.get_or_404(layer_id)
    q = Artifact.query.filter_by(layer_id=layer_id)
    kf = request.args.get('knowledge_form')
    if kf and current_app.config.get('KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED', True):
        kf_norm = canonical_knowledge_form(kf)
        if kf_norm:
            q = q.filter(Artifact.knowledge_form == kf_norm)
    if tag_filters_enabled(current_app.config):
        tags_and = request.args.get('tags')
        tags_any = request.args.get('tags_any')
        if tags_and:
            q = apply_tag_filter(q, tags_and.split(','), match_any=False)
        elif tags_any:
            q = apply_tag_filter(q, tags_any.split(','), match_any=True)
    arts = q.order_by(Artifact.created_at.desc()).limit(100).all()
    if tags_enabled(current_app.config):
        artifacts = enrich_artifact_dicts(arts)
    else:
        artifacts = [a.to_dict() for a in arts]
    return jsonify({'artifacts': artifacts}), 200


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
    if tags_enabled(current_app.config) and ('tag_slugs' in data or 'tags' in data):
        raw_tags = data.get('tag_slugs', data.get('tags'))
        try:
            added, _ = set_artifact_tags(art, raw_tags or [], current_user['id'])
        except ValueError as exc:
            db.session.rollback()
            return jsonify({'error': str(exc)}), 400
        for slug in added:
            emit_event(
                'artifact_tag_added',
                actor_type='user',
                actor_id=current_user['id'],
                subject_type='artifact',
                subject_id=art.id,
                layer_id=layer_id,
                payload={'tag_slug': slug, 'source': 'create'},
            )
    db.session.commit()
    payload = artifact_to_dict(art) if tags_enabled(current_app.config) else art.to_dict()
    return jsonify({'success': True, 'artifact': payload}), 201


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


@bp.route('/artifacts/<artifact_id>/comments/', methods=['POST'])
@require_auth
def create_artifact_comment(artifact_id):
    """Create a comment on an artifact."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    
    art = Artifact.query.get_or_404(artifact_id)
    data = request.get_json() or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Comment text is required'}), 400
    
    parent_id = (data.get('parent_id') or '').strip() or None
    if parent_id:
        parent = Comment.query.get(parent_id)
        if not parent or parent.artifact_id != artifact_id:
            return jsonify({'error': 'Parent comment not found or not on this artifact'}), 404
    
    comment = Comment(
        artifact_id=artifact_id,
        text=text,
        author_user_id=current_user['id'],
        author=current_user.get('display_name') or current_user.get('username') or current_user.get('email') or 'Anonymous',
        parent_id=parent_id,
    )
    db.session.add(comment)
    db.session.flush()
    
    emit_event('artifact_commented', actor_type='user', actor_id=current_user['id'],
               subject_type='artifact', subject_id=artifact_id, layer_id=art.layer_id,
               payload={'comment_id': comment.id, 'parent_id': parent_id})
    db.session.commit()
    
    return jsonify({
        'comment': {
            'id': comment.id,
            'text': comment.text,
            'author': comment.author,
            'author_user_id': comment.author_user_id,
            'timestamp': comment.timestamp.isoformat() if comment.timestamp else None,
            'parent_id': comment.parent_id,
        }
    }), 201


@bp.route('/artifacts/<artifact_id>/comments/', methods=['GET'])
def list_artifact_comments(artifact_id):
    """List all comments for an artifact (with replies nested)."""
    Artifact.query.get_or_404(artifact_id)
    
    # Get all comments for this artifact
    all_comments = Comment.query.filter_by(artifact_id=artifact_id, is_deleted=False).order_by(Comment.timestamp).all()
    
    # Build comment tree
    comment_map = {}
    root_comments = []
    
    def comment_to_dict(c):
        return {
            'id': c.id,
            'text': c.text,
            'author': c.author,
            'author_user_id': c.author_user_id,
            'timestamp': c.timestamp.isoformat() if c.timestamp else None,
            'parent_id': c.parent_id,
            'edited_at': c.edited_at.isoformat() if c.edited_at else None,
            'replies': [],
        }
    
    for c in all_comments:
        comment_map[c.id] = comment_to_dict(c)
    
    for c in all_comments:
        c_dict = comment_map[c.id]
        if c.parent_id and c.parent_id in comment_map:
            comment_map[c.parent_id]['replies'].append(c_dict)
        else:
            root_comments.append(c_dict)
    
    return jsonify({'comments': root_comments, 'count': len(all_comments)}), 200
