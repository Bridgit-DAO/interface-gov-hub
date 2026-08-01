"""Canopi server-to-server internal routes (workgroup membership, etc.)."""
from __future__ import annotations

import os
import secrets
import hmac
import hashlib

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from extensions import db
from models import User, Workgroup

bp = Blueprint('canopi_internal', __name__)


def _canopi_internal_allowed() -> bool:
    secret = (os.environ.get('GOV_HUB_API_KEY') or '').strip()
    if not secret:
        return False
    header = request.headers.get('Authorization', '').strip()
    if not header.lower().startswith('bearer '):
        return False
    supplied = header[7:].strip()
    try:
        return bool(supplied) and secrets.compare_digest(
            supplied.encode('utf-8'),
            secret.encode('utf-8'),
        )
    except UnicodeEncodeError:
        return False


def _canopi_signature_valid() -> bool:
    secret = (os.environ.get('CANOPI_SIGNING_SECRET') or '').encode('utf-8')
    signature = (request.headers.get('X-Canopi-Signature') or '').strip().lower()
    if not secret or not signature:
        return False
    digest = hmac.new(secret, request.get_data(cache=True), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, digest)


def _normalize_email(raw: str | None) -> str:
    return (raw or '').strip().lower()


def _resolve_workgroup(workgroup_ref: str | None):
    ref = (workgroup_ref or '').strip()
    if not ref:
        return None
    wg = Workgroup.query.get(ref)
    if wg:
        return wg
    return Workgroup.query.filter(
        (Workgroup.slug == ref) | (Workgroup.acronym == ref)
    ).first()


@bp.route('/api/internal/canopi/workgroup-membership', methods=['GET'])
def workgroup_membership():
    """
    Check whether an email belongs to a GovHub workgroup.

    Auth: GOV_HUB_API_KEY via Authorization: Bearer.
    Query: workgroup_id (uuid, slug, or acronym), email
    """
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    workgroup_ref = request.args.get('workgroup_id') or request.args.get('workgroupId')
    email = _normalize_email(request.args.get('email'))
    if not workgroup_ref or not email:
        return jsonify({'error': 'workgroup_id and email are required'}), 400

    workgroup = _resolve_workgroup(workgroup_ref)
    if not workgroup or not workgroup.acronym:
        return jsonify({'isMember': False, 'reason': 'workgroup_not_found'})

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return jsonify({'isMember': False, 'reason': 'user_not_found'})

    row = db.session.execute(
        text(
            """
            SELECT id FROM working_group_member
            WHERE group_acronym = :acronym AND user_id = :user_id
            LIMIT 1
            """
        ),
        {'acronym': workgroup.acronym, 'user_id': user.id},
    ).fetchone()

    return jsonify({
        'isMember': bool(row),
        'workgroupId': workgroup.id,
        'workgroupAcronym': workgroup.acronym,
        'email': email,
    })


@bp.route('/api/internal/canopi/layer-admin', methods=['GET'])
def layer_admin_check():
    """
    Check whether an email is a Gov Hub layer admin (owner or assigned admin).

    Auth: GOV_HUB_API_KEY via Authorization: Bearer.
    Query: layer_id, email
    """
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    from models import Layer, LayerAdmin

    layer_ref = request.args.get('layer_id') or request.args.get('layerId')
    email = _normalize_email(request.args.get('email'))
    if not layer_ref or not email:
        return jsonify({'error': 'layer_id and email are required'}), 400

    layer = Layer.query.get(layer_ref)
    if not layer:
        layer = Layer.query.filter(
            (Layer.slug == layer_ref) | (Layer.name == layer_ref)
        ).first()
    if not layer:
        return jsonify({'isAdmin': False, 'reason': 'layer_not_found'})

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return jsonify({'isAdmin': False, 'reason': 'user_not_found'})

    is_admin = False
    if getattr(layer, 'initiator_id', None) == user.id:
        is_admin = True
    elif LayerAdmin.query.filter_by(layer_id=layer.id, user_id=user.id).first():
        is_admin = True
    elif getattr(user, 'role', None) == 'admin':
        is_admin = True

    return jsonify({
        'isAdmin': is_admin,
        'layerId': layer.id,
        'email': email,
    })


@bp.route('/api/internal/canopi/contributions', methods=['POST'])
def canopi_contribution_intake():
    """
    Ingest Canopi smart-tag patch or comment into Gov Hub + scout queue.

    Auth: GOV_HUB_API_KEY via Authorization: Bearer.

    Body:
      kind: patch | comment
      draft_ref: ML number or draft slug
      external_id: Canopi message UUID (idempotent key)
      author_email | author_user_id
      canopi_overlay_id: optional
      payload: patch or comment fields
    """
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401
    if not _canopi_signature_valid():
        return jsonify({
            'error': 'Signed Canopi assertion required',
            'error_code': 'CANOPI_SIGNATURE_REQUIRED',
        }), 503

    from services.canopi_contributions import intake_canopi_contribution

    body = request.get_json(silent=True) or {}
    resp, status = intake_canopi_contribution(body)
    return jsonify(resp), status


@bp.route('/api/internal/contribution-pipeline/pending', methods=['GET'])
def contribution_pipeline_pending():
    """Unprocessed scout queue rows. Auth: GOV_HUB_API_KEY."""
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    from services.contribution_pipeline import list_pending_pipeline_events

    limit = request.args.get('limit', 100, type=int)
    events = list_pending_pipeline_events(limit=limit)
    return jsonify({'events': events, 'count': len(events)})


@bp.route('/api/internal/contribution-pipeline/claim', methods=['POST'])
def contribution_pipeline_claim():
    """Claim pending rows for a Scout worker (lease). Auth: GOV_HUB_API_KEY."""
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    from services.contribution_pipeline import claim_pending_pipeline_events

    body = request.get_json(silent=True) or {}
    limit = body.get('limit', 100)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 100
    claimant = (body.get('claimant') or body.get('claimed_by') or 'scout').strip()
    events = claim_pending_pipeline_events(claimant=claimant, limit=limit)
    db.session.commit()
    return jsonify({'events': events, 'count': len(events), 'claimant': claimant})


@bp.route('/api/internal/contribution-pipeline/mark-processed', methods=['POST'])
def contribution_pipeline_mark_processed():
    """Mark scout queue rows processed. Auth: GOV_HUB_API_KEY."""
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    from services.contribution_pipeline import mark_pipeline_events_processed

    body = request.get_json(silent=True) or {}
    ids = body.get('ids') or body.get('event_ids') or []
    if not isinstance(ids, list):
        return jsonify({'error': 'ids must be an array'}), 400
    claimant = (body.get('claimant') or body.get('claimed_by') or '').strip()
    if not claimant:
        return jsonify({'error': 'claimant required'}), 400
    try:
        updated = mark_pipeline_events_processed(
            [str(i) for i in ids if i],
            claimant=claimant,
        )
    except ValueError as err:
        return jsonify({'error': str(err)}), 400
    db.session.commit()
    return jsonify({'updated': updated})

