"""Public nomination respond page and API."""
import html
import json

from flask import Blueprint, jsonify, request, session
from datetime import datetime

from extensions import db
from models import User, Workgroup, WorkingGroupChair, Layer
from services.workgroup_positions import (
    NOMINATION_STATUS_NOMINEE_ACCEPTED,
    NOMINATION_STATUS_NOMINEE_DECLINED,
    NOMINATION_STATUS_PENDING_NOMINEE,
    position_label,
    status_label,
)
from services.workgroup_nomination_mail import (
    send_nominee_accepted,
    send_nominee_declined,
)

bp = Blueprint('nominations_pages', __name__, url_prefix='')


def _get_render():
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/nomination/respond/<token>/')
def nomination_respond_page(token):
    """Landing page for nominee to review and accept/decline."""
    render_page, generate_user_menu = _get_render()
    nomination = WorkingGroupChair.query.filter_by(nominee_response_token=token).first()
    current_theme = session.get('theme', 'dark')

    if not nomination:
        content = """
        <div class="gh-page container mt-4">
            <div class="alert alert-danger">This nomination link is invalid or has expired.</div>
        </div>
        """
        return render_page('Nomination — Gov Hub', content, theme=current_theme, user_menu=generate_user_menu())

    expired = (
        nomination.nominee_token_expires_at
        and nomination.nominee_token_expires_at < datetime.utcnow()
    )
    wg = Workgroup.query.filter_by(acronym=nomination.group_acronym).first()
    layer = Layer.query.get(wg.layer_id) if wg and wg.layer_id else None
    nominator = User.query.get(nomination.nominated_by_user_id) if nomination.nominated_by_user_id else None
    pos_label = position_label(nomination.position_key or 'chair')
    wg_name = html.escape(wg.name if wg else nomination.group_acronym)
    layer_name = html.escape(layer.name if layer else 'Gov Hub')
    nominator_name = html.escape(
        (nominator.displayName or nominator.username) if nominator else 'A community member'
    )
    statement = html.escape(nomination.statement or '').replace('\n', '<br>')
    status = nomination.status or NOMINATION_STATUS_PENDING_NOMINEE
    token_json = json.dumps(token)

    if expired and status == NOMINATION_STATUS_PENDING_NOMINEE:
        content = f"""
        <div class="gh-page container mt-4">
            <div class="alert alert-warning">This nomination link has expired. Ask the nominator to submit a new nomination.</div>
        </div>
        """
        return render_page('Nomination expired', content, theme=current_theme, user_menu=generate_user_menu())

    already_html = ''
    if status == NOMINATION_STATUS_NOMINEE_ACCEPTED:
        already_html = '<div class="alert alert-success">You already accepted this nomination. It is pending administrator approval.</div>'
    elif status == NOMINATION_STATUS_NOMINEE_DECLINED:
        already_html = '<div class="alert alert-secondary">You declined this nomination.</div>'
    elif nomination.approved:
        already_html = '<div class="alert alert-success">This nomination was approved. Thank you for serving.</div>'

    action_html = ''
    if status == NOMINATION_STATUS_PENDING_NOMINEE and not nomination.approved:
        action_html = f"""
        <div class="mb-3">
            <label for="decline-reason" class="form-label">Optional note if declining</label>
            <textarea id="decline-reason" class="form-control" rows="2" placeholder="Reason for declining (optional)"></textarea>
        </div>
        <div class="d-flex flex-wrap gap-2">
            <button type="button" class="btn btn-success" onclick="respondNomination('accept')">
                <i class="fas fa-check me-2"></i>Accept nomination
            </button>
            <button type="button" class="btn btn-outline-danger" onclick="respondNomination('decline')">
                <i class="fas fa-times me-2"></i>Decline
            </button>
        </div>
        """

    content = f"""
    <div class="gh-page container mt-4">
        <div class="living-module">
            <div class="living-module-header">
                <div class="living-module-icon"><i class="fas fa-user-check"></i></div>
                <h5 class="living-module-title">Workgroup nomination</h5>
            </div>
            <div class="living-module-body">
                {already_html}
                <p class="text-muted mb-3">Status: <strong>{html.escape(status_label(status))}</strong></p>
                <dl class="row mb-4">
                    <dt class="col-sm-3">Position</dt><dd class="col-sm-9">{html.escape(pos_label)}</dd>
                    <dt class="col-sm-3">Workgroup</dt><dd class="col-sm-9">{wg_name}</dd>
                    <dt class="col-sm-3">Layer</dt><dd class="col-sm-9">{layer_name}</dd>
                    <dt class="col-sm-3">Nominated by</dt><dd class="col-sm-9">{nominator_name}</dd>
                    <dt class="col-sm-3">Nominee</dt><dd class="col-sm-9">{html.escape(nomination.chair_name or '')}</dd>
                </dl>
                <h6>Statement</h6>
                <blockquote class="border-start border-3 ps-3 text-muted mb-4">{statement}</blockquote>
                <p class="small text-muted">Accepting means you are willing to serve if administrators approve. It does not appoint you immediately.</p>
                {action_html}
            </div>
        </div>
    </div>
    <script>
    const nominationToken = {token_json};
    async function respondNomination(action) {{
        const payload = {{ action: action }};
        if (action === 'decline') {{
            payload.reason = (document.getElementById('decline-reason')?.value || '').trim();
        }}
        try {{
            const resp = await fetch('/api/nomination/respond/' + encodeURIComponent(nominationToken) + '/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
            }});
            const data = await resp.json();
            if (resp.ok) {{
                if (typeof GhDialog !== 'undefined') {{
                    await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: data.title || 'Done', message: data.message, variant: data.variant || 'success' }}), variant: 'info' }});
                }} else {{
                    await GhDialog.alert({{ title: 'Notice', message: (data.message), variant: 'info' }});
                }}
                location.reload();
            }} else {{
                if (typeof GhDialog !== 'undefined') {{
                    await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Error', message: data.error || 'Could not save response', variant: 'danger' }}), variant: 'info' }});
                }} else {{
                    await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Could not save response'), variant: 'info' }});
                }}
            }}
        }} catch (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Error', message: 'Network error.', variant: 'danger' }}), variant: 'info' }});
            }}
        }}
    }}
    </script>
    """
    return render_page('Review nomination — Gov Hub', content, theme=current_theme, user_menu=generate_user_menu())


