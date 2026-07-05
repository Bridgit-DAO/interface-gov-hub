"""Bridges API: CRUD, sessions, set-source/set-target. Web2 bridges between content."""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, abort

from extensions import db
from models import Bridge, BridgeSession
from services.identity import get_current_user, require_auth

bp = Blueprint('bridges', __name__, url_prefix='/api/bridges')

# Claim-centric: how other content relates to the claim (source → target).
RELATIONSHIP_TYPES = frozenset({'cites', 'contradicted_by', 'supported_by', 'related_to'})
DEFAULT_RELATIONSHIP = 'related_to'
CONTENT_TYPES = frozenset({'text', 'image', 'video', 'audio'})


def parse_bridge_relationship(raw, *, default_if_missing=False):
    """
    Validate relationship for API. Pre-launch: no legacy aliases – must be canonical.

    If default_if_missing and raw is empty/whitespace, return DEFAULT_RELATIONSHIP.
    Otherwise return (value, None) or (None, error_message).
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if default_if_missing:
            return DEFAULT_RELATIONSHIP, None
        return None, f'relationship is required; must be one of: {sorted(RELATIONSHIP_TYPES)}'
    r = raw.strip().lower()
    if r not in RELATIONSHIP_TYPES:
        return None, f'relationship must be one of: {sorted(RELATIONSHIP_TYPES)}'
    return r, None


def _require_user():
    """Return current user or 401."""
    user = get_current_user()
    if not user:
        return None, jsonify({'error': 'Authentication required'}), 401
    return user, None


def _content_from_json(data):
    """Extract content reference from JSON. Returns dict or None."""
    if not data or not isinstance(data, dict):
        return None
    url = (data.get('url') or '').strip()
    if not url:
        return None
    ct = (data.get('content_type') or 'text').lower()
    if ct not in CONTENT_TYPES:
        ct = 'text'
    return {
        'url': url,
        'content_type': ct,
        'text_excerpt': data.get('text_excerpt') or None,
        'media_url': data.get('media_url') or None,
        'media_alt': data.get('media_alt') or None,
        'name': data.get('name') or None,
        'page_title': data.get('page_title') or None,
        'timestamp': data.get('timestamp') or None,
        'selector': data.get('selector') or None,
        'video_timestamp': data.get('video_timestamp'),
    }


def _content_to_bridge_fields(prefix, content):
    """Map content dict to Bridge model field names."""
    if not content:
        return {}
    return {
        f'{prefix}_url': content.get('url'),
        f'{prefix}_content_type': content.get('content_type', 'text'),
        f'{prefix}_text_excerpt': content.get('text_excerpt'),
        f'{prefix}_media_url': content.get('media_url'),
        f'{prefix}_media_alt': content.get('media_alt'),
        f'{prefix}_name': content.get('name'),
        f'{prefix}_page_title': content.get('page_title'),
        f'{prefix}_selector': content.get('selector'),
        f'{prefix}_video_timestamp': content.get('video_timestamp'),
    }


# ============================================================================
# Bridge CRUD
# ============================================================================

@bp.route('/', methods=['GET'])
def list_bridges():
    """List bridges with optional filters: relationship, inscribed, source_url, target_url."""
    query = Bridge.query
    relationship = request.args.get('relationship', '').strip()
    if relationship:
        rel, err = parse_bridge_relationship(relationship, default_if_missing=False)
        if err:
            return jsonify({'error': err}), 400
        query = query.filter_by(relationship=rel)
    source_url = (request.args.get('source_url') or '').strip()
    if source_url:
        query = query.filter(Bridge.source_url == source_url)
    target_url = (request.args.get('target_url') or '').strip()
    if target_url:
        query = query.filter(Bridge.target_url == target_url)
    inscribed = request.args.get('inscribed')
    if inscribed == 'true' or inscribed == '1':
        query = query.filter(Bridge.inscription_id.isnot(None))
    elif inscribed == 'false' or inscribed == '0':
        query = query.filter(Bridge.inscription_id.is_(None))

    bridges = query.order_by(Bridge.created_at.desc()).limit(100).all()
    return jsonify({
        'bridges': [b.to_dict() for b in bridges],
        'count': len(bridges),
    })


@bp.route('/', methods=['POST'])
@require_auth
def create_bridge():
    """Create a new bridge."""
    user, err = _require_user()
    if err:
        return err

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    source = _content_from_json(data.get('source'))
    target = _content_from_json(data.get('target'))
    if not source:
        return jsonify({'error': 'source with url is required'}), 400
    if not target:
        return jsonify({'error': 'target with url is required'}), 400

    relationship, rel_err = parse_bridge_relationship(
        data.get('relationship'), default_if_missing=True
    )
    if rel_err:
        return jsonify({'error': rel_err}), 400
    explanation = (data.get('explanation') or '').strip() or None

    bridge = Bridge(
        name=name,
        relationship=relationship,
        explanation=explanation,
        created_by=user['id'],
        **_content_to_bridge_fields('source', source),
        **_content_to_bridge_fields('target', target),
    )
    db.session.add(bridge)
    db.session.commit()

    return jsonify({'success': True, 'bridge': bridge.to_dict()}), 201


@bp.route('/<bridge_id>/', methods=['GET'])
def get_bridge(bridge_id):
    """Get a single bridge by id."""
    bridge = Bridge.query.get(bridge_id)
    if not bridge:
        abort(404)
    return jsonify(bridge.to_dict())


@bp.route('/<bridge_id>/', methods=['PATCH'])
@require_auth
def update_bridge(bridge_id):
    """Update a bridge. Creator only."""
    user, err = _require_user()
    if err:
        return err

    bridge = Bridge.query.get(bridge_id)
    if not bridge:
        abort(404)
    if bridge.created_by != user['id']:
        return jsonify({'error': 'Not authorized to update this bridge'}), 403

    data = request.get_json() or {}
    if 'name' in data:
        bridge.name = (data['name'] or '').strip() or bridge.name
    if 'relationship' in data:
        r, rel_err = parse_bridge_relationship(data['relationship'], default_if_missing=False)
        if rel_err:
            return jsonify({'error': rel_err}), 400
        bridge.relationship = r
    if 'explanation' in data:
        bridge.explanation = (data['explanation'] or '').strip() or None

    source = _content_from_json(data.get('source'))
    if source:
        for k, v in _content_to_bridge_fields('source', source).items():
            setattr(bridge, k, v)
    target = _content_from_json(data.get('target'))
    if target:
        for k, v in _content_to_bridge_fields('target', target).items():
            setattr(bridge, k, v)

    db.session.commit()
    return jsonify({'success': True, 'bridge': bridge.to_dict()})


@bp.route('/<bridge_id>/inscribe/', methods=['POST'])
@require_auth
def start_inscribe(bridge_id):
    """Start inscription flow for a bridge. Placeholder - returns not implemented."""
    user, err = _require_user()
    if err:
        return err

    bridge = Bridge.query.get(bridge_id)
    if not bridge:
        abort(404)
    if bridge.inscription_id:
        return jsonify({'error': 'Bridge already inscribed', 'inscription_id': bridge.inscription_id}), 400

    return jsonify({
        'error': 'Inscription flow not yet implemented',
        'message': 'Save & Inscribe will be wired to Unisat per UNISAT_INSCRIPTION_FEASIBILITY.md',
    }), 501


# ============================================================================
# Bridge Sessions (for extension)
# ============================================================================

@bp.route('/sessions/', methods=['GET'])
@require_auth
def list_sessions():
    """List active bridge sessions for current user (open, source_set, target_set)."""
    user, err = _require_user()
    if err:
        return err

    sessions = BridgeSession.query.filter_by(user_id=user['id']).filter(
        BridgeSession.status.in_(['open', 'source_set', 'target_set'])
    ).order_by(BridgeSession.created_at.desc()).limit(20).all()

    # Filter expired
    active = [s for s in sessions if not s.is_expired]
    return jsonify({
        'sessions': [s.to_dict() for s in active],
        'count': len(active),
    })


@bp.route('/sessions/', methods=['POST'])
@require_auth
def create_session():
    """Create a new bridge session (or return existing open one)."""
    user, err = _require_user()
    if err:
        return err

    # Reuse open session if exists
    existing = BridgeSession.query.filter_by(
        user_id=user['id'], status='open'
    ).filter(BridgeSession.expires_at > datetime.utcnow()).first()
    if existing:
        return jsonify({'success': True, 'session': existing.to_dict()}), 200

    session = BridgeSession.create_for_user(user['id'])
    db.session.add(session)
    db.session.commit()
    return jsonify({'success': True, 'session': session.to_dict()}), 201


@bp.route('/sessions/<session_id>/', methods=['GET'])
@require_auth
def get_session(session_id):
    """Get session with source/target content."""
    user, err = _require_user()
    if err:
        return err

    sess = BridgeSession.query.get(session_id)
    if not sess:
        abort(404)
    if sess.user_id != user['id']:
        return jsonify({'error': 'Not authorized'}), 403

    return jsonify(sess.to_dict())


@bp.route('/sessions/<session_id>/set-source', methods=['POST'])
@require_auth
def set_source(session_id):
    """Set source content from extension."""
    user, err = _require_user()
    if err:
        return err

    sess = BridgeSession.query.get(session_id)
    if not sess:
        abort(404)
    if sess.user_id != user['id']:
        return jsonify({'error': 'Not authorized'}), 403
    if sess.status not in ('open', 'source_set'):
        return jsonify({'error': 'Session already has source and target set'}), 400

    data = request.get_json() or {}
    content = _content_from_json(data)
    if not content:
        return jsonify({'error': 'source content with url is required'}), 400

    sess.source_content = content
    sess.status = 'source_set'
    sess.expires_at = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    return jsonify({'success': True, 'session': sess.to_dict()})


@bp.route('/sessions/<session_id>/set-target', methods=['POST'])
@require_auth
def set_target(session_id):
    """Set target content from extension."""
    user, err = _require_user()
    if err:
        return err

    sess = BridgeSession.query.get(session_id)
    if not sess:
        abort(404)
    if sess.user_id != user['id']:
        return jsonify({'error': 'Not authorized'}), 403
    if sess.status not in ('source_set', 'target_set'):
        return jsonify({'error': 'Set source first'}), 400

    data = request.get_json() or {}
    content = _content_from_json(data)
    if not content:
        return jsonify({'error': 'target content with url is required'}), 400

    sess.target_content = content
    sess.status = 'target_set'
    sess.expires_at = datetime.utcnow() + timedelta(hours=1)
    db.session.commit()

    return jsonify({'success': True, 'session': sess.to_dict()})
