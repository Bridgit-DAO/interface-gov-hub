"""Admin-only UI for product rollout (SiteConfig JSON). Kept separate from the main admin module."""
from __future__ import annotations

import html

from flask import Blueprint, flash, get_flashed_messages, redirect, request, url_for

from extensions import db
from services.product_rollout import (
    FEATURE_KEYS,
    get_rollout_config,
    is_feature_enabled,
    set_rollout_config,
    rollout_config_to_json_stored,
)
from services.identity import get_current_user, require_role
from services.rendering import generate_user_menu, render_page
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module

bp = Blueprint('product_rollout_admin', __name__, url_prefix='')

FEATURE_LABELS = {
    'layers': 'Layers (listing, layer pages, layer-scoped entry points)',
    'docs': 'Docs & Drafts (document flows tied to layers)',
    'roles': 'Roles (role directory, role pages, role admin tools; clusters & claims APIs)',
    'workgroups': 'Workgroups (workgroup surfaces and workgroup admin)',
    'guilds': 'Guilds (guild pages, directory, and /api/guilds/)',
    'badges': 'Badges (badge directory, one-time badges, badge APIs, /admin/badges/)',
    'waitlists': 'Waitlists (directory, layer tabs, /api/waitlists/, embed widgets)',
    'immortalize': 'Immortalize (Participate nav, /submit/?tab=immortalize, /immortalize/, inscription APIs)',
    'admin': 'Admin UI (/admin/ except this Product rollout page, which stays reachable when off)',
    'civic_mason': 'Civic Mason (page, recognition nav, and /api/civic-mason/)',
    'soft_launch': 'Soft-launch & demo flow (/soft-launch/, /api/soft-launch/)',
    'votes': 'Votes (directory, vote pages, and vote APIs under /api/…/votes/ and /api/votes/)',
    'artifacts': 'Artifacts, monuments, and collections (HTML + /api/artifacts, etc.)',
    'quests': 'Quests (layer quest pages, /api/quests/, guild quest links, open quests)',
    'bridges': 'Bridges (list/create pages and /api/bridges/)',
    'opportunities': 'Opportunities directory and layer /opportunities/ surfaces',
    'dp_proposals': 'DP Proposals (sentence-level suggested edits, amendments, /admin/dp-proposals/)',
}

FEATURE_ICONS = {
    'layers': 'fa-layer-group',
    'docs': 'fa-file-alt',
    'roles': 'fa-user-tag',
    'workgroups': 'fa-users',
    'guilds': 'fa-shield-halved',
    'badges': 'fa-award',
    'waitlists': 'fa-list-alt',
    'immortalize': 'fa-infinity',
    'admin': 'fa-tools',
    'civic_mason': 'fa-gopuram',
    'soft_launch': 'fa-rocket',
    'votes': 'fa-vote-yea',
    'artifacts': 'fa-gem',
    'quests': 'fa-tasks',
    'bridges': 'fa-link',
    'opportunities': 'fa-bullseye',
    'dp_proposals': 'fa-highlighter',
}


@bp.route('/admin/product-rollout/', methods=['GET', 'POST'])
@require_role('admin')
def product_rollout_page():
    user_menu = generate_user_menu()
    current_user = get_current_user() or {}
    theme = (current_user or {}).get('theme', 'dark') or 'dark'

    if request.method == 'POST':
        partial = {}
        for key in FEATURE_KEYS:
            # Checkbox present => True; missing => False
            partial[key] = request.form.get(f'feature_{key}') == 'on'
        try:
            set_rollout_config(partial)
        except Exception as exc:
            db.session.rollback()
            flash(f'Could not save settings: {exc}', 'error')
        else:
            flash('Product rollout settings saved.', 'success')
        return redirect(url_for('product_rollout_admin.product_rollout_page'))

    cfg = get_rollout_config()
    _ = is_feature_enabled('layers')

    flashed = get_flashed_messages(with_categories=True)
    flash_html = ''
    for category, msg in flashed:
        cls = 'info'
        if category == 'error':
            cls = 'danger'
        elif category == 'success':
            cls = 'success'
        elif category == 'warning':
            cls = 'warning'
        safe = html.escape(str(msg), quote=True)
        flash_html += (
            f'<div class="alert alert-{cls} alert-dismissible fade show" role="alert">'
            f'{safe}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>'
        )

    check_rows = []
    for key in FEATURE_KEYS:
        en = bool(cfg.get(key, True))
        label = FEATURE_LABELS.get(key, key)
        icon = FEATURE_ICONS.get(key, 'fa-toggle-on')
        check_rows.append(
            f'''<div class="form-check form-switch mb-3 p-3 border rounded">
            <input class="form-check-input" type="checkbox" name="feature_{key}" id="feature_{key}"{' checked' if en else ''}>
            <label class="form-check-label" for="feature_{key}">
                <i class="fas {icon} me-2 text-primary"></i><strong class="text-capitalize">{key}</strong>
                <span class="d-block small text-muted mt-1">{label}</span>
            </label>
        </div>'''
        )

    checks_html = '\n'.join(check_rows)
    json_preview = html.escape(rollout_config_to_json_stored(), quote=True)

    content = f'''
    <style>
      .product-rollout-json-preview {{
        background: var(--card-bg) !important;
        color: var(--text-primary);
        border-color: var(--border-color) !important;
      }}
    </style>
    <div class="gh-page container py-4">
        {flash_html}
        {gh_page_header('Product rollout', 'Turn major product areas on or off without redeploying', 'fa-toggle-on', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Product rollout', None)]))}
        <p class="text-muted small mb-4">Use <code>services.product_rollout.is_feature_enabled</code> in routes and templates to enforce. After changing toggles, click <strong>Save</strong>.</p>

        <div class="row g-4">
            <div class="col-lg-7">
                <form method="post" class="living-module mb-0">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-sliders-h"></i></div>
                        <h5 class="living-module-title">Features</h5>
                    </div>
                    <div class="living-module-body">
                        {checks_html}
                        <button type="submit" class="btn btn-primary">Save</button>
                        <a href="/admin/" class="btn btn-outline-secondary">Back to admin</a>
                    </div>
                </form>
            </div>
            <div class="col-lg-5">
                {gh_living_module('Effective config (read-only)', f'<p class="small text-muted">Stored in <code>site_config</code> key <code>product_rollout</code> as JSON.</p><pre class="small border rounded p-3 mb-0 product-rollout-json-preview" style="max-height:20rem; overflow:auto;"><code id="rollout-json-preview">{json_preview}</code></pre>', 'fa-code')}
            </div>
        </div>
    </div>
    '''

    return render_page('Product rollout — Admin', content, theme=theme, user_menu=user_menu)