@bp.route('/api/nomination/respond/<token>/', methods=['POST'])
def api_nomination_respond(token):
    nomination = WorkingGroupChair.query.filter_by(nominee_response_token=token).first()
    if not nomination:
        return jsonify({'error': 'Invalid nomination link'}), 404

    if nomination.nominee_token_expires_at and nomination.nominee_token_expires_at < datetime.utcnow():
        if nomination.status == NOMINATION_STATUS_PENDING_NOMINEE:
            return jsonify({'error': 'This nomination link has expired'}), 410

    if nomination.status not in (NOMINATION_STATUS_PENDING_NOMINEE, None, ''):
        return jsonify({'error': f'Nomination already resolved ({status_label(nomination.status)})'}), 400

    data = request.get_json() or {}
    action = (data.get('action') or '').strip().lower()
    if action not in ('accept', 'decline'):
        return jsonify({'error': 'action must be accept or decline'}), 400

    nomination.nominee_responded_at = datetime.utcnow()
    if action == 'accept':
        nomination.status = NOMINATION_STATUS_NOMINEE_ACCEPTED
        db.session.commit()
        send_nominee_accepted(nomination)
        db.session.commit()
        return jsonify({
            'success': True,
            'title': 'Nomination accepted',
            'message': 'Thank you. Your acceptance was recorded. Layer administrators will review this nomination before you are appointed.',
            'variant': 'success',
        })

    nomination.status = NOMINATION_STATUS_NOMINEE_DECLINED
    nomination.nominee_decline_reason = (data.get('reason') or '').strip() or None
    db.session.commit()
    send_nominee_declined(nomination)
    db.session.commit()
    return jsonify({
        'success': True,
        'title': 'Nomination declined',
        'message': 'Your response was recorded. The person who nominated you has been notified.',
        'variant': 'info',
    })
