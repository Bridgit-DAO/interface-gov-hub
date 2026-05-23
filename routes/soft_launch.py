"""JSON fixtures for soft-launch UI (replace with real APIs when wiring)."""
from flask import Blueprint, jsonify

from fixtures.soft_launch import full_fixtures_payload

bp = Blueprint('soft_launch_api', __name__, url_prefix='/api/soft-launch')


@bp.route('/fixtures/', methods=['GET'], strict_slashes=False)
def get_fixtures():
    """Full static payload for homepage, onboarding copy, lifecycle, demo artifacts."""
    return jsonify(full_fixtures_payload())


@bp.route('/lifecycle/', methods=['GET'], strict_slashes=False)
def get_lifecycle():
    """Ordered stages for steppers and tooltips."""
    from fixtures.soft_launch import lifecycle_steps_for_json

    return jsonify({'stages': lifecycle_steps_for_json()})
