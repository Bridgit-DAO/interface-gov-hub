"""Support pages: /support/ and /support/admin/."""
from __future__ import annotations

import html as html_mod

from flask import Blueprint

from services.identity import require_auth, require_role

bp = Blueprint('support_pages', __name__)


def _render(title: str, body_html: str):
    from services.rendering import render_page, generate_user_menu
    return render_page(
        title=title,
        content=body_html,
        user_menu=generate_user_menu(),
    )


@bp.route('/support/')
@require_auth
def support_home():
    body = '''
    <div class="container py-4" style="max-width:820px">
      <h1 class="h3 mb-2">Gov Hub support</h1>
      <p class="text-muted mb-4">Ask about workgroups, layers, nominations, or report a technical issue.</p>
      <div id="gh-support-app" data-mode="user"></div>
    </div>
    <script src="/static/js/gh-support.js"></script>
    '''
    return _render('Support', body)


@bp.route('/support/admin/')
@require_role('admin')
def support_admin():
    body = '''
    <div class="container-fluid py-4">
      <h1 class="h4 mb-3">Support admin</h1>
      <div id="gh-support-app" data-mode="admin"></div>
    </div>
    <script src="/static/js/gh-support.js"></script>
    '''
    return _render('Support admin', body)
