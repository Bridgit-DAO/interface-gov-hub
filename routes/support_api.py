"""Support ticket API — public, admin, and Hermes routes."""
from __future__ import annotations

import mimetypes
import os

from flask import Blueprint, jsonify, request, send_file

from services.api_auth import get_api_user, require_api_auth
from services.support_auth import require_hermes, require_support_admin
from services.support_notify import send_support_reply_email, send_support_ticket_ack, send_support_ticket_alert
from services.support_store import (
    create_ticket,
    mark_draft_reply_sent,
    patch_ticket,
    public_ticket_summary,
    read_ticket,
    search_tickets,
    support_data_dir,
    ticket_for_hermes,
    attachment_abs_path,
)

bp = Blueprint('support_api', __name__)

ERROR_MESSAGES = {
    'invalid_urgency': 'Choose urgency: critical, blocking, or non_blocking.',
    'invalid_category': 'Choose a valid category.',
    'subject_required': 'Subject is required.',
    'body_required': 'Message body is required.',
    'screenshot_ack_required': 'For technical support, confirm the screenshot acknowledgement or attach a screenshot.',
}


def _data_dir():
    return support_data_dir()


@bp.route('/api/support/tickets', methods=['GET'])
@require_api_auth
def list_my_tickets():
    user = get_api_user()
    result = search_tickets(_data_dir(), {'userId': user['id'], 'limit': 50})
    return jsonify({
        'ok': True,
        'tickets': [public_ticket_summary(t) for t in result['tickets']],
        'total': result['total'],
    })


@bp.route('/api/support/tickets', methods=['POST'])
@require_api_auth
def create_support_ticket():
    user = get_api_user()
    body = request.get_json(silent=True) or {}
    result = create_ticket(_data_dir(), {
        'subject': body.get('subject'),
        'body': body.get('body'),
        'urgency': body.get('urgency', 'non_blocking'),
        'category': body.get('category', 'general'),
        'screenshotAcknowledged': body.get('screenshotAcknowledged'),
        'userId': user.get('id'),
        'email': user.get('email') or body.get('email'),
        'handle': user.get('displayName') or user.get('name') or user.get('username') or body.get('handle'),
        'screenshots': body.get('screenshots') if isinstance(body.get('screenshots'), list) else [],
        'pageUrl': body.get('pageUrl'),
        'browser': body.get('browser'),
        'os': body.get('os'),
        'canopiMode': body.get('canopiMode'),
        'stepsToReproduce': body.get('stepsToReproduce'),
        'expectedBehavior': body.get('expectedBehavior'),
        'actualBehavior': body.get('actualBehavior'),
        'triedAlready': body.get('triedAlready'),
        'diagnosticBundle': body.get('diagnosticBundle') if isinstance(body.get('diagnosticBundle'), dict) else None,
    })
    if not result.get('ok'):
        err = result.get('error')
        return jsonify({'ok': False, 'error': err, 'message': ERROR_MESSAGES.get(err, 'Could not create ticket.')}), 400
    ticket = result['ticket']
    try:
        send_support_ticket_alert(_data_dir(), ticket)
    except Exception:
        pass
    try:
        send_support_ticket_ack(ticket)
    except Exception:
        pass
    return jsonify({'ok': True, 'ticket': public_ticket_summary(ticket)})


@bp.route('/api/support/admin/tickets', methods=['GET'])
@require_support_admin
def admin_list_tickets():
    args = request.args
    result = search_tickets(_data_dir(), {
        'q': args.get('q'),
        'urgency': args.get('urgency'),
        'category': args.get('category'),
        'status': args.get('status'),
        'limit': args.get('limit'),
        'offset': args.get('offset'),
    })
    from services.support_store import public_ticket_summary_extended
    return jsonify({
        'ok': True,
        'total': result['total'],
        'tickets': [public_ticket_summary_extended(t, include_body=True) for t in result['tickets']],
    })


@bp.route('/api/support/admin/tickets/<ticket_id>', methods=['GET'])
@require_support_admin
def admin_get_ticket(ticket_id):
    ticket = read_ticket(_data_dir(), ticket_id)
    if not ticket:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    from services.support_store import public_ticket_summary_extended
    return jsonify({'ok': True, 'ticket': public_ticket_summary_extended(ticket, include_body=True)})


@bp.route('/api/support/admin/tickets/<ticket_id>', methods=['PATCH'])
@require_support_admin
def admin_patch_ticket(ticket_id):
    body = request.get_json(silent=True) or {}
    result = patch_ticket(_data_dir(), ticket_id, body)
    if not result.get('ok'):
        return jsonify({'ok': False, 'error': result.get('error')}), 400
    from services.support_store import public_ticket_summary_extended
    return jsonify({'ok': True, 'ticket': public_ticket_summary_extended(result['ticket'], include_body=True)})


