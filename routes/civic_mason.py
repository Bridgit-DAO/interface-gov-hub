"""Civic Mason: global brick wall. Badge-gated placement."""
from datetime import datetime

from flask import Blueprint, jsonify, request

from extensions import db
from models import Brick, BrickMessage, User
from services.identity import get_current_user, require_auth
from services.events import emit_event
from services.civic_mason import user_has_civic_mason_eligibility, is_valid_placement

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
    """Check if current user can place bricks (has Civic Mason-eligible badge)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'eligible': False, 'reason': 'Authentication required'}), 401
    eligible = user_has_civic_mason_eligibility(current_user['id'])
    return jsonify({'eligible': eligible}), 200


@bp.route('/bricks/', methods=['POST'])
@require_auth
def place_brick():
    """Place a brick. Requires Civic Mason-eligible badge."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    user = User.query.get(current_user['id'])
    if not user_has_civic_mason_eligibility(user.id):
        return jsonify({'error': 'Earn a Civic Mason-eligible badge to place bricks'}), 403

    data = request.get_json() or {}
    grid_x = data.get('grid_x')
    grid_y = data.get('grid_y')
    message = (data.get('message') or '')[:200]
    artifact_id = data.get('artifact_id') or None
    badge_id = data.get('badge_id') or None

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
