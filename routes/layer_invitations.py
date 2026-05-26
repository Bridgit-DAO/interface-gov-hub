"""Layer invitation API (token accept/decline) and page routes."""
import json

from flask import Blueprint, jsonify, request, session

from services.identity import get_current_user, require_auth
from services.layer_invitations import (
    accept_layer_invitation,
    create_layer_invitation,
    decline_layer_invitation,
    list_layer_invitations,
    preview_layer_invitation,
)
from services.directory_ui import gh_page_header

bp = Blueprint('layer_invitations', __name__, url_prefix='/api/layer-invitations')
bp_pages = Blueprint('layer_invite_pages', __name__, url_prefix='')

_LAYER_INVITE_STORAGE_KEY = 'gh_layer_invite'


@bp.route('/by-token/<token>/', methods=['GET'])
def invitation_preview(token):
    body, status = preview_layer_invitation(token.strip())
    return jsonify(body), status


@bp.route('/by-token/<token>/accept/', methods=['POST'])
@require_auth
def invitation_accept(token):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body, status = accept_layer_invitation(token.strip(), current_user['id'])
    return jsonify(body), status


@bp.route('/by-token/<token>/decline/', methods=['POST'])
@require_auth
def invitation_decline(token):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body, status = decline_layer_invitation(token.strip(), current_user['id'])
    return jsonify(body), status


