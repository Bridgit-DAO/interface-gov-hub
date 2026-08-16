"""DP site admin invite-by-email (workgroup-agnostic research + draft + send)."""
from pathlib import Path

from flask import Blueprint, jsonify, request

from services.api_auth import get_api_user, require_api_auth
from services.dp_admin_invite_store import (
    get_selected_invite_contacts,
    hide_invite_contact,
    list_admin_invite_sends,
    list_hidden_invite_contacts,
    patch_selected_invite_emails,
    record_admin_invite_send,
    resolve_agent_drop_file,
    send_history_by_recipient,
    set_selected_invite_emails,
    unhide_invite_contact,
)
from services.invite_research_pathways import (
    build_pathway_context_bundle,
    pathway_name_search,
    pathway_url_authors,
    pathway_zoho_mail_contacts,
)
from services.workgroup_authority import is_dp_site_admin
from services.invite_long_gap_dispatch import (
    classify_long_gap_dispatch,
    get_draft_long_gap_dispatch_job_status,
    get_long_gap_dispatch_review,
    get_long_gap_dispatch_template,
    get_send_all_long_gap_dispatch_job_status,
    patch_long_gap_dispatch_review,
    send_long_gap_dispatch_email,
    start_draft_long_gap_dispatch_job,
    start_send_all_long_gap_dispatch_job,
    start_retry_failed_long_gap_dispatch_job,
)
from services.workgroup_invite_ai import (
    draft_admin_invitation_email,
    research_admin_invite_contact,
    send_admin_invitation_email,
)
from services.zoho_mail import admin_contacts_snapshot_path, normalize_admin_email
from services.zoho_mail_ingest import build_snapshot

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
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    show_hidden = bool(data.get('show_hidden'))
    payload, status = pathway_zoho_mail_contacts(
        admin_email=normalize_admin_email(current_user.get('email') or ''),
        admin=current_user,
        show_hidden=show_hidden,
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/contacts/hide/', methods=['POST'])
@require_api_auth
def admin_dp_invite_hide_contact():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    recipient_email = (data.get('recipient_email') or data.get('email') or '').strip()
    if not recipient_email:
        return jsonify({'error': 'recipient_email is required'}), 400
    try:
        row = hide_invite_contact(
            current_user,
            recipient_email=recipient_email,
            note=(data.get('note') or '').strip(),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'success': True, 'hidden': row}), 200


@bp.route('/api/admin/dp-invite/contacts/unhide/', methods=['POST'])
@require_api_auth
def admin_dp_invite_unhide_contact():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    recipient_email = (data.get('recipient_email') or data.get('email') or '').strip()
    if not recipient_email:
        return jsonify({'error': 'recipient_email is required'}), 400
    try:
        removed = unhide_invite_contact(current_user, recipient_email=recipient_email)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'success': True, 'removed': removed}), 200


@bp.route('/api/admin/dp-invite/contacts/hidden/', methods=['GET'])
@require_api_auth
def admin_dp_invite_hidden_contacts():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    rows = list_hidden_invite_contacts(current_user)
    return jsonify({'success': True, 'hidden': rows}), 200


@bp.route('/api/admin/dp-invite/contacts/selection/', methods=['GET'])
@require_api_auth
def admin_dp_invite_get_selection():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload = get_selected_invite_contacts(current_user)
    return jsonify({'success': True, **payload}), 200


@bp.route('/api/admin/dp-invite/contacts/selection/', methods=['POST'])
@require_api_auth
def admin_dp_invite_set_selection():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    emails = data.get('emails') or data.get('recipient_emails') or []
    if not isinstance(emails, list):
        return jsonify({'error': 'emails must be an array'}), 400
    payload = set_selected_invite_emails(current_user, emails)
    return jsonify({'success': True, **payload}), 200


