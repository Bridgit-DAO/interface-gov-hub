"""API: layer organizational connections (types + submissions)."""
from flask import Blueprint, jsonify, request, abort

from extensions import db
from models import LayerConnection, LayerConnectionType
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.layer_connections import (
    resolve_layer,
    list_connection_types,
    create_connection_type,
    update_connection_type,
    submit_connection,
    review_connection,
    withdraw_connection,
    revoke_connection,
    enrich_connection,
)

bp = Blueprint('layer_connections', __name__, url_prefix='/api/layers')


def _layer_or_404(layer_ref):
    layer = resolve_layer(layer_ref)
    if not layer:
        abort(404)
    return layer


def _require_layer_admin(layer, user):
    if not user or not is_layer_admin(layer, user):
        abort(403)


@bp.route('/<layer_ref>/connection-types/', methods=['GET'])
def api_list_connection_types(layer_ref):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    admin = bool(user and is_layer_admin(layer, user))
    rows = list_connection_types(layer.id, active_only=not admin)
    return jsonify({'connection_types': [r.to_dict() for r in rows], 'count': len(rows)})


@bp.route('/<layer_ref>/connection-types/', methods=['POST'])
@require_auth
def api_create_connection_type(layer_ref):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    _require_layer_admin(layer, user)
    data = request.get_json(silent=True) or {}
    try:
        row = create_connection_type(layer, user, data)
        db.session.commit()
        return jsonify({'success': True, 'connection_type': row.to_dict()}), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/<layer_ref>/connection-types/<type_id>/', methods=['PATCH'])
@require_auth
def api_update_connection_type(layer_ref, type_id):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    _require_layer_admin(layer, user)
    row = LayerConnectionType.query.filter_by(id=type_id, layer_id=layer.id).first()
    if not row:
        abort(404)
    data = request.get_json(silent=True) or {}
    update_connection_type(row, data)
    db.session.commit()
    return jsonify({'success': True, 'connection_type': row.to_dict()})


@bp.route('/<layer_ref>/connections/', methods=['GET'])
def api_list_connections(layer_ref):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    admin = bool(user and is_layer_admin(layer, user))
    status = (request.args.get('status') or '').strip().lower()
    q = LayerConnection.query.filter_by(layer_id=layer.id)
    if admin and status:
        q = q.filter_by(status=status)
    elif admin:
        pass
    else:
        q = q.filter_by(status='active')
    rows = q.order_by(LayerConnection.created_at.desc()).all()
    return jsonify({
        'connections': [enrich_connection(r, include_admin=admin) for r in rows],
        'count': len(rows),
    })


@bp.route('/<layer_ref>/connections/', methods=['POST'])
@require_auth
def api_submit_connection(layer_ref):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    try:
        conn = submit_connection(layer, user, data)
        db.session.commit()
        return jsonify({'success': True, 'connection': enrich_connection(conn, include_admin=True)}), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/<layer_ref>/connections/<conn_id>/approve/', methods=['POST'])
@require_auth
def api_approve_connection(layer_ref, conn_id):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    _require_layer_admin(layer, user)
    conn = LayerConnection.query.filter_by(id=conn_id, layer_id=layer.id).first()
    if not conn:
        abort(404)
    data = request.get_json(silent=True) or {}
    try:
        review_connection(conn, user, approve=True, notes=data.get('notes'))
        db.session.commit()
        return jsonify({'success': True, 'connection': enrich_connection(conn, include_admin=True)})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/<layer_ref>/connections/<conn_id>/reject/', methods=['POST'])
@require_auth
def api_reject_connection(layer_ref, conn_id):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    _require_layer_admin(layer, user)
    conn = LayerConnection.query.filter_by(id=conn_id, layer_id=layer.id).first()
    if not conn:
        abort(404)
    data = request.get_json(silent=True) or {}
    try:
        review_connection(
            conn,
            user,
            approve=False,
            notes=data.get('notes'),
            rejected_reason=data.get('rejected_reason'),
        )
        db.session.commit()
        return jsonify({'success': True, 'connection': enrich_connection(conn, include_admin=True)})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400


@bp.route('/<layer_ref>/connections/<conn_id>/withdraw/', methods=['POST'])
@require_auth
def api_withdraw_connection(layer_ref, conn_id):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    conn = LayerConnection.query.filter_by(id=conn_id, layer_id=layer.id).first()
    if not conn:
        abort(404)
    try:
        withdraw_connection(conn, user)
        db.session.commit()
        return jsonify({'success': True, 'connection': enrich_connection(conn, include_admin=True)})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 403


@bp.route('/<layer_ref>/connections/<conn_id>/revoke/', methods=['POST'])
@require_auth
def api_revoke_connection(layer_ref, conn_id):
    layer = _layer_or_404(layer_ref)
    user = get_current_user()
    _require_layer_admin(layer, user)
    conn = LayerConnection.query.filter_by(id=conn_id, layer_id=layer.id).first()
    if not conn:
        abort(404)
    data = request.get_json(silent=True) or {}
    try:
        revoke_connection(conn, user, reason=data.get('reason'))
        db.session.commit()
        return jsonify({'success': True, 'connection': enrich_connection(conn, include_admin=True)})
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