@bp.route('/api/support/admin/tickets/<ticket_id>/send-reply', methods=['POST'])
@require_support_admin
def admin_send_reply(ticket_id):
    body = request.get_json(silent=True) or {}
    if body.get('draftReply'):
        patch_ticket(_data_dir(), ticket_id, {'draftReply': body['draftReply']})
    ticket = read_ticket(_data_dir(), ticket_id)
    if not ticket:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    email_result = send_support_reply_email(
        ticket,
        subject=body.get('subject'),
        body=body.get('body'),
    )
    if not email_result.get('ok'):
        return jsonify({'ok': False, 'error': email_result.get('error')}), 400
    updated = mark_draft_reply_sent(_data_dir(), ticket_id, 'admin')
    return jsonify({'ok': True, 'emailId': email_result.get('id'), 'ticket': ticket_for_hermes(updated['ticket'])})


@bp.route('/api/support/hermes/queue', methods=['GET'])
@require_hermes
def hermes_queue():
    args = request.args
    result = search_tickets(_data_dir(), {
        'status': args.get('status', 'open'),
        'limit': args.get('limit', 10),
        'offset': args.get('offset', 0),
    })
    from services.support_store import public_ticket_summary_extended
    return jsonify({
        'ok': True,
        'tickets': [public_ticket_summary_extended(t) for t in result['tickets']],
        'total': result['total'],
    })


@bp.route('/api/support/hermes/health', methods=['GET'])
@require_hermes
def hermes_health():
    import urllib.request
    base = os.environ.get('GOVHUB_PUBLIC_BASE') or request.host_url.rstrip('/')
    probe = f'{base}/support'
    ok = True
    try:
        with urllib.request.urlopen(probe, timeout=8) as resp:
            ok = 200 <= resp.status < 400
    except Exception:
        ok = False
    return jsonify({'ok': ok, 'checkedAt': __import__('datetime').datetime.utcnow().isoformat() + 'Z', 'probe': probe})


@bp.route('/api/support/hermes/knowledge', methods=['GET'])
@require_hermes
def hermes_knowledge():
    from config import PROJECT_ROOT
    import json
    data_path = os.path.join(PROJECT_ROOT, 'data', 'support-runbooks.json')
    agent_path = os.path.join(PROJECT_ROOT, 'data', 'support-hermes-agent.md')
    runbooks = {}
    if os.path.isfile(data_path):
        with open(data_path, 'r', encoding='utf-8') as fh:
            runbooks = json.load(fh)
    agent_prompt = ''
    if os.path.isfile(agent_path):
        with open(agent_path, 'r', encoding='utf-8') as fh:
            agent_prompt = fh.read()
    base = os.environ.get('GOVHUB_PUBLIC_BASE') or request.host_url.rstrip('/')
    return jsonify({
        'ok': True,
        'runbooks': runbooks.get('runbooks', []),
        'escalationRules': runbooks.get('escalationRules', []),
        'faq': runbooks.get('faq', {}),
        'agentPrompt': agent_prompt,
        'baseUrl': base,
    })


@bp.route('/api/support/hermes/tickets/<ticket_id>', methods=['GET'])
@require_hermes
def hermes_get_ticket(ticket_id):
    ticket = read_ticket(_data_dir(), ticket_id)
    if not ticket:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    return jsonify({'ok': True, 'ticket': ticket_for_hermes(ticket)})


@bp.route('/api/support/hermes/tickets/<ticket_id>', methods=['PATCH'])
@require_hermes
def hermes_patch_ticket(ticket_id):
    body = request.get_json(silent=True) or {}
    result = patch_ticket(_data_dir(), ticket_id, body)
    if not result.get('ok'):
        return jsonify({'ok': False, 'error': result.get('error')}), 400
    return jsonify({'ok': True, 'ticket': ticket_for_hermes(result['ticket'])})


@bp.route('/api/support/hermes/tickets/<ticket_id>/send-reply', methods=['POST'])
@require_hermes
def hermes_send_reply(ticket_id):
    body = request.get_json(silent=True) or {}
    if body.get('draftReply'):
        patch_ticket(_data_dir(), ticket_id, {'draftReply': body['draftReply']})
    ticket = read_ticket(_data_dir(), ticket_id)
    if not ticket:
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    email_result = send_support_reply_email(ticket, subject=body.get('subject'), body=body.get('body'))
    if not email_result.get('ok'):
        return jsonify({'ok': False, 'error': email_result.get('error')}), 400
    updated = mark_draft_reply_sent(_data_dir(), ticket_id, 'hermes')
    return jsonify({'ok': True, 'emailId': email_result.get('id'), 'ticket': ticket_for_hermes(updated['ticket'])})


@bp.route('/api/support/hermes/tickets/<ticket_id>/attachments/<filename>', methods=['GET'])
@require_hermes
def hermes_attachment(ticket_id, filename):
    abs_path = attachment_abs_path(_data_dir(), ticket_id, filename)
    if not abs_path or not os.path.isfile(abs_path):
        return jsonify({'ok': False, 'error': 'not_found'}), 404
    mime, _ = mimetypes.guess_type(filename)
    return send_file(abs_path, mimetype=mime or 'application/octet-stream', as_attachment=False)