@bp.route('/api/admin/dp-invite/contacts/selection/', methods=['PATCH'])
@require_api_auth
def admin_dp_invite_patch_selection():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    add = data.get('add') or data.get('add_emails') or []
    remove = data.get('remove') or data.get('remove_emails') or []
    if data.get('email') or data.get('recipient_email'):
        email = (data.get('email') or data.get('recipient_email') or '').strip()
        action = (data.get('action') or '').strip().lower()
        if action == 'add':
            add = [email, *add]
        elif action == 'remove':
            remove = [email, *remove]
        else:
            return jsonify({'error': 'action must be add or remove when email is provided'}), 400
    if not isinstance(add, list) or not isinstance(remove, list):
        return jsonify({'error': 'add and remove must be arrays'}), 400
    payload = patch_selected_invite_emails(current_user, add=add, remove=remove)
    return jsonify({'success': True, **payload}), 200


@bp.route('/api/admin/dp-invite/ingest-zoho/', methods=['POST'])
@require_api_auth
def admin_dp_invite_ingest_zoho():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code

    data = request.get_json(silent=True) or {}
    agent_drop_name = (data.get('agent_drop_name') or data.get('filename') or '').strip()
    if not agent_drop_name:
        return jsonify({'error': 'agent_drop_name is required'}), 400

    owner_email = normalize_admin_email(current_user.get('email') or '')
    output_path = Path(admin_contacts_snapshot_path(owner_email))

    try:
        input_path = resolve_agent_drop_file(agent_drop_name)
    except FileNotFoundError:
        return jsonify({'error': f'Agent drop file not found: {agent_drop_name}'}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    if input_path.suffix.lower() not in {'.zip', '.eml'} and not input_path.is_dir():
        return jsonify({'error': 'Agent drop file must be a .zip archive, .eml file, or directory'}), 400

    try:
        payload = build_snapshot(
            input_path=input_path,
            owner_email=owner_email,
            output_path=output_path,
        )
    except Exception as exc:  # noqa: BLE001 - surface ingest errors to admin UI
        return jsonify({'error': f'Ingest failed: {exc}'[:300]}), 502

    return jsonify({
        'success': True,
        'owner_email': owner_email,
        'snapshot_path': str(output_path),
        'agent_drop_name': input_path.name,
        'agent_drop_dir': str(input_path.parent),
        'message_count': payload.get('message_count') or 0,
        'contact_count': len(payload.get('contacts') or []),
        'exported_at': payload.get('exported_at') or '',
    }), 200


@bp.route('/api/admin/dp-invite/send-records/', methods=['GET'])
@require_api_auth
def admin_dp_invite_send_records():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code

    recipient_email = (request.args.get('recipient_email') or '').strip()
    try:
        limit = int(request.args.get('limit') or 50)
    except ValueError:
        limit = 50

    rows = list_admin_invite_sends(
        current_user,
        limit=limit,
        recipient_email=recipient_email or None,
    )
    return jsonify({'success': True, 'records': rows}), 200


@bp.route('/api/admin/dp-invite/batch/history/', methods=['POST'])
@require_api_auth
def admin_dp_invite_batch_history():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code

    data = request.get_json(silent=True) or {}
    emails = data.get('recipient_emails') or []
    if not isinstance(emails, list):
        return jsonify({'error': 'recipient_emails must be an array'}), 400

    grouped = send_history_by_recipient(current_user, emails)
    return jsonify({'success': True, 'history_by_email': grouped}), 200


@bp.route('/api/admin/dp-invite/batch/record/', methods=['POST'])
@require_api_auth
def admin_dp_invite_batch_record():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code

    data = request.get_json(silent=True) or {}
    status = (data.get('status') or '').strip().lower()
    if status not in {'skipped', 'draft'}:
        return jsonify({'error': 'status must be skipped or draft'}), 400

    recipient_email = (data.get('recipient_email') or data.get('email') or '').strip()
    if not recipient_email:
        return jsonify({'error': 'recipient_email is required'}), 400

    wg_ids = data.get('workgroup_ids') or []
    if data.get('primary_workgroup_id'):
        wg_ids = [data.get('primary_workgroup_id'), *wg_ids]
    deduped = []
    for wg_id in wg_ids:
        clean = (wg_id or '').strip()
        if clean and clean not in deduped:
            deduped.append(clean)

    try:
        row = record_admin_invite_send(
            admin=current_user,
            recipient_email=recipient_email,
            recipient_name=(data.get('recipient_name') or data.get('name') or '').strip(),
            workgroup_ids=deduped,
            body=(data.get('body') or data.get('draft') or '').strip(),
            status=status,
            source=(data.get('source') or 'zoho_batch').strip() or 'zoho_batch',
            message_strategy=(data.get('message_strategy') or '').strip(),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'success': True, 'record': row.to_dict()}), 201


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
        zoho_contact_context=data.get('zoho_contact_context'),
        message_strategy=(data.get('message_strategy') or '').strip(),
        strategy_confirmed=bool(data.get('strategy_confirmed')),
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
        audit_source=(data.get('source') or 'manual').strip() or 'manual',
        message_strategy=(data.get('message_strategy') or '').strip(),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/classify/', methods=['POST'])
