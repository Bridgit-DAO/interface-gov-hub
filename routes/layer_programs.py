"""Layer program API: initiatives on a layer (DP Challenge, future cohorts)."""
from flask import Blueprint, jsonify, request

from extensions import db
from models import Layer
from services.identity import get_current_user, require_auth
from services.layer_programs import (
    create_program,
    get_program,
    join_program_notify_list,
    launch_program,
    list_programs_for_layer,
    notify_config_for_program,
    program_public_view,
    resolve_program_for_hub,
    set_program_submissions,
    update_program,
)

bp = Blueprint('layer_programs', __name__)


@bp.route('/api/layers/<layer_id>/programs/', methods=['GET'])
def list_layer_programs(layer_id):
    Layer.query.get_or_404(layer_id)
    programs = list_programs_for_layer(layer_id)
    user = get_current_user()
    return jsonify({
        'programs': [program_public_view(p, user) for p in programs],
        'count': len(programs),
    }), 200


@bp.route('/api/layers/<layer_id>/programs/', methods=['POST'])
@require_auth
def create_layer_program(layer_id):
    layer = Layer.query.get_or_404(layer_id)
    user = get_current_user()
    program, err, status = create_program(layer, user, request.get_json() or {})
    if err:
        return jsonify({'error': err}), status
    return jsonify({'program': program_public_view(program, get_current_user())}), status


@bp.route('/api/layers/<layer_id>/programs/<program_id>/', methods=['GET'])
def get_layer_program(layer_id, program_id):
    Layer.query.get_or_404(layer_id)
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    return jsonify({'program': program_public_view(program)}), 200


@bp.route('/api/layers/<layer_id>/programs/<program_id>/notify-config/', methods=['GET'])
def get_program_notify_config(layer_id, program_id):
    Layer.query.get_or_404(layer_id)
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    user = get_current_user()
    return jsonify(notify_config_for_program(program, user)), 200


@bp.route('/api/layers/<layer_id>/programs/<program_id>/notify/', methods=['POST'])
@require_auth
def post_program_notify(layer_id, program_id):
    Layer.query.get_or_404(layer_id)
    user = get_current_user()
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    data = request.get_json() or {}
    body, err, status = join_program_notify_list(
        program,
        user,
        dp_interests=data.get('dp_interests') or data.get('submission_ids'),
        source=data.get('source') or 'dp-challenge-notify',
        source_url=data.get('source_url') or request.referrer,
    )
    if err:
        return jsonify({'error': err}), status
    return jsonify(body), status


@bp.route('/api/programs/notify-config/', methods=['GET'])
def resolve_program_notify_config():
    hub_path = (request.args.get('hub_path') or request.args.get('path') or '').strip()
    program_slug = (request.args.get('program') or request.args.get('slug') or '').strip() or None
    layer_slug = (request.args.get('layer') or request.args.get('layer_slug') or '').strip() or None
    if not hub_path:
        return jsonify({'error': 'hub_path required'}), 400
    program = resolve_program_for_hub(hub_path, program_slug=program_slug, layer_slug=layer_slug)
    if not program:
        return jsonify({'error': 'Program not found'}), 404
    user = get_current_user()
    return jsonify(notify_config_for_program(program, user)), 200


@bp.route('/api/layers/<layer_id>/programs/<program_id>/', methods=['PATCH'])
@require_auth
def patch_layer_program(layer_id, program_id):
    layer = Layer.query.get_or_404(layer_id)
    user = get_current_user()
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    program, err, status = update_program(program, layer, user, request.get_json() or {})
    if err:
        return jsonify({'error': err}), status
    return jsonify({'program': program_public_view(program, get_current_user())}), status


@bp.route('/api/layers/<layer_id>/programs/<program_id>/submissions/', methods=['PUT'])
@require_auth
def put_layer_program_submissions(layer_id, program_id):
    layer = Layer.query.get_or_404(layer_id)
    user = get_current_user()
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    data = request.get_json() or {}
    ids = data.get('submission_ids') or []
    if not isinstance(ids, list):
        return jsonify({'error': 'submission_ids must be a list'}), 400
    program, err, status = set_program_submissions(program, layer, user, ids)
    if err:
        return jsonify({'error': err}), status
    return jsonify({'program': program_public_view(program, get_current_user())}), status


@bp.route('/api/layers/<layer_id>/programs/<program_id>/launch/', methods=['POST'])
@require_auth
def post_layer_program_launch(layer_id, program_id):
    layer = Layer.query.get_or_404(layer_id)
    user = get_current_user()
    program = get_program(program_id)
    if not program or program.layer_id != layer_id:
        return jsonify({'error': 'Program not found'}), 404
    data = request.get_json() or {}
    body, err, status = launch_program(
        program,
        layer,
        user,
        promote_waitlist=bool(data.get('promote_waitlist')),
        join_policy_after=(data.get('join_policy_after') or None),
    )
    if err:
        return jsonify({'error': err}), status
    return jsonify(body), status


@bp.route('/api/programs/resolve/', methods=['GET'])
def resolve_program():
    hub_path = (request.args.get('hub_path') or request.args.get('path') or '').strip()
    program_slug = (request.args.get('program') or request.args.get('slug') or '').strip() or None
    layer_slug = (request.args.get('layer') or request.args.get('layer_slug') or '').strip() or None
    if not hub_path and not (program_slug and layer_slug):
        return jsonify({'error': 'hub_path or layer+program required'}), 400
    program = resolve_program_for_hub(
        hub_path,
        program_slug=program_slug,
        layer_slug=layer_slug,
    )
    if not program:
        return jsonify({'program': None}), 404
    return jsonify({'program': program_public_view(program)}), 200
