"""Artifact collections API (constitution sets, etc.)."""
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request

from extensions import db
from models import (
    Layer, LayerMember, Artifact, ArtifactCollection, ArtifactCollectionItem,
)
from services.coordination import is_layer_admin
from services.identity import get_current_user, require_auth
from services.events import emit_event

bp = Blueprint('collections', __name__, url_prefix='/api')


def _layer_write_access(layer, user):
    if not user:
        return False
    if is_layer_admin(layer, user):
        return True
    return bool(
        LayerMember.query.filter_by(
            layer_id=layer.id, user_id=user['id'], status='active'
        ).first()
    )


@bp.route('/layers/<layer_id>/collections/', methods=['GET'])
def list_collections(layer_id):
    Layer.query.get_or_404(layer_id)
    rows = ArtifactCollection.query.filter_by(layer_id=layer_id).order_by(
        ArtifactCollection.created_at.desc()
    ).limit(200).all()
    return jsonify({'collections': [c.to_dict(include_items=True) for c in rows]}), 200


@bp.route('/layers/<layer_id>/collections/', methods=['POST'])
@require_auth
def create_collection(layer_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    layer = Layer.query.get_or_404(layer_id)
    if not _layer_write_access(layer, current_user):
        return jsonify({'error': 'Not a layer member'}), 403
    data = request.get_json() or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    col = ArtifactCollection(
        id=str(uuid4()),
        layer_id=layer_id,
        title=title[:255],
        description=(data.get('description') or '').strip() or None,
        creator_user_id=current_user['id'],
        created_at=datetime.utcnow(),
    )
    db.session.add(col)
    db.session.flush()
    emit_event(
        'artifact_collection_created',
        actor_type='user',
        actor_id=current_user['id'],
        subject_type='artifact_collection',
        subject_id=col.id,
        layer_id=layer_id,
        payload={'title': col.title},
    )
    db.session.commit()
    return jsonify({'success': True, 'collection': col.to_dict(include_items=False)}), 201


@bp.route('/collections/<collection_id>/', methods=['GET'])
def get_collection(collection_id):
    col = ArtifactCollection.query.get_or_404(collection_id)
    return jsonify({'collection': col.to_dict(include_items=True)}), 200


@bp.route('/collections/<collection_id>/artifacts/', methods=['POST'])
@require_auth
def add_artifact_to_collection(collection_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    col = ArtifactCollection.query.get_or_404(collection_id)
    layer = Layer.query.get(col.layer_id)
    if not layer or not _layer_write_access(layer, current_user):
        return jsonify({'error': 'Not a layer member'}), 403
    data = request.get_json() or {}
    artifact_id = data.get('artifact_id')
    if not artifact_id:
        return jsonify({'error': 'artifact_id required'}), 400
    art = Artifact.query.get_or_404(artifact_id)
    if art.layer_id != col.layer_id:
        return jsonify({'error': 'artifact must belong to the same layer as the collection'}), 400
    existing = ArtifactCollectionItem.query.filter_by(
        collection_id=collection_id, artifact_id=artifact_id
    ).first()
    if existing:
        return jsonify({'success': True, 'item_id': existing.id, 'duplicate': True}), 200
    item = ArtifactCollectionItem(
        id=str(uuid4()),
        collection_id=collection_id,
        artifact_id=artifact_id,
        created_at=datetime.utcnow(),
    )
    db.session.add(item)
    emit_event(
        'artifact_collection_item_added',
        actor_type='user',
        actor_id=current_user['id'],
        subject_type='artifact_collection',
        subject_id=col.id,
        layer_id=col.layer_id,
        payload={'artifact_id': artifact_id},
    )
    db.session.commit()
    return jsonify({'success': True, 'item_id': item.id}), 201