@bp_pages.route('/layer/invite/<path:invite_token>/')
def layer_invite_landing(invite_token):
    from services.rendering import render_page, generate_user_menu

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    tok = invite_token.strip('/')
    content = f"""
    <div class="gh-page container mt-4">
        <div class="col-lg-8 mx-auto">
            {gh_page_header('Layer invitation', 'Accept an invitation to join a layer', 'fa-envelope-open-text', actions_html='<a href="/layers/" class="btn btn-outline-secondary btn-sm">Layer directory</a>')}
            <div id="invite-status" class="mb-3"><div class="spinner-border spinner-border-sm"></div> Loading…</div>
            <div id="invite-layer-info" class="d-none mb-3"></div>
            <div id="invite-actions" class="d-none d-flex flex-wrap gap-2">
                <a href="/login/" class="btn btn-primary" id="invite-login-btn">Log in to accept</a>
                <button type="button" class="btn btn-success d-none" id="invite-accept-btn">Accept invitation</button>
                <button type="button" class="btn btn-outline-secondary d-none" id="invite-decline-btn">Decline</button>
            </div>
        </div>
    </div>
    <script>
    const inviteToken = {json.dumps(tok)};
    const inviteStorageKey = {json.dumps(_LAYER_INVITE_STORAGE_KEY)};
    const isAuthenticated = {'true' if current_user else 'false'};

    function escHtml(s) {{
        if (!s) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }}

    function persistLayerInvite(ctx) {{
        try {{
            sessionStorage.setItem(inviteStorageKey, JSON.stringify({{
                token: ctx.token,
                layerSlug: ctx.layer.slug,
                layerId: ctx.layer.id,
                layerName: ctx.layer.name || '',
                inviterName: ctx.inviter_name || '',
                savedAt: Date.now()
            }}));
        }} catch (e) {{}}
    }}

    function clearLayerInvite() {{
        try {{ sessionStorage.removeItem(inviteStorageKey); }} catch (e) {{}}
    }}

    function layerPageHref(slug) {{
        return '/layers/' + encodeURIComponent(slug) + '/?invite=' + encodeURIComponent(inviteToken);
    }}

    function renderLayerInfo(layer, inviterName) {{
        const info = document.getElementById('invite-layer-info');
        if (!info) return;
        let html = '';
        if (layer.mission) {{
            html += '<div class="living-module mb-3"><div class="living-module-header">'
                + '<div class="living-module-icon"><i class="fas fa-bullseye"></i></div>'
                + '<h5 class="living-module-title">Mission</h5></div>'
                + '<div class="living-module-body"><p class="mb-0" style="white-space:pre-wrap;">'
                + escHtml(layer.mission) + '</p></div></div>';
        }}
        if (layer.description) {{
            html += '<div class="living-module mb-3"><div class="living-module-header">'
                + '<div class="living-module-icon"><i class="fas fa-align-left"></i></div>'
                + '<h5 class="living-module-title">About this layer</h5></div>'
                + '<div class="living-module-body"><p class="mb-0" style="white-space:pre-wrap;">'
                + escHtml(layer.description) + '</p></div></div>';
        }}
        if (layer.slug) {{
            html += '<p class="mb-0"><a href="' + escHtml(layerPageHref(layer.slug)) + '" class="btn btn-outline-primary btn-sm">'
                + '<i class="fas fa-external-link-alt me-1"></i>Explore ' + escHtml(layer.name || 'this layer') + '</a></p>';
        }}
        if (html) {{
            info.innerHTML = html;
            info.classList.remove('d-none');
        }} else {{
            info.innerHTML = '';
            info.classList.add('d-none');
        }}
    }}

    (async function() {{
        const st = document.getElementById('invite-status');
        const act = document.getElementById('invite-actions');
        const loginBtn = document.getElementById('invite-login-btn');
        const acceptBtn = document.getElementById('invite-accept-btn');
        const declineBtn = document.getElementById('invite-decline-btn');
        try {{
            const r = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(inviteToken) + '/');
            const d = await r.json();
            if (!r.ok) {{
                st.innerHTML = '<div class="alert alert-warning">' + escHtml(d.error || 'Invalid invitation') + '</div>';
                act.classList.remove('d-none');
                loginBtn.classList.add('d-none');
                return;
            }}
            const layer = d.layer || {{}};
            persistLayerInvite({{ token: inviteToken, layer: layer, inviter_name: d.inviter_name }});
            let html = '<p class="lead mb-2"><strong>' + escHtml(d.inviter_name || 'A member') + '</strong> invited you to join <strong>'
                + escHtml(layer.name || 'a layer') + '</strong>.</p>';
            html += '<p class="text-muted small mb-3">Sent to: ' + escHtml(d.invitee_email_masked || '') + '</p>';
            if (d.message) {{
                html += '<blockquote class="blockquote border-start border-3 ps-3 mb-4 text-muted">'
                    + escHtml(d.message) + '</blockquote>';
            }}
            st.innerHTML = html;
            renderLayerInfo(layer, d.inviter_name);
            act.classList.remove('d-none');
            if (isAuthenticated) {{
                loginBtn.classList.add('d-none');
                acceptBtn.classList.remove('d-none');
                declineBtn.classList.remove('d-none');
            }} else {{
                loginBtn.href = '/login/?next=' + encodeURIComponent('/layer/invite/' + inviteToken + '/');
            }}
            acceptBtn.addEventListener('click', async function() {{
                acceptBtn.disabled = true;
                try {{
                    const ar = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(inviteToken) + '/accept/', {{
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: '{{}}'
                    }});
                    const ad = await ar.json();
                    if (ar.ok) {{
                        clearLayerInvite();
                        const slug = ad.layer_slug || layer.slug || '';
                        const dup = ad.duplicate || ad.already_member;
                        st.innerHTML = '<div class="alert alert-success">' + escHtml(dup ? 'You are already a member of this layer.' : 'You joined the layer!') +
                            ' <a href="/layers/' + escHtml(slug) + '/">Open layer</a></div>';
                        document.getElementById('invite-layer-info').classList.add('d-none');
                        act.classList.add('d-none');
                    }} else {{
                        st.innerHTML = '<div class="alert alert-danger">' + escHtml(ad.error || 'Failed') + '</div>';
                        acceptBtn.disabled = false;
                    }}
                }} catch (e) {{
                    st.innerHTML = '<div class="alert alert-danger">' + escHtml(e.message) + '</div>';
                    acceptBtn.disabled = false;
                }}
            }});
            declineBtn.addEventListener('click', async function() {{
                declineBtn.disabled = true;
                try {{
                    const dr = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(inviteToken) + '/decline/', {{
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: '{{}}'
                    }});
                    const dd = await dr.json();
                    if (dr.ok) {{
                        clearLayerInvite();
                        st.innerHTML = '<div class="alert alert-secondary">Invitation declined.</div>';
                        document.getElementById('invite-layer-info').classList.add('d-none');
                        act.classList.add('d-none');
                    }} else {{
                        st.innerHTML = '<div class="alert alert-danger">' + escHtml(dd.error || 'Failed') + '</div>';
                        declineBtn.disabled = false;
                    }}
                }} catch (e) {{
                    st.innerHTML = '<div class="alert alert-danger">' + escHtml(e.message) + '</div>';
                    declineBtn.disabled = false;
                }}
            }});
        }} catch (e) {{
            st.innerHTML = '<div class="alert alert-danger">Could not load invitation.</div>';
            act.classList.remove('d-none');
        }}
    }})();
    </script>
    """
    return render_page('Layer invitation - Gov Hub', content, theme=current_theme, user_menu=user_menu)
