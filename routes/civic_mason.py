"""Civic Mason: global brick wall. Badge-gated placement."""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session

from extensions import db
from models import Brick, BrickMessage, User
from services.identity import get_current_user, require_auth
from services.events import emit_event
from services.civic_mason import (
    CIVIC_MASON_SESSION_DEMO,
    civic_mason_can_place_brick,
    civic_mason_eligibility_payload,
    is_valid_placement,
)

bp = Blueprint('civic_mason', __name__, url_prefix='/api/civic-mason')


@bp.route('/bricks/', methods=['GET'])
def list_bricks():
    """List all bricks on the global Civic Mason wall."""
    bricks = Brick.query.order_by(Brick.grid_y.asc(), Brick.grid_x.asc()).all()
    brick_list = []
    for b in bricks:
        d = b.to_dict()
        if b.user:
            d['user_display_name'] = b.user.displayName or b.user.username or b.user.name or 'Anonymous'
        else:
            d['user_display_name'] = 'Unknown'
        brick_list.append(d)
    return jsonify({'bricks': brick_list}), 200


@bp.route('/eligible/', methods=['GET'])
@require_auth
def check_eligible():
    """Check if current user can place bricks (badge + one per year; dev demo mode optional)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'eligible': False, 'reason': 'authentication_required'}), 401
    is_dev = bool(current_app.config.get('IS_DEVELOPMENT'))
    payload = civic_mason_eligibility_payload(current_user['id'], session, is_dev)
    return jsonify(payload), 200


@bp.route('/demo-mode/', methods=['POST'])
@require_auth
def set_civic_mason_demo_mode():
    """Dev only: toggle session flag for unlimited Civic Mason placements (no badge / no yearly cap)."""
    if not current_app.config.get('IS_DEVELOPMENT'):
        return jsonify({'error': 'Not available'}), 404
    data = request.get_json() or {}
    enabled = bool(data.get('enabled'))
    session[CIVIC_MASON_SESSION_DEMO] = enabled
    session.modified = True
    return jsonify({'demo_mode': enabled}), 200


@bp.route('/bricks/', methods=['POST'])
@require_auth
def place_brick():
    """Place a brick. Requires Civic Mason-eligible badge."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user['id'])
    is_dev = bool(current_app.config.get('IS_DEVELOPMENT'))
    ok, err_msg = civic_mason_can_place_brick(user.id, session, is_dev)
    if not ok:
        return jsonify({'error': err_msg}), 403

    data = request.get_json() or {}
    grid_x = data.get('grid_x')
    grid_y = data.get('grid_y')
    message = (data.get('message') or '')[:200]
    artifact_id = data.get('artifact_id') or None
    badge_id = data.get('badge_id') or None
    color_index = data.get('color_index')

    if grid_x is None or grid_y is None:
        return jsonify({'error': 'grid_x and grid_y required'}), 400

    try:
        grid_x = float(grid_x)
        grid_y = float(grid_y)
    except (TypeError, ValueError):
        return jsonify({'error': 'grid_x and grid_y must be numbers'}), 400

    existing_bricks = Brick.query.all()
    valid, err = is_valid_placement(grid_x, grid_y, existing_bricks)
    if not valid:
        return jsonify({'error': err}), 400

    if color_index is not None and 0 <= int(color_index) < 8:
        year = 2031 + int(color_index)
    else:
        year = datetime.utcnow().year
    brick = Brick(
        user_id=user.id,
        grid_x=grid_x,
        grid_y=grid_y,
        artifact_id=artifact_id,
        badge_id=badge_id,
        year=year,
    )
    db.session.add(brick)
    db.session.flush()

    if message:
        msg = BrickMessage(brick_id=brick.id, user_id=user.id, message=message)
        db.session.add(msg)

    emit_event('brick_placed', actor_type='user', actor_id=user.id,
               subject_type='brick', subject_id=brick.id,
               layer_id=None, payload={'grid_x': grid_x, 'grid_y': grid_y})
    db.session.commit()

    d = brick.to_dict()
    d['user_display_name'] = user.displayName or user.username or user.name or 'Anonymous'
    return jsonify({'brick': d}), 201


@bp.route('/bricks/<brick_id>', methods=['DELETE'])
@require_auth
def delete_brick(brick_id):
    """Delete a brick (owner only, used during 5-second edit window)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    brick = Brick.query.get_or_404(brick_id)
    if brick.user_id != current_user['id']:
        return jsonify({'error': 'Only the brick owner can remove it'}), 403

    db.session.delete(brick)
    db.session.commit()
    return jsonify({'success': True}), 200


@bp.route('/bricks/<brick_id>', methods=['PATCH'])
@require_auth
def update_brick(brick_id):
    """Update color / message of a brick (owner only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    brick = Brick.query.get_or_404(brick_id)
    if brick.user_id != current_user['id']:
        return jsonify({'error': 'Only the brick owner can update it'}), 403

    data = request.get_json() or {}
    color_index = data.get('color_index')
    message = (data.get('message') or '')[:200]

    if color_index is not None:
        try:
            ci = int(color_index)
            if 0 <= ci < 8:
                brick.year = 2031 + ci
        except (TypeError, ValueError):
            pass

    if 'message' in data and message:
        msg = BrickMessage(brick_id=brick.id, user_id=current_user['id'], message=message)
        db.session.add(msg)

    db.session.commit()
    d = brick.to_dict()
    if brick.user:
        d['user_display_name'] = brick.user.displayName or brick.user.username or brick.user.name or 'Anonymous'
    else:
        d['user_display_name'] = 'Unknown'
    return jsonify({'brick': d}), 200


@bp.route('/bricks/<brick_id>/messages/', methods=['POST'])
@require_auth
def add_brick_message(brick_id):
    """Append a message to a brick (append-only history)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    brick = Brick.query.get_or_404(brick_id)
    if brick.user_id != current_user['id']:
        return jsonify({'error': 'Only the brick owner can add messages'}), 403

    data = request.get_json() or {}
    message = (data.get('message') or '')[:200]
    if not message:
        return jsonify({'error': 'message required'}), 400

    msg = BrickMessage(brick_id=brick.id, user_id=current_user['id'], message=message)
    db.session.add(msg)
    db.session.commit()

    return jsonify({'message': {'id': msg.id, 'message': msg.message, 'created_at': msg.created_at.isoformat()}}), 201
