"""In-app notifications, subscription hub, and email unsubscribe (transactional opt-out)."""

from html import escape
from urllib.parse import quote as urlquote

from flask import Blueprint, flash, jsonify, redirect, request, session

from extensions import db
from models import User, UserNotification
from services.identity import get_current_user

bp = Blueprint('notifications', __name__, url_prefix='')


@bp.route('/notifications/email/unsubscribe/<token>', methods=['GET', 'POST'])
def email_unsubscribe_one_click(token):
    """RFC 8058 one-click + browser GET: disable transactional email opt-in."""
    user = User.query.filter_by(notification_unsubscribe_token=token).first()
    if not user:
        return '<p>Invalid or expired link.</p>', 404
    user.email_notifications_opt_in = False
    db.session.commit()
    if request.method == 'POST':
        return ('', 204)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Unsubscribed</title></head>'
        '<body style="font-family:system-ui,sans-serif;max-width:480px;margin:2rem auto;">'
        '<h1>You are unsubscribed</h1><p>We will not send further transactional notification '
        'emails to this account. You can re-enable email in your profile settings.</p></body></html>'
    )


@bp.route('/notifications/')
def notifications_hub():
    """Profile-level hub: in-app feed + per-draft event subscriptions."""
    from services.rendering import render_page, generate_user_menu
    from services.documents import render_draft_subscription_form_html
    from services.event_subscriptions import list_user_draft_subjects

    current = get_current_user()
    if not current:
        flash('Sign in to view notifications and subscription settings.', 'warning')
        return redirect('/login/?redirect=' + urlquote('/notifications/', safe=''))

    user_menu = generate_user_menu()
    current_theme = session.get('theme', current.get('theme', 'dark'))
    uid = current['id']

    notif_rows = (
        UserNotification.query.filter_by(user_id=uid)
        .filter(UserNotification.archived_at.is_(None))
        .order_by(UserNotification.created_at.desc())
        .limit(50)
        .all()
    )
    notif_html = []
    for n in notif_rows:
        read_badge = '<span class="badge bg-secondary">Read</span>' if n.read_at else '<span class="badge bg-primary">New</span>'
        link = n.link_url or '#'
        mark_read = ''
        if not n.read_at:
            mark_read = (
                f'<form method="post" action="/api/me/notifications/{escape(n.id)}/read/" class="d-inline">'
                f'<button type="submit" class="btn btn-sm btn-outline-secondary">Mark read</button></form>'
            )
        notif_html.append(
            f'<li class="list-group-item d-flex justify-content-between align-items-start flex-wrap gap-2">'
            f'<div><span class="me-2">{read_badge}</span><strong>{escape(n.title or "")}</strong><br>'
            f'<span class="small text-muted">{escape((n.body or "")[:300])}</span><br>'
            f'<a href="{escape(link)}" class="small">Open</a> · <span class="text-muted small">'
            f'{n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else ""}</span></div><div>{mark_read}</div></li>'
        )
    if not notif_html:
        notif_html.append('<li class="list-group-item text-muted">No in-app notifications yet.</li>')

    draft_keys = list_user_draft_subjects(uid)
    subs_cards = []
    hub_next = '/notifications/'
    for dn in draft_keys:
        subs_cards.append(
            f'<div class="card mb-3"><div class="card-header py-2 d-flex justify-content-between align-items-center">'
            f'<span class="font-monospace small">{escape(dn)}</span>'
            f'<a class="btn btn-sm btn-outline-primary" href="/doc/draft/{urlquote(dn, safe="/")}/">Open draft</a>'
            f'</div><div class="card-body py-2">'
            f'{render_draft_subscription_form_html(dn, current, compact=True, next_url=hub_next, show_hub_link=False)}'
            f'</div></div>'
        )

    subs_section = ''.join(subs_cards) if subs_cards else (
        '<p class="text-muted">You have no draft subscriptions yet. Open an approved document and use '
        '<strong>Actions → Notifications</strong> to choose events.</p>'
    )

    content = f'''
    <nav aria-label="breadcrumb"><ol class="breadcrumb">
      <li class="breadcrumb-item"><a href="/">Home</a></li>
      <li class="breadcrumb-item active">Notifications</li>
    </nav>

    <h1 class="mb-4">Notifications</h1>

    <p class="lead text-muted mb-4">
      Manage <a href="/profile/">profile &amp; email preferences</a> and subscriptions below.
    </p>

    <ul class="nav nav-tabs mb-4" role="tablist">
      <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-inapp" type="button">In-app</button></li>
      <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-subs" type="button">Draft subscriptions</button></li>
    </ul>
    <div class="tab-content">
      <div class="tab-pane fade show active" id="tab-inapp">
        <div class="card"><div class="card-body p-0">
          <ul class="list-group list-group-flush">{''.join(notif_html)}</ul>
        </div></div>
      </div>
      <div class="tab-pane fade" id="tab-subs">
        <p class="small text-muted">Per draft, choose event types and channels (in-app vs email).</p>
        {subs_section}
      </div>
    </div>
    '''

    return render_page(
        title='Notifications - Gov Hub',
        content=content,
        theme=current_theme,
        user_menu=user_menu,
        body_attrs='',
    )


@bp.route('/api/me/notifications/', methods=['GET'])
def api_list_my_notifications():
    current = get_current_user()
    if not current:
        return jsonify({'error': 'Authentication required'}), 401
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    unread_only = request.args.get('unread') == '1'
    q = UserNotification.query.filter_by(user_id=current['id']).filter(
        UserNotification.archived_at.is_(None)
    )
    if unread_only:
        q = q.filter(UserNotification.read_at.is_(None))
    rows = q.order_by(UserNotification.created_at.desc()).offset(offset).limit(limit).all()
    return jsonify({
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'body': n.body,
                'link_url': n.link_url,
                'read_at': n.read_at.isoformat() if n.read_at else None,
                'email_sent_at': n.email_sent_at.isoformat() if n.email_sent_at else None,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'event_log_id': n.event_log_id,
            }
            for n in rows
        ],
        'count': len(rows),
    })


@bp.route('/api/me/notifications/<notif_id>/read/', methods=['POST'])
def api_mark_notification_read(notif_id):
    from datetime import datetime

    current = get_current_user()
    if not current:
        return jsonify({'error': 'Authentication required'}), 401
    n = UserNotification.query.filter_by(id=notif_id, user_id=current['id']).first()
    if not n:
        return jsonify({'error': 'Not found'}), 404
    n.read_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})