@require_api_auth
def admin_dp_invite_dispatch_classify():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    emails = data.get('emails') or data.get('recipient_emails') or None
    if emails is not None and not isinstance(emails, list):
        return jsonify({'error': 'emails must be an array'}), 400
    payload, status = classify_long_gap_dispatch(
        current_user,
        emails=emails,
        force=bool(data.get('force')),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/review/', methods=['GET'])
@require_api_auth
def admin_dp_invite_dispatch_review_get():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload, status = get_long_gap_dispatch_review(current_user)
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/review/', methods=['PATCH'])
@require_api_auth
def admin_dp_invite_dispatch_review_patch():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or data.get('recipient_email') or '').strip()
    if not email:
        return jsonify({'success': False, 'error': 'email is required'}), 400
    patch = {key: data[key] for key in data if key not in {'email', 'recipient_email'}}
    try:
        payload, status = patch_long_gap_dispatch_review(current_user, email=email, patch=patch)
    except Exception as exc:
        import logging
        logging.getLogger('dp_admin_invite').exception(
            'dispatch review patch failed for %s: %s', email, exc,
        )
        return jsonify({
            'success': False,
            'error': 'Failed to update dispatch row',
            'code': 'dispatch_patch_failed',
        }), 500
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/draft/', methods=['POST'])
@require_api_auth
def admin_dp_invite_dispatch_draft():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    emails = data.get('emails') or data.get('recipient_emails') or None
    if emails is not None and not isinstance(emails, list):
        return jsonify({'error': 'emails must be an array'}), 400
    payload, status = start_draft_long_gap_dispatch_job(
        current_user,
        emails=emails,
        force=bool(data.get('force')),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/draft/status/', methods=['GET'])
@require_api_auth
def admin_dp_invite_dispatch_draft_status():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload, status = get_draft_long_gap_dispatch_job_status(current_user)
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/template/', methods=['GET'])
@require_api_auth
def admin_dp_invite_dispatch_template():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload, status = get_long_gap_dispatch_template(current_user)
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/send/', methods=['POST'])
@require_api_auth
def admin_dp_invite_dispatch_send():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or data.get('recipient_email') or '').strip()
    if not email:
        return jsonify({'error': 'email is required'}), 400
    payload, status = send_long_gap_dispatch_email(
        current_user,
        email=email,
        test_mode=bool(data.get('test_mode')),
        test_recipient_email=(data.get('test_recipient_email') or '').strip(),
    )
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/send-all/', methods=['POST'])
@require_api_auth
def admin_dp_invite_dispatch_send_all():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    if bool(data.get('test_mode')):
        return jsonify({'error': 'Bulk send requires test mode off (production sends only)'}), 400
    payload, status = start_send_all_long_gap_dispatch_job(current_user)
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/send-all/status/', methods=['GET'])
@require_api_auth
def admin_dp_invite_dispatch_send_all_status():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    payload, status = get_send_all_long_gap_dispatch_job_status(current_user)
    return jsonify(payload), status


@bp.route('/api/admin/dp-invite/dispatch/retry-failed/', methods=['POST'])
@require_api_auth
def admin_dp_invite_dispatch_retry_failed():
    current_user, err_resp, err_code = _require_dp_admin()
    if err_resp:
        return err_resp, err_code
    data = request.get_json(silent=True) or {}
    if bool(data.get('test_mode')):
        return jsonify({'error': 'Retry failed requires test mode off (production sends only)'}), 400
    payload, status = start_retry_failed_long_gap_dispatch_job(current_user)
    return jsonify(payload), status
