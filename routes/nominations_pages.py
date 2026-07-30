"""Public nomination respond page and API."""
import html
import json

from flask import Blueprint, current_app, jsonify, request, session
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
from services.dp_welcome import require_nominee_email
from services.workgroup_nomination_flow import record_nominee_response

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
        return render_page('Nomination – Gov Hub', content, theme=current_theme, user_menu=generate_user_menu())

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
            <button type="button" id="nomination-accept-btn" class="btn btn-success">
                <i class="fas fa-check me-2"></i>Accept nomination
            </button>
            <button type="button" id="nomination-decline-btn" class="btn btn-outline-danger">
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
                <p class="small text-muted">Accepting means you are willing to serve if the administrators approve.</p>
                {action_html}
            </div>
        </div>
    </div>
    <script>
    (function () {{
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
                    await GhDialog.alert({{
                        title: data.title || 'Done',
                        message: data.message,
                        variant: data.variant || 'success',
                    }});
                    location.reload();
                }} else {{
                    await GhDialog.alert({{
                        title: 'Error',
                        message: data.error || 'Could not save response',
                        variant: 'danger',
                    }});
                }}
            }} catch (e) {{
                await GhDialog.alert({{
                    title: 'Error',
                    message: 'Network error.',
                    variant: 'danger',
                }});
            }}
        }}

        document.addEventListener('DOMContentLoaded', function () {{
            document.getElementById('nomination-accept-btn')?.addEventListener('click', function () {{
                respondNomination('accept');
            }});
            document.getElementById('nomination-decline-btn')?.addEventListener('click', function () {{
                respondNomination('decline');
            }});
        }});
    }})();
    </script>
    """
    return render_page('Review nomination – Gov Hub', content, theme=current_theme, user_menu=generate_user_menu())


@bp.route('/api/nomination/respond/<token>/', methods=['POST'])
def api_nomination_respond(token):
    """Accept/decline via the single-use link emailed to the nominee.

    Possession of the token is the identity proof here: it is only ever sent to
    ``nominee_email``, which for account-linked nominations is the account's own
    verified address (see ``services.workgroup_nomination_flow``).
    """
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

    if action == 'accept':
        email_error = require_nominee_email(nomination)
        if email_error:
            return jsonify({'error': email_error}), 400
        record_nominee_response(nomination, accept=True)
        db.session.commit()
        _notify_response(nomination, accept=True)
        return jsonify({
            'success': True,
            'title': 'Nomination accepted',
            'message': 'Thank you. Your acceptance was recorded. Layer administrators will review this nomination before you are appointed.',
            'variant': 'success',
        })

    record_nominee_response(nomination, accept=False)
    nomination.nominee_decline_reason = (data.get('reason') or '').strip() or None
    db.session.commit()
    _notify_response(nomination, accept=False)
    return jsonify({
        'success': True,
        'title': 'Nomination declined',
        'message': 'Your response was recorded. The person who nominated you has been notified.',
        'variant': 'info',
    })


def _notify_response(nomination, *, accept: bool) -> bool:
    """Send follow-up notifications without risking the recorded response.

    The response is already committed. In-app notifications (nominator, and the
    layer administrators who review the nomination) are written here and
    committed even when email delivery fails, so nothing depends on the mail
    provider being reachable.
    """
    email_ok = send_nominee_accepted(nomination) if accept else send_nominee_declined(nomination)
    db.session.commit()
    if not email_ok:
        current_app.logger.warning(
            'Response emails incomplete for nomination %s', nomination.id
        )
    return email_ok
