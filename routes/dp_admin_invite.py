"""DP site admin invite-by-email (workgroup-agnostic research + draft + send)."""
from flask import Blueprint, jsonify, request

from services.api_auth import get_api_user, require_api_auth
from services.invite_research_pathways import (
    build_pathway_context_bundle,
    pathway_name_search,
    pathway_url_authors,
    pathway_zoho_mail_contacts,
)
from services.workgroup_authority import is_dp_site_admin
from services.workgroup_invite_ai import (
    draft_admin_invitation_email,
    research_admin_invite_contact,
    send_admin_invitation_email,
)

bp = Blueprint('dp_admin_invite', __name__)


def _require_dp_admin():
    current_user = get_api_user()
    if not current_user:
        return None, jsonify({'error': 'Authentication required'}), 401
    if not is_dp_site_admin(current_user):
        return None, jsonify({'error': 'DP site admin required'}), 403
    return current_user, None, None


@bp.route('/api/admin/dp-invite/pathways/zoho/', methods=['POST'])
@require_api_auth
def admin_dp_invite_pathway_zoho():
    _user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload, status = pathway_zoho_mail_contacts()
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/pathways/search/', methods=['POST'])
@require_api_auth
def admin_dp_invite_pathway_search():
    _user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    payload, status = pathway_name_search(
        name=(data.get('name') or '').strip(),
        context=(data.get('context') or '').strip(),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/pathways/url/', methods=['POST'])
@require_api_auth
def admin_dp_invite_pathway_url():
    _user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    payload, status = pathway_url_authors(url=(data.get('url') or '').strip())
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/pathways/apply/', methods=['POST'])
@require_api_auth
def admin_dp_invite_pathway_apply():
    _user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    bundle = build_pathway_context_bundle(
        zoho_contact=data.get('zoho_contact'),
        search_results=data.get('search_results') or [],
        url_author=data.get('url_author'),
        page_summary=(data.get('page_summary') or '').strip(),
    )
    return jsonify({'success': True, **bundle}), 200


@bp.route('/api/admin/dp-invite/research/', methods=['POST'])
@require_api_auth
def admin_dp_invite_research():
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json(silent=True) or {}
    payload, status = research_admin_invite_contact(
        inviter=current_user,
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        linkedin_url=(data.get('linkedin_url') or data.get('linkedin') or '').strip(),
        previous_interaction=(data.get('previous_interaction') or '').strip(),
        extra_links=data.get('extra_links') or [],
        selected_candidate_index=data.get('selected_candidate_index'),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/draft/', methods=['POST'])
@require_api_auth
def admin_dp_invite_draft():
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json(silent=True) or {}
    payload, status = draft_admin_invitation_email(
        primary_workgroup_id=(data.get('primary_workgroup_id') or '').strip(),
        inviter=current_user,
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        tone=(data.get('tone') or 'warm').strip(),
        length=(data.get('length') or 'medium').strip(),
        previous_interaction=(data.get('previous_interaction') or '').strip(),
        extra_guidance=(data.get('extra_guidance') or '').strip(),
        resolved_person=data.get('resolved_person'),
        additional_workgroup_ids=data.get('additional_workgroup_ids') or [],
        prior_invitations=data.get('prior_invitations'),
        invite_content=data.get('invite_content'),
        regenerate=bool(data.get('regenerate')),
        previous_draft=(data.get('previous_draft') or '').strip(),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/send/', methods=['POST'])
@require_api_auth
def admin_dp_invite_send():
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json(silent=True) or {}
    payload, status = send_admin_invitation_email(
        primary_workgroup_id=(data.get('primary_workgroup_id') or '').strip(),
        inviter_id=current_user['id'],
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        body=(data.get('body') or data.get('draft') or '').strip(),
        additional_workgroup_ids=data.get('additional_workgroup_ids') or [],
        send_mode=(data.get('send_mode') or 'platform').strip(),
    )
    return jsonify(payload), status
