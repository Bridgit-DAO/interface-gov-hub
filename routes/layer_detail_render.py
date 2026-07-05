"""Layer detail page renderer."""
import json
from flask import session, current_app, make_response, request

from models import Layer
from services.identity import get_current_user
from services.coordination import is_layer_admin
from services.layer_features import (
    LAYER_FEATURE_LABELS,
    LAYER_FEATURE_ORDER,
    get_effective_features,
    is_layer_tab_enabled,
)
from services.product_rollout import get_rollout_config
from config import METAWEB_PIONEERS_LAYER_SLUG, METAWEB_BOOK_PURCHASE_URL
from services.nav_pills import (
    PILL_ANIMATIONS,
    get_effective_nav_pill_settings,
    layer_tab_tip,
    nav_pill_button_attrs,
    nav_pills_container_attrs,
    parse_layer_nav_pill_config,
)


_LAYER_TAB_GROUP_LABELS = {
    'home': 'Home',
    'core': 'Core',
    'decision': 'Decisions',
    'community': 'Community',
    'admin': 'Admin',
}


def _layer_tab_button(tab_id, label, icon_class, active=False, tip=''):
    act = ' active' if active else ''
    attrs = nav_pill_button_attrs(tab_id, tip)
    return (
        f'<li class="nav-item" role="presentation">'
        f'<button class="nav-link gh-nav-pill{act}" id="{tab_id}-tab" data-bs-toggle="tab" '
        f'data-bs-target="#{tab_id}" type="button"{attrs}>'
        f'<i class="fas {icon_class}" aria-hidden="true"></i><span>{label}</span></button></li>'
    )


def _build_layer_tabs_markup(effective, admin_tab_html='', admin_tab_pane_html='', *, layer=None):
    """Return (nav_html, tab_panes_html, enabled_tab_ids). Single tablist so Bootstrap tabs work."""
    opp_body_hint = (
        'Drafts, quests, and ways to contribute.'
        if effective.get('quests', True)
        else 'Drafts and ways to contribute.'
    )
    tab_defs = [
        (
            'overview', 'Overview', None, True, 'fa-compass', 'home',
            '<div id="project-header" class="mb-4"></div><div id="overview-content"></div>',
        ),
        ('workgroups', 'Workgroups', 'workgroups', False, 'fa-users-cog', 'core', '<div id="workgroups-content"></div>'),
        (
            'docs', 'Docs', 'docs', False, 'fa-file-alt', 'core',
            '<div class="living-module mb-4"><div class="living-module-header">'
            '<div class="living-module-icon"><i class="fas fa-file-alt"></i></div>'
            '<h5 class="living-module-title">Docs &amp; drafts</h5></div>'
            '<div class="living-module-body"><p class="text-muted small">Every draft submitted to this layer &mdash; '
            'approved, pending, or in revision.</p>'
            '<div id="docs-tab-container"><div class="text-center py-4">'
            '<div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>'
            '</div></div>',
        ),
        ('clusters', 'Clusters', 'clusters', False, 'fa-project-diagram', 'core', '<div id="clusters-content"></div>'),
        ('roles', 'Roles', 'roles', False, 'fa-user-tag', 'core', '<div id="roles-content"></div>'),
        ('claims', 'Claims', 'claims', False, 'fa-hand-paper', 'core', '<div id="claims-content"></div>'),
        ('votes', 'Votes', 'votes', False, 'fa-vote-yea', 'decision', '<div id="votes-content"></div>'),
        (
            'artifacts', 'Artifacts', 'artifacts', False, 'fa-cube', 'decision',
            '<div class="living-module mb-4"><div class="living-module-header">'
            '<div class="living-module-icon"><i class="fas fa-cube"></i></div>'
            '<h5 class="living-module-title">Artifacts</h5></div>'
            '<div class="living-module-body"><p class="text-muted small">Knowledge objects: proposals, evidence, submissions.</p>'
            '<div id="artifacts-tab-container"><div class="text-center py-4">'
            '<div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>'
            '</div></div>',
        ),
        (
            'opportunities', 'Opportunities', 'opportunities', False, 'fa-bullseye', 'decision',
            '<div class="living-module mb-4"><div class="living-module-header">'
            '<div class="living-module-icon"><i class="fas fa-bullseye"></i></div>'
            '<h5 class="living-module-title">Opportunities</h5></div>'
            f'<div class="living-module-body"><p class="text-muted small">{opp_body_hint}</p>'
            '<div id="opportunities-tab-container"><div class="text-center py-4">'
            '<div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>'
            '</div></div>',
        ),
    ]
    groups_nav: dict = {g: [] for g in ('home', 'core', 'decision', 'community', 'admin')}
    pane_parts = []
    enabled_ids = []
    first = True
    for tab_id, label, feat_key, is_overview, icon, group, pane_inner in tab_defs:
        if feat_key and not is_layer_tab_enabled(feat_key, effective):
            continue
        active = first and is_overview
        show = ' show active' if active else ''
        first = False
        enabled_ids.append(f'{tab_id}-tab')
        tip = layer_tab_tip(tab_id)
        groups_nav.setdefault(group, []).append(
            _layer_tab_button(tab_id, label, icon, active=active, tip=tip)
        )
        pane_parts.append(f'<div class="tab-pane fade{show}" id="{tab_id}" role="tabpanel">{pane_inner}</div>')

    show_waitlists = effective.get('waitlists', True)
    if show_waitlists:
        groups_nav['community'].append(
            '<li id="waitlist-tabs-marker" class="nav-item d-none" role="presentation"></li>'
        )

    nav_items = []
    for group_key in ('home', 'core', 'decision', 'community'):
        items = groups_nav.get(group_key) or []
        if not items:
            continue
        label = _LAYER_TAB_GROUP_LABELS[group_key]
        nav_items.append(
            f'<li class="layer-tab-group-label-item" data-tab-group="{group_key}" aria-hidden="true">'
            f'<span class="layer-tab-group-label">{label}</span></li>'
        )
        nav_items.extend(items)

    if admin_tab_html.strip():
        nav_items.append(
            f'<li class="layer-tab-group-label-item" data-tab-group="admin" aria-hidden="true">'
            f'<span class="layer-tab-group-label">{_LAYER_TAB_GROUP_LABELS["admin"]}</span></li>'
        )
        nav_items.append(admin_tab_html.strip())

    nav_settings = get_effective_nav_pill_settings(page='layer', layer=layer)
    container_attrs = nav_pills_container_attrs(
        nav_settings,
        context_id=layer.slug if layer else '',
    )
    nav_html = (
        f'<ul class="nav layer-feature-pills gh-nav-pills flex-wrap"{container_attrs} id="projectTabs" role="tablist">'
        + '\n'.join(nav_items)
        + '</ul>'
    )
    panes_html = '\n'.join(pane_parts) + '\n' + admin_tab_pane_html
    return nav_html, panes_html, enabled_ids


def _render_layer_standalone(project_slug, waitlist_id=None):
    """Standalone layer view: layer branding, tabs as nav, Overview as home."""
    return _render_project_detail(project_slug, waitlist_id=waitlist_id, standalone=True)


def _render_project_detail(project_slug, waitlist_id=None, standalone=False):
    """Shared logic for project detail page. waitlist_id when from /layers/<slug>/waitlist/<id>/.
    standalone=True: layer branding (logo, name), View in GovHub button."""
    from services.rendering import render_page, render_layer_standalone_page, generate_user_menu

    current_app.logger.info(f"[LAYER] _render_project_detail: project_slug={project_slug!r} waitlist_id={waitlist_id}")
    user_menu = generate_user_menu(layer_slug=project_slug if not standalone else None)
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    
    project_obj = Layer.query.filter_by(slug=project_slug).first()
    effective_features = get_effective_features(project_obj)
    show_quests = effective_features.get('quests', True)
    show_admin_tab = bool(project_obj and current_user and is_layer_admin(project_obj, current_user))
    initial_waitlist_id = str(waitlist_id) if waitlist_id else None
    site_rollout = get_rollout_config()
    layer_features_json = json.dumps({k: effective_features.get(k, True) for k in LAYER_FEATURE_ORDER})
    site_rollout_json = json.dumps({k: bool(site_rollout.get(k, True)) for k in LAYER_FEATURE_ORDER})
    layer_feat_keys_json = json.dumps(LAYER_FEATURE_ORDER)
    layer_feat_labels_json = json.dumps(LAYER_FEATURE_LABELS)
    nav_pill_animations_json = json.dumps(
        {k: v['label'] for k, v in PILL_ANIMATIONS.items()}
    )
    layer_nav_pill_json = json.dumps(parse_layer_nav_pill_config(project_obj))
    site_nav_pill_json = json.dumps(get_effective_nav_pill_settings(page='layer', layer=project_obj))
    metaweb_pioneers_slug_json = json.dumps(METAWEB_PIONEERS_LAYER_SLUG)
    metaweb_book_purchase_url_json = json.dumps(METAWEB_BOOK_PURCHASE_URL)
    
    admin_tab_html = ''
    admin_tab_pane_html = ''
    admin_tab_listener = ''
    # Layer-centric view: no Admin tab (admin via /layers/<slug>/#admin). No About|Admin row (About in Governance nav).
    if show_admin_tab and not standalone:
        admin_tab_html = (
            '<li class="nav-item" role="presentation">'
            '<button class="nav-link gh-nav-pill" id="admin-tab" data-bs-toggle="tab" data-bs-target="#admin" type="button"'
            + nav_pill_button_attrs('admin', layer_tab_tip('admin'))
            + '><i class="fas fa-cog" aria-hidden="true"></i><span>Admin</span></button></li>'
        )
        admin_tab_pane_html = '''
            <div class="tab-pane fade" id="admin">
                <div id="admin-content"></div>
            </div>
        '''
        admin_tab_listener = "document.getElementById('admin-tab').addEventListener('shown.bs.tab', loadAdmins);"
    
    tabs_nav_html = ''
    tabs_panes_html = ''
    enabled_layer_tab_ids_json = '[]'
    if not standalone:
        tabs_nav_html, tabs_panes_html, enabled_tab_ids = _build_layer_tabs_markup(
            effective_features, admin_tab_html, admin_tab_pane_html, layer=project_obj
        )
        enabled_layer_tab_ids_json = json.dumps(enabled_tab_ids + (['admin-tab'] if show_admin_tab else []))

    create_quest_admin_btn = (
        '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showCreateQuestModal()">'
        '<i class="fas fa-tasks me-2"></i>Create Quest</button></div>'
        if show_quests
        else ''
    )
    quest_modal_html = ''
    if show_quests:
        quest_modal_html = """
    <div class="modal fade" id="createQuestModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-tasks me-2"></i>Create Quest</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="create-quest-alert" class="alert d-none" role="alert"></div>
                    <form id="createQuestForm">
                        <div class="mb-3">
                            <label for="quest-title" class="form-label">Title *</label>
                            <input type="text" class="form-control" id="quest-title" required placeholder="e.g. Write opposition for draft X">
                        </div>
                        <div class="mb-3">
                            <label for="quest-description" class="form-label">Description</label>
                            <textarea class="form-control" id="quest-description" rows="3" placeholder="What contribution are you looking for?"></textarea>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="quest-type" class="form-label">Type</label>
                                <select class="form-select" id="quest-type">
                                    <option value="contribution">Contribution</option>
                                    <option value="bounty">Bounty</option>
                                    <option value="review">Review</option>
                                    <option value="documentation">Documentation</option>
                                </select>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="quest-difficulty" class="form-label">Difficulty</label>
                                <select class="form-select" id="quest-difficulty">
                                    <option value="easy">Easy</option>
                                    <option value="medium" selected>Medium</option>
                                    <option value="hard">Hard</option>
                                </select>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="quest-acceptance-criteria" class="form-label">Acceptance criteria (optional)</label>
                            <textarea class="form-control" id="quest-acceptance-criteria" rows="2" placeholder="What must be done to complete this quest?"></textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="create-quest-submit-btn" onclick="submitCreateQuest()"><i class="fas fa-check me-2"></i>Create Quest</button>
                </div>
            </div>
        </div>
    </div>
"""

    tabs_hidden_class = ' d-none' if standalone else ''
    if standalone:
        container_html = """
    <div class="gh-page container mt-4">
        <div id="project-title" class="mb-3">
            <div class="d-flex justify-content-center py-3">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
        <div id="layer-invite-banner" class="d-none mb-3"></div>
        <div id="project-header" class="mb-4"></div>
        <div id="overview-content"></div>
    </div>
"""
    else:
        container_html = f"""
    <div class="gh-page container mt-4">
        <div id="project-title" class="mb-3">
            <div class="d-flex justify-content-center py-3">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
        
        <div id="layer-invite-banner" class="d-none mb-3"></div>
        
        <div class="layer-feature-tabs-wrap mb-4{tabs_hidden_class}" id="projectTabsWrap">
            {tabs_nav_html}
        </div>
        
        <div class="tab-content" id="projectTabContent">
            {tabs_panes_html}
            <div id="waitlist-panes-marker" class="d-none"></div>
        </div>
    </div>
"""
    content = f"""
    {container_html}
    
    <div class="modal fade" id="joinProjectModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-plus me-2"></i>Join Layer</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted mb-0">You will join this layer as a contributor. If you arrived via a referral link, attribution is applied automatically.</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="join-project-confirm-btn" onclick="submitJoinProjectModal()"><i class="fas fa-check me-2"></i>Join</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="inviteMemberModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-user-plus me-2"></i>Invite by email</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="invite-member-alert" class="alert d-none" role="alert"></div>
                    <div id="layer-invite-shareable-block" class="card bg-secondary bg-opacity-10 mb-3 d-none">
                        <div class="card-body py-3">
                            <p class="small fw-semibold mb-2"><i class="fas fa-link me-1"></i>Shareable layer invitation link</p>
                            <p class="small text-muted mb-2">Anyone with this link can join after signing in. Same link for every invitee.</p>
                            <div class="input-group input-group-sm">
                                <input type="text" class="form-control font-monospace" id="layer-invite-shareable-url" readonly>
                                <button type="button" class="btn btn-outline-primary" id="layer-invite-shareable-copy" title="Copy link"><i class="fas fa-copy"></i></button>
                                <button type="button" class="btn btn-outline-danger" id="layer-invite-shareable-revoke" title="Revoke link"><i class="fas fa-ban"></i></button>
                            </div>
                        </div>
                    </div>
                    <p class="text-muted small" id="layer-invite-email-hint">Send invitation links to join this layer. You can invite multiple people at once. Already-members will be skipped.</p>
                    <p class="small text-muted d-none" id="layer-invite-email-divider">Or invite specific people by email</p>
                    <form id="inviteMemberForm" onsubmit="return false;">
                        <div class="mb-3">
                            <label for="invite-member-email" class="form-label">Email address(es)</label>
                            <textarea class="form-control" id="invite-member-email" rows="2" placeholder="colleague@example.com, friend@example.com"></textarea>
                            <div class="form-text">Separate multiple emails with commas or new lines</div>
                        </div>
                        <div class="mb-0">
                            <label for="invite-member-message" class="form-label">Personal note (optional)</label>
                            <textarea class="form-control" id="invite-member-message" rows="3" placeholder="Why you are inviting them…"></textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="invite-member-submit-btn" onclick="submitLayerInvite()"><i class="fas fa-paper-plane me-2"></i>Send invitation(s)</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="metawebPioneersJoinModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-book me-2"></i>Join Metaweb Pioneers</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-3">Becoming a member of Metaweb Pioneers requires holding a Metaweb Book or Punk ordinal.</p>
                    <p class="mb-0">
                        <a href="{METAWEB_BOOK_PURCHASE_URL}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-primary">
                            <i class="fas fa-external-link-alt me-2"></i>Get a Metaweb Book
                        </a>
                    </p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    <button type="button" class="btn btn-primary" onclick="submitJoinFromPioneersModal()">
                        <i class="fas fa-check me-2"></i>I have an ordinal – join
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="joinWaitlistModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="join-waitlist-modal-title"><i class="fas fa-list-alt me-2"></i>Join Waitlist</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted mb-3" id="join-waitlist-modal-desc">Add an optional message for the waitlist owner.</p>
                    <div class="mb-0">
                        <label for="join-waitlist-message" class="form-label">Message (optional)</label>
                        <textarea class="form-control" id="join-waitlist-message" rows="3" placeholder="Leave blank to skip"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="join-waitlist-confirm-btn" onclick="submitJoinWaitlistModal()"><i class="fas fa-check me-2"></i>Join</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="addAdminModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Add layer admin</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <label class="form-label">Search by username or name</label>
                    <input type="text" class="form-control" id="add-admin-username" placeholder="Type to search..." oninput="searchUsersForAdmin()">
                    <div id="add-admin-results" class="mt-3"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="embedCodeModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Embed Waitlist Widget</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="lead" id="embed-waitlist-name"></p>
                    <a id="embed-builder-link" href="#" class="btn btn-primary mb-3"><i class="fas fa-sliders-h me-1"></i>Customize Embed (colors, options, preview)</a>
                    <p class="text-muted small">Copy and paste this code into your website. Signups are tracked with the source URL.</p>
                    
                    <div class="mb-4">
                        <label class="form-label"><strong>Embed Code (iframe)</strong></label>
                        <div class="input-group">
                            <textarea class="form-control font-monospace" id="embed-code-iframe" rows="3" readonly></textarea>
                            <button class="btn btn-outline-primary" onclick="copyEmbedCode('iframe')"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                        <small class="text-muted">Recommended: Simple iframe embed with automatic sizing</small>
                    </div>
                    
                    <div class="mb-4">
                        <label class="form-label"><strong>Direct Widget URL</strong></label>
                        <div class="input-group">
                            <input type="text" class="form-control font-monospace" id="embed-url" readonly>
                            <button class="btn btn-outline-primary" onclick="copyEmbedCode('url')"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                        <small class="text-muted">Use this URL to embed in an iframe or link directly</small>
                    </div>
                    
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>Source Tracking:</strong> All signups from the embedded widget will be tracked with the source domain and URL where the signup occurred.
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    {quest_modal_html}
    
    <div class="modal fade" id="createVoteModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-vote-yea me-2"></i>Create Vote</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="create-vote-alert" class="alert d-none" role="alert"></div>
                    <form id="createVoteForm">
                        <div class="mb-3">
                            <label class="form-label">Vote type *</label>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="vote-type" id="vote-type-approval" value="approval" checked onchange="toggleVoteTypeFields()">
                                <label class="form-check-label" for="vote-type-approval">Approval – Vote on a draft (yes/no)</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="vote-type" id="vote-type-election" value="election" onchange="toggleVoteTypeFields()">
                                <label class="form-check-label" for="vote-type-election">Election – Vote for a role (choose among candidates)</label>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="vote-title" class="form-label">Title *</label>
                            <input type="text" class="form-control" id="vote-title" required placeholder="e.g. Approve ML-DRAFT-001 or Election: Director">
                        </div>
                        <div class="mb-3">
                            <label for="vote-description" class="form-label">Description</label>
                            <textarea class="form-control" id="vote-description" rows="2" placeholder="What is being decided"></textarea>
                        </div>
                        <div class="mb-3" id="vote-submission-section">
                            <label for="vote-submission-id" class="form-label">Draft to vote on *</label>
                            <select class="form-select" id="vote-submission-id">
                                <option value="">Loading drafts...</option>
                            </select>
                            <div class="form-text">Select an approved draft from this layer's workgroups</div>
                        </div>
                        <div class="mb-3 d-none" id="vote-role-section">
                            <label for="vote-role-id" class="form-label">Role to elect *</label>
                            <select class="form-select" id="vote-role-id">
                                <option value="">Loading roles...</option>
                            </select>
                            <div class="form-text">Roles with "requires election" (or any role) can be filled via vote</div>
                            <div class="mt-2">
                                <label for="vote-seats" class="form-label small">Seats (winners)</label>
                                <input type="number" class="form-control form-control-sm" id="vote-seats" min="1" value="1" style="max-width:80px">
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="vote-start" class="form-label">Start (<span id="timezone-start">your local time</span>) *</label>
                                <input type="datetime-local" class="form-control" id="vote-start" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="vote-end" class="form-label">End (<span id="timezone-end">your local time</span>) *</label>
                                <input type="datetime-local" class="form-control" id="vote-end" required>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="vote-quorum" class="form-label">Quorum (min votes) *</label>
                                <input type="number" class="form-control" id="vote-quorum" required min="1" value="1">
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="vote-threshold" class="form-label">Win threshold (0–1) *</label>
                                <input type="number" class="form-control" id="vote-threshold" required min="0" max="1" step="0.01" value="0.5" placeholder="0.5 = majority">
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="create-vote-submit-btn" onclick="submitCreateVote()"><i class="fas fa-check me-2"></i>Create Vote</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="emailModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-envelope me-2"></i>Email (layer admin)</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="email-modal-alert" class="alert d-none" role="alert"></div>
                    <form id="emailForm">
                        <div class="mb-3">
                            <label class="form-label">Recipients (max 100 per immediate send)</label>
                            <div id="email-recipient-groups" class="border rounded p-3 bg-light"></div>
                            <div class="form-text">Select groups and/or specific people. Unsubscribed users are excluded.</div>
                        </div>
                        <div class="mb-3">
                            <label for="email-people" class="form-label">Specific people (optional)</label>
                            <select class="form-select" id="email-people" multiple size="4"></select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">When to send</label>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="email-schedule-mode" id="email-schedule-immediate" value="immediate" checked>
                                <label class="form-check-label" for="email-schedule-immediate">Send now</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="email-schedule-mode" id="email-schedule-at" value="at">
                                <label class="form-check-label" for="email-schedule-at">Schedule for date/time</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="email-schedule-mode" id="email-schedule-after-join" value="after_join">
                                <label class="form-check-label" for="email-schedule-after-join">Hours after join</label>
                            </div>
                        </div>
                        <div class="mb-3 d-none" id="email-scheduled-at-wrap">
                            <label for="email-scheduled-at" class="form-label">Send at</label>
                            <input type="datetime-local" class="form-control" id="email-scheduled-at">
                        </div>
                        <div class="mb-3 d-none" id="email-delay-wrap">
                            <label for="email-delay-hours" class="form-label">Hours after join</label>
                            <input type="number" class="form-control" id="email-delay-hours" min="0.25" step="0.25" placeholder="e.g. 24">
                            <label for="email-anchor-kind" class="form-label mt-2">Join event</label>
                            <select class="form-select" id="email-anchor-kind">
                                <option value="layer_member">Layer membership join</option>
                                <option value="waitlist_member">Waitlist join</option>
                            </select>
                            <div class="form-text">New joiners matching selected groups will also receive this email.</div>
                        </div>
                        <div class="mb-3">
                            <label for="email-subject" class="form-label">Subject *</label>
                            <input type="text" class="form-control" id="email-subject" required placeholder="e.g. Layer update">
                        </div>
                        <div class="mb-3">
                            <label for="email-body" class="form-label">Message *</label>
                            <textarea class="form-control" id="email-body" rows="6" required placeholder="Your message..."></textarea>
                            <div class="form-text">An unsubscribe link is added automatically to every email.</div>
                        </div>
                    </form>
                    <div id="email-scheduled-list-wrap" class="d-none">
                        <hr>
                        <h6 class="mb-2">Scheduled campaigns</h6>
                        <div id="email-scheduled-list" class="small"></div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="email-submit-btn" onclick="submitEmail()"><i class="fas fa-paper-plane me-2"></i>Send / schedule</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="editProjectModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Edit Layer</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                    <div id="edit-project-alert" class="alert d-none" role="alert"></div>
                    <form id="editProjectForm">
                        <div class="card bg-secondary bg-opacity-10 mb-4">
                            <div class="card-body py-3">
                                <h6 class="card-title mb-2"><i class="fas fa-user-shield me-2"></i>Layer Admins</h6>
                                <p class="text-muted small mb-2">Admins can manage workgroups, roles, claims, and other admins. The owner cannot be removed.</p>
                                <div id="edit-modal-admins-list" class="list-group mb-3"></div>
                                <div class="mb-0">
                                    <label class="form-label small">Add admin</label>
                                    <div class="input-group input-group-sm">
                                        <input type="text" class="form-control" id="edit-modal-add-admin-q" placeholder="Search by username (min 2 chars)..." oninput="searchUsersForEditModalAdmin()">
                                        <button type="button" class="btn btn-outline-primary" onclick="searchUsersForEditModalAdmin()"><i class="fas fa-search"></i></button>
                                    </div>
                                    <div id="edit-modal-add-admin-results" class="mt-2"></div>
                                </div>
                            </div>
                        </div>
                        <hr>
                        <div class="mb-3">
                            <label for="edit-project-name" class="form-label">Layer Name *</label>
                            <input type="text" class="form-control" id="edit-project-name" required maxlength="255">
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-mission" class="form-label">Mission</label>
                            <textarea class="form-control" id="edit-project-mission" rows="3"></textarea>
                            <div class="form-text">Core purpose and values (line breaks preserved)</div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-description" class="form-label">Description</label>
                            <textarea class="form-control" id="edit-project-description" rows="4"></textarea>
                            <div class="form-text">Line breaks are preserved when displayed</div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-image-url" class="form-label">Image (optional)</label>
                            <input type="url" class="form-control mb-2" id="edit-project-image-url" placeholder="https://example.com/image.png or upload below">
                            <div class="input-group">
                                <input type="file" class="form-control" id="edit-project-image-file" accept="image/*" onchange="openProjectImageCrop()">
                            </div>
                            <div class="form-text">Square image (will be cropped to 600×600). Select a file to open the crop tool.</div>
                            <div id="edit-project-image-upload-status" class="mt-1"></div>
                            <div class="mt-2 text-center">
                                <img id="edit-project-image-preview" src="" alt="Layer image preview" class="img-fluid rounded layer-hero-image d-none" style="max-height: 120px; object-fit: contain;">
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-status" class="form-label">Status</label>
                            <select class="form-select" id="edit-project-status">
                                <option value="proposed">Proposed</option>
                                <option value="active">Active</option>
                                <option value="stabilizing">Stabilizing</option>
                                <option value="maintaining">Maintaining</option>
                                <option value="dormant">Dormant</option>
                                <option value="concluded">Concluded</option>
                                <option value="archived">Archived</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-status-reason" class="form-label">Status Reason (optional)</label>
                            <input type="text" class="form-control" id="edit-project-status-reason" placeholder="e.g. reason for status change">
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-meta-domain-inscription" class="form-label">Meta-domain inscription ID</label>
                            <input type="text" class="form-control" id="edit-project-meta-domain-inscription" placeholder="e.g. abc123...i0">
                            <div class="form-text">Ordinal inscription whose content is the meta-domain (e.g. example.com.meta). Fetched once and cached.</div>
                            <div id="edit-project-meta-domain-display" class="mt-1 text-muted small"></div>
                        </div>

                        <hr class="my-4">

                        <div class="card bg-secondary bg-opacity-10 mb-2" id="edit-modal-prefixes-card">
                            <div class="card-body py-3">
                                <h6 class="card-title mb-2"><i class="fas fa-tag me-2"></i>Draft prefixes</h6>
                                <p class="text-muted small mb-2">Two-letter prefix prepended to draft identifiers in this layer (e.g. <code>ML-001</code>). Prefixes are <strong>globally unique across the entire Gov Hub</strong>.</p>
                                <div id="edit-modal-prefixes-list" class="mb-2"></div>
                                <div class="input-group input-group-sm" style="max-width: 18rem;">
                                    <input type="text" class="form-control text-uppercase font-monospace" id="edit-modal-add-prefix-input"
                                           maxlength="2" placeholder="ML" autocomplete="off" style="letter-spacing: 0.1em;">
                                    <button class="btn btn-primary" type="button" id="edit-modal-add-prefix-btn" onclick="editModalAddPrefix()">
                                        <i class="fas fa-plus me-1"></i>Add
                                    </button>
                                </div>
                                <div id="edit-modal-add-prefix-feedback" class="form-text small mt-1"></div>
                                <p class="small text-muted mt-2 mb-0">The active (default) prefix is the one shown in the header chip. A layer must always have at least one prefix.</p>
                            </div>
                        </div>

                        <div class="card bg-secondary bg-opacity-10 mb-2" id="edit-modal-display-status-card">
                            <div class="card-body py-3">
                                <h6 class="card-title mb-2"><i class="fas fa-eye me-2"></i>Visibility</h6>
                                <p class="text-muted small mb-2">Control whether this layer is listed publicly. Independent of GovHub super-admin approval.</p>
                                <div class="mb-2">
                                    <label for="edit-project-display-status" class="form-label small">Display status</label>
                                    <select class="form-select" id="edit-project-display-status">
                                        <option value="pending">Pending – only admins can see this layer</option>
                                        <option value="active">Active – listed publicly</option>
                                    </select>
                                </div>
                                <div class="d-flex gap-2 align-items-center">
                                    <button type="button" class="btn btn-primary btn-sm" id="edit-modal-display-status-save-btn" onclick="saveDisplayStatus()">
                                        <i class="fas fa-save me-1"></i>Save visibility
                                    </button>
                                    <span id="edit-modal-display-status-feedback" class="small text-muted"></span>
                                </div>
                                <p class="small text-muted mt-2 mb-0">Switch to <strong>Active</strong> once your layer is ready to receive public submissions.</p>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="edit-project-save-btn" onclick="saveProjectEdit()"><i class="fas fa-save me-2"></i>Save</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    let project = null;
    let layerWorkgroupsList = [];
    let layerRolesList = [];
    const projectSlug = {json.dumps(project_slug)};
    const metawebPioneersSlug = {metaweb_pioneers_slug_json};
    const metawebBookPurchaseUrl = {metaweb_book_purchase_url_json};
    const initialWaitlistId = {json.dumps(initial_waitlist_id)};
    const isAuthenticated = {'true' if current_user else 'false'};
    const isAdmin = {('true' if current_user and current_user.get('is_admin') else 'false')};
    const isProjectAdmin = {'true' if show_admin_tab else 'false'};
    const showCarousel = {json.dumps(standalone)};
    const layerEffectiveFeatures = {layer_features_json};
    const siteProductRollout = {site_rollout_json};
    const layerFeatKeys = {layer_feat_keys_json};
    const layerFeatLabels = {layer_feat_labels_json};
    const navPillAnimations = {nav_pill_animations_json};
    const layerNavPillConfig = {layer_nav_pill_json};
    const siteNavPillSettings = {site_nav_pill_json};

    function layerFeatKeysSiteEnabled() {{
        return (layerFeatKeys || []).filter(function(k) {{ return siteProductRollout[k] === true; }});
    }}
    const enabledLayerTabIds = {enabled_layer_tab_ids_json};
    const layerBase = showCarousel ? '/layer/' + projectSlug + '/' : '/layers/' + projectSlug + '/';

    function isLayerFeatureOn(key) {{
        return layerEffectiveFeatures[key] !== false;
    }}

    function layerImageUrl(url, p) {{
        if (!url) return '';
        const bust = (p && p._imgBust) ? String(p._imgBust) : ((p && (p.updated_at || p.id)) ? String(p.updated_at || p.id) : String(Date.now()));
        const sep = url.indexOf('?') >= 0 ? '&' : '?';
        return url + sep + 'v=' + encodeURIComponent(bust);
    }}

    function syncLayerBrandImages() {{
        if (!project) return;
        const url = project.image_url ? layerImageUrl(project.image_url, project) : '';
        const navImg = document.getElementById('layer-navbar-brand-img');
        if (navImg) {{
            navImg.src = url || '/static/images/overweb_logo.png';
            navImg.alt = project.name || '';
        }}
        document.querySelectorAll('.layer-hero-image, .layer-display-image').forEach(function(img) {{
            if (url) {{
                img.src = url;
                img.style.display = '';
            }} else {{
                img.style.display = 'none';
            }}
        }});
        const editPreview = document.getElementById('edit-project-image-preview');
        if (editPreview) {{
            if (url) {{
                editPreview.src = url;
                editPreview.classList.remove('d-none');
            }} else {{
                editPreview.classList.add('d-none');
            }}
        }}
    }}

    function layerDetailApiUrl(slug) {{
        const url = '/api/layers/by-slug/' + encodeURIComponent(slug) + '/';
        const token = new URLSearchParams(window.location.search).get('ref_token');
        return token ? url + '?ref_token=' + encodeURIComponent(token) : url;
    }}

    async function refreshProjectFromApi() {{
        if (!projectSlug) return false;
        try {{
            const resp = await fetch(layerDetailApiUrl(projectSlug), {{ credentials: 'include' }});
            if (!resp.ok) return false;
            const detail = await resp.json();
            project = detail;
            project.is_member = detail.is_member === true;
            project.member_role = detail.member_role || null;
            if (detail.effective_features) {{
                Object.keys(detail.effective_features).forEach(function(k) {{
                    layerEffectiveFeatures[k] = detail.effective_features[k];
                }});
            }}
            displayProjectHeader();
            syncLayerBrandImages();
            if (showCarousel) loadCarousel();
            return true;
        }} catch (e) {{
            console.error('refreshProjectFromApi:', e);
            return false;
        }}
    }}

    let artifactKnowledgeFilter = '';
    let artifactTagFilters = [];
    
    const referralRefToken = {json.dumps(request.args.get('ref_token') or '')};

    (function() {{
        if (!referralRefToken) return;
        fetch('/api/referral/landings/', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ ref_token: referralRefToken, landing_url: window.location.href }}),
            keepalive: true,
        }}).catch(function() {{}});
    }})();
    
    function getProjectTabKey(buttonId) {{
        if (!buttonId) return null;
        if (buttonId === 'overview-tab') return 'overview';
        if (buttonId === 'workgroups-tab') return 'workgroups';
        if (buttonId === 'clusters-tab') return 'clusters';
        if (buttonId === 'roles-tab') return 'roles';
        if (buttonId === 'claims-tab') return 'claims';
        if (buttonId === 'votes-tab') return 'votes';
        if (buttonId === 'artifacts-tab') return 'artifacts';
        if (buttonId === 'opportunities-tab') return 'opportunities';
        if (buttonId === 'admin-tab') return 'admin';
        const m = buttonId.match(/^waitlist-tab-(\\d+)$/);
        return m ? 'waitlist-' + m[1] : null;
    }}
    
    function saveTabState(current, previous) {{
        try {{
            const key = 'projectDetailTab_' + projectSlug;
            localStorage.setItem(key + '_current', current);
            if (previous) localStorage.setItem(key + '_previous', previous);
        }} catch (e) {{ console.warn('saveTabState:', e); }}
    }}
    
    function switchToTab(tabId) {{
        const map = {{
            overview: 'overview-tab',
            workgroups: 'workgroups-tab',
            clusters: 'clusters-tab',
            roles: 'roles-tab',
            claims: 'claims-tab',
            votes: 'votes-tab',
            artifacts: 'artifacts-tab',
            opportunities: 'opportunities-tab',
            admin: 'admin-tab',
        }};
        const btnId = map[tabId];
        const tabEl = btnId ? document.getElementById(btnId) : null;
        if (tabEl) {{
            if (typeof bootstrap !== 'undefined' && bootstrap.Tab) {{
                bootstrap.Tab.getOrCreateInstance(tabEl).show();
            }} else {{
                tabEl.click();
            }}
        }}
    }}
    
    function switchToTabFromHash() {{
        const hash = (window.location.hash || '').replace(/^#/, '');
        if (['claims', 'votes', 'admin'].includes(hash)) switchToTab(hash);
    }}
    
    function restoreTabState() {{
        try {{
            if (window.location.hash && ['claims', 'votes', 'admin'].includes(window.location.hash.replace('#', ''))) {{
                switchToTabFromHash();
                return;
            }}
            const key = 'projectDetailTab_' + projectSlug;
            const stored = localStorage.getItem(key + '_current');
            if (!stored || stored === 'overview') return;
            let tabEl = null;
            if (stored.startsWith('waitlist-')) {{
                const id = stored.replace('waitlist-', '');
                tabEl = document.getElementById('waitlist-tab-' + id);
            }} else {{
                const map = {{
                    overview: 'overview-tab',
                    workgroups: 'workgroups-tab',
                    clusters: 'clusters-tab',
                    roles: 'roles-tab',
                    claims: 'claims-tab',
                    votes: 'votes-tab',
                    artifacts: 'artifacts-tab',
                    opportunities: 'opportunities-tab',
                    admin: 'admin-tab',
                }};
                const btnId = map[stored];
                tabEl = btnId ? document.getElementById(btnId) : null;
            }}
            if (tabEl) tabEl.click();
        }} catch (e) {{ console.warn('restoreTabState:', e); }}
    }}
    
    function escapeHtml(text) {{
        if (!text) return '';
        return String(text).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;').split('\\n').join('<br>');
    }}
    
    function escapeHtmlBasic(text) {{
        if (!text) return '';
        return String(text).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;').split('"').join('&quot;').split("'").join('&#39;').split('`').join('&#96;');
    }}
    
    function escapeForTemplate(text) {{
        if (!text) return '';
        return String(text).replace(/\\\\/g, '\\\\\\\\').replace(/`/g, '\\\\`').replace(/\\$/g, '\\\\$');
    }}
    
    function escapeForJsAttr(text) {{
        if (!text) return '';
        return String(text).replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'").replace(/"/g, '\\\\"').replace(/`/g, '\\\\`');
    }}
    
    async function loadProject() {{
        try {{
            console.log('[LAYER] loadProject called, projectSlug=', projectSlug, 'type=', typeof projectSlug);
            if (!projectSlug || typeof projectSlug !== 'string') {{
                console.error('[LAYER] loadProject: invalid projectSlug');
                document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Invalid layer URL. <a href="/layers/">Back to Layers</a></div>';
                return;
            }}
            const slug = String(projectSlug).trim();
            const url = layerDetailApiUrl(slug);
            console.log('[LAYER] loadProject fetching:', url);
            const resp = await fetch(url, {{ credentials: 'include' }});
            console.log('[LAYER] loadProject response:', resp.status, resp.statusText, 'url=', resp.url);
            if (!resp.ok) {{
                const text = await resp.text();
                console.error('[LAYER] loadProject fetch failed:', resp.status, text.substring(0, 200));
                document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Layer not found. <a href="/layers/">Back to Layers</a></div>';
                return;
            }}
            const detail = await resp.json();
            console.log('[LAYER] loadProject got project:', detail?.name, 'id=', detail?.id);
            project = detail;
            project.is_member = detail.is_member === true;
            project.member_role = detail.member_role || null;
            if (detail.effective_features) {{
                Object.keys(detail.effective_features).forEach(function(k) {{
                    layerEffectiveFeatures[k] = detail.effective_features[k];
                }});
            }}
            
            displayProjectHeader();
            syncLayerBrandImages();
            await maybeShowLayerInviteBanner();
            loadOverview();
            if (isLayerFeatureOn('waitlists')) {{
                const wlResp = await fetch('/api/layers/' + project.id + '/waitlists/');
                const wlData = await wlResp.json().catch(() => ({{ waitlists: [], count: 0 }}));
                const enabledWaitlists = (wlData.waitlists || []).filter(w => w.active !== false);
                buildWaitlistTabs(enabledWaitlists);
            }}
            if (initialWaitlistId) {{
                const wl = enabledWaitlists.find(w => w.id === initialWaitlistId);
                if (wl) {{
                    document.getElementById('waitlist-tab-' + wl.id)?.click();
                }} else {{
                    showWaitlistInactiveMessage(initialWaitlistId);
                }}
            }} else {{
                restoreTabState();
            }}
        }} catch (error) {{
            console.error('Error loading project:', error);
            document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Error loading project</div>';
        }}
    }}
    
    function isOrdinalMembershipLayer() {{
        if (!project) return projectSlug === metawebPioneersSlug;
        return project.slug === metawebPioneersSlug || project.join_policy === 'nft_gated';
    }}

    function hideLayerEmailInvite() {{
        return isOrdinalMembershipLayer();
    }}

    async function showMetawebPioneersJoinModal() {{
        if (!isAuthenticated) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please sign in to join this project'), variant: 'info' }}); return; }}
        const modal = new bootstrap.Modal(document.getElementById('metawebPioneersJoinModal'));
        modal.show();
    }}

    async function showJoinProjectModal() {{
        if (!isAuthenticated) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please sign in to join this project'), variant: 'info' }}); return; }}
        if (isOrdinalMembershipLayer()) {{
            showMetawebPioneersJoinModal();
            return;
        }}
        const modal = new bootstrap.Modal(document.getElementById('joinProjectModal'));
        modal.show();
    }}

    async function submitJoinFromPioneersModal() {{
        const pioneersEl = document.getElementById('metawebPioneersJoinModal');
        const inst = pioneersEl ? bootstrap.Modal.getInstance(pioneersEl) : null;
        if (inst) inst.hide();
        await submitJoinProjectModal();
    }}
    
    async function submitJoinProjectModal() {{
        const body = {{}};
        if (referralRefToken) body.ref_token = referralRefToken;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/join/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();
            if (res.ok) {{
                project.is_member = true;
                project.member_role = data.member && data.member.role ? data.member.role : 'contributor';
                displayProjectHeader();
                const joinEl = document.getElementById('joinProjectModal');
                const joinInst = joinEl ? bootstrap.Modal.getInstance(joinEl) : null;
                if (joinInst) joinInst.hide();
                const pioneersEl = document.getElementById('metawebPioneersJoinModal');
                const pioneersInst = pioneersEl ? bootstrap.Modal.getInstance(pioneersEl) : null;
                if (pioneersInst) pioneersInst.hide();
            }} else {{ await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to join'), variant: 'info' }}); }}
        }} catch (e) {{ console.error(e); await GhDialog.alert({{ title: 'Notice', message: ('Failed to join project'), variant: 'info' }}); }}
    }}
    
    async function leaveProject() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Leave this project?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/leave/', {{ method: 'POST' }});
            if (res.ok) {{
                project.is_member = false;
                project.member_role = null;
                displayProjectHeader();
            }} else {{ const d = await res.json(); await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed to leave'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to leave project'), variant: 'info' }}); }}
    }}
    
    async function loadLayerShareableInvite() {{
        const block = document.getElementById('layer-invite-shareable-block');
        const urlInput = document.getElementById('layer-invite-shareable-url');
        const divider = document.getElementById('layer-invite-email-divider');
        if (!project || !project.id || (project.listing_visibility || 'public') !== 'public') {{
            if (block) block.classList.add('d-none');
            if (divider) divider.classList.add('d-none');
            return;
        }}
        try {{
            const res = await fetch('/api/layers/' + project.id + '/invitations/campaign/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ message: (document.getElementById('invite-member-message') || {{}}).value || null }})
            }});
            const data = await res.json();
            if (res.ok && data.invite_path && urlInput && block) {{
                const full = window.location.origin + data.invite_path;
                urlInput.value = full;
                block.classList.remove('d-none');
                if (divider) divider.classList.remove('d-none');
                const copyBtn = document.getElementById('layer-invite-shareable-copy');
                if (copyBtn && !copyBtn.dataset.ghBound) {{
                    copyBtn.dataset.ghBound = '1';
                    copyBtn.onclick = function () {{
                        navigator.clipboard.writeText(full).catch(function () {{}});
                    }};
                }}
                const revokeBtn = document.getElementById('layer-invite-shareable-revoke');
                if (revokeBtn && !revokeBtn.dataset.ghBound) {{
                    revokeBtn.dataset.ghBound = '1';
                    revokeBtn.onclick = async function () {{
                        const m = data.invite_path || '';
                        const tok = m.split('/layer/invite/')[1];
                        const token = tok ? tok.replace(/\\/$/, '') : '';
                        if (!token) return;
                        if (!(await GhDialog.confirm({{ title: 'Confirm', message: 'Revoke this layer invitation link for everyone?', variant: 'warning' }}))) return;
                        const rr = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(token) + '/revoke/', {{
                            method: 'POST', credentials: 'same-origin', headers: {{ 'Content-Type': 'application/json' }}, body: '{{}}'
                        }});
                        const rd = await rr.json();
                        if (rr.ok) await GhDialog.alert({{ title: 'Notice', message: (rd.message || 'Link revoked'), variant: 'info' }});
                        else await GhDialog.alert({{ title: 'Notice', message: (rd.error || 'Revoke failed'), variant: 'info' }});
                    }};
                }}
            }}
        }} catch (e) {{ /* private layer */ }}
    }}

    async function showInviteMemberModal() {{
        if (!isAuthenticated) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please sign in to invite members'), variant: 'info' }}); return; }}
        const alertEl = document.getElementById('invite-member-alert');
        if (alertEl) {{
            alertEl.classList.add('d-none');
            alertEl.innerHTML = '';
        }}
        const form = document.getElementById('inviteMemberForm');
        if (form) form.reset();
        loadLayerShareableInvite();
        const modal = new bootstrap.Modal(document.getElementById('inviteMemberModal'));
        modal.show();
    }}

    function renderInviteLinkAlert(alertEl, baseMsg, link, alertClass) {{
        if (!alertEl) return;
        alertEl.className = 'alert alert-' + alertClass;
        if (!link) {{
            alertEl.textContent = baseMsg;
            alertEl.classList.remove('d-none');
            return;
        }}
        const trunc = link.length > 52 ? (link.slice(0, 30) + '…' + link.slice(-18)) : link;
        alertEl.innerHTML = escapeHtml(baseMsg) +
            '<div class="input-group input-group-sm mt-2">' +
            '<input type="text" class="form-control font-monospace small" value="' + escapeHtmlBasic(link) + '" readonly title="' + escapeHtmlBasic(link) + '">' +
            '<button type="button" class="btn btn-outline-secondary" onclick="copyText(\\'' + escapeForJsAttr(link) + '\\')" title="Copy invite link"><i class="fas fa-copy"></i></button>' +
            '</div>' +
            '<div class="small text-muted mt-1 text-truncate" title="' + escapeHtmlBasic(link) + '">' + escapeHtmlBasic(trunc) + '</div>';
        alertEl.classList.remove('d-none');
    }}
    
    async function submitLayerInvite() {{
        const emailEl = document.getElementById('invite-member-email');
        const msgEl = document.getElementById('invite-member-message');
        const alertEl = document.getElementById('invite-member-alert');
        const btn = document.getElementById('invite-member-submit-btn');
        const rawInput = emailEl && emailEl.value ? emailEl.value.trim() : '';
        const message = msgEl && msgEl.value ? msgEl.value.trim() : '';
        if (alertEl) alertEl.classList.add('d-none');
        const shareUrl = document.getElementById('layer-invite-shareable-url');
        const isPublicLayer = project && (project.listing_visibility || 'public') === 'public';
        if (!rawInput && !isPublicLayer) {{
            if (alertEl) {{
                alertEl.textContent = 'Email address is required for private layers';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
            return;
        }}
        if (!rawInput && isPublicLayer && shareUrl && shareUrl.value) {{
            renderInviteLinkAlert(alertEl, 'Copy the shareable link above to invite anyone.', shareUrl.value, 'info');
            return;
        }}
        if (!rawInput) {{
            if (alertEl) {{
                alertEl.textContent = 'Enter an email or use the shareable link above';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
            return;
        }}

        const emails = rawInput.split(/[,;\\n]+/).map(e => e.trim()).filter(e => e.length > 0);
        if (emails.length === 0) {{
            if (alertEl) {{
                alertEl.textContent = 'Enter at least one valid email address';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
            return;
        }}

        if (btn) {{
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending ' + emails.length + '…';
        }}

        const results = [];
        for (const email of emails) {{
            try {{
                const res = await fetch('/api/layers/' + project.id + '/invitations/', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    credentials: 'same-origin',
                    body: JSON.stringify({{ email: email, message: message || null }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    if (data.duplicate) {{
                        results.push({{ email, status: 'duplicate', msg: 'Already a member' }});
                    }} else if (data.email_sent === false) {{
                        const path = data.invite_path || (data.invitation && data.invitation.token ? '/layer/invite/' + data.invitation.token + '/' : '');
                        results.push({{ email, status: 'link', msg: 'Email not sent – share link', link: path ? (window.location.origin + path) : '' }});
                    }} else {{
                        results.push({{ email, status: 'sent', msg: data.resent ? 'Resent' : 'Sent' }});
                    }}
                }} else {{
                    results.push({{ email, status: 'error', msg: data.error || 'Failed' }});
                }}
            }} catch (e) {{
                results.push({{ email, status: 'error', msg: e.message || 'Network error' }});
            }}
        }}

        const sent = results.filter(r => r.status === 'sent').length;
        const dupes = results.filter(r => r.status === 'duplicate').length;
        const errors = results.filter(r => r.status === 'error').length;
        const links = results.filter(r => r.status === 'link');

        let summaryHtml = '';
        if (sent > 0) summaryHtml += '<div class="text-success small"><i class="fas fa-check me-1"></i>' + sent + ' invitation' + (sent > 1 ? 's' : '') + ' sent</div>';
        if (dupes > 0) summaryHtml += '<div class="text-muted small"><i class="fas fa-info-circle me-1"></i>' + dupes + ' already member' + (dupes > 1 ? 's' : '') + '</div>';
        if (errors > 0) summaryHtml += '<div class="text-danger small"><i class="fas fa-times me-1"></i>' + errors + ' failed: ' + results.filter(r => r.status === 'error').map(r => r.email).join(', ') + '</div>';
        if (links.length > 0) {{
            summaryHtml += '<div class="text-warning small mt-1"><i class="fas fa-link me-1"></i>Email could not be sent for ' + links.length + '. Share links manually:</div>';
            links.forEach(r => {{
                if (r.link) summaryHtml += '<div class="small font-monospace text-truncate">' + escapeHtmlBasic(r.email) + ': <a href="' + escapeHtmlBasic(r.link) + '">' + escapeHtmlBasic(r.link) + '</a></div>';
            }});
        }}

        if (alertEl) {{
            alertEl.innerHTML = summaryHtml;
            alertEl.className = 'alert alert-' + (errors > 0 ? 'warning' : (dupes === results.length ? 'secondary' : 'success'));
            alertEl.classList.remove('d-none');
        }}
        if (errors === 0 && emailEl) emailEl.value = '';
        if (errors === 0 && msgEl) msgEl.value = '';

        if (btn) {{
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send invitation';
        }}
    }}
    
    function displayProjectHeader() {{
        const statusMap = {{'proposed':'<span class="badge bg-info ms-2">Proposed</span>','active':'<span class="badge bg-success ms-2">Active</span>','stabilizing':'<span class="badge bg-primary ms-2">Stabilizing</span>','maintaining':'<span class="badge bg-secondary ms-2">Maintaining</span>','dormant':'<span class="badge bg-warning ms-2">Dormant</span>','concluded':'<span class="badge bg-dark ms-2">Concluded</span>','archived':'<span class="badge bg-secondary ms-2">Archived</span>'}};
        const approvalMap = {{'pending':'<span class="badge bg-warning ms-2">Pending Approval</span>','approved':'<span class="badge bg-success ms-2">Approved</span>','rejected':'<span class="badge bg-danger ms-2">Rejected</span>'}};
        const statusBadge = (project.approval_status === 'approved' && project.status === 'proposed') ? '' : (statusMap[project.status] || (project.status ? '<span class="badge bg-secondary ms-2">' + escapeHtml(String(project.status)) + '</span>' : ''));
        const approvalBadge = approvalMap[project.approval_status] || (project.approval_status ? '<span class="badge bg-secondary ms-2">' + escapeHtml(String(project.approval_status)) + '</span>' : '');
        const showTags = !showCarousel;
        const isJoined = project.is_member || isProjectAdmin;
        let actionsHtml = '';
        if (isAuthenticated) {{
            if (isJoined) {{
                actionsHtml += '<div class="mb-3"><span class="badge bg-success">Joined</span></div>';
                if (!hideLayerEmailInvite()) {{
                    actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showInviteMemberModal()"><i class="fas fa-user-plus me-2"></i>Invite by email</button></div>';
                }}
            }} else {{
                actionsHtml += '<div class="mb-3"><button class="btn btn-primary btn-sm w-100" onclick="showJoinProjectModal()"><i class="fas fa-plus me-2"></i>Join Layer</button></div>';
            }}
        }} else if (referralRefToken && project && (project.join_policy || 'open') === 'open') {{
            const joinNext = encodeURIComponent(window.location.pathname + window.location.search);
            actionsHtml += '<div class="mb-3"><a href="/login/?next=' + joinNext + '" class="btn btn-primary btn-sm w-100"><i class="fas fa-sign-in-alt me-2"></i>Sign in to join</a></div>';
        }}
        actionsHtml += '<div class="mb-3"><a href="' + layerBase + 'connections/" class="btn btn-outline-primary btn-sm w-100"><i class="fas fa-handshake me-2"></i>Connect your organization</a></div>';
        actionsHtml += '<div class="mb-3"><a href="/workgroups/join/" class="btn btn-outline-success btn-sm w-100"><i class="fas fa-users-cog me-2"></i>Join a Workgroup</a></div>';
        if (isProjectAdmin) {{
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button></div>';
            actionsHtml += {json.dumps(create_quest_admin_btn)};
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showCreateVoteModal()"><i class="fas fa-vote-yea me-2"></i>Create Vote</button></div>';
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showEmailModal()"><i class="fas fa-envelope me-2"></i>Email</button></div>';
        }}
        actionsHtml += '<div class="mb-2"><a href="' + (showCarousel ? layerBase : '/layers/') + '" class="btn btn-outline-secondary btn-sm w-100"><i class="fas fa-arrow-left me-2"></i>' + (showCarousel ? 'Back to Layer' : 'Back to Layers') + '</a></div>';
        if (isProjectAdmin) {{
            actionsHtml += '<button type="button" class="btn btn-secondary btn-sm w-100" onclick="editProject()"><i class="fas fa-edit me-2"></i>Edit</button>';
        }}
        const layerImgSrc = project.image_url ? layerImageUrl(project.image_url, project) : '';
        const mediaHtml = layerImgSrc
            ? '<div class="living-layer-hero-media"><img src="' + layerImgSrc + '" alt="' + escapeHtmlBasic(project.name) + '" class="layer-hero-image layer-display-image"></div>'
            : '<div class="living-layer-hero-media"><i class="fas fa-layer-group fa-3x text-muted opacity-50"></i></div>';
        const missionHtml = project.mission
            ? '<p class="living-layer-hero-mission">' + escapeHtml(project.mission) + '</p>'
            : '';
        const descHtml = (!showCarousel && project.description)
            ? '<p class="living-layer-hero-desc">' + escapeHtml(project.description) + '</p>'
            : '';
        const pulseHtml = buildLayerPulseStrip();
        const titleEl = document.getElementById('project-title');
        if (titleEl) titleEl.innerHTML = '';
        const heroCore =
            '<div class="living-layer-hero">' +
            '<div class="living-layer-hero-inner">' +
            mediaHtml +
            '<div class="living-layer-hero-body">' +
            '<h1>' + escapeHtml(project.name) + '</h1>' +
            (showTags ? '<div class="mb-2">' + statusBadge + approvalBadge + '</div>' : '') +
            missionHtml + descHtml + pulseHtml +
            '</div>' +
            '<div class="living-layer-hero-actions">' + actionsHtml + '</div>' +
            '</div></div>';
        if (showCarousel) {{
            document.getElementById('project-header').innerHTML =
                heroCore +
                '<div class="row mt-3"><div class="col-12"><div id="carousel-container"></div></div></div>';
        }} else {{
            document.getElementById('project-header').innerHTML = heroCore;
        }}
    }}

    function buildLayerPulseStrip() {{
        const chips = [];
        if (isLayerFeatureOn('workgroups')) chips.push('<span class="living-layer-pulse-chip is-live">Workgroups</span>');
        if (isLayerFeatureOn('roles')) chips.push('<span class="living-layer-pulse-chip is-live">Roles</span>');
        if (isLayerFeatureOn('guilds')) chips.push('<span class="living-layer-pulse-chip is-live">Guilds</span>');
        if (isLayerFeatureOn('waitlists')) chips.push('<span class="living-layer-pulse-chip is-live">Waitlists</span>');
        if (isLayerFeatureOn('docs')) chips.push('<span class="living-layer-pulse-chip is-live">Docs</span>');
        if (isLayerFeatureOn('votes')) chips.push('<span class="living-layer-pulse-chip">Votes</span>');
        if (isLayerFeatureOn('artifacts')) chips.push('<span class="living-layer-pulse-chip">Artifacts</span>');
        if (isLayerFeatureOn('badges')) chips.push('<span class="living-layer-pulse-chip">Badges</span>');
        if (!chips.length) return '';
        return '<div class="living-layer-pulse-strip">' + chips.join('') + '</div>';
    }}
    
    function livingModule(icon, title, bodyHtml, spanFull) {{
        const spanCls = spanFull ? ' living-module-span-2' : '';
        return '<div class="living-module' + spanCls + '">' +
            '<div class="living-module-header"><div class="living-module-icon"><i class="fas ' + icon + '"></i></div>' +
            '<h5 class="living-module-title">' + title + '</h5></div>' +
            '<div class="living-module-body">' + bodyHtml + '</div></div>';
    }}

    function livingModuleStatLink(tabKey, label, countId, countInitial) {{
        const countVal = countInitial != null ? String(countInitial) : '…';
        const countAttrs = countId ? ' id="' + countId + '"' : '';
        return '<a href="#' + tabKey + '" class="living-module-stat-link" data-layer-tab="' + tabKey + '" onclick="switchToTab(\\'' + tabKey + '\\'); return false;">' +
            '<span class="living-module-stat-value"' + countAttrs + '>' + countVal + '</span>' +
            '<span class="living-module-stat-text">' + escapeHtml(label) + '</span></a>';
    }}

    function loadOverview() {{
        const statusEsc = escapeHtml(String(project.status || ''));
        const approvalEsc = escapeHtml(String(project.approval_status || ''));
        const createdStr = project.created_at ? new Date(project.created_at).toLocaleDateString() : '–';
        const lastActivityStr = project.last_activity_at ? new Date(project.last_activity_at).toLocaleDateString() : 'Never';
        const wgCount = project.workgroups_count || 0;
        const modules = [];
        let pulseBody = '';
        const pulseStats = [];
        if (isLayerFeatureOn('workgroups')) {{
            pulseStats.push(livingModuleStatLink('workgroups', 'Workgroups', null, wgCount));
        }}
        if (isLayerFeatureOn('roles')) {{
            pulseStats.push(livingModuleStatLink('roles', 'Roles', 'roles-count'));
            pulseStats.push(livingModuleStatLink('claims', 'Active claims', 'claims-count'));
        }}
        if (pulseStats.length) {{
            pulseBody += '<div class="living-module-stat-list">' + pulseStats.join('') + '</div>';
        }}
        if (pulseBody) modules.push(livingModule('fa-heartbeat', 'Layer pulse', pulseBody, false));
        modules.push(livingModule('fa-info-circle', 'Layer info',
            '<p class="small mb-1"><strong>Status:</strong> ' + statusEsc + '</p>' +
            '<p class="small mb-1"><strong>Approval:</strong> ' + approvalEsc + '</p>' +
            '<p class="small mb-1"><strong>Created:</strong> ' + createdStr + '</p>' +
            '<p class="small mb-0"><strong>Last activity:</strong> ' + lastActivityStr + '</p>', false));
        if (isLayerFeatureOn('guilds')) {{
            modules.push(livingModule('fa-users', 'Affiliated guilds',
                '<div id="overview-guilds-body"><div class="text-center py-2"><div class="spinner-border spinner-border-sm text-secondary"></div></div></div>', false));
        }}
        if (isLayerFeatureOn('waitlists')) {{
            modules.push(livingModule('fa-list-alt', 'Waitlists',
                '<div id="overview-waitlists-body"><div class="text-center py-2"><div class="spinner-border spinner-border-sm text-secondary"></div></div></div>', false));
        }}
        modules.push(livingModule('fa-stream', 'Recent activity',
            '<div id="activity-feed-container" class="living-module-activity"><div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div></div></div>', true));
        const gridCls = modules.length > 3 ? ' living-modules-grid--wide' : '';
        document.getElementById('overview-content').innerHTML =
            '<div class="living-modules-grid' + gridCls + '">' + modules.join('') + '</div>';
        if (showCarousel) loadCarousel();
        if (isLayerFeatureOn('roles')) loadRolesCounts();
        loadActivityFeed();
        if (isLayerFeatureOn('guilds')) loadOverviewGuilds();
        if (isLayerFeatureOn('waitlists')) loadOverviewWaitlists();
    }}

    async function loadOverviewWaitlists() {{
        const el = document.getElementById('overview-waitlists-body');
        if (!el || !project) return;
        try {{
            const r = await fetch('/api/layers/' + project.id + '/waitlists/', {{ credentials: 'same-origin' }});
            const d = await r.json();
            const list = d.waitlists || [];
            if (!list.length) {{
                el.innerHTML = '<p class="text-muted small mb-0">No waitlists yet.</p>';
                return;
            }}
            let html = '<ul class="list-unstyled small mb-0">';
            list.slice(0, 4).forEach(function(w) {{
                html += '<li class="mb-2"><a href="#" class="text-decoration-none" onclick="document.getElementById(\\'waitlist-tab-' + w.id + '\\')?.click(); return false;">' +
                    escapeHtmlBasic(w.name || 'Waitlist') + '</a>';
                if (w.active) html += ' <span class="badge bg-success">Active</span>';
                html += '</li>';
            }});
            if (list.length > 4) html += '<li class="text-muted">+' + (list.length - 4) + ' more</li>';
            html += '</ul>';
            el.innerHTML = html;
        }} catch (e) {{
            el.innerHTML = '<p class="text-muted small mb-0">Could not load waitlists.</p>';
        }}
    }}
    
    async function loadOverviewGuilds() {{
        const el = document.getElementById('overview-guilds-body');
        if (!el || !project) return;
        try {{
            const r = await fetch('/api/layers/' + project.id + '/guilds/', {{ credentials: 'same-origin' }});
            const d = await r.json();
            const links = d.links || [];
            if (links.length === 0) {{
                el.innerHTML = '<p class="text-muted small mb-0">No affiliated guilds yet.</p>';
                return;
            }}
            let h = '<ul class="list-unstyled mb-0">';
            links.forEach(lnk => {{
                const g = lnk.guild || {{}};
                const name = escapeHtmlBasic(g.name || 'Guild');
                const slug = escapeHtmlBasic(g.slug || '');
                h += '<li class="mb-1"><a href="/guilds/' + slug + '/">' + name + '</a></li>';
            }});
            h += '</ul>';
            el.innerHTML = h;
        }} catch (e) {{
            el.innerHTML = '<p class="text-muted small mb-0">Unable to load guilds.</p>';
        }}
    }}
    
    async function loadCarousel() {{
        const container = document.getElementById('carousel-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/carousel/');
            const data = await res.json();
            const items = data.items || [];
            if (items.length === 0) {{
                if (project.image_url) {{
                    container.innerHTML = '';
                    return;
                }}
                container.innerHTML = '<div class="rounded p-4 text-center text-muted" style="background: var(--bg-secondary);"><p class="mb-0">No featured items yet. Drafts, roles, and opportunities will appear here.</p></div>';
                return;
            }}
            const imgPlaceholder = 'background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--border-color) 100%); color: var(--text-muted);';
            if (showCarousel) {{
                let slidesHtml = '';
                items.forEach((it, i) => {{
                    const isDraft = it.type === 'draft';
                    const hasAbstract = isDraft && it.description;
                    let img = '';
                    if (it.image) {{
                        img = '<img src="' + escapeHtmlBasic(it.image) + '" alt="" class="w-100" style="height:200px;object-fit:cover;">';
                    }} else if (hasAbstract) {{
                        img = '';
                    }} else {{
                        img = '<div class="d-flex align-items-center justify-content-center rounded-top" style="height:160px;' + imgPlaceholder + '"><i class="fas fa-' + (it.type === 'role' ? 'user-tag' : it.type === 'opportunity' ? 'bullseye' : 'file-alt') + ' fa-3x opacity-50"></i></div>';
                    }}
                    const descLen = hasAbstract ? 800 : 200;
                    const descHtml = it.description ? '<div class="mt-2"><p class="text-muted mb-0" style="white-space:pre-wrap;line-height:1.5;">' + escapeHtmlBasic((it.description || '').slice(0, descLen)) + (it.description && it.description.length > descLen ? '…' : '') + '</p></div>' : '';
                    let href = it.link ? escapeHtmlBasic(it.link) : '';
                    if (href && href.indexOf('/layers/') === 0 && href.includes('/#')) {{ href = href.replace('/layers/', '/layer/').replace('/#', '/'); if (!href.endsWith('/')) href += '/'; }}
                    const link = href ? 'href="' + href + '" class="text-decoration-none"' : '';
                    const bodyCls = hasAbstract ? 'p-4' : 'p-4';
                    slidesHtml += '<div class="carousel-slide" data-index="' + i + '" style="display:none;width:100%;max-width:720px;margin:0 auto;">' + (link ? '<a ' + link + ' style="color:inherit;">' : '') + '<div class="card overflow-hidden" style="background:transparent;border:none;">' + img + '<div class="card-body ' + bodyCls + '"><h5 class="mb-2">' + escapeHtmlBasic((it.title || '').slice(0, 100)) + '</h5>' + descHtml + '</div></div>' + (link ? '</a>' : '') + '</div>';
                }});
                container.innerHTML = '<style>.carousel-hero .carousel-prev, .carousel-hero .carousel-next {{ opacity: 0; transition: opacity 0.2s ease; }} .carousel-hero:hover .carousel-prev, .carousel-hero:hover .carousel-next {{ opacity: 1; }}</style>' +
                    '<div class="carousel-hero position-relative rounded overflow-hidden d-flex flex-column" style="background: var(--bg-secondary); min-height: 50vh;">' +
                    '<div class="carousel-slides flex-grow-1 d-flex align-items-center px-5" style="padding-left: 56px !important; padding-right: 56px !important;">' + slidesHtml + '</div>' +
                    '<button type="button" class="carousel-prev btn btn-light position-absolute top-50 start-0 translate-middle-y ms-2 rounded-circle shadow" style="width:44px;height:44px;z-index:2;" aria-label="Previous"><i class="fas fa-chevron-left"></i></button>' +
                    '<button type="button" class="carousel-next btn btn-light position-absolute top-50 end-0 translate-middle-y me-2 rounded-circle shadow" style="width:44px;height:44px;z-index:2;" aria-label="Next"><i class="fas fa-chevron-right"></i></button>' +
                    '<div class="carousel-dots position-absolute bottom-0 start-0 end-0 py-2 d-flex justify-content-center gap-2" style="z-index:2;"></div>' +
                    '</div>';
                const slides = container.querySelectorAll('.carousel-slide');
                const dots = container.querySelector('.carousel-dots');
                items.forEach((_, i) => {{ dots.innerHTML += '<button type="button" class="carousel-dot btn btn-sm rounded-circle p-0 ' + (i === 0 ? 'bg-primary' : 'bg-secondary') + '" data-index="' + i + '" style="width:8px;height:8px;" aria-label="Slide ' + (i+1) + '"></button>'; }});
                let idx = 0;
                function showSlide(i) {{ idx = ((i % items.length) + items.length) % items.length; slides.forEach((s, j) => {{ s.style.display = j === idx ? 'block' : 'none'; }}); container.querySelectorAll('.carousel-dot').forEach((d, j) => {{ d.className = 'carousel-dot btn btn-sm rounded-circle p-0 ' + (j === idx ? 'bg-primary' : 'bg-secondary'); }}); }}
                showSlide(0);
                container.querySelector('.carousel-prev').addEventListener('click', () => showSlide(idx - 1));
                container.querySelector('.carousel-next').addEventListener('click', () => showSlide(idx + 1));
                container.querySelectorAll('.carousel-dot').forEach(d => {{ d.addEventListener('click', () => showSlide(parseInt(d.getAttribute('data-index'), 10))); }});
            }}
        }} catch (e) {{
            console.error('loadCarousel:', e);
        }}
    }}
    
    function reportContributionFilterApplied(kf) {{
        if (!project || !project.id) return;
        fetch('/api/layers/' + project.id + '/contribution-type-filter/', {{
            method: 'POST',
            credentials: 'same-origin',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ knowledge_form: kf || null }})
        }}).catch(function() {{}});
    }}
    
    function ensureArtifactFilterBar() {{
        const container = document.getElementById('artifacts-tab-container');
        if (!container || container.dataset.klFilterBar) return;
        container.dataset.klFilterBar = '1';
        const wrap = document.createElement('div');
        wrap.id = 'artifact-filter-bar';
        wrap.className = 'mb-3';
        const kfRow = document.createElement('div');
        kfRow.className = 'd-flex flex-wrap gap-1 align-items-center mb-2';
        const forms = ['', 'inquiry', 'principle', 'model', 'claim', 'decision', 'gloss', 'scenario'];
        let btns = '<span class="small text-muted me-2">Contribution:</span>';
        forms.forEach(function(kf, i) {{
            const label = kf || 'All';
            btns += '<button type="button" class="btn btn-sm btn-outline-secondary artifact-kf-btn' + (i === 0 ? ' active' : '') + '" data-kf="' + kf + '">' + label + '</button>';
        }});
        kfRow.innerHTML = btns;
        wrap.appendChild(kfRow);
        const tagRow = document.createElement('div');
        tagRow.id = 'artifact-tag-filter-row';
        tagRow.className = 'd-flex flex-wrap gap-1 align-items-center';
        tagRow.innerHTML = '<span class="small text-muted me-2">Tags:</span><span class="small text-muted">Loading…</span>';
        wrap.appendChild(tagRow);
        container.parentNode.insertBefore(wrap, container);
        wrap.querySelectorAll('.artifact-kf-btn').forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                wrap.querySelectorAll('.artifact-kf-btn').forEach(function(b) {{ b.classList.remove('active'); }});
                btn.classList.add('active');
                artifactKnowledgeFilter = btn.getAttribute('data-kf') || '';
                reportContributionFilterApplied(artifactKnowledgeFilter);
                loadArtifacts();
            }});
        }});
        loadArtifactTagFilterChips();
    }}

    async function loadArtifactTagFilterChips() {{
        const row = document.getElementById('artifact-tag-filter-row');
        if (!row || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/artifact-tags/', {{ credentials: 'same-origin' }});
            const data = await res.json();
            if (!res.ok || !data.enabled) {{
                row.style.display = 'none';
                return;
            }}
            const tags = data.tags || [];
            if (tags.length === 0) {{
                row.innerHTML = '<span class="small text-muted">Tags: none yet</span>';
                return;
            }}
            let html = '<span class="small text-muted me-2">Tags:</span>';
            html += '<button type="button" class="btn btn-sm btn-outline-secondary artifact-tag-btn' + (artifactTagFilters.length === 0 ? ' active' : '') + '" data-tag="">All</button>';
            tags.forEach(function(t) {{
                const slug = t.slug || '';
                const active = artifactTagFilters.indexOf(slug) >= 0 ? ' active' : '';
                const label = escapeHtmlBasic(t.label || slug);
                const count = t.artifact_count != null ? ' (' + t.artifact_count + ')' : '';
                html += '<button type="button" class="btn btn-sm btn-outline-secondary artifact-tag-btn' + active + '" data-tag="' + escapeHtmlBasic(slug) + '">' + label + count + '</button>';
            }});
            row.innerHTML = html;
            row.querySelectorAll('.artifact-tag-btn').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    const slug = btn.getAttribute('data-tag') || '';
                    if (!slug) {{
                        artifactTagFilters = [];
                    }} else {{
                        const idx = artifactTagFilters.indexOf(slug);
                        if (idx >= 0) artifactTagFilters.splice(idx, 1);
                        else artifactTagFilters.push(slug);
                    }}
                    loadArtifactTagFilterChips();
                    loadArtifacts();
                }});
            }});
        }} catch (e) {{
            row.innerHTML = '<span class="small text-muted">Tags unavailable</span>';
        }}
    }}
    
    async function loadDocs() {{
        const container = document.getElementById('docs-tab-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/docs/', {{ credentials: 'same-origin' }});
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load docs.</p>';
                return;
            }}
            const docs = data.docs || [];
            if (docs.length === 0) {{
                container.innerHTML = '<p class="text-muted small mb-0">No drafts yet. Submit a draft from a workgroup or the global submit form to see it here.</p>';
                return;
            }}
            const statusMap = {{
                approved: 'bg-success',
                submitted: 'bg-warning text-dark',
                rejected: 'bg-danger',
            }};
            const statusLabel = {{
                approved: 'Approved',
                submitted: 'Pending',
                rejected: 'Rejected',
            }};
            const rows = docs.map(function (d) {{
                const statusKey = (d.status || '').toLowerCase();
                const badgeCls = statusMap[statusKey] || 'bg-secondary';
                const badgeText = statusLabel[statusKey] || (d.status || '–');
                const ref = d.draft_name || d.id;
                const href = '/doc/draft/' + encodeURIComponent(ref) + '/';
                const title = (d.title || ref).toString();
                const safeTitle = title.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                const ml = d.ml_number ? '<span class="badge bg-info flex-shrink-0">' + d.ml_number + '</span>' : '';
                const submitter = d.submitted_by ? '<span class="text-muted small">' + d.submitted_by + '</span>' : '';
                return (
                    '<li class="list-group-item px-0 py-2 border-bottom">' +
                    '<div class="d-flex align-items-center gap-2 text-nowrap" style="min-width:0">' +
                    ml +
                    '<a href="' + href + '" class="text-decoration-none text-truncate flex-grow-1" style="min-width:0" title="' + safeTitle + '">' + safeTitle + '</a>' +
                    submitter +
                    '<span class="badge ' + badgeCls + ' flex-shrink-0">' + badgeText + '</span>' +
                    '</div></li>'
                );
            }}).join('');
            container.innerHTML = '<ul class="list-group list-group-flush">' + rows + '</ul>';
        }} catch (err) {{
            console.error('loadDocs:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load docs.</p>';
        }}
    }}

    async function loadArtifacts() {{
        const container = document.getElementById('artifacts-tab-container');
        if (!container || !project) return;
        ensureArtifactFilterBar();
        try {{
            let url = '/api/layers/' + project.id + '/artifacts/';
            const params = [];
            if (artifactKnowledgeFilter) params.push('knowledge_form=' + encodeURIComponent(artifactKnowledgeFilter));
            if (artifactTagFilters.length) params.push('tags=' + encodeURIComponent(artifactTagFilters.join(',')));
            if (params.length) url += '?' + params.join('&');
            const res = await fetch(url, {{ credentials: 'same-origin' }});
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load artifacts.</p>';
                return;
            }}
            const arts = data.artifacts || [];
            if (arts.length === 0) {{
                let msg = 'No artifacts yet. Submissions and quest outputs create artifacts.';
                if (artifactKnowledgeFilter) msg = 'No artifacts with this contribution type.';
                else if (artifactTagFilters.length) msg = 'No artifacts match the selected tags.';
                container.innerHTML = '<p class="text-muted small mb-0">' + msg + '</p>';
                return;
            }}
            let html = '<ul class="list-group list-group-flush artifact-list-rows">';
            arts.forEach(a => {{
                const ref = a.public_ref || a.id;
                const fullTitle = a.title || a.public_ref || 'Untitled';
                const title = escapeHtmlBasic(fullTitle);
                const kf = a.knowledge_form;
                const kfBadge = kf ? '<span class="badge text-bg-info flex-shrink-0">' + escapeHtmlBasic(kf) + '</span>' : '';
                const tags = a.tags || [];
                let tagHtml = '';
                tags.forEach(function(t) {{
                    const slug = t.slug || '';
                    tagHtml += '<span class="badge bg-light text-dark border flex-shrink-0 me-1">' + escapeHtmlBasic(t.label || slug) + '</span>';
                }});
                const statusCls = (a.status === 'approved' || a.status === 'adopted') ? 'success' : (a.status === 'submitted' ? 'info' : 'secondary');
                html += '<li class="list-group-item px-0 py-2 border-bottom"><div class="d-flex align-items-center gap-2 text-nowrap" style="min-width:0">';
                html += kfBadge;
                html += '<a href="' + layerBase + 'artifacts/' + ref + '/" class="text-decoration-none text-truncate flex-grow-1" style="min-width:0" title="' + title + '">' + title + '</a>';
                html += tagHtml;
                html += '<span class="badge bg-' + statusCls + ' flex-shrink-0">' + (a.status || 'draft') + '</span>';
                html += '</div></li>';
            }});
            html += '</ul>';
            container.innerHTML = html;
        }} catch (err) {{
            console.error('loadArtifacts:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load artifacts.</p>';
        }}
    }}
    
    async function loadOpportunities() {{
        const container = document.getElementById('opportunities-container') || document.getElementById('opportunities-content') || document.getElementById('opportunities-tab-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/opportunities/');
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load opportunities.</p>';
                return;
            }}
            const ms = data.missing_support || [];
            const mo = data.missing_opposition || [];
            const oq = isLayerFeatureOn('quests') ? (data.open_quests || []) : [];
            if (ms.length === 0 && mo.length === 0 && oq.length === 0) {{
                const emptyMsg = isLayerFeatureOn('quests')
                    ? 'All drafts have support and opposition. No open quests. Great participation!'
                    : 'All drafts have support and opposition.';
                container.innerHTML = '<p class="text-muted small mb-0">' + emptyMsg + '</p>';
                return;
            }}
            let html = '<div class="row">';
            if (ms.length > 0) {{
                html += '<div class="col-md-6"><h6 class="text-success"><i class="fas fa-thumbs-up me-1"></i>Drafts needing support</h6><ul class="list-unstyled small">';
                ms.slice(0, 5).forEach(a => {{
                    html += '<li class="mb-1"><a href="/doc/draft/' + (a.draft_id || a.id) + '/" class="text-decoration-none">' + escapeHtmlBasic(a.title || 'Untitled') + '</a></li>';
                }});
                if (ms.length > 5) html += '<li class="text-muted">+' + (ms.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            if (mo.length > 0) {{
                html += '<div class="col-md-6"><h6 class="text-danger"><i class="fas fa-thumbs-down me-1"></i>Drafts needing opposition</h6><ul class="list-unstyled small">';
                mo.slice(0, 5).forEach(a => {{
                    html += '<li class="mb-1"><a href="/doc/draft/' + (a.draft_id || a.id) + '/" class="text-decoration-none">' + escapeHtmlBasic(a.title || 'Untitled') + '</a></li>';
                }});
                if (mo.length > 5) html += '<li class="text-muted">+' + (mo.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            if (isLayerFeatureOn('quests') && oq.length > 0) {{
                html += '<div class="col-12 mt-2"><h6 class="text-primary"><i class="fas fa-tasks me-1"></i>Open quests</h6><ul class="list-unstyled small">';
                oq.slice(0, 5).forEach(q => {{
                    html += '<li class="mb-1"><span class="badge bg-secondary me-1">' + escapeHtmlBasic(q.quest_type || 'quest') + '</span><a href="' + layerBase + 'quests/' + q.id + '/" class="text-decoration-none">' + escapeHtmlBasic(q.title || 'Untitled') + '</a></li>';
                }});
                if (oq.length > 5) html += '<li class="text-muted">+' + (oq.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            html += '</div>';
            container.innerHTML = html;
        }} catch (err) {{
            console.error('loadOpportunities:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load opportunities.</p>';
        }}
    }}
    
    function formatActivityEvent(ev) {{
        const who = ev.actor_display_name || (ev.actor_type === 'user' ? 'A member' : ev.actor_type === 'anonymous' ? 'Someone' : 'System');
        const p = ev.payload || {{}};
        const timeAgo = (d) => {{
            const s = Math.floor((Date.now() - new Date(d)) / 1000);
            if (s < 60) return 'just now';
            if (s < 3600) return Math.floor(s/60) + 'm ago';
            if (s < 86400) return Math.floor(s/3600) + 'h ago';
            if (s < 604800) return Math.floor(s/86400) + 'd ago';
            return new Date(d).toLocaleDateString();
        }};
        let text = '';
        let tabId = null;
        switch (ev.event_type) {{
            case 'member_joined': text = who + ' joined as ' + (p.role || 'contributor'); break;
            case 'member_removed': text = who + ' left the layer'; break;
            case 'role_claimed': text = who + ' claimed a role'; tabId = 'claims'; break;
            case 'badge_nominated': text = who + ' was nominated for a badge'; tabId = 'claims'; break;
            case 'badge_approved': text = who + ' received a badge'; tabId = 'claims'; break;
            case 'badge_rejected': text = 'A badge request was rejected'; break;
            case 'vote_started': text = 'Vote started: ' + (p.title || 'Vote'); tabId = 'votes'; break;
            case 'vote_closed': text = 'Vote closed' + (p.result ? ' (' + p.result + ')' : ''); tabId = 'votes'; break;
            case 'ballot_cast': text = who + ' cast a ballot'; break;
            case 'layer_config_changed': text = who + ' updated layer settings'; break;
            case 'waitlist_joined': text = (ev.actor_type === 'email' ? 'Someone' : who) + ' joined waitlist' + (p.waitlist_name ? ': ' + p.waitlist_name : ''); break;
            case 'waitlist_left': text = who + ' left waitlist' + (p.waitlist_name ? ': ' + p.waitlist_name : ''); break;
            case 'artifact_created': text = p.artifact_type === 'submission' ? 'A draft was submitted' : p.artifact_type === 'support' ? who + ' added support' : p.artifact_type === 'opposition' ? who + ' added opposition' : 'New artifact created'; tabId = 'artifacts'; break;
            case 'artifact_updated': text = who + ' updated an artifact'; tabId = 'artifacts'; break;
            case 'artifact_status_changed': text = who + ' changed artifact status: ' + (p.old_status || '') + ' → ' + (p.new_status || ''); tabId = 'artifacts'; break;
            case 'artifact_linked': text = who + ' linked artifacts' + (p.relation_type ? ' (' + p.relation_type + ')' : ''); tabId = 'artifacts'; break;
            case 'contribution_type_set': text = (p.source === 'moderation' ? who + ' set contribution type (moderation): ' : who + ' set contribution type: ') + (p.knowledge_form || ''); tabId = 'artifacts'; break;
            case 'contribution_type_cleared': text = (p.source === 'moderation' ? who + ' cleared contribution type (moderation)' : who + ' cleared contribution type'); tabId = 'artifacts'; break;
            case 'contribution_type_filter_applied': text = who + ' filtered artifacts by contribution' + (p.knowledge_form ? ': ' + p.knowledge_form : ' (all)'); tabId = 'artifacts'; break;
            case 'guild_layer_linked': text = who + ' linked guild' + (p.guild_name ? ' "' + p.guild_name + '"' : '') + ' to this layer'; break;
            case 'guild_layer_unlinked': text = who + ' unlinked guild' + (p.guild_name ? ' "' + p.guild_name + '"' : '') + ' from this layer'; break;
            case 'guild_artifact_linked': text = who + ' linked a guild to an artifact as ' + (p.link_type || 'link'); tabId = 'artifacts'; break;
            case 'guild_artifact_unlinked': text = who + ' removed a guild ' + (p.link_type || '') + ' link from an artifact'; tabId = 'artifacts'; break;
            case 'guild_quest_linked': text = who + ' linked a guild to a quest as ' + (p.link_type || 'link'); tabId = 'opportunities'; break;
            case 'guild_quest_unlinked': text = who + ' removed a guild quest link (' + (p.link_type || '') + ')'; tabId = 'opportunities'; break;
            case 'brick_placed': text = who + ' placed a brick on Civic Mason'; break;
            default: text = ev.event_type.replace(/_/g, ' ');
        }}
        return {{ text, tabId, timeAgo: timeAgo(ev.created_at) }};
    }}
    
    async function loadActivityFeed() {{
        const container = document.getElementById('activity-feed-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/activity/?limit=15');
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load activity.</p>';
                return;
            }}
            const events = data.events || [];
            if (events.length === 0) {{
                container.innerHTML = '<p class="text-muted small mb-0">No activity yet. Join the layer or claim a role to get started.</p>';
                return;
            }}
            let html = '<ul class="list-unstyled mb-0">';
            events.forEach(ev => {{
                const {{ text, tabId, timeAgo }} = formatActivityEvent(ev);
                html += '<li class="d-flex justify-content-between align-items-start py-2 border-bottom border-light">';
                html += '<span class="small">' + (tabId ? '<span class="text-decoration-none activity-tab-link link-primary" style="cursor:pointer" data-tab="' + tabId + '">' + escapeHtmlBasic(text) + '</span>' : escapeHtmlBasic(text)) + '</span>';
                html += '<span class="text-muted small ms-2">' + timeAgo + '</span>';
                html += '</li>';
            }});
            html += '</ul>';
            container.innerHTML = html;
            container.querySelectorAll('.activity-tab-link[data-tab]').forEach(function(el) {{
                el.addEventListener('click', function(e) {{
                    e.preventDefault();
                    const tab = this.getAttribute('data-tab');
                    if (showCarousel) {{
                        window.location.href = '/layer/' + projectSlug + '/' + tab + '/';
                    }} else {{
                        switchToTab(tab);
                    }}
                }});
            }});
        }} catch (err) {{
            console.error('loadActivityFeed:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load activity.</p>';
        }}
    }}
    
    async function loadRolesCounts() {{
        try {{
            const rolesResp = await fetch('/api/layers/' + project.id + '/roles/');
            const rolesData = await rolesResp.json();
            document.getElementById('roles-count').textContent = rolesData.count;
            
            const claimsResp = await fetch('/api/layers/' + project.id + '/claims/?status=active');
            const claimsData = await claimsResp.json();
            document.getElementById('claims-count').textContent = claimsData.count;
        }} catch (error) {{
            console.error('Error loading counts:', error);
        }}
    }}
    
    async function loadVotes() {{
        const container = document.getElementById('votes-content');
        if (!container || !project) {{
            console.log('loadVotes: container or project missing', {{container: !!container, project: !!project}});
            return;
        }}
        container.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
        try {{
            console.log('loadVotes: fetching from /api/layers/' + project.id + '/votes/');
            const res = await fetch('/api/layers/' + project.id + '/votes/');
            console.log('loadVotes: response status', res.status, res.ok);
            
            const data = await res.json();
            console.log('loadVotes: received data', data);
            
            if (!res.ok) {{
                console.error('loadVotes: API error', res.status, data.error || 'Unknown error');
                container.innerHTML = '<div class="alert alert-danger">Error loading votes: ' + (data.error || 'HTTP ' + res.status) + '</div>';
                return;
            }}
            const votes = data.votes || [];
            if (votes.length === 0) {{
                container.innerHTML = '<div class="alert alert-info">No votes yet. Layer admins can create a vote using the Create Vote button above.</div>';
                return;
            }}
            let html = '<div class="list-group">';
            votes.forEach(v => {{
                const statusBadge = v.status === 'active' ? '<span class="badge bg-success">Active</span>' : v.status === 'closed' ? '<span class="badge bg-secondary">Closed</span>' : v.status === 'scheduled' ? '<span class="badge bg-info">Scheduled</span>' : '<span class="badge bg-warning">' + (v.status || '') + '</span>';
                const resultBadge = v.result ? '<span class="badge bg-' + (v.result === 'passed' ? 'success' : v.result === 'failed' ? 'danger' : v.result === 'no_quorum' ? 'warning' : 'secondary') + ' ms-1">' + v.result + '</span>' : '';
                html += '<a href="/votes/' + v.public_id + '/" class="list-group-item list-group-item-action">';
                html += '<div class="d-flex w-100 justify-content-between"><h6 class="mb-1">' + escapeHtmlBasic(v.title) + '</h6>' + statusBadge + resultBadge + '</div>';
                html += '<p class="mb-1 small text-muted">' + escapeHtmlBasic(v.description || '') + '</p>';
                html += '<small>Start: ' + new Date(v.start_at).toLocaleString() + ' &middot; End: ' + new Date(v.end_at).toLocaleString() + '</small>';
                html += '</a>';
            }});
            html += '</div>';
            container.innerHTML = html;
        }} catch (error) {{
            console.error('Error loading votes:', error);
            container.innerHTML = '<div class="alert alert-danger">Error loading votes: ' + error.message + '</div>';
        }}
    }}
    
    function toggleVoteTypeFields() {{
        const isElection = document.getElementById('vote-type-election')?.checked;
        const subSec = document.getElementById('vote-submission-section');
        const roleSec = document.getElementById('vote-role-section');
        const subSelect = document.getElementById('vote-submission-id');
        if (subSec) subSec.classList.toggle('d-none', !!isElection);
        if (roleSec) roleSec.classList.toggle('d-none', !isElection);
        if (subSelect) subSelect.required = !isElection;
    }}
    
    async function showCreateVoteModal() {{
        document.getElementById('create-vote-alert').classList.add('d-none');
        document.getElementById('createVoteForm').reset();
        document.getElementById('vote-type-approval').checked = true;
        toggleVoteTypeFields();
        
        // Set timezone labels (handle both modal variants)
        const tzAbbr = new Date().toLocaleTimeString('en-us', {{timeZoneName:'short'}}).split(' ').pop();
        const startLabel = document.getElementById('timezone-start') || document.getElementById('timezone-start-at');
        const endLabel = document.getElementById('timezone-end') || document.getElementById('timezone-end-at');
        if (startLabel) startLabel.textContent = tzAbbr || 'your local time';
        if (endLabel) endLabel.textContent = tzAbbr || 'your local time';
        
        // Set default times: next hour + 7 days
        const now = new Date();
        const nextHour = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours() + 1, 0, 0);
        const sevenDaysLater = new Date(nextHour.getTime() + 7 * 24 * 60 * 60 * 1000);
        
        const formatDatetimeLocal = (d) => {{
            const pad = (n) => String(n).padStart(2, '0');
            return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
        }};
        
        // Set default times (handle both modal variants)
        const startInput = document.getElementById('vote-start') || document.getElementById('vote-start-at');
        const endInput = document.getElementById('vote-end') || document.getElementById('vote-end-at');
        if (startInput) startInput.value = formatDatetimeLocal(nextHour);
        if (endInput) endInput.value = formatDatetimeLocal(sevenDaysLater);
        document.getElementById('vote-quorum').value = '1';
        document.getElementById('vote-threshold').value = '0.5';
        
        // Load submissions for this project
        const submissionSelect = document.getElementById('vote-submission-id');
        submissionSelect.innerHTML = '<option value="">Loading...</option>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/submissions/');
            const data = await res.json();
            const submissions = data.submissions || [];
            if (submissions.length === 0) {{
                submissionSelect.innerHTML = '<option value="">No approved drafts available</option>';
            }} else {{
                submissionSelect.innerHTML = '<option value="">Select a draft...</option>';
                submissions.forEach(s => {{
                    const label = s.ml_number ? (s.ml_number + ' - ' + (s.title || '')) : ((s.title || '') + ' (' + s.id + ')');
                    submissionSelect.innerHTML += '<option value="' + escapeHtmlBasic(String(s.id)) + '">' + escapeHtmlBasic(label) + '</option>';
                }});
            }}
        }} catch (e) {{
            submissionSelect.innerHTML = '<option value="">Error loading drafts</option>';
        }}
        
        // Load roles for election
        const roleSelect = document.getElementById('vote-role-id');
        if (roleSelect) {{
            roleSelect.innerHTML = '<option value="">Loading...</option>';
            try {{
                const rRes = await fetch('/api/layers/' + project.id + '/roles/');
                const rData = await rRes.json();
                const roles = rData.roles || [];
                roleSelect.innerHTML = '<option value="">Select a role...</option>';
                roles.forEach(r => {{
                    const lab = r.requires_election ? r.title_guild + ' (requires election)' : r.title_guild;
                    roleSelect.innerHTML += '<option value="' + escapeHtmlBasic(String(r.id)) + '">' + escapeHtmlBasic(lab) + '</option>';
                }});
            }} catch (e) {{
                roleSelect.innerHTML = '<option value="">Error loading roles</option>';
            }}
        }}
        
        toggleVoteTypeFields();
        const modal = new bootstrap.Modal(document.getElementById('createVoteModal'));
        modal.show();
    }}
    
    function toggleVoteTypeFields() {{
        const isElection = document.getElementById('vote-type-election')?.checked;
        const subSec = document.getElementById('vote-submission-section');
        const roleSec = document.getElementById('vote-role-section');
        const subSel = document.getElementById('vote-submission-id');
        if (subSec) subSec.classList.toggle('d-none', !!isElection);
        if (roleSec) roleSec.classList.toggle('d-none', !isElection);
        if (subSel) subSel.required = !isElection;
        const roleSel = document.getElementById('vote-role-id');
        if (roleSel) roleSel.required = !!isElection;
    }}
    
    async function showEmailModal() {{
        document.getElementById('email-modal-alert').classList.add('d-none');
        document.getElementById('emailForm').reset();
        document.getElementById('email-schedule-immediate').checked = true;
        document.getElementById('email-scheduled-at-wrap').classList.add('d-none');
        document.getElementById('email-delay-wrap').classList.add('d-none');
        const groupsEl = document.getElementById('email-recipient-groups');
        const peopleEl = document.getElementById('email-people');
        groupsEl.innerHTML = '<div class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading...</div>';
        peopleEl.innerHTML = '';
        try {{
            const res = await fetch('/api/scope-email/layers/' + project.id + '/recipients/');
            const data = await res.json();
            if (!res.ok) {{
                groupsEl.innerHTML = '<div class="text-danger">' + (data.error || 'Failed to load') + '</div>';
                return;
            }}
            const groups = data.groups || {{}};
            let html = '';
            for (const [key, info] of Object.entries(groups)) {{
                const count = info.count || 0;
                const label = info.label || key;
                html += '<div class="form-check"><input class="form-check-input" type="checkbox" value="' + escapeHtmlBasic(key) + '" id="email-grp-' + escapeHtmlBasic(key) + '"><label class="form-check-label" for="email-grp-' + escapeHtmlBasic(key) + '">' + escapeHtml(label) + ' (' + count + ')</label></div>';
            }}
            groupsEl.innerHTML = html || '<p class="text-muted mb-0">No recipient groups available.</p>';
            const people = data.people || [];
            peopleEl.innerHTML = people.map(p => '<option value="' + escapeHtmlBasic(p.user_id) + '">' + escapeHtml(p.label || p.email) + '</option>').join('');
            await loadScheduledEmailCampaigns();
            document.querySelectorAll('input[name="email-schedule-mode"]').forEach(el => {{
                el.onchange = syncEmailScheduleFields;
            }});
            syncEmailScheduleFields();
            const modal = new bootstrap.Modal(document.getElementById('emailModal'));
            modal.show();
        }} catch (e) {{
            groupsEl.innerHTML = '<div class="text-danger">Error: ' + escapeHtml(e.message) + '</div>';
        }}
    }}

    function syncEmailScheduleFields() {{
        const mode = document.querySelector('input[name="email-schedule-mode"]:checked')?.value || 'immediate';
        document.getElementById('email-scheduled-at-wrap').classList.toggle('d-none', mode !== 'at');
        document.getElementById('email-delay-wrap').classList.toggle('d-none', mode !== 'after_join');
    }}

    async function loadScheduledEmailCampaigns() {{
        const wrap = document.getElementById('email-scheduled-list-wrap');
        const list = document.getElementById('email-scheduled-list');
        if (!wrap || !list) return;
        try {{
            const res = await fetch('/api/scope-email/layers/' + project.id + '/campaigns/');
            const data = await res.json();
            const rows = (data.campaigns || []).filter(c => c.status === 'scheduled' || c.status === 'active');
            if (!rows.length) {{
                wrap.classList.add('d-none');
                return;
            }}
            wrap.classList.remove('d-none');
            list.innerHTML = rows.map(c => {{
                const when = c.schedule_mode === 'at' ? (c.scheduled_at || 'scheduled') :
                    c.schedule_mode === 'after_join' ? (c.delay_hours + 'h after ' + (c.anchor_kind || 'join')) :
                    'immediate';
                return '<div class="d-flex justify-content-between align-items-start border rounded p-2 mb-2">' +
                    '<div><strong>' + escapeHtml(c.subject || '') + '</strong><br><span class="text-muted">' + escapeHtml(when) + ' · ' + escapeHtml(c.status) + '</span></div>' +
                    (c.status !== 'completed' && c.status !== 'cancelled' ?
                        '<button type="button" class="btn btn-sm btn-outline-danger" onclick="cancelEmailCampaign(\\'' + escapeHtmlBasic(c.id) + '\\')">Cancel</button>' : '') +
                    '</div>';
            }}).join('');
        }} catch (e) {{
            wrap.classList.add('d-none');
        }}
    }}

    async function cancelEmailCampaign(campaignId) {{
        const ok = await GhDialog.confirm({{
            title: 'Cancel scheduled email',
            message: 'Cancel this scheduled email campaign?',
            variant: 'warning',
            confirmLabel: 'Cancel campaign',
        }});
        if (!ok) return;
        const res = await fetch('/api/scope-email/campaigns/' + campaignId + '/', {{ method: 'DELETE' }});
        const data = await res.json();
        if (!res.ok) {{
            await GhDialog.alert({{ title: 'Could not cancel', message: data.error || 'Failed', variant: 'danger' }});
            return;
        }}
        await loadScheduledEmailCampaigns();
    }}
    
    async function submitEmail() {{
        const groups = Array.from(document.querySelectorAll('#email-recipient-groups input:checked')).map(cb => cb.value);
        const userIds = Array.from(document.getElementById('email-people').selectedOptions || []).map(o => o.value);
        const subject = document.getElementById('email-subject').value.trim();
        const body = document.getElementById('email-body').value.trim();
        const scheduleMode = document.querySelector('input[name="email-schedule-mode"]:checked')?.value || 'immediate';
        const scheduledAt = document.getElementById('email-scheduled-at').value;
        const delayHours = document.getElementById('email-delay-hours').value;
        const anchorKind = document.getElementById('email-anchor-kind').value;
        const alertEl = document.getElementById('email-modal-alert');
        alertEl.classList.add('d-none');
        if (!groups.length && !userIds.length) {{
            alertEl.textContent = 'Select at least one recipient group or person';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (!subject || !body) {{
            alertEl.textContent = 'Subject and message are required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (scheduleMode === 'at' && !scheduledAt) {{
            alertEl.textContent = 'Choose a date/time to schedule';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (scheduleMode === 'after_join' && !(parseFloat(delayHours) > 0)) {{
            alertEl.textContent = 'Enter hours after join (must be greater than 0)';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        const btn = document.getElementById('email-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
        try {{
            const payload = {{
                groups: groups,
                user_ids: userIds,
                subject: subject,
                body: body,
                schedule_mode: scheduleMode,
            }};
            if (scheduleMode === 'at') payload.scheduled_at = scheduledAt;
            if (scheduleMode === 'after_join') {{
                payload.delay_hours = parseFloat(delayHours);
                payload.anchor_kind = anchorKind;
            }}
            const res = await fetch('/api/layers/' + project.id + '/send-email/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }});
            const data = await res.json();
            if (!res.ok) {{
                alertEl.textContent = data.error || 'Failed to send';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
                return;
            }}
            const campaign = data.campaign || {{}};
            const msg = scheduleMode === 'immediate'
                ? ('Sent to ' + (data.sent || campaign.stats_sent || 0) + ' recipient(s).')
                : (scheduleMode === 'at' ? 'Email scheduled.' : 'After-join email campaign active.');
            alertEl.textContent = msg;
            alertEl.className = 'alert alert-success';
            alertEl.classList.remove('d-none');
            if (scheduleMode === 'immediate') {{
                setTimeout(() => {{
                    bootstrap.Modal.getInstance(document.getElementById('emailModal')).hide();
                }}, 1500);
            }} else {{
                await loadScheduledEmailCampaigns();
            }}
        }} catch (e) {{
            alertEl.textContent = 'Error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }} finally {{
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send / schedule';
        }}
    }}
    
    async function submitCreateVote() {{
        const title = document.getElementById('vote-title').value.trim();
        const description = document.getElementById('vote-description').value.trim();
        const submission_id = document.getElementById('vote-submission-id').value.trim();
        const role_id = document.getElementById('vote-role-id')?.value?.trim() || '';
        const seats = parseInt(document.getElementById('vote-seats')?.value || '1', 10) || 1;
        const isElection = document.getElementById('vote-type-election')?.checked;
        const vote_type = isElection ? 'election' : 'approval';
        const startVal = document.getElementById('vote-start').value;
        const endVal = document.getElementById('vote-end').value;
        const quorum = parseInt(document.getElementById('vote-quorum').value, 10);
        const threshold = parseFloat(document.getElementById('vote-threshold').value);
        
        const alertEl = document.getElementById('create-vote-alert');
        alertEl.classList.add('d-none');
        if (!title || !startVal || !endVal) {{
            alertEl.textContent = 'Title, Start, and End are required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (isElection && !role_id) {{
            alertEl.textContent = 'Role is required for election votes';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (!isElection && !submission_id) {{
            alertEl.textContent = 'Draft is required for approval votes';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        const startAt = new Date(startVal).toISOString();
        const endAt = new Date(endVal).toISOString();
        
        const btn = document.getElementById('create-vote-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
        
        try {{
            const res = await fetch('/api/layers/' + project.id + '/votes/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    title: title,
                    description: description,
                    submission_id: submission_id || null,
                    role_id: role_id || null,
                    vote_type: vote_type,
                    seats: seats,
                    start_at: startAt,
                    end_at: endAt,
                    quorum_count: quorum,
                    win_threshold: threshold
                }})
            }});
            // Read body once as text, then parse as JSON
            const rawText = await res.text();
            let data = {{}};
            try {{ data = JSON.parse(rawText); }} catch {{}}
            
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('createVoteModal')).hide();
                document.getElementById('votes-tab').click();
                loadVotes();
            }} else {{
                const msg = data.error || rawText.slice(0, 300) || 'HTTP ' + res.status;
                alertEl.textContent = msg;
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            console.error('Create vote fetch error:', e);
            alertEl.textContent = 'Network error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Create Vote';
    }}
    
    function showCreateQuestModal() {{
        const alertEl = document.getElementById('create-quest-alert');
        if (alertEl) alertEl.classList.add('d-none');
        const form = document.getElementById('createQuestForm');
        if (form) form.reset();
        const modal = new bootstrap.Modal(document.getElementById('createQuestModal'));
        modal.show();
    }}
    
    async function submitCreateQuest() {{
        const title = document.getElementById('quest-title').value.trim();
        const description = document.getElementById('quest-description').value.trim();
        const questType = document.getElementById('quest-type').value || 'contribution';
        const difficulty = document.getElementById('quest-difficulty').value || 'medium';
        const acceptanceCriteria = document.getElementById('quest-acceptance-criteria').value.trim();
        
        const alertEl = document.getElementById('create-quest-alert');
        alertEl.classList.add('d-none');
        if (!title) {{
            alertEl.textContent = 'Title is required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        
        const btn = document.getElementById('create-quest-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
        
        try {{
            const res = await fetch('/api/layers/' + project.id + '/quests/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    title: title,
                    description: description || null,
                    quest_type: questType,
                    difficulty: difficulty,
                    acceptance_criteria: acceptanceCriteria || null
                }})
            }});
            const data = await res.json().catch(() => ({{}}));
            
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('createQuestModal')).hide();
                document.getElementById('opportunities-tab').click();
                loadOpportunities();
            }} else {{
                alertEl.textContent = data.error || 'Failed to create quest';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            console.error('Create quest fetch error:', e);
            alertEl.textContent = 'Network error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Create Quest';
    }}
    
    // Tab event listeners (skip when standalone - no tabs in DOM)
    if (!showCarousel) {{
        const tabLoaders = [
            ['workgroups-tab', loadWorkgroups],
            ['docs-tab', loadDocs],
            ['clusters-tab', loadClusters],
            ['roles-tab', loadRoles],
            ['claims-tab', loadClaims],
            ['votes-tab', loadVotes],
            ['artifacts-tab', loadArtifacts],
            ['opportunities-tab', loadOpportunities],
        ];
        tabLoaders.forEach(function(pair) {{
            const el = document.getElementById(pair[0]);
            if (el) el.addEventListener('shown.bs.tab', pair[1]);
        }});
        {admin_tab_listener}
        
        enabledLayerTabIds.forEach(function(id) {{
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', function() {{ clearHashIfNeeded(getProjectTabKey(id)); }}, true);
        }});
        
        const overviewTabBtn = document.getElementById('overview-tab');
        if (overviewTabBtn) {{
            overviewTabBtn.addEventListener('shown.bs.tab', function() {{
                if (project && document.getElementById('overview-content')) loadOverview();
            }});
        }}

        const projectTabs = document.getElementById('projectTabs');
        if (projectTabs) {{
            projectTabs.addEventListener('shown.bs.tab', function(e) {{
                const tabKey = getProjectTabKey(e.target.id);
                if (tabKey) {{
                    const prevKey = localStorage.getItem('projectDetailTab_' + projectSlug + '_current');
                    saveTabState(tabKey, (prevKey && prevKey !== tabKey) ? prevKey : 'overview');
                    clearHashIfNeeded(tabKey);
                }}
            }});
            projectTabs.addEventListener('click', function(e) {{
                const btn = e.target.closest('[id^="waitlist-tab-"]');
                if (btn && btn.id && btn.id.match(/^waitlist-tab-(\\d+)$/)) {{
                    clearHashIfNeeded('waitlist-' + btn.id.match(/^waitlist-tab-(\\d+)$/)[1]);
                }}
            }}, true);
        }}
        
        if (window.location.hash && ['claims', 'votes'].includes(window.location.hash.replace(/^#/, ''))) {{
            setTimeout(switchToTabFromHash, 50);
        }}
    }}
    
    function clearHashIfNeeded(tabKey) {{
        const nonHashTabs = ['overview', 'workgroups', 'clusters', 'roles', 'admin'];
        const isNonHash = nonHashTabs.includes(tabKey) || (tabKey && tabKey.startsWith('waitlist-'));
        if (isNonHash && window.location.hash) {{
            saveTabState(tabKey, 'claims');
            const clean = window.location.origin + window.location.pathname + window.location.search;
            try {{ history.replaceState(null, '', clean); }} catch (e) {{}}
            if (window.location.hash) window.location.replace(clean);
        }}
    }}
    
    function buildWaitlistTabs(waitlists) {{
        if (!isLayerFeatureOn('waitlists')) return;
        const marker = document.getElementById('waitlist-tabs-marker');
        const paneMarker = document.getElementById('waitlist-panes-marker');
        if (!marker || !paneMarker) return;
        while (marker.previousElementSibling && marker.previousElementSibling.id && marker.previousElementSibling.id.startsWith('waitlist-tab-li-')) {{
            marker.previousElementSibling.remove();
        }}
        document.querySelectorAll('[id^="waitlist-pane-"]').forEach(el => el.remove());
        function setCommunityTabGroupVisible(visible) {{
            document.querySelectorAll('#projectTabs [data-tab-group="community"]').forEach(function(el) {{
                el.classList.toggle('d-none', !visible);
            }});
        }}
        setCommunityTabGroupVisible(true);
        if (waitlists.length === 0) {{
            setCommunityTabGroupVisible(false);
            return;
        }}
        waitlists.forEach((w, idx) => {{
            const li = document.createElement('li');
            li.className = 'nav-item';
            li.id = 'waitlist-tab-li-' + w.id;
            li.innerHTML = '<button class="nav-link waitlist-tab-flair" id="waitlist-tab-' + w.id + '" data-bs-toggle="tab" data-bs-target="#waitlist-pane-' + w.id + '" type="button" data-waitlist-id="' + w.id + '"><i class="fas fa-list-alt" aria-hidden="true"></i><span>' + escapeHtmlBasic(w.name || '') + '</span></button>';
            marker.parentNode.insertBefore(li, marker);
            const pane = document.createElement('div');
            pane.className = 'tab-pane fade' + (idx === 0 ? '' : '');
            pane.id = 'waitlist-pane-' + w.id;
            pane.dataset.waitlistId = w.id;
            pane.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
            paneMarker.parentNode.insertBefore(pane, paneMarker);
            li.querySelector('button').addEventListener('shown.bs.tab', () => loadWaitlistPane(w.id));
        }});
    }}
    
    function showWaitlistInactiveMessage(waitlistId) {{
        const header = document.getElementById('project-header');
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show';
        alert.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>This waitlist is no longer active.<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
        header.insertAdjacentElement('afterend', alert);
    }}
    
    async function loadWaitlistPane(waitlistId) {{
        const pane = document.getElementById('waitlist-pane-' + waitlistId);
        if (!pane || !project) return;
        pane.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/waitlists/');
            const data = await res.json();
            const w = (data.waitlists || []).find(x => x.id === waitlistId);
            if (!w) {{
                pane.innerHTML = '<div class="alert alert-warning">Waitlist not found or no longer active.</div>';
                return;
            }}
            const started = w.started !== false;
            const closed = w.closed === true;
            const full = w.full === true;
            const canJoin = isAuthenticated && started && !closed && !full && !w.my_entry;
            const countStr = w.max_number != null ? (w.count + ' of ' + w.max_number) : String(w.count);
            const closingStr = w.closing_date ? new Date(w.closing_date).toLocaleDateString() : '-';
                const link = w.referral_url || (window.location.origin + '/layers/' + projectSlug + '/waitlist/' + w.id + '/');
            const wName = escapeHtmlBasic(w.name || '');
            const wDesc = escapeHtmlBasic(w.description || 'No description');
            let milestonesHtml = '';
            if (w.milestones && w.milestones.length) {{
                const items = w.milestones.map(function(m) {{
                    return '<li><strong>' + escapeHtmlBasic(m.title || '') + '</strong> at ' + m.threshold + ' - ' + escapeHtmlBasic(m.description || '') + '</li>';
                }});
                milestonesHtml = '<div class="mt-3"><h6>Milestones</h6><ul class="list-unstyled small">' + items.join('') + '</ul></div>';
            }}
            let actionHtml = '';
            if (w.my_entry) {{
                actionHtml = '<span class="badge bg-success">Joined</span><span class="text-muted">Position #' + w.my_entry.position + '</span>';
            }} else if (canJoin) {{
                const wlNameForJs = (w.name || 'Waitlist').split("\\\\").join("\\\\\\\\").split("'").join("\\\\'");
                actionHtml = '<button class="btn btn-primary btn-sm" data-waitlist-id="' + (w.id || '').replace(/"/g, '&quot;') + '" data-waitlist-name="' + wlNameForJs.replace(/"/g, '&quot;') + '" onclick="showJoinWaitlistModal(this.dataset.waitlistId, this.dataset.waitlistName)">Join</button>';
            }} else if (!started) {{
                actionHtml = '<span class="badge bg-secondary">Not started</span>';
            }} else if (full) {{
                actionHtml = '<span class="badge bg-secondary">Full</span>';
            }} else if (closed) {{
                actionHtml = '<span class="badge bg-secondary">Closed</span>';
            }} else if (!isAuthenticated) {{
                actionHtml = '<a href="/login/" class="btn btn-primary btn-sm">Sign in to join</a>';
            }}
            const leaveBtn = w.my_entry ? '<button class="btn btn-outline-danger btn-sm" data-waitlist-id="' + (w.id || '').replace(/"/g, '&quot;') + '" onclick="leaveWaitlist(this.dataset.waitlistId)">Leave</button>' : '';
            const embedBtn = isProjectAdmin ? '<button class="btn btn-outline-primary btn-sm" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + w.id + '" data-waitlist-name="' + (w.name || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"><i class="fas fa-code me-1"></i>Embed</button>' : '';
            const detailBtn = '<a href="/waitlists/' + w.id + '/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-external-link-alt me-1"></i>Detail Page</a>';
            const linkHtml = w.referrals ? 'Your referral link: <a href="' + link + '" target="_blank">' + link + '</a>' : 'Link: <a href="' + link + '">' + link + '</a>';
            const dateStarted = w.start_date ? new Date(w.start_date).toLocaleDateString() : '-';
            const visibility = w.public ? 'Public' : 'Private';
            
            const wImg = (w.image_url) ? '<div class="mb-3"><img src="' + w.image_url + '" alt="' + wName + '" class="img-fluid gh-entity-thumb" style="max-height: 180px;"></div>' : '';
            const html = '<div class="card mb-4"><div class="card-body">' +
                '<nav aria-label="breadcrumb"><ol class="breadcrumb mb-2"><li class="breadcrumb-item"><a href="' + (showCarousel ? layerBase : '/layers/') + '">' + (showCarousel ? escapeHtmlBasic(project.name) : 'Layers') + '</a></li>' + (showCarousel ? '' : '<li class="breadcrumb-item"><a href="/layers/' + projectSlug + '/">' + escapeHtmlBasic(project.name) + '</a></li>') + '<li class="breadcrumb-item active">' + wName + ' Waitlist</li></ol></nav>' +
                wImg +
                '<h5 class="card-title">' + wName + '</h5>' +
                '<p class="text-muted">' + wDesc + '</p>' +
                '<p class="small mb-2">Date started: ' + dateStarted + ' · ' + visibility + '</p>' +
                '<p class="small">' + linkHtml + '</p>' +
                '<div class="d-flex flex-wrap align-items-center gap-3 mt-3">' +
                actionHtml +
                embedBtn +
                detailBtn +
                '<span class="text-muted">' + countStr + ' on waitlist</span>' +
                '<span class="text-muted">Closing: ' + closingStr + '</span>' +
                leaveBtn +
                '</div>' + milestonesHtml + '</div></div>';
            pane.innerHTML = html;
        }} catch (e) {{
            console.error(e);
            pane.innerHTML = '<div class="alert alert-danger">Error loading waitlist</div>';
        }}
    }}
    
    let pendingWaitlistId = null;
    
    async function showJoinWaitlistModal(waitlistId, waitlistName) {{
        if (!isAuthenticated) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please sign in to join this waitlist'), variant: 'info' }}); return; }}
        pendingWaitlistId = waitlistId;
        const titleEl = document.getElementById('join-waitlist-modal-title');
        if (titleEl) titleEl.innerHTML = '<i class="fas fa-list-alt me-2"></i>Join: ' + escapeHtmlBasic(waitlistName || 'Waitlist');
        const msgEl = document.getElementById('join-waitlist-message');
        if (msgEl) msgEl.value = '';
        const modal = new bootstrap.Modal(document.getElementById('joinWaitlistModal'));
        modal.show();
    }}
    
    async function submitJoinWaitlistModal() {{
        if (!pendingWaitlistId) return;
        const msgEl = document.getElementById('join-waitlist-message');
        const msg = msgEl ? msgEl.value : '';
        try {{
            const body = {{ message: msg || '' }};
            if (referralRefToken) body.ref_token = referralRefToken;
            const res = await fetch('/api/waitlists/' + pendingWaitlistId + '/join/', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
            const data = await res.json();
            if (res.ok) {{
                loadWaitlistPane(pendingWaitlistId);
                bootstrap.Modal.getInstance(document.getElementById('joinWaitlistModal')).hide();
            }} else {{ await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to join'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to join'), variant: 'info' }}); }}
        pendingWaitlistId = null;
    }}
    
    async function leaveWaitlist(waitlistId) {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Leave this waitlist?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const res = await fetch('/api/waitlists/' + waitlistId + '/leave/', {{ method: 'POST' }});
            if (res.ok) loadWaitlistPane(waitlistId); else {{ const d = await res.json(); await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed to leave'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to leave'), variant: 'info' }}); }}
    }}
    
    async function attachGuildToLayer() {{
        const inp = document.getElementById('layer-attach-guild-id');
        const msg = document.getElementById('layer-attach-guild-msg');
        if (!inp || !project) return;
        const gid = inp.value.trim();
        if (!gid) {{ if (msg) msg.textContent = 'Enter a guild id'; return; }}
        if (msg) {{ msg.textContent = ''; msg.className = 'small mt-1 mb-0 text-muted'; }}
        try {{
            const r = await fetch('/api/layers/' + project.id + '/guilds/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ guild_id: gid }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (r.ok) {{ inp.value = ''; loadAdmins(); loadOverviewGuilds(); }}
            else {{ if (msg) {{ msg.textContent = d.error || 'Failed'; msg.className = 'small mt-1 mb-0 text-danger'; }} }}
        }} catch (e) {{ if (msg) {{ msg.textContent = e.message; msg.className = 'small mt-1 mb-0 text-danger'; }} }}
    }}
    
    async function detachGuildFromLayer(guildId) {{
        if (!project || !guildId) return;
        if (!(await GhDialog.confirm({{ title: 'Confirm', message: 'Remove this guild link from the layer?', variant: 'warning' }}))) return;
        try {{
            const r = await fetch('/api/layers/' + project.id + '/guilds/' + encodeURIComponent(guildId) + '/', {{
                method: 'DELETE',
                credentials: 'same-origin'
            }});
            if (r.ok) {{ loadAdmins(); loadOverviewGuilds(); }}
            else {{ const d = await r.json().catch(() => ({{}})); await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: (e.message), variant: 'info' }}); }}
    }}

    function formatReferralConversionType(key) {{
        const labels = {{
            layer_member_join: 'Layer join',
            waitlist_join: 'Waitlist join',
            user_signup: 'Signup',
            embed_signup: 'Embed signup',
            embed_visit: 'Embed visit',
            install_click: 'Install click',
        }};
        return labels[key] || key || '–';
    }}

    function renderReferralByType(byType) {{
        if (!byType || typeof byType !== 'object') return '–';
        const parts = Object.keys(byType).map(function(k) {{
            return formatReferralConversionType(k) + ': ' + byType[k];
        }});
        return parts.length ? escapeHtml(parts.join(' · ')) : '–';
    }}

    let layerReferralLinkUrl = '';

    function renderReferralStatsCard(stats, options) {{
        options = options || {{}};
        const title = options.title || 'Referral analytics';
        const subtitle = options.subtitle || 'Scoped link visits and attributed joins for this layer.';
        const landings = stats.landing_count || 0;
        const conversions = stats.conversion_count || 0;
        const referrers = stats.referrers || [];
        let card = '<div class="card mb-4" id="layer-referral-stats-card"><div class="card-header d-flex justify-content-between align-items-center">';
        card += '<h5 class="mb-0"><i class="fas fa-chart-line me-2"></i>' + escapeHtml(title) + '</h5>';
        card += '<div class="btn-group btn-group-sm"><button type="button" class="btn btn-outline-secondary" onclick="loadAdmins()" title="Refresh"><i class="fas fa-sync-alt"></i></button>';
        if (options.showCopyLink) {{
            card += '<button type="button" class="btn btn-outline-primary" onclick="copyLayerReferralLink()"><i class="fas fa-link me-1"></i>Copy my link</button>';
        }}
        card += '</div></div><div class="card-body">';
        card += '<p class="text-muted small mb-3">' + escapeHtml(subtitle) + '</p>';
        if (options.referralUrl) {{
            card += '<div class="input-group input-group-sm mb-3">';
            card += '<span class="input-group-text"><i class="fas fa-link"></i></span>';
            card += '<input type="text" class="form-control font-monospace" id="layer-referral-link-url" readonly value="' + escapeHtmlBasic(options.referralUrl) + '" onclick="this.select()">';
            card += '<button type="button" class="btn btn-outline-primary" onclick="copyLayerReferralLink()">Copy</button>';
            card += '</div>';
        }}
        card += '<div class="row g-3 mb-3"><div class="col-md-4"><div class="border rounded p-3 text-center h-100">';
        card += '<div class="fs-4 fw-bold">' + landings + '</div><div class="small text-muted">Link landings</div></div></div>';
        card += '<div class="col-md-4"><div class="border rounded p-3 text-center h-100">';
        card += '<div class="fs-4 fw-bold">' + conversions + '</div><div class="small text-muted">Attributed conversions</div></div></div>';
        card += '<div class="col-md-4"><div class="border rounded p-3 text-center h-100">';
        const rate = landings > 0 ? Math.round((conversions / landings) * 100) + '%' : '–';
        card += '<div class="fs-4 fw-bold">' + rate + '</div><div class="small text-muted">Landing → conversion</div></div></div></div>';
        if (!referrers.length) {{
            card += '<p class="text-muted small mb-0">No referral activity recorded yet. Enable referrals on a waitlist so members receive shareable <code>?ref_token=</code> links.</p>';
        }} else {{
            card += '<div class="table-responsive"><table class="table table-sm table-hover align-middle mb-0">';
            card += '<thead><tr><th>Referrer</th><th class="text-end">Landings</th><th class="text-end">Conversions</th><th>Breakdown</th></tr></thead><tbody>';
            referrers.forEach(function(row) {{
                const uname = escapeHtmlBasic(row.username || '');
                const dname = escapeHtml(row.display_name || row.username || 'User');
                const profile = uname ? '<a href="/profile/' + uname + '/" class="text-decoration-none">' + dname + '</a>' : dname;
                card += '<tr><td>' + profile + '</td>';
                card += '<td class="text-end">' + (row.landings || 0) + '</td>';
                card += '<td class="text-end">' + (row.conversions || 0) + '</td>';
                card += '<td class="small text-muted">' + renderReferralByType(row.by_type) + '</td></tr>';
            }});
            card += '</tbody></table></div>';
        }}
        card += '</div></div>';
        return card;
    }}

    function copyTextToClipboard(text) {{
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.top = '-1000px';
        textarea.style.left = '-1000px';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        let copied = false;
        try {{
            copied = document.execCommand('copy');
        }} catch (e) {{
            console.warn('Fallback copy failed:', e);
        }}
        document.body.removeChild(textarea);
        if (copied) return Promise.resolve(true);
        if (navigator.clipboard && navigator.clipboard.writeText) {{
            return navigator.clipboard.writeText(text).then(function() {{
                return true;
            }}).catch(function(e) {{
                console.warn('Clipboard API copy failed:', e);
                return false;
            }});
        }}
        return Promise.resolve(false);
    }}

    async function copyLayerReferralLink() {{
        if (!project || !project.id) return;
        try {{
            const input = document.getElementById('layer-referral-link-url');
            const url = (input && input.value) || layerReferralLinkUrl;
            if (!url) throw new Error('Referral link is not loaded yet. Refresh the Admin tab and try again.');
            const copied = await copyTextToClipboard(url);
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{
                    title: copied ? 'Referral link copied' : 'Copy manually',
                    message: copied
                        ? 'Your scoped layer referral link is on the clipboard.'
                        : 'Clipboard access was blocked. The link field is visible above. Select it and press Cmd+C.',
                    variant: copied ? 'success' : 'warning',
                }});
            }}
        }} catch (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{
                    title: 'Copy failed',
                    message: e.message || 'Could not copy the referral link.',
                    variant: 'danger',
                }});
            }} else {{
                console.warn('Copy failed:', e);
            }}
        }}
    }}
    
    async function launchLayerProgram(programId, promoteWaitlist) {{
        if (!project || !project.id || !programId) return;
        const ok = typeof GhDialog !== 'undefined'
            ? await GhDialog.confirm({{
                title: 'Launch program',
                message: promoteWaitlist
                    ? 'Open this program and promote waitlist members to layer contributors?'
                    : 'Open this program for participation?',
                variant: 'warning',
                confirmLabel: 'Launch',
            }})
            : false;
        if (!ok) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/programs/' + programId + '/launch/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ promote_waitlist: !!promoteWaitlist }}),
            }});
            const data = await res.json().catch(function() {{ return {{}}; }});
            if (!res.ok) throw new Error(data.error || res.statusText);
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{
                    title: 'Program launched',
                    message: promoteWaitlist && data.promoted_waitlist_members
                        ? ('Program is active. Promoted ' + data.promoted_waitlist_members + ' waitlist member(s).')
                        : 'Program is now active.',
                    variant: 'success',
                }});
            }}
            loadAdmins();
        }} catch (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{ title: 'Launch failed', message: e.message || 'Could not launch program.', variant: 'danger' }});
            }} else {{
                console.warn('Launch failed:', e);
            }}
        }}
    }}

    async function loadAdmins() {{
        const container = document.getElementById('admin-content');
        if (!container) return;
        container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/');
            if (response.status === 403) {{
                container.innerHTML = '<div class="alert alert-warning">You do not have permission to view layer admins.</div>';
                return;
            }}
            const data = await response.json();
            
            const ownerUserEsc = escapeHtmlBasic(data.owner.username || '');
            const ownerNameEsc = escapeHtml(data.owner.display_name || '');
            const curStatus = project.status || 'proposed';
            const statusReasonEsc = escapeHtmlBasic(project.status_reason || '');
            const approvalEsc = escapeHtml(String(project.approval_status || 'pending'));
            let html = '<div class="card mb-4"><div class="card-header"><h5 class="mb-0">Layer lifecycle status</h5></div><div class="card-body">';
            html += '<p class="text-muted small mb-3">Operational status (separate from site approval). Set to <strong>Active</strong> when the layer is ready to operate publicly.</p>';
            html += '<div class="row g-3 align-items-end"><div class="col-md-4"><label class="form-label" for="admin-layer-status">Status</label><select class="form-select" id="admin-layer-status">';
            [['proposed','Proposed'],['active','Active'],['stabilizing','Stabilizing'],['maintaining','Maintaining'],['dormant','Dormant'],['concluded','Concluded'],['archived','Archived']].forEach(function(pair) {{
                html += '<option value="' + pair[0] + '"' + (curStatus === pair[0] ? ' selected' : '') + '>' + pair[1] + '</option>';
            }});
            html += '</select></div><div class="col-md-5"><label class="form-label" for="admin-layer-status-reason">Status reason (optional)</label>';
            html += '<input type="text" class="form-control" id="admin-layer-status-reason" value="' + statusReasonEsc + '" placeholder="Reason for change"></div>';
            html += '<div class="col-md-3"><button type="button" class="btn btn-primary w-100" onclick="saveLayerStatus()"><i class="fas fa-save me-1"></i>Save status</button></div></div>';
            html += '<p class="small text-muted mt-2 mb-0">Site approval: <strong>' + approvalEsc + '</strong> (site admins only – <a href="/admin/layers/">Admin → Layers</a>).</p>';
            html += '<p class="small mb-0 mt-1" id="admin-layer-status-msg"></p></div></div>';
            const curVis = (project.listing_visibility || 'public');
            html += '<div class="card mb-4"><div class="card-header"><h5 class="mb-0">Discovery &amp; access</h5></div><div class="card-body">';
            html += '<p class="text-muted small mb-2">Directory listing: <strong>' + (curVis === 'private' ? 'Private' : 'Public') + '</strong>. ';
            html += 'Private layers are visible only to members and invitees. Making a layer public is one-way.</p>';
            if (curVis === 'private') {{
                html += '<button type="button" class="btn btn-outline-primary btn-sm" id="btn-make-layer-public" onclick="makeLayerPublic()">';
                html += '<i class="fas fa-globe me-1"></i>Make layer public in directory</button>';
                html += '<p class="small text-muted mt-2 mb-0" id="layer-visibility-msg"></p>';
            }} else {{
                html += '<p class="small text-muted mb-0">This layer is listed in the public directory.</p>';
            }}
            const jp = project.join_policy || 'open';
            html += '<hr class="my-3"><p class="mb-1"><strong>Join policy:</strong> ' + escapeHtml(jp) + '</p>';
            if (jp === 'nft_gated') {{
                html += '<p class="text-muted small mb-2">Members must hold an allowed NFT (ETH, Solana, or Bitcoin inscription).</p>';
                html += '<label class="form-label small" for="layer-nft-gate-rules">Allowed NFTs (one per line: <code>eth:0xContract</code>, <code>sol:mint</code>, <code>btc:inscriptionId</code>)</label>';
                html += '<textarea class="form-control font-monospace small" id="layer-nft-gate-rules" rows="4"></textarea>';
                html += '<button type="button" class="btn btn-primary btn-sm mt-2" onclick="saveLayerNftGate()"><i class="fas fa-save me-1"></i>Save NFT gate</button>';
                html += '<p class="small text-muted mt-2 mb-0" id="layer-nft-gate-msg"></p>';
            }}
            html += '</div></div>';
            try {{
                const refStatsRes = await fetch('/api/layers/' + project.id + '/referral-stats/', {{ credentials: 'same-origin' }});
                if (refStatsRes.ok) {{
                    const refStats = await refStatsRes.json();
                    try {{
                        const refLinkRes = await fetch('/api/layers/' + project.id + '/referral-link/', {{ credentials: 'same-origin' }});
                        if (refLinkRes.ok) {{
                            const refLink = await refLinkRes.json();
                            layerReferralLinkUrl = refLink.url || '';
                        }}
                    }} catch (linkErr) {{
                        console.warn('Referral link:', linkErr);
                    }}
                    html += renderReferralStatsCard(refStats, {{
                        title: 'Referral analytics',
                        subtitle: 'Link landings and attributed joins for this layer (includes waitlist-driven layer joins).',
                        showCopyLink: true,
                        referralUrl: layerReferralLinkUrl,
                    }});
                }} else if (refStatsRes.status !== 403) {{
                    html += '<div class="card mb-4"><div class="card-body"><p class="text-muted small mb-0">Referral stats could not be loaded.</p></div></div>';
                }}
            }} catch (refErr) {{
                console.warn('Referral stats:', refErr);
            }}

            html += '<div class="card mb-4" id="layer-programs-card"><div class="card-header d-flex justify-content-between align-items-center">';
            html += '<h5 class="mb-0"><i class="fas fa-rocket me-2"></i>Programs</h5>';
            html += '<button type="button" class="btn btn-outline-secondary btn-sm" onclick="loadAdmins()" title="Refresh"><i class="fas fa-sync-alt"></i></button>';
            html += '</div><div class="card-body">';
            html += '<p class="text-muted small mb-3">Time-bounded initiatives on this layer (e.g. DP Challenge). Start in <code>waitlist</code> or <code>draft</code>, then launch to open the hub.</p>';
            try {{
                const progRes = await fetch('/api/layers/' + project.id + '/programs/', {{ credentials: 'same-origin' }});
                if (progRes.ok) {{
                    const progData = await progRes.json();
                    const programs = progData.programs || [];
                    if (!programs.length) {{
                        html += '<p class="text-muted small mb-0">No programs yet. Seed or create one via API (slug, name, hub_path, hub_mode).</p>';
                    }} else {{
                        html += '<div class="table-responsive"><table class="table table-sm align-middle mb-0">';
                        html += '<thead><tr><th>Program</th><th>Status</th><th>Hub</th><th class="text-end">Actions</th></tr></thead><tbody>';
                        programs.forEach(function(p) {{
                            const pid = escapeForJsAttr(String(p.id || ''));
                            const hub = p.hub_path ? '<a href="' + escapeHtmlBasic(p.hub_path) + '" target="_blank" rel="noopener">' + escapeHtmlBasic(p.hub_path) + '</a>' : '–';
                            const statusBadge = p.status === 'active'
                                ? '<span class="badge bg-success">Active</span>'
                                : (p.status === 'waitlist'
                                    ? '<span class="badge bg-warning text-dark">Waitlist</span>'
                                    : '<span class="badge bg-secondary">' + escapeHtmlBasic(p.status || 'draft') + '</span>');
                            let actions = '';
                            if (p.status !== 'active' && p.status !== 'archived') {{
                                actions += '<button type="button" class="btn btn-sm btn-primary me-1" onclick="launchLayerProgram(\\'' + pid + '\\', false)">Launch</button>';
                                if (p.waitlist_id) {{
                                    actions += '<button type="button" class="btn btn-sm btn-outline-primary" onclick="launchLayerProgram(\\'' + pid + '\\', true)">Launch + promote waitlist</button>';
                                }}
                            }} else if (p.hub_path) {{
                                actions = '<a class="btn btn-sm btn-outline-secondary" href="' + escapeHtmlBasic(p.hub_path) + '" target="_blank" rel="noopener">Open hub</a>';
                            }}
                            html += '<tr><td><strong>' + escapeHtml(p.name || p.slug || '') + '</strong><br><span class="small text-muted">' + escapeHtmlBasic(p.slug || '') + '</span></td>';
                            html += '<td>' + statusBadge;
                            if (p.launch_at_label) {{
                                html += '<br><span class="small text-muted">Opens ' + escapeHtml(p.launch_at_label) + '</span>';
                            }}
                            html += '</td><td class="small">' + hub + '</td><td class="text-end">' + actions + '</td></tr>';
                        }});
                        html += '</tbody></table></div>';
                    }}
                }} else {{
                    html += '<p class="text-muted small mb-0">Programs could not be loaded.</p>';
                }}
            }} catch (progErr) {{
                console.warn('Programs:', progErr);
                html += '<p class="text-muted small mb-0">Programs could not be loaded.</p>';
            }}
            html += '</div></div>';

            html += '<div class="card mb-4"><div class="card-header"><h5 class="mb-0">Product features</h5></div><div class="card-body">';
            html += '<p class="text-muted small mb-3">Turn off capabilities for this layer only (among features enabled site-wide). Disabled areas are removed from navigation, tabs, and admin sections.</p>';
            html += '<div class="row g-2">';
            const siteKeys = layerFeatKeysSiteEnabled();
            if (!siteKeys.length) {{
                html += '<div class="col-12"><p class="text-muted small mb-0">No site-wide features are enabled to configure per layer.</p></div>';
            }}
            siteKeys.forEach(function(k) {{
                const on = layerEffectiveFeatures[k] !== false;
                html += '<div class="col-md-6 col-lg-4"><div class="form-check"><input class="form-check-input" type="checkbox" id="layer-feat-' + k + '" ' + (on ? 'checked' : '') + '><label class="form-check-label" for="layer-feat-' + k + '">' + (layerFeatLabels[k] || k) + '</label></div></div>';
            }});
            html += '</div><button type="button" class="btn btn-primary btn-sm mt-2" onclick="saveLayerFeatures()"><i class="fas fa-save me-1"></i>Save features</button>';
            html += '<p class="small text-muted mt-2 mb-0" id="layer-feat-save-msg"></p></div></div>';
            html += '<div class="card mb-4"><div class="card-header"><h5 class="mb-0">Navigation pills</h5></div><div class="card-body">';
            html += '<p class="text-muted small mb-3">Micro-animations and newcomer tips for this layer\\'s tab pills. Site defaults apply when left blank.</p>';
            const curAnim = (layerNavPillConfig && layerNavPillConfig.animation) || (siteNavPillSettings && siteNavPillSettings.animation) || 'hover-grow';
            const tipsOn = layerNavPillConfig.tooltips_enabled !== undefined ? layerNavPillConfig.tooltips_enabled : (siteNavPillSettings.tooltips_enabled !== false);
            html += '<div class="row g-3"><div class="col-md-6"><label class="form-label" for="layer-nav-pill-animation">Animation style</label><select class="form-select form-select-sm" id="layer-nav-pill-animation">';
            Object.keys(navPillAnimations || {{}}).forEach(function(k) {{
                html += '<option value="' + k + '"' + (curAnim === k ? ' selected' : '') + '>' + navPillAnimations[k] + '</option>';
            }});
            html += '</select></div><div class="col-md-6 d-flex align-items-end"><div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="layer-nav-pill-tooltips" ' + (tipsOn ? 'checked' : '') + '><label class="form-check-label" for="layer-nav-pill-tooltips">Show newcomer tips on hover</label></div></div></div>';
            html += '<button type="button" class="btn btn-primary btn-sm mt-2" onclick="saveNavPillConfig()"><i class="fas fa-save me-1"></i>Save navigation pills</button>';
            html += '<p class="small text-muted mt-2 mb-0" id="layer-nav-pill-save-msg"></p></div></div>';
            html += renderPrefixesCard();
            html += '<div class="d-flex justify-content-between align-items-center mb-3"><h4>Layer admins</h4><button class="btn btn-primary btn-sm" onclick="showAddAdminModal()"><i class="fas fa-plus me-2"></i>Add admin</button></div><p class="text-muted">Admins can manage workgroups, roles, claims, and other admins. The owner cannot be removed.</p><div class="list-group"><div class="list-group-item d-flex justify-content-between align-items-center"><div><a href="/profile/' + ownerUserEsc + '/" class="fw-bold text-decoration-none">' + ownerNameEsc + '</a><span class="badge bg-primary ms-2">Owner</span></div><span class="text-muted">–</span></div>';
            (data.admins || []).forEach(a => {{
                html += '<div class="list-group-item d-flex justify-content-between align-items-center"><a href="/profile/' + escapeHtmlBasic(a.username || '') + '/" class="text-decoration-none">' + escapeHtml(a.display_name || '') + '</a><button class="btn btn-outline-danger btn-sm" onclick="removeAdmin(\\'' + (a.user_id || '') + '\\', this)">Remove</button></div>';
            }});
            html += '</div>';
            
            if (isLayerFeatureOn('workgroups')) {{
                html += '<hr class="my-4"><h4 class="mb-3">Pending workgroups</h4>';
                const wgResponse = await fetch('/api/layers/' + project.id + '/workgroups/?approval_status=pending');
                const wgData = await wgResponse.json();
                if (wgData.workgroups && wgData.workgroups.length > 0) {{
                    html += '<div class="list-group">';
                    wgData.workgroups.forEach(wg => {{
                        const wgNameEsc = escapeHtml(wg.name || '');
                        const wgDescEsc = escapeHtml(wg.description || 'No description');
                        const wgIdEsc = escapeForJsAttr(String(wg.id || ''));
                        html += '<div class="list-group-item"><div class="d-flex justify-content-between align-items-start"><div><h6 class="mb-1">' + wgNameEsc + '</h6><p class="mb-1 text-muted small">' + wgDescEsc + '</p></div><div class="btn-group btn-group-sm"><button class="btn btn-success" onclick="approveWorkgroup(\\'' + wgIdEsc + '\\')"><i class="fas fa-check me-1"></i>Approve</button><button class="btn btn-danger" onclick="rejectWorkgroup(\\'' + wgIdEsc + '\\')"><i class="fas fa-times me-1"></i>Reject</button></div></div></div>';
                    }});
                    html += '</div>';
                }} else {{
                    html += '<p class="text-muted">No pending workgroups</p>';
                }}
            }}

            if (isLayerFeatureOn('waitlists')) {{
                html += '<hr class="my-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Waitlists</h4><button class="btn btn-primary btn-sm" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button></div>';
                const wlResponse = await fetch('/api/layers/' + project.id + '/waitlists/');
                const wlData = await wlResponse.json();
                const wlStatsMap = {{}};
                if (wlData.waitlists && wlData.waitlists.length) {{
                    const referralWaitlists = wlData.waitlists.filter(function(w) {{ return w.referrals; }});
                    if (referralWaitlists.length) {{
                        const statsResults = await Promise.all(referralWaitlists.map(async function(wl) {{
                            try {{
                                const sr = await fetch('/api/waitlists/' + wl.id + '/referral-stats/', {{ credentials: 'same-origin' }});
                                if (sr.ok) return {{ id: wl.id, stats: await sr.json() }};
                            }} catch (e) {{ /* ignore */ }}
                            return null;
                        }}));
                        statsResults.filter(Boolean).forEach(function(entry) {{
                            wlStatsMap[entry.id] = entry.stats;
                        }});
                    }}
                }}
                if (wlData.waitlists && wlData.waitlists.length > 0) {{
                    html += '<div class="list-group">';
                    wlData.waitlists.forEach(wl => {{
                        const statusBadge = wl.active ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Inactive</span>';
                        const refBadge = wl.referrals ? ' <span class="badge bg-primary">Referrals on</span>' : '';
                        const wlNameEsc = escapeHtmlBasic(wl.name || '');
                        const wlDescEsc = escapeHtmlBasic(wl.description || 'No description');
                        const wlNameAttr = (wl.name || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
                        let refStatsLine = '';
                        if (wl.referrals && wlStatsMap[wl.id]) {{
                            const ws = wlStatsMap[wl.id];
                            refStatsLine = '<p class="mb-0 small text-muted"><i class="fas fa-chart-line me-1"></i>' +
                                (ws.landing_count || 0) + ' landings · ' + (ws.conversion_count || 0) + ' conversions</p>';
                        }} else if (wl.referrals) {{
                            refStatsLine = '<p class="mb-0 small text-muted">Referrals enabled – no activity yet</p>';
                        }}
                        html += '<div class="list-group-item"><div class="d-flex justify-content-between align-items-start">' +
                            '<div class="flex-grow-1">' +
                            '<h6 class="mb-1"><a href="/waitlists/' + wl.id + '/" class="text-decoration-none">' + wlNameEsc + '</a> ' + statusBadge + refBadge + '</h6>' +
                            '<p class="mb-1 text-muted small">' + wlDescEsc + '</p>' +
                            '<p class="mb-0 small text-muted">Members: ' + wl.count + (wl.max_number ? ' / ' + wl.max_number : '') + '</p>' +
                            refStatsLine +
                            '</div><div class="btn-group btn-group-sm">' +
                            '<button class="btn btn-outline-primary" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + wl.id + '" data-waitlist-name="' + wlNameAttr + '"><i class="fas fa-code"></i></button>' +
                            '<a href="/waitlists/' + wl.id + '/" class="btn btn-outline-secondary"><i class="fas fa-external-link-alt"></i></a>' +
                            '</div></div></div>';
                    }});
                    html += '</div>';
                }} else {{
                    html += '<p class="text-muted">No waitlists yet. Create one to start collecting signups.</p>';
                }}
            }}

            if (isLayerFeatureOn('guilds')) {{
                const guildRes = await fetch('/api/layers/' + project.id + '/guilds/', {{ credentials: 'same-origin' }});
                const guildData = guildRes.ok ? await guildRes.json() : {{ links: [] }};
                html += '<hr class="my-4"><h4 class="mb-3">Affiliated guilds</h4>';
                html += '<p class="text-muted small mb-2">Unified Phase I: link guilds to this layer. Layer admins may attach any guild; guild officers who are also active layer members may attach.</p>';
                if (guildData.links && guildData.links.length > 0) {{
                    html += '<ul class="list-group list-group-flush mb-3">';
                    guildData.links.forEach(lnk => {{
                        const g = lnk.guild || {{}};
                        const gname = escapeHtmlBasic(g.name || lnk.guild_id || '');
                        const gslug = escapeHtmlBasic(g.slug || '');
                        const gid = escapeForJsAttr(String(lnk.guild_id || ''));
                        html += '<li class="list-group-item d-flex justify-content-between align-items-center"><span><a href="/guilds/' + gslug + '/">' + gname + '</a></span><button type="button" class="btn btn-sm btn-outline-danger" onclick="detachGuildFromLayer(\\'' + gid + '\\')">Remove</button></li>';
                    }});
                    html += '</ul>';
                }} else {{
                    html += '<p class="text-muted small mb-3">No guilds linked yet.</p>';
                }}
                html += '<div class="card card-body py-2 mb-2"><label class="form-label small mb-1">Attach guild (UUID from guild API or URL)</label><div class="input-group input-group-sm"><input type="text" class="form-control" id="layer-attach-guild-id" placeholder="Guild id"><button class="btn btn-primary" type="button" onclick="attachGuildToLayer()">Attach</button></div><p class="small mt-1 mb-0 text-muted" id="layer-attach-guild-msg"></p></div>';
            }}
            
            // About page section
            html += '<hr class="my-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>About Page</h4><a href="' + layerBase + 'about/" class="btn btn-outline-secondary btn-sm" target="_blank">View</a></div>';
            const aboutEsc = (project.about_content || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            html += '<p class="text-muted small mb-2">Markdown content for the layer About page. Supports images via URLs.</p>';
            html += '<textarea class="form-control font-monospace mb-2" id="about-content-edit" rows="10" placeholder="# About this layer\\n\\nWrite your layer description in markdown...">' + aboutEsc + '</textarea>';
            html += '<button class="btn btn-primary btn-sm" id="save-about-btn" onclick="saveAboutContent()"><i class="fas fa-save me-1"></i>Save About</button>';
            
            // Carousel config section
            let carouselConfig = {{ auto_items: {{ recent_drafts: true, open_roles: true, open_opportunities: true }}, custom_items: [] }};
            try {{ if (project.carousel_config) carouselConfig = JSON.parse(project.carousel_config); }} catch(e) {{}}
            const cc = carouselConfig.auto_items || carouselConfig.autoItems || {{}};
            const recentDrafts = cc.recent_drafts !== false;
            const openRoles = cc.open_roles !== false;
            const openOpps = cc.open_opportunities !== false;
            html += '<hr class="my-4"><h4 class="mb-3">Carousel</h4><p class="text-muted small mb-2">Show items in the overview carousel. Auto items are generated from layer data.</p>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-recent-drafts" ' + (recentDrafts ? 'checked' : '') + '><label class="form-check-label" for="cc-recent-drafts">Recent drafts</label></div>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-open-roles" ' + (openRoles ? 'checked' : '') + '><label class="form-check-label" for="cc-open-roles">Open roles</label></div>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-open-opportunities" ' + (openOpps ? 'checked' : '') + '><label class="form-check-label" for="cc-open-opportunities">Open opportunities</label></div>';
            html += '<div class="mt-2"><button class="btn btn-primary btn-sm" onclick="saveCarouselConfig()"><i class="fas fa-save me-1"></i>Save Carousel</button></div>';
            html += '<div class="mt-3"><h6 class="mb-2">Custom items</h6><div id="carousel-custom-items"></div><button class="btn btn-outline-primary btn-sm mt-2" onclick="addCarouselCustomItem()"><i class="fas fa-plus me-1"></i>Add custom item</button></div>';
            
            container.innerHTML = html;
            renderCarouselCustomItems(carouselConfig.custom_items || []);
            const nftRulesEl = document.getElementById('layer-nft-gate-rules');
            if (nftRulesEl) nftRulesEl.value = nftGateRulesFromProject();
            // Hydrate the new prefixes card now that the admin pane is in the DOM.
            try {{ loadPrefixes(); }} catch (prefixErr) {{ console.warn('Prefixes:', prefixErr); }}
        }} catch (error) {{
            console.error('Error loading admins:', error);
            container.innerHTML = '<div class="alert alert-danger">Error loading admins</div>';
        }}
    }}
    
    async function makeLayerPublic() {{
        if (!project || (project.listing_visibility || 'public') !== 'private') return;
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Make this layer public in the directory? This cannot be undone.'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        const msgEl = document.getElementById('layer-visibility-msg');
        if (msgEl) {{
            msgEl.textContent = 'Saving…';
            msgEl.className = 'small text-muted mt-2 mb-0';
        }}
        try {{
            const r = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ listing_visibility: 'public' }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (!r.ok) {{
                if (msgEl) {{
                    msgEl.textContent = d.error || 'Could not update visibility';
                    msgEl.className = 'small text-danger mt-2 mb-0';
                }}
                return;
            }}
            if (d.project) project = d.project;
            if (msgEl) {{
                msgEl.textContent = 'Layer is now public.';
                msgEl.className = 'small text-success mt-2 mb-0';
            }}
            setTimeout(function() {{ loadAdminsTab(); }}, 800);
        }} catch (e) {{
            if (msgEl) {{
                msgEl.textContent = e.message || 'Save failed';
                msgEl.className = 'small text-danger mt-2 mb-0';
            }}
        }}
    }}

    function nftGateRulesFromProject() {{
        const raw = project && project.nft_gate;
        if (!raw || typeof raw !== 'object') return '';
        const lines = [];
        (raw.eth || []).forEach(function(e) {{
            if (e && e.contract) lines.push('eth:' + e.contract);
        }});
        (raw.sol || []).forEach(function(s) {{
            if (s && (s.mint || s.collection)) lines.push('sol:' + (s.mint || s.collection));
        }});
        (raw.btc || []).forEach(function(b) {{
            if (b && b.inscription_id) lines.push('btc:' + b.inscription_id);
        }});
        return lines.join('\\n');
    }}

    async function saveLayerNftGate() {{
        if (!project) return;
        const rulesEl = document.getElementById('layer-nft-gate-rules');
        const msgEl = document.getElementById('layer-nft-gate-msg');
        const rules = rulesEl ? rulesEl.value : '';
        if (msgEl) msgEl.textContent = 'Saving…';
        try {{
            const r = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ nft_gate_rules: rules }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (!r.ok) {{
                if (msgEl) msgEl.textContent = d.error || 'Save failed';
                return;
            }}
            if (d.project) project = d.project;
            if (msgEl) msgEl.textContent = 'NFT gate saved.';
        }} catch (e) {{
            if (msgEl) msgEl.textContent = e.message || 'Save failed';
        }}
    }}

    async function saveLayerStatus() {{
        if (!project) return;
        const statusEl = document.getElementById('admin-layer-status');
        const reasonEl = document.getElementById('admin-layer-status-reason');
        const msgEl = document.getElementById('admin-layer-status-msg');
        if (!statusEl) return;
        const payload = {{
            status: statusEl.value,
            status_reason: reasonEl ? reasonEl.value.trim() : ''
        }};
        if (msgEl) {{
            msgEl.textContent = 'Saving…';
            msgEl.className = 'small text-muted mt-1 mb-0';
        }}
        try {{
            const r = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }});
            const d = await r.json().catch(() => ({{}}));
            if (!r.ok) {{
                if (msgEl) {{
                    msgEl.textContent = d.error || 'Save failed';
                    msgEl.className = 'small text-danger mt-1 mb-0';
                }}
                return;
            }}
            if (d.project) project = d.project;
            displayProjectHeader();
            if (msgEl) {{
                msgEl.textContent = 'Status saved.';
                msgEl.className = 'small text-success mt-1 mb-0';
            }}
        }} catch (e) {{
            if (msgEl) {{
                msgEl.textContent = e.message || 'Save failed';
                msgEl.className = 'small text-danger mt-1 mb-0';
            }}
        }}
    }}

    async function saveNavPillConfig() {{
        if (!project) return;
        const animEl = document.getElementById('layer-nav-pill-animation');
        const tipsEl = document.getElementById('layer-nav-pill-tooltips');
        const msgEl = document.getElementById('layer-nav-pill-save-msg');
        const payload = {{
            animation: animEl ? animEl.value : 'hover-grow',
            tooltips_enabled: tipsEl ? tipsEl.checked : true,
        }};
        try {{
            const r = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ nav_pill_config: payload }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (!r.ok) {{
                if (msgEl) msgEl.textContent = d.error || 'Save failed';
                return;
            }}
            if (msgEl) {{
                msgEl.textContent = 'Saved. Refreshing tabs…';
                msgEl.className = 'small text-success mt-2 mb-0';
            }}
            setTimeout(function() {{ window.location.reload(); }}, 600);
        }} catch (e) {{
            if (msgEl) msgEl.textContent = e.message || 'Save failed';
        }}
    }}

    async function saveLayerFeatures() {{
        if (!project) return;
        const payload = {{}};
        layerFeatKeysSiteEnabled().forEach(function(k) {{
            const el = document.getElementById('layer-feat-' + k);
            if (el && !el.checked) payload[k] = false;
        }});
        const msgEl = document.getElementById('layer-feat-save-msg');
        try {{
            const r = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ enabled_features: payload }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (!r.ok) {{
                if (msgEl) msgEl.textContent = d.error || 'Save failed';
                return;
            }}
            if (d.project && d.project.effective_features) {{
                Object.keys(d.project.effective_features).forEach(function(k) {{
                    layerEffectiveFeatures[k] = d.project.effective_features[k];
                }});
            }}
            if (msgEl) {{
                msgEl.textContent = 'Saved. Updating tabs…';
                msgEl.className = 'small text-success mt-2 mb-0';
            }}
            setTimeout(function() {{ window.location.reload(); }}, 600);
        }} catch (e) {{
            if (msgEl) msgEl.textContent = e.message || 'Save failed';
        }}
    }}

    async function saveAboutContent() {{
        const textarea = document.getElementById('about-content-edit');
        if (!textarea || !project) return;
        const content = textarea.value;
        const btn = document.getElementById('save-about-btn');
        if (btn) {{ btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...'; }}
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ about_content: content }}),
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok) {{
                project.about_content = content;
                if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
                await GhDialog.alert({{ title: 'Notice', message: ('About page saved!'), variant: 'info' }});
            }} else {{
                if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to save'), variant: 'info' }});
            }}
        }} catch (e) {{
            if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to save'), variant: 'info' }});
        }}
    }}
    
    let carouselCustomItems = [];
    function renderCarouselCustomItems(items) {{
        carouselCustomItems = items || [];
        const container = document.getElementById('carousel-custom-items');
        if (!container) return;
        if (carouselCustomItems.length === 0) {{
            container.innerHTML = '<p class="text-muted small">No custom items. Add one to feature specific content.</p>';
            return;
        }}
        let html = '<div class="list-group list-group-flush">';
        carouselCustomItems.forEach((it, idx) => {{
            html += '<div class="list-group-item d-flex justify-content-between align-items-start py-2"><div><strong>' + escapeHtmlBasic((it.title || '').slice(0, 40)) + '</strong>';
            if (it.link) html += '<br><small class="text-muted">' + escapeHtmlBasic((it.link || '').slice(0, 50)) + '</small>';
            html += '</div><div><button class="btn btn-outline-danger btn-sm" onclick="removeCarouselCustomItem(' + idx + ')"><i class="fas fa-trash"></i></button></div></div>';
        }});
        html += '</div>';
        container.innerHTML = html;
    }}
    async function addCarouselCustomItem() {{
        const title = (await GhDialog.prompt({{ title: 'Enter value', message: 'Title for this carousel item:', variant: 'info' }}));
        if (!title) return;
        const link = (await GhDialog.prompt({{ title: 'Enter value', message: 'Link URL (optional):', variant: 'info' }}));
        const description = (await GhDialog.prompt({{ title: 'Enter value', message: 'Description (optional):', variant: 'info' }}));
        const image = (await GhDialog.prompt({{ title: 'Enter value', message: 'Image URL (optional):', variant: 'info' }}));
        carouselCustomItems.push({{ title: title.trim(), link: (link || '').trim() || null, description: (description || '').trim() || null, image: (image || '').trim() || null }});
        renderCarouselCustomItems(carouselCustomItems);
    }}
    function removeCarouselCustomItem(idx) {{
        carouselCustomItems.splice(idx, 1);
        renderCarouselCustomItems(carouselCustomItems);
    }}
    async function saveCarouselConfig() {{
        if (!project) return;
        const config = {{
            auto_items: {{
                recent_drafts: document.getElementById('cc-recent-drafts').checked,
                open_roles: document.getElementById('cc-open-roles').checked,
                open_opportunities: document.getElementById('cc-open-opportunities').checked
            }},
            custom_items: carouselCustomItems
        }};
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ carousel_config: config }}),
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok) {{
                project.carousel_config = JSON.stringify(config);
                loadOverview();
                await GhDialog.alert({{ title: 'Notice', message: ('Carousel saved!'), variant: 'info' }});
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to save'), variant: 'info' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to save'), variant: 'info' }});
        }}
    }}
    
    async function approveWorkgroup(wgId) {{
        const confirmed = await GhDialog.confirm({{
            title: 'Approve workgroup',
            message: 'Approve this workgroup?',
            variant: 'warning',
        }});
        if (!confirmed) return;
        try {{
            const response = await fetch('/api/workgroups/' + wgId + '/approve/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{action: 'approve'}})
            }});
            if (response.ok) {{
                loadAdmins();
                loadWorkgroups();
                await GhDialog.alert({{ title: 'Approved', message: 'Workgroup approved.', variant: 'success' }});
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Could not approve', message: data.error || 'Failed to approve workgroup', variant: 'danger' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Error', message: 'Failed to approve workgroup.', variant: 'danger' }});
        }}
    }}
    
    async function rejectWorkgroup(wgId) {{
        const confirmed = await GhDialog.confirm({{
            title: 'Reject workgroup',
            message: 'Reject this workgroup?',
            variant: 'warning',
        }});
        if (!confirmed) return;
        try {{
            const response = await fetch('/api/workgroups/' + wgId + '/approve/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{action: 'reject'}})
            }});
            if (response.ok) {{
                loadAdmins();
                loadWorkgroups();
                await GhDialog.alert({{ title: 'Rejected', message: 'Workgroup rejected.', variant: 'success' }});
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Could not reject', message: data.error || 'Failed to reject workgroup', variant: 'danger' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Error', message: 'Failed to reject workgroup.', variant: 'danger' }});
        }}
    }}
    
    function showAddAdminModal() {{
        const modal = new bootstrap.Modal(document.getElementById('addAdminModal'));
        document.getElementById('add-admin-username').value = '';
        document.getElementById('add-admin-results').innerHTML = '';
        modal.show();
    }}
    
    async function searchUsersForAdmin() {{
        const q = document.getElementById('add-admin-username').value.trim();
        const resultsEl = document.getElementById('add-admin-results');
        if (q.length < 2) {{ resultsEl.innerHTML = ''; return; }}
        const response = await fetch('/api/users/search/?q=' + encodeURIComponent(q));
        const data = await response.json();
        if (data.users.length === 0) {{
            resultsEl.innerHTML = '<p class="text-muted small">No users found</p>';
            return;
        }}
        resultsEl.innerHTML = data.users.map(u => {{
            const uNameEsc = escapeHtml(u.display_name || '');
            const uUserEsc = escapeHtml(u.username || '');
            const uIdEsc = escapeForJsAttr(String(u.id || ''));
            return '<div class="d-flex justify-content-between align-items-center border-bottom py-2"><span>' + uNameEsc + ' <small class="text-muted">@' + uUserEsc + '</small></span><button class="btn btn-sm btn-primary" onclick="addAdmin(\\'' + uIdEsc + '\\')">Add</button></div>';
        }}).join('');
    }}
    
    async function addAdmin(userId) {{
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ user_id: userId }})
            }});
            const data = await response.json();
            if (response.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('addAdminModal')).hide();
                loadAdmins();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to add admin'), variant: 'info' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to add admin'), variant: 'info' }});
        }}
    }}
    
    async function removeAdmin(userId, btn) {{
        const displayName = (btn && btn.closest('.list-group-item')) ? btn.closest('.list-group-item').querySelector('a').textContent : 'this user';
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Remove "' + displayName + '" as layer admin?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/' + userId + '/', {{ method: 'DELETE' }});
            const data = await response.json();
            if (response.ok) {{
                loadAdmins();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to remove admin'), variant: 'info' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to remove admin'), variant: 'info' }});
        }}
    }}
    
    async function loadWorkgroups() {{
        document.getElementById('workgroups-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/workgroups/');
            const data = await response.json();
            layerWorkgroupsList = data.workgroups || [];
            renderLayerWorkgroupsChrome();
            renderLayerWorkgroupsList();
        }} catch (error) {{
            console.error('Error loading workgroups:', error);
            document.getElementById('workgroups-content').innerHTML = '<div class="alert alert-danger">Error loading workgroups</div>';
        }}
    }}

    function filterLayerWorkgroups() {{
        renderLayerWorkgroupsList();
    }}

    function renderLayerWorkgroupsChrome() {{
        const wgBtn = isAuthenticated ? '<button class="btn btn-primary btn-sm" onclick="createWorkgroup()"><i class="fas fa-plus me-2"></i>Create Workgroup</button>' : '';
        document.getElementById('workgroups-content').innerHTML =
            '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">' +
            '<h4 class="mb-0">Workgroups (<span id="layer-wg-count">0</span>)</h4>' + wgBtn + '</div>' +
            '<div class="row g-2 mb-3">' +
            '<div class="col-md-5">' +
            '<input type="search" id="layer-wg-search" class="form-control form-control-sm" placeholder="Search workgroups..." oninput="filterLayerWorkgroups()">' +
            '</div><div class="col-md-4">' +
            '<select id="layer-wg-sort" class="form-select form-select-sm" onchange="filterLayerWorkgroups()">' +
            '<option value="name-asc" selected>A–Z</option><option value="name-desc">Z–A</option><option value="recent">Most recent</option>' +
            '</select></div></div>' +
            '<div id="workgroups-list"></div>';
    }}

    function renderLayerWorkgroupsList() {{
        const term = (document.getElementById('layer-wg-search')?.value || '').trim();
        const sort = document.getElementById('layer-wg-sort')?.value || 'name-asc';
        let items = GhDirectory.filterAndSort(layerWorkgroupsList, {{
            searchTerm: term,
            sort: sort,
            searchFields: ['name', 'description', 'acronym', 'slug'],
            nameKey: 'name',
            dateKeys: ['updated_at', 'created_at'],
        }});

        const countEl = document.getElementById('layer-wg-count');
        if (countEl) {{
            countEl.textContent = items.length === layerWorkgroupsList.length
                ? String(items.length)
                : (items.length + ' of ' + layerWorkgroupsList.length);
        }}

        const listEl = document.getElementById('workgroups-list');
        if (!listEl) return;

        if (items.length === 0) {{
            listEl.innerHTML = layerWorkgroupsList.length === 0
                ? '<div class="alert alert-info">No workgroups yet</div>'
                : '<div class="alert alert-info">No workgroups match your search</div>';
            return;
        }}

        let html = '<div class="row">';
        items.forEach(wg => {{
            const approvalBadge = wg.approval_status === 'pending' ? '<span class="badge bg-warning ms-2">Pending Approval</span>' : (wg.approval_status === 'rejected' ? '<span class="badge bg-danger ms-2">Rejected</span>' : '');
            const wgImg = wg.image_url ? '<div class="gh-card-entity-visual"><img src="' + escapeHtmlBasic(wg.image_url) + '" alt="' + escapeHtmlBasic(wg.name) + '"></div>' : '';
            const wgNameEsc = escapeHtml(wg.name || '');
            const wgDescEsc = escapeHtml(wg.description || 'No description');
            const wgSlugEsc = escapeHtmlBasic(wg.slug || '');
            const wgStatusEsc = escapeHtml(String(wg.status || ''));
            html += '<div class="col-md-6 mb-3"><div class="card">' + wgImg + '<div class="card-body"><h5 class="card-title"><a href="/workgroups/' + wgSlugEsc + '/">' + wgNameEsc + '</a></h5><p class="card-text text-muted" data-gh-clamp-6>' + wgDescEsc + '</p><a class="gh-card-more" href="/workgroups/' + wgSlugEsc + '/" data-gh-more hidden>More</a><span class="badge bg-' + (wg.status === 'active' ? 'success' : 'secondary') + '">' + wgStatusEsc + '</span>' + approvalBadge + '</div></div></div>';
        }});
        html += '</div>';
        listEl.innerHTML = html;
    }}
    
    async function loadClusters() {{
        document.getElementById('clusters-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/clusters/?include_roles=1');
            const data = await response.json();
            
            const clusterBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createCluster()"><i class="fas fa-plus me-2"></i>Create Cluster</button>' : '';
            let html = '<div class="d-flex justify-content-between mb-3"><h4>Role Clusters (' + (data.count || 0) + ')</h4>' + clusterBtn + '</div><p class="text-muted">Clusters group related roles together for better organization.</p>';
            
            const clusters = Array.isArray(data.clusters) ? data.clusters : [];
            if (clusters.length === 0) {{
                html += '<div class="alert alert-info">No clusters yet. Create one to organize your roles!</div>';
            }} else {{
                html += '<div class="row">';
                clusters.forEach(cluster => {{
                    if (!cluster) return;
                    const cName = (cluster.name != null && cluster.name !== '') ? cluster.name : 'Unnamed';
                    const cNameEsc = escapeForJsAttr(cName);
                    const cDescEsc = escapeHtml(cluster.description || 'No description');
                    const roles = cluster.roles || [];
                    const rolesHtml = roles.length
                        ? '<ul class="list-unstyled mb-0 mt-2 small">' + roles.map(r => '<li><a href="/layer/' + (project.slug || project.id || '') + '/roles/' + escapeHtmlBasic(r.role_slug || r.slug || '') + '/">' + escapeHtml(r.title_guild || r.title_operational || 'Role') + '</a></li>').join('') + '</ul>'
                        : '<p class="text-muted small mb-0 mt-2">No roles in this cluster</p>';
                    const orderStr = cluster.order != null ? cluster.order : '–';
                    const adminBtns = isProjectAdmin ? '<div class="btn-group btn-group-sm"><button class="btn btn-outline-secondary" onclick="editCluster(\\'' + (cluster.id || '') + '\\')"><i class="fas fa-edit"></i></button><button class="btn btn-outline-danger" onclick="deleteCluster(\\'' + (cluster.id || '') + '\\', \\'' + cNameEsc + '\\')"><i class="fas fa-trash"></i></button></div>' : '';
                    html += '<div class="col-md-6 mb-3"><div class="card"><div class="card-body"><div class="d-flex justify-content-between align-items-start"><div><h5 class="card-title">' + escapeHtml(cName) + '</h5><p class="card-text text-muted">' + cDescEsc + '</p><small class="text-muted">Order: ' + orderStr + '</small><div class="mt-2"><strong>Roles:</strong> ' + rolesHtml + '</div></div>' + adminBtns + '</div></div></div></div>';
                }});
                html += '</div>';
            }}
            
            document.getElementById('clusters-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading clusters:', error);
            document.getElementById('clusters-content').innerHTML = '<div class="alert alert-danger">Error loading clusters</div>';
        }}
    }}
    
    async function loadRoles() {{
        document.getElementById('roles-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/roles/');
            const data = await response.json();
            layerRolesList = data.roles || [];
            renderLayerRolesChrome();
            renderLayerRolesList();
        }} catch (error) {{
            console.error('Error loading roles:', error);
            document.getElementById('roles-content').innerHTML = '<div class="alert alert-danger">Error loading roles</div>';
        }}
    }}

    function filterLayerRoles() {{
        renderLayerRolesList();
    }}

    function renderLayerRolesChrome() {{
        const roleBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createRole()"><i class="fas fa-plus me-2"></i>Create Role</button>' : '';
        document.getElementById('roles-content').innerHTML =
            '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">' +
            '<h4 class="mb-0">Roles (<span id="layer-roles-count">0</span>)</h4>' + roleBtn + '</div>' +
            '<div class="row g-2 mb-3">' +
            '<div class="col-md-5">' +
            '<input type="search" id="layer-roles-search" class="form-control form-control-sm" placeholder="Search roles..." oninput="filterLayerRoles()">' +
            '</div><div class="col-md-4">' +
            '<select id="layer-roles-sort" class="form-select form-select-sm" onchange="filterLayerRoles()">' +
            '<option value="recent" selected>Most recent</option><option value="name-asc">A–Z</option><option value="name-desc">Z–A</option>' +
            '</select></div></div>' +
            '<div id="roles-list"></div>';
    }}

    function renderLayerRolesList() {{
        const term = (document.getElementById('layer-roles-search')?.value || '').trim();
        const sort = document.getElementById('layer-roles-sort')?.value || 'recent';
        let items = GhDirectory.filterAndSort(layerRolesList, {{
            searchTerm: term,
            sort: sort,
            searchFields: ['title_guild', 'title_operational', 'description', 'role_slug', 'slug'],
            nameKey: 'title_guild',
            dateKeys: ['updated_at', 'created_at'],
        }});

        const countEl = document.getElementById('layer-roles-count');
        if (countEl) {{
            countEl.textContent = items.length === layerRolesList.length
                ? String(items.length)
                : (items.length + ' of ' + layerRolesList.length);
        }}

        const listEl = document.getElementById('roles-list');
        if (!listEl) return;

        if (items.length === 0) {{
            listEl.innerHTML = layerRolesList.length === 0
                ? '<div class="alert alert-info">No roles yet</div>'
                : '<div class="alert alert-info">No roles match your search</div>';
            return;
        }}

        let html = '<div class="row">';
        items.forEach(role => {{
            const roleSlugEsc = escapeHtmlBasic(role.role_slug || role.slug || '');
            const titleGuildEsc = escapeHtml(role.title_guild || '');
            const titleOpEsc = role.title_operational ? '<h6 class="card-subtitle mb-2 text-muted">' + escapeHtml(role.title_operational) + '</h6>' : '';
            const descEsc = escapeHtml((role.description || '').substring(0, 150));
            const statusEsc = escapeHtml(String(role.status || ''));
            const statusClass = role.status === 'approved' ? 'success' : 'warning';
            const publicBadge = role.public_visible ? '<span class="badge bg-info ms-2">Public</span>' : '';
            html += '<div class="col-md-6 mb-3"><div class="card"><div class="card-body"><h5 class="card-title"><a href="/layer/' + (project.slug || project.id || '') + '/roles/' + roleSlugEsc + '/">' + titleGuildEsc + '</a></h5>' + titleOpEsc + '<p class="card-text">' + descEsc + '...</p><span class="badge bg-' + statusClass + '">' + statusEsc + '</span>' + publicBadge + '</div></div></div>';
        }});
        html += '</div>';
        listEl.innerHTML = html;
    }}
    
    async function loadClaims() {{
        document.getElementById('claims-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/claims/');
            const data = await response.json();
            
            let html = '<h4 class="mb-3">Claims (' + (data.count || 0) + ')</h4>';
            
            if (!data.claims || data.claims.length === 0) {{
                html += '<div class="alert alert-info">No claims yet</div>';
            }} else {{
                html += '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>Claim</th><th>Status</th><th>Role</th><th>User</th></tr></thead><tbody>';
                data.claims.forEach((claim, idx) => {{
                    const claimName = claim.role_name ? (claim.intent ? (claim.intent.substring(0, 40) + (claim.intent.length > 40 ? '…' : '')) : ('Claim: ' + claim.role_name)) : ('Claim #' + (claim.id || '').toString().slice(-6));
                    const roleName = claim.role_name || ('Role ' + (claim.role_id || '').toString().slice(-6));
                    const roleLink = claim.role_slug ? '/layer/' + (project.slug || project.id || '') + '/roles/' + escapeHtmlBasic(claim.role_slug) + '/' : '#';
                    const userName = claim.claimant_name || ('User #' + (claim.claimant_id || ''));
                    const userLink = claim.claimant_username ? '/profile/' + escapeHtmlBasic(claim.claimant_username) + '/' : '#';
                    const statusClass = claim.status === 'active' ? 'success' : (claim.status === 'pending_approval' ? 'warning' : 'secondary');
                    const claimNameEsc = escapeHtml(claimName);
                    const roleNameEsc = escapeHtml(roleName);
                    const userNameEsc = escapeHtml(userName);
                    const statusEsc = escapeHtml(claim.status || '–');
                    const tdRole = claim.role_slug ? '<a href="' + roleLink + '">' + roleNameEsc + '</a>' : roleNameEsc;
                    const tdUser = claim.claimant_username ? '<a href="' + userLink + '">' + userNameEsc + '</a>' : userNameEsc;
                    html += '<tr class="project-claim-row" data-claim-index="' + idx + '" tabindex="0" title="Hover for claim details"><td>' + claimNameEsc + '</td><td><span class="badge bg-' + statusClass + '">' + statusEsc + '</span></td><td>' + tdRole + '</td><td>' + tdUser + '</td></tr>';
                }});
                html += '</tbody></table></div>';
            }}
            
            document.getElementById('claims-content').innerHTML = html;
            
            // Attach claim popover (same content as role detail page) on hover
            if (data.claims && data.claims.length > 0) {{
                function getClaimPopoverContent(c) {{
                    const intent = c.intent ? '<p class="mb-2"><strong>Intent:</strong><br><span style="white-space: pre-wrap; word-wrap: break-word;">' + (c.intent || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span></p>' : '';
                    const links = (c.evidence_links || []).filter(u => u && u.trim());
                    const evidenceHtml = links.length ? links.map(u => '<a href="' + u + '" target="_blank" rel="noopener">' + u + '</a>').join('<br>') : '<span class="text-muted">No evidence yet</span>';
                    const termStr = c.term_duration_days ? (c.term_duration_days + ' days' + (c.term_end ? ', until ' + new Date(c.term_end).toLocaleDateString() : '')) : 'Indefinite';
                    return '<div class="text-start" style="min-width: 280px; max-width: 480px; white-space: normal; word-wrap: break-word;">' + intent +
                        '<p class="mb-2"><strong>Supporting work:</strong><br>' + evidenceHtml + '</p>' +
                        '<p class="mb-2"><strong>Term:</strong> ' + termStr + '</p>' +
                        '<p class="mb-0 small text-muted">Claimed: ' + new Date(c.created_at).toLocaleDateString() + '</p></div>';
                }}
                document.querySelectorAll('.project-claim-row').forEach(el => {{
                    const idx = parseInt(el.getAttribute('data-claim-index'), 10);
                    const claim = data.claims[idx];
                    if (claim) {{
                        new bootstrap.Popover(el, {{ content: getClaimPopoverContent(claim), html: true, trigger: 'hover focus', placement: 'auto', container: 'body' }});
                    }}
                }});
            }}
        }} catch (error) {{
            console.error('Error loading claims:', error);
            document.getElementById('claims-content').innerHTML = '<div class="alert alert-danger">Error loading claims</div>';
        }}
    }}
    
    async function loadWaitlists() {{
        document.getElementById('waitlist-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        try {{
            const response = await fetch('/api/layers/' + project.id + '/waitlists/');
            const data = await response.json();
            
            const wlBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button>' : '';
            let html = '<div class="d-flex justify-content-between align-items-center mb-4"><h4>Waitlists (' + (data.count || 0) + ')</h4>' + wlBtn + '</div>';
            
            if (!data.waitlists || data.waitlists.length === 0) {{
                html += '<div class="alert alert-info">No waitlists yet</div>';
            }} else {{
                data.waitlists.forEach(wl => {{
                    const started = wl.started;
                    const closed = wl.closed;
                    const full = wl.full;
                    const canJoin = isAuthenticated && started && !closed && !full && !wl.my_entry;
                    const statusBadge = full ? '<span class="badge bg-danger">Full</span>' : (closed ? '<span class="badge bg-secondary">Closed</span>' : (started ? '<span class="badge bg-success">Open</span>' : '<span class="badge bg-warning">Not Started</span>'));
                    const myEntry = wl.my_entry;
                    const wlNameEsc = escapeHtml(wl.name || '');
                    const wlDescEsc = escapeHtml(wl.description || 'No description');
                    const projSlugEsc = escapeHtmlBasic(project.slug || '');
                    const startStr = new Date(wl.start_date).toLocaleDateString();
                    const visStr = wl.public ? 'Public' : 'Private (layer members or link)';
                    const refBlock = wl.referral_url && myEntry ? '<p class="mb-2"><strong>Your referral link:</strong> <code class="user-select-all">' + escapeHtmlBasic(wl.referral_url) + '</code> <button class="btn btn-sm btn-outline-primary" onclick="copyText(\\'' + escapeForJsAttr(wl.referral_url) + '\\')"><i class="fas fa-copy"></i></button></p>' : '';
                    const joinHint = !myEntry && wl.referrals ? '<p class="text-muted mb-2"><em>Join to get your referral link</em></p>' : '';
                    const milestonesHtml = wl.milestones && wl.milestones.length > 0 ? '<hr><h5 class="mt-3">Milestones</h5><ul class="list-unstyled">' + wl.milestones.map(m => '<li class="mb-2"><strong>' + escapeHtml(m.title || '') + '</strong> (at ' + m.threshold + ' members)' + (m.description ? '<br><small class="text-muted">' + escapeHtml(m.description) + '</small>' : '') + '</li>').join('') + '</ul>' : '';
                    const actionsBlock = myEntry ? '<div class="mb-3"><span class="badge bg-success fs-6">Joined</span> <span class="text-muted">#' + myEntry.position + '</span><br><button class="btn btn-outline-danger btn-sm mt-2" data-waitlist-id="' + escapeHtmlBasic(String(wl.id || '')) + '" onclick="leaveWaitlist(this.dataset.waitlistId)">Leave</button></div>' : (canJoin ? '<button class="btn btn-primary w-100 mb-3" data-waitlist-id="' + escapeHtmlBasic(String(wl.id || '')) + '" onclick="joinWaitlist(this.dataset.waitlistId)">Join Waitlist</button>' : '<p class="text-muted">' + (started ? (closed ? 'Closed' : (full ? 'Full' : 'Login to join')) : 'Not started') + '</p>');
                    const countStr = wl.count + (wl.max_number ? ' of ' + wl.max_number : '');
                    const closeStr = wl.closing_date ? '<p class="mb-2"><strong>Closes:</strong> ' + new Date(wl.closing_date).toLocaleDateString() + '</p>' : '';
                    const embedBtn = isProjectAdmin ? '<hr><p class="small text-muted mb-2">Embed this waitlist on your website:</p><button class="btn btn-outline-primary btn-sm w-100" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + wl.id + '" data-waitlist-name="' + escapeHtmlBasic(wl.name || '') + '"><i class="fas fa-code me-2"></i>Get Embed Code</button>' : '';
                    const wlBc = showCarousel ? '<li class="breadcrumb-item"><a href="' + layerBase + '">' + escapeHtmlBasic(project.name || '') + '</a></li>' : '<li class="breadcrumb-item"><a href="/layers/' + projSlugEsc + '/">Layer</a></li>';
                    html += '<div class="card mb-4 waitlist-card" id="waitlist-' + wl.id + '" style="border-left: 4px solid var(--accent-color);"><div class="card-body"><div class="row"><div class="col-md-8"><nav aria-label="breadcrumb"><ol class="breadcrumb">' + wlBc + '<li class="breadcrumb-item active">' + wlNameEsc + ' Waitlist</li></ol></nav><h3 class="mb-3">' + wlNameEsc + '</h3><p class="lead">' + wlDescEsc + '</p><p class="text-muted mb-2"><strong>Started:</strong> ' + startStr + '</p><p class="text-muted mb-2"><strong>Visibility:</strong> ' + visStr + '</p>' + refBlock + joinHint + milestonesHtml + '</div><div class="col-md-4"><div class="card"><div class="card-body"><h5 class="card-title">Actions</h5>' + actionsBlock + '<p class="mb-2"><strong>On waitlist:</strong> ' + countStr + '</p>' + closeStr + statusBadge + embedBtn + '</div></div></div></div></div></div>';
                }});
            }}
            
            document.getElementById('waitlist-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading waitlists:', error);
            document.getElementById('waitlist-content').innerHTML = '<div class="alert alert-danger">Error loading waitlists</div>';
        }}
    }}
    
    async function joinWaitlist(wlId) {{
        if (!isAuthenticated) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please sign in to join'), variant: 'info' }}); return; }}
        const msg = (await GhDialog.prompt({{ title: 'Enter value', message: 'Optional message:', variant: 'info' }}));
        if (msg === null) return;
        try {{
            const body = {{ message: msg }};
            if (referralRefToken) body.ref_token = referralRefToken;
            const res = await fetch('/api/waitlists/' + wlId + '/join/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const d = await res.json();
            if (res.ok) {{
                await GhDialog.alert({{ title: 'Notice', message: ('Joined! Position: #' + d.entry.position), variant: 'info' }});
                loadWaitlists();
            }} else {{ await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed to join'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to join waitlist'), variant: 'info' }}); }}
    }}
    
    async function leaveWaitlist(wlId) {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Leave this waitlist?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const res = await fetch('/api/waitlists/' + wlId + '/leave/', {{ method: 'POST' }});
            if (res.ok) {{ loadWaitlists(); }} else {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to leave'), variant: 'info' }}); }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Failed to leave waitlist'), variant: 'info' }}); }}
    }}
    
    function copyText(text) {{
        navigator.clipboard.writeText(text).then(() => {{
            const btn = event.target.closest('button');
            if (btn) {{ const o = btn.innerHTML; btn.innerHTML = '<i class="fas fa-check"></i>'; setTimeout(() => btn.innerHTML = o, 1500); }}
        }});
    }}

    const layerInviteStorageKey = 'gh_layer_invite';

    function getPendingLayerInvite() {{
        try {{
            const raw = sessionStorage.getItem(layerInviteStorageKey);
            if (raw) {{
                const parsed = JSON.parse(raw);
                if (parsed && parsed.token) return parsed;
            }}
        }} catch (e) {{}}
        const params = new URLSearchParams(window.location.search);
        const token = params.get('invite');
        if (token) {{
            return {{ token: token, layerSlug: projectSlug }};
        }}
        return null;
    }}

    function persistLayerInviteFromPreview(token, layer, inviterName) {{
        try {{
            sessionStorage.setItem(layerInviteStorageKey, JSON.stringify({{
                token: token,
                layerSlug: layer.slug,
                layerId: layer.id,
                layerName: layer.name || '',
                inviterName: inviterName || '',
                savedAt: Date.now()
            }}));
        }} catch (e) {{}}
    }}

    function clearPendingLayerInvite() {{
        try {{ sessionStorage.removeItem(layerInviteStorageKey); }} catch (e) {{}}
    }}

    async function maybeShowLayerInviteBanner() {{
        const banner = document.getElementById('layer-invite-banner');
        if (!banner || !project) return;
        if (project.is_member) {{
            clearPendingLayerInvite();
            banner.classList.add('d-none');
            banner.innerHTML = '';
            return;
        }}
        const pending = getPendingLayerInvite();
        if (!pending || !pending.token) {{
            banner.classList.add('d-none');
            banner.innerHTML = '';
            return;
        }}
        if (pending.layerSlug && pending.layerSlug !== projectSlug) {{
            banner.classList.add('d-none');
            banner.innerHTML = '';
            return;
        }}
        try {{
            const r = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(pending.token) + '/');
            const d = await r.json();
            if (!r.ok) {{
                clearPendingLayerInvite();
                banner.classList.add('d-none');
                banner.innerHTML = '';
                return;
            }}
            const layer = d.layer || {{}};
            if (layer.slug && layer.slug !== projectSlug) {{
                banner.classList.add('d-none');
                banner.innerHTML = '';
                return;
            }}
            persistLayerInviteFromPreview(pending.token, layer, d.inviter_name);
            const inviter = escapeHtml(d.inviter_name || 'A member');
            const inviteUrl = '/layer/invite/' + encodeURIComponent(pending.token) + '/';
            banner.innerHTML =
                '<div class="alert alert-success mb-0 d-flex flex-wrap align-items-center justify-content-between gap-3">' +
                '<div><strong>You\\'re invited!</strong> ' + inviter + ' invited you to join this layer.</div>' +
                '<div class="d-flex flex-wrap gap-2">' +
                (isAuthenticated
                    ? '<button type="button" class="btn btn-success btn-sm" id="layer-invite-accept-btn">Accept invitation</button>' +
                      '<button type="button" class="btn btn-outline-secondary btn-sm" id="layer-invite-decline-btn">Decline</button>'
                    : '<a href="/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search) + '" class="btn btn-success btn-sm">Log in to accept</a>') +
                '<a href="' + inviteUrl + '" class="btn btn-link btn-sm">Invitation details</a>' +
                '</div></div>';
            banner.classList.remove('d-none');
            const acceptBtn = document.getElementById('layer-invite-accept-btn');
            const declineBtn = document.getElementById('layer-invite-decline-btn');
            if (acceptBtn) {{
                acceptBtn.addEventListener('click', async function() {{
                    acceptBtn.disabled = true;
                    try {{
                        const ar = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(pending.token) + '/accept/', {{
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: '{{}}'
                        }});
                        const ad = await ar.json();
                        if (ar.ok) {{
                            clearPendingLayerInvite();
                            project.is_member = true;
                            displayProjectHeader();
                            banner.innerHTML = '<div class="alert alert-success mb-0">' +
                                escapeHtml(ad.duplicate || ad.already_member ? 'You are already a member of this layer.' : 'You joined the layer!') +
                                '</div>';
                            await refreshProjectFromApi();
                        }} else {{
                            await GhDialog.alert({{ title: 'Notice', message: (ad.error || 'Failed to accept invitation'), variant: 'info' }});
                            acceptBtn.disabled = false;
                        }}
                    }} catch (e) {{
                        await GhDialog.alert({{ title: 'Notice', message: (e.message || 'Failed to accept invitation'), variant: 'info' }});
                        acceptBtn.disabled = false;
                    }}
                }});
            }}
            if (declineBtn) {{
                declineBtn.addEventListener('click', async function() {{
                    if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Decline this invitation?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
                    declineBtn.disabled = true;
                    try {{
                        const dr = await fetch('/api/layer-invitations/by-token/' + encodeURIComponent(pending.token) + '/decline/', {{
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: '{{}}'
                        }});
                        const dd = await dr.json();
                        if (dr.ok) {{
                            clearPendingLayerInvite();
                            banner.classList.add('d-none');
                            banner.innerHTML = '';
                        }} else {{
                            await GhDialog.alert({{ title: 'Notice', message: (dd.error || 'Failed to decline invitation'), variant: 'info' }});
                            declineBtn.disabled = false;
                        }}
                    }} catch (e) {{
                        await GhDialog.alert({{ title: 'Notice', message: (e.message || 'Failed to decline invitation'), variant: 'info' }});
                        declineBtn.disabled = false;
                    }}
                }});
            }}
        }} catch (e) {{
            console.warn('maybeShowLayerInviteBanner:', e);
        }}
    }}
    
    function showEmbedCodeFromEl(el) {{
        const id = el.getAttribute('data-waitlist-id');
        const name = el.getAttribute('data-waitlist-name') || '';
        showEmbedCode(parseInt(id, 10), name);
    }}
    function showEmbedCode(waitlistId, waitlistName) {{
        const baseUrl = window.location.origin;
        const embedUrl = baseUrl + '/embed/waitlist/' + waitlistId + '/';
        const iframeCode = '<iframe src="' + escapeHtmlBasic(embedUrl) + '" width="100%" height="600" frameborder="0" style="border: none; border-radius: 12px;"></iframe>';
        
        document.getElementById('embed-waitlist-name').textContent = waitlistName;
        document.getElementById('embed-builder-link').href = baseUrl + '/embed/waitlist/' + waitlistId + '/build/';
        document.getElementById('embed-url').value = embedUrl;
        document.getElementById('embed-code-iframe').value = iframeCode;
        
        const modal = new bootstrap.Modal(document.getElementById('embedCodeModal'));
        modal.show();
    }}
    
    function copyEmbedCode(type) {{
        const elementId = type === 'iframe' ? 'embed-code-iframe' : 'embed-url';
        const element = document.getElementById(elementId);
        element.select();
        navigator.clipboard.writeText(element.value).then(() => {{
            const btn = event.target.closest('button');
            if (btn) {{
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => btn.innerHTML = original, 2000);
            }}
        }});
    }}
    
    async function uploadWaitlistImage() {{
        const fileInput = document.getElementById('wl-image-file');
        const statusEl = document.getElementById('wl-image-upload-status');
        const urlInput = document.getElementById('wl-image-url');
        
        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'waitlist');
        
        statusEl.innerHTML = '<small class="text-info"><i class="fas fa-spinner fa-spin"></i> Uploading...</small>';
        
        try {{
            const response = await fetch('/api/upload/entity-image', {{
                method: 'POST',
                credentials: 'include',
                body: formData
            }});
            
            const data = await response.json();
            
            if (response.ok && data.image_url) {{
                urlInput.value = data.image_url;
                statusEl.innerHTML = '<small class="text-success"><i class="fas fa-check"></i> Uploaded successfully</small>';
                fileInput.value = '';
            }} else {{
                statusEl.innerHTML = '<small class="text-danger">' + escapeHtml(data.error || 'Upload failed') + '</small>';
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}
    
    function createWaitlist() {{
        const modalHtml = `
            <div class="modal fade" id="createWaitlistModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create Waitlist</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="wl-alert-container"></div>
                            <form id="createWaitlistForm">
                                <div class="mb-3">
                                    <label for="wl-name" class="form-label">Waitlist Name *</label>
                                    <input type="text" class="form-control" id="wl-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="wl-description" rows="3"></textarea>
                                </div>
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label for="wl-start-date" class="form-label">Start Date *</label>
                                        <input type="date" class="form-control" id="wl-start-date" required>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label for="wl-closing-date" class="form-label">Closing Date (optional)</label>
                                        <input type="date" class="form-control" id="wl-closing-date">
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-max-number" class="form-label">Max Number of Entries (optional)</label>
                                    <input type="number" class="form-control" id="wl-max-number" min="1">
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-public" checked>
                                    <label class="form-check-label" for="wl-public">Public (visible to all)</label>
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-referrals" checked>
                                    <label class="form-check-label" for="wl-referrals">Enable Referrals</label>
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-active" checked>
                                    <label class="form-check-label" for="wl-active">Active</label>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-image-url" class="form-label">Image (optional)</label>
                                    <input type="url" class="form-control mb-2" id="wl-image-url" placeholder="https://example.com/image.png or upload below">
                                    <div class="input-group">
                                        <input type="file" class="form-control" id="wl-image-file" accept="image/*">
                                        <button class="btn btn-outline-primary" type="button" onclick="uploadWaitlistImage()">
                                            <i class="fas fa-upload"></i> Upload
                                        </button>
                                    </div>
                                    <div class="form-text">Waitlist banner or icon. Max 600×600px, 5MB. Upload or paste URL above.</div>
                                    <div id="wl-image-upload-status" class="mt-1"></div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitWaitlistBtn">
                                <i class="fas fa-plus me-2"></i>Create Waitlist
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('createWaitlistModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('wl-alert-container').innerHTML = '';
        document.getElementById('wl-name').value = '';
        document.getElementById('wl-description').value = '';
        document.getElementById('wl-image-url').value = '';
        document.getElementById('wl-start-date').value = new Date().toISOString().split('T')[0];
        document.getElementById('wl-closing-date').value = '';
        document.getElementById('wl-max-number').value = '';
        document.getElementById('wl-public').checked = true;
        document.getElementById('wl-referrals').checked = true;
        document.getElementById('wl-active').checked = true;
        if (document.getElementById('wl-image-url')) document.getElementById('wl-image-url').value = '';
        if (document.getElementById('wl-image-file')) document.getElementById('wl-image-file').value = '';
        if (document.getElementById('wl-image-upload-status')) document.getElementById('wl-image-upload-status').innerHTML = '';
        const modal = new bootstrap.Modal(document.getElementById('createWaitlistModal'));
        modal.show();
        document.getElementById('submitWaitlistBtn').onclick = async () => {{
            const name = document.getElementById('wl-name').value.trim();
            const description = document.getElementById('wl-description').value.trim();
            const image_url = document.getElementById('wl-image-url').value.trim();
            const startDate = document.getElementById('wl-start-date').value;
            const closingDate = document.getElementById('wl-closing-date').value;
            const maxNumber = document.getElementById('wl-max-number').value;
            const isPublic = document.getElementById('wl-public').checked;
            const referrals = document.getElementById('wl-referrals').checked;
            const active = document.getElementById('wl-active').checked;
            if (!name || !startDate) {{
                document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">Name and start date are required.</div>';
                return;
            }}
            const btn = document.getElementById('submitWaitlistBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            try {{
                const body = {{ name, description, image_url: image_url || null, start_date: startDate, public: isPublic, referrals, active }};
                if (closingDate) body.closing_date = closingDate;
                if (maxNumber) body.max_number = parseInt(maxNumber, 10);
                const res = await fetch('/api/layers/' + project.id + '/waitlists/', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(body)
                }});
                const d = await res.json();
                if (res.ok) {{
                    modal.hide();
                    loadWaitlists();
                }} else {{
                    document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">' + (d.error || 'Failed to create waitlist') + '</div>';
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Waitlist';
                }}
            }} catch (e) {{
                document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">Failed to create waitlist</div>';
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Waitlist';
            }}
        }};
    }}
    
    function getStatusBadge(status) {{
        const badges = {{
            'proposed': '<span class="badge bg-info">Proposed</span>',
            'active': '<span class="badge bg-success">Active</span>',
            'stabilizing': '<span class="badge bg-primary">Stabilizing</span>',
            'maintaining': '<span class="badge bg-secondary">Maintaining</span>',
            'dormant': '<span class="badge bg-warning">Dormant</span>',
            'concluded': '<span class="badge bg-dark">Concluded</span>',
            'archived': '<span class="badge bg-secondary">Archived</span>'
        }};
        return badges[status] || '';
    }}
    
    function getApprovalBadge(approval) {{
        const badges = {{
            'pending': '<span class="badge bg-warning">Pending Approval</span>',
            'approved': '<span class="badge bg-success">Approved</span>',
            'rejected': '<span class="badge bg-danger">Rejected</span>'
        }};
        return badges[approval] || '';
    }}
    
    function openProjectImageCrop() {{
        const fileInput = document.getElementById('edit-project-image-file');
        const statusEl = document.getElementById('edit-project-image-upload-status');
        if (!fileInput.files || !fileInput.files[0]) return;
        const file = fileInput.files[0];
        if (!file.type.startsWith('image/')) {{
            statusEl.innerHTML = '<small class="text-danger">Please select an image file</small>';
            fileInput.value = '';
            return;
        }}
        statusEl.innerHTML = '';
        GhImageCrop.open(file, {{
            onConfirm: function(blob) {{ uploadCroppedProjectImage(blob); }},
            onCancel: function() {{ fileInput.value = ''; }}
        }});
    }}

    async function uploadCroppedProjectImage(blob) {{
        const fileInput = document.getElementById('edit-project-image-file');
        const statusEl = document.getElementById('edit-project-image-upload-status');
        const urlInput = document.getElementById('edit-project-image-url');
        const previewImg = document.getElementById('edit-project-image-preview');

        const formData = new FormData();
        formData.append('file', new File([blob], 'layer-image.jpg', {{ type: 'image/jpeg' }}));
        formData.append('entity_type', 'project');

        statusEl.innerHTML = '<small class="text-info"><i class="fas fa-spinner fa-spin"></i> Uploading...</small>';

        try {{
            const response = await fetch('/api/upload/entity-image', {{
                method: 'POST',
                credentials: 'include',
                body: formData
            }});

            const data = await response.json();

            if (response.ok && data.image_url) {{
                urlInput.value = data.image_url;
                previewImg.src = data.image_url;
                previewImg.classList.remove('d-none');
                try {{
                    const patchRes = await fetch('/api/layers/' + project.id + '/', {{
                        method: 'PATCH',
                        headers: {{ 'Content-Type': 'application/json' }},
                        credentials: 'include',
                        body: JSON.stringify({{ image_url: data.image_url }})
                    }});
                    const patchData = await patchRes.json();
                    if (patchRes.ok && patchData.project) {{
                        project = patchData.project;
                        project._imgBust = Date.now();
                        await refreshProjectFromApi();
                        syncLayerBrandImages();
                        statusEl.innerHTML = '<small class="text-success"><i class="fas fa-check"></i> Image cropped, uploaded, and saved</small>';
                    }} else {{
                        const err = (patchData && patchData.error) ? patchData.error : ('HTTP ' + patchRes.status);
                        statusEl.innerHTML = '<small class="text-danger"><i class="fas fa-exclamation-triangle"></i> Upload OK but save failed: ' + escapeHtmlBasic(err) + '</small>';
                    }}
                }} catch (_) {{
                    statusEl.innerHTML = '<small class="text-warning"><i class="fas fa-check"></i> Uploaded – click Save to apply</small>';
                }}
                fileInput.value = '';
            }} else {{
                statusEl.innerHTML = '<small class="text-danger">' + escapeHtml(data.error || 'Upload failed') + '</small>';
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}
    
    async function editProject() {{
        if (!project) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Layer details are still loading. Please wait a moment and try again.'), variant: 'info' }});
            return;
        }}
        if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Unable to open the edit dialog (page scripts did not load). Try refreshing the page.'), variant: 'info' }});
            return;
        }}
        document.getElementById('edit-project-name').value = project.name || '';
        document.getElementById('edit-project-mission').value = project.mission || '';
        document.getElementById('edit-project-description').value = project.description || '';
        document.getElementById('edit-project-image-url').value = project.image_url || '';
        document.getElementById('edit-project-image-file').value = '';
        document.getElementById('edit-project-image-upload-status').innerHTML = '';
        syncLayerBrandImages();
        document.getElementById('edit-project-status').value = project.status || 'proposed';
        document.getElementById('edit-project-status-reason').value = project.status_reason || '';
        document.getElementById('edit-project-meta-domain-inscription').value = project.meta_domain_inscription_id || '';
        document.getElementById('edit-project-meta-domain-display').textContent = project.meta_domain ? 'Cached: ' + project.meta_domain : '';
        document.getElementById('edit-modal-add-admin-q').value = '';
        document.getElementById('edit-modal-add-admin-results').innerHTML = '';
        const alertEl = document.getElementById('edit-project-alert');
        alertEl.classList.add('d-none');
        alertEl.textContent = '';
        // Visibility card – initialize from the live project data.
        const displayStatusSelect = document.getElementById('edit-project-display-status');
        if (displayStatusSelect) {{
            displayStatusSelect.value = (project.display_status || 'pending');
        }}
        const displayStatusFeedback = document.getElementById('edit-modal-display-status-feedback');
        if (displayStatusFeedback) {{
            displayStatusFeedback.textContent = '';
            displayStatusFeedback.className = 'small text-muted';
        }}
        loadEditModalAdmins();
        loadEditModalPrefixes();
        const modal = new bootstrap.Modal(document.getElementById('editProjectModal'));
        modal.show();
    }}
    
    async function loadEditModalAdmins() {{
        const container = document.getElementById('edit-modal-admins-list');
        if (!container || !project) return;
        container.innerHTML = '<div class="list-group-item text-muted small">Loading...</div>';
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{ credentials: 'include' }});
            if (response.status === 403) {{
                container.innerHTML = '<div class="list-group-item text-warning small">You need layer admin access to view or manage admins.</div>';
                return;
            }}
            if (!response.ok) {{
                container.innerHTML = '<div class="list-group-item text-danger small">Failed to load admins (status ' + response.status + '). Try refreshing.</div>';
                return;
            }}
            const data = await response.json();
            const ownerUserEsc = escapeHtmlBasic(data.owner.username || '');
            const ownerNameEsc = escapeHtml(data.owner.display_name || '');
            let html = '<div class="list-group-item d-flex justify-content-between align-items-center py-2"><div><a href="/profile/' + ownerUserEsc + '/" class="fw-bold text-decoration-none small">' + ownerNameEsc + '</a><span class="badge bg-primary ms-2">Owner</span></div><span class="text-muted small">-</span></div>';
            (data.admins || []).forEach(a => {{
                const aUserEsc = escapeHtmlBasic(a.username || '');
                const aNameEsc = escapeHtml(a.display_name || '');
                const aIdEsc = escapeForJsAttr(String(a.user_id || ''));
                html += '<div class="list-group-item d-flex justify-content-between align-items-center py-2" id="edit-modal-admin-' + (a.user_id || '') + '"><a href="/profile/' + aUserEsc + '/" class="text-decoration-none small">' + aNameEsc + '</a><button type="button" class="btn btn-outline-danger btn-sm" onclick="removeAdminFromEditModal(\\'' + aIdEsc + '\\')">Remove</button></div>';
            }});
            container.innerHTML = html || '<div class="list-group-item text-muted small">No assigned admins</div>';
        }} catch (e) {{
            console.error('loadEditModalAdmins error:', e);
            container.innerHTML = '<div class="list-group-item text-danger small">Failed to load admins. Check console for details.</div>';
        }}
    }}

    // ------------------------------------------------------------------------
    // Edit Layer modal – draft prefixes
    // ------------------------------------------------------------------------
    async function loadEditModalPrefixes() {{
        const container = document.getElementById('edit-modal-prefixes-list');
        if (!container || !project) return;
        container.innerHTML = '<div class="text-muted small py-2"><span class="spinner-border spinner-border-sm text-secondary"></span> Loading...</div>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/', {{ credentials: 'same-origin' }});
            const data = await res.json().catch(function () {{ return {{}}; }});
            if (!res.ok) {{
                container.innerHTML = '<div class="alert alert-danger small mb-0">' + escapeHtml(data.error || ('HTTP ' + res.status)) + '</div>';
                return;
            }}
            const items = data.prefixes || [];
            if (!items.length) {{
                container.innerHTML = '<p class="text-muted small mb-0">No prefixes yet – add one below.</p>';
                return;
            }}
            let html = '<div class="list-group">';
            items.forEach(function (p) {{
                const isDefault = !!p.is_default;
                const idAttr = escapeForJsAttr(String(p.id || ''));
                const prefixAttr = escapeForJsAttr(String(p.prefix || ''));
                const badge = isDefault
                    ? '<span class="badge bg-success ms-2">Default</span>'
                    : '';
                const defaultBtn = isDefault
                    ? '<button type="button" class="btn btn-outline-success btn-sm me-1" disabled title="Already default"><i class="fas fa-check"></i></button>'
                    : '<button type="button" class="btn btn-outline-success btn-sm me-1" onclick="editModalSetDefaultPrefix(\\'' + idAttr + '\\')" title="Make this the default"><i class="fas fa-check"></i></button>';
                const renameBtn = '<button type="button" class="btn btn-outline-secondary btn-sm me-1" onclick="editModalRenamePrefix(\\'' + idAttr + '\\', \\'' + prefixAttr + '\\')" title="Rename"><i class="fas fa-pen"></i></button>';
                const deleteBtn = '<button type="button" class="btn btn-outline-danger btn-sm" onclick="editModalDeletePrefix(\\'' + idAttr + '\\', ' + isDefault + ')" title="Delete"><i class="fas fa-trash"></i></button>';
                html += '<div class="list-group-item d-flex justify-content-between align-items-center py-2">' +
                    '<div><span class="font-monospace fs-6 fw-bold">' + escapeHtmlBasic(p.prefix || '') + '</span>' + badge + '</div>' +
                    '<div class="btn-group btn-group-sm">' + defaultBtn + renameBtn + deleteBtn + '</div>' +
                    '</div>';
            }});
            html += '</div>';
            container.innerHTML = html;
        }} catch (e) {{
            container.innerHTML = '<div class="alert alert-danger small mb-0">Could not load prefixes: ' + escapeHtml(e.message || '') + '</div>';
        }}
    }}

    function editModalShowPrefixFeedback(message, variant) {{
        const el = document.getElementById('edit-modal-add-prefix-feedback');
        if (!el) return;
        el.textContent = message || '';
        el.className = 'form-text small mt-1 ' + (variant === 'error' ? 'text-danger' : variant === 'success' ? 'text-success' : 'text-muted');
    }}

    function editModalWirePrefixInput() {{
        const input = document.getElementById('edit-modal-add-prefix-input');
        if (!input || input._ghWired) return;
        input._ghWired = true;
        input.addEventListener('input', function () {{
            const cleaned = (input.value || '').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 2);
            if (cleaned !== input.value) input.value = cleaned;
            const fb = document.getElementById('edit-modal-add-prefix-feedback');
            if (fb) {{
                if (!input.value) {{
                    fb.textContent = '';
                    fb.className = 'form-text small mt-1 text-muted';
                }} else if (!/^[A-Z]{{2}}$/.test(input.value)) {{
                    fb.textContent = 'Two uppercase letters required.';
                    fb.className = 'form-text small mt-1 text-danger';
                }} else {{
                    fb.textContent = 'Ready to add.';
                    fb.className = 'form-text small mt-1 text-muted';
                }}
            }}
        }});
        input.addEventListener('keydown', function (ev) {{
            if (ev.key === 'Enter') {{
                ev.preventDefault();
                editModalAddPrefix();
            }}
        }});
        const btn = document.getElementById('edit-modal-add-prefix-btn');
        if (btn && !btn._ghWired) {{
            btn._ghWired = true;
            btn.addEventListener('click', function (ev) {{
                ev.preventDefault();
                editModalAddPrefix();
            }});
        }}
    }}

    // Shared JSON-aware response parser. When the server returns HTML (e.g.
    // a redirect to the login page that fetch followed silently), res.ok can
    // be true but the body is not JSON – surface that as an error instead of
    // treating it as success.
    async function _ghParseApiResponse(res, fallbackError) {{
        const ct = (res.headers.get('content-type') || '').toLowerCase();
        if (!ct.includes('application/json')) {{
            if (res.redirected) {{
                return {{ ok: false, status: res.status, data: {{ error: 'Not signed in (redirected to ' + res.url + ').' }} }};
            }}
            if (!res.ok) {{
                return {{ ok: false, status: res.status, data: {{ error: fallbackError || ('HTTP ' + res.status) }} }};
            }}
            return {{ ok: false, status: res.status, data: {{ error: 'Unexpected response from server (not JSON).' }} }};
        }}
        const data = await res.json().catch(function () {{ return {{}}; }});
        return {{ ok: res.ok, status: res.status, data: data }};
    }}

    async function _ghShowDanger(title, message) {{
        if (typeof GhDialog !== 'undefined' && GhDialog.alert) {{
            return await GhDialog.alert({{ title: title, message: message || 'Unknown error', variant: 'danger' }});
        }}
        // Fallback: write into the inline feedback area so we never use native alert().
        editModalShowPrefixFeedback((title ? title + ': ' : '') + (message || 'Unknown error'), 'error');
    }}

    async function editModalAddPrefix() {{
        editModalWirePrefixInput();
        const input = document.getElementById('edit-modal-add-prefix-input');
        const btn = document.getElementById('edit-modal-add-prefix-btn');
        if (!input || !project) return;
        const value = (input.value || '').trim();
        if (!/^[A-Z]{{2}}$/.test(value)) {{
            editModalShowPrefixFeedback('Enter exactly two uppercase letters.', 'error');
            return;
        }}
        if (btn) btn.disabled = true;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
                body: JSON.stringify({{ prefix: value }}),
            }});
            const parsed = await _ghParseApiResponse(res, 'Could not add prefix.');
            if (!parsed.ok) {{
                editModalShowPrefixFeedback(parsed.data.error || ('HTTP ' + parsed.status), 'error');
                return;
            }}
            input.value = '';
            editModalShowPrefixFeedback('Prefix "' + value + '" added.', 'success');
            loadEditModalPrefixes();
            if (typeof loadPrefixes === 'function') loadPrefixes();
            if (typeof window.GhPrefixUpdateChip === 'function' && parsed.data.prefix) {{
                window.GhPrefixUpdateChip(parsed.data.prefix.prefix, project.name || '');
            }}
        }} catch (e) {{
            editModalShowPrefixFeedback(e.message || 'Could not add prefix.', 'error');
        }} finally {{
            if (btn) btn.disabled = false;
        }}
    }}

    async function editModalSetDefaultPrefix(prefixId) {{
        if (!prefixId || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/default/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
                body: JSON.stringify({{}}),
            }});
            const parsed = await _ghParseApiResponse(res, 'Could not set default.');
            if (!parsed.ok) {{
                await _ghShowDanger('Could not set default', parsed.data.error);
                return;
            }}
            loadEditModalPrefixes();
            if (typeof loadPrefixes === 'function') loadPrefixes();
            if (parsed.data.prefix && typeof window.GhPrefixUpdateChip === 'function') {{
                window.GhPrefixUpdateChip(parsed.data.prefix.prefix, project.name || '');
            }}
        }} catch (e) {{
            await _ghShowDanger('Could not set default', e.message);
        }}
    }}

    async function editModalDeletePrefix(prefixId, isDefault) {{
        if (!prefixId || !project) return;
        const message = isDefault
            ? 'This is the current default prefix. Mark another prefix as default first, then delete this one.'
            : 'Delete this prefix? Drafts already created will keep their existing identifier.';
        let ok = true;
        if (typeof GhDialog !== 'undefined' && GhDialog.confirm) {{
            ok = await GhDialog.confirm({{
                title: 'Delete prefix',
                message: message,
                variant: isDefault ? 'warning' : 'danger',
                confirmLabel: 'Delete',
            }});
        }} else {{
            // No GhDialog available – render an inline confirmation instead of native confirm().
            const fb = document.getElementById('edit-modal-add-prefix-feedback');
            if (fb) {{
                fb.innerHTML = '<span class="text-danger">' + message + '</span> '
                    + '<button type="button" class="btn btn-sm btn-danger ms-2" id="edit-modal-fallback-confirm-delete">Confirm delete</button>';
                const c = document.getElementById('edit-modal-fallback-confirm-delete');
                if (c) {{
                    c.onclick = async function () {{
                        fb.innerHTML = '';
                        await _editModalDeletePrefixInternal(prefixId);
                    }};
                }}
            }}
            return;
        }}
        if (!ok) return;
        await _editModalDeletePrefixInternal(prefixId);
    }}

    async function _editModalDeletePrefixInternal(prefixId) {{
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/', {{
                method: 'DELETE',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
                body: JSON.stringify({{}}),
            }});
            const parsed = await _ghParseApiResponse(res, 'Could not delete prefix.');
            if (!parsed.ok) {{
                await _ghShowDanger('Could not delete prefix', parsed.data.error);
                return;
            }}
            loadEditModalPrefixes();
            if (typeof loadPrefixes === 'function') loadPrefixes();
        }} catch (e) {{
            await _ghShowDanger('Could not delete prefix', e.message);
        }}
    }}

    async function editModalRenamePrefix(prefixId, currentPrefix) {{
        if (!prefixId || !project) return;
        var next = await GhDialog.prompt({{ title: 'Input required', message: ('New prefix (2 uppercase letters):'), defaultValue: (currentPrefix || ''), confirmLabel: 'OK', inputType: 'text' }});
        if (next == null) return;
        const value = (next || '').trim().toUpperCase();
        if (!/^[A-Z]{{2}}$/.test(value)) {{
            await _ghShowDanger('Invalid prefix', 'Prefix must be exactly two uppercase ASCII letters.');
            return;
        }}
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/', {{
                method: 'PATCH',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json', 'Accept': 'application/json' }},
                body: JSON.stringify({{ prefix: value }}),
            }});
            const parsed = await _ghParseApiResponse(res, 'Could not rename prefix.');
            if (!parsed.ok) {{
                await _ghShowDanger('Could not rename prefix', parsed.data.error);
                return;
            }}
            loadEditModalPrefixes();
            if (typeof loadPrefixes === 'function') loadPrefixes();
            if (parsed.data.prefix && typeof window.GhPrefixUpdateChip === 'function') {{
                window.GhPrefixUpdateChip(parsed.data.prefix.prefix, project.name || '');
            }}
        }} catch (e) {{
            await _ghShowDanger('Could not rename prefix', e.message);
        }}
    }}

    // Wire the edit-modal prefix input on DOMContentLoaded (idempotent).
    document.addEventListener('DOMContentLoaded', function () {{
        editModalWirePrefixInput();
    }});

    function searchUsersForEditModalAdmin() {{
        const q = document.getElementById('edit-modal-add-admin-q').value.trim();
        const resultsEl = document.getElementById('edit-modal-add-admin-results');
        if (q.length < 2) {{ resultsEl.innerHTML = ''; return; }}
        fetch('/api/users/search/?q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(data => {{
                if (!data.users || data.users.length === 0) {{
                    resultsEl.innerHTML = '<p class="text-muted small mb-0">No users found</p>';
                    return;
                }}
                resultsEl.innerHTML = data.users.map(u => {{
                    const uNameEsc = escapeHtml(u.display_name || '');
                    const uUserEsc = escapeHtml(u.username || '');
                    const uIdEsc = escapeForJsAttr(String(u.id || ''));
                    return '<div class="d-flex justify-content-between align-items-center border-bottom py-1 small"><span>' + uNameEsc + ' <small class="text-muted">@' + uUserEsc + '</small></span><button type="button" class="btn btn-sm btn-primary" onclick="addAdminFromEditModal(\\'' + uIdEsc + '\\')">Add</button></div>';
                }}).join('');
            }})
            .catch(() => {{ resultsEl.innerHTML = '<p class="text-danger small mb-0">Search failed</p>'; }});
    }}
    
    async function addAdminFromEditModal(userId) {{
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'include',
                body: JSON.stringify({{ user_id: userId }})
            }});
            const data = await response.json();
            if (response.ok) {{
                document.getElementById('edit-modal-add-admin-q').value = '';
                document.getElementById('edit-modal-add-admin-results').innerHTML = '';
                loadEditModalAdmins();
                if (typeof loadAdmins === 'function') loadAdmins();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to add admin'), variant: 'info' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to add admin'), variant: 'info' }});
        }}
    }}
    
    async function removeAdminFromEditModal(userId) {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Remove this user as layer admin?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/' + userId + '/', {{
                method: 'DELETE',
                credentials: 'include'
            }});
            const data = await response.json();
            if (response.ok) {{
                loadEditModalAdmins();
                if (typeof loadAdmins === 'function') loadAdmins();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to remove admin'), variant: 'info' }});
            }}
        }} catch (e) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to remove admin'), variant: 'info' }});
        }}
    }}
    
    async function saveProjectEdit() {{
        if (!project) return;
        const name = document.getElementById('edit-project-name').value.trim();
        const mission = document.getElementById('edit-project-mission').value;
        const description = document.getElementById('edit-project-description').value;
        const image_url = document.getElementById('edit-project-image-url').value.trim();
        const status = document.getElementById('edit-project-status').value;
        const status_reason = document.getElementById('edit-project-status-reason').value.trim();
        const meta_domain_inscription_id = document.getElementById('edit-project-meta-domain-inscription').value.trim();
        const alertEl = document.getElementById('edit-project-alert');
        const saveBtn = document.getElementById('edit-project-save-btn');
        
        if (!name) {{
            alertEl.textContent = 'Layer name is required.';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        
        saveBtn.disabled = true;
        alertEl.classList.add('d-none');
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'include',
                body: JSON.stringify({{ name: name, mission: mission || null, description: description, image_url: image_url || null, status: status, status_reason: status_reason || null, meta_domain_inscription_id: meta_domain_inscription_id || null }})
            }});
            let data;
            try {{ data = await res.json(); }} catch (_) {{
                alertEl.textContent = res.status === 401 ? 'Please sign in to edit projects.' : 'Server error. Please try again.';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
                saveBtn.disabled = false;
                return;
            }}
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('editProjectModal')).hide();
                project = data.project;
                project._imgBust = Date.now();
                if (project.slug !== projectSlug) {{
                    window.location.href = (showCarousel ? '/layer/' : '/layers/') + project.slug + '/';
                    return;
                }}
                await refreshProjectFromApi();
                syncLayerBrandImages();
                loadOverview();
            }} else {{
                alertEl.textContent = data.error || 'Failed to update project';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            alertEl.textContent = 'Network error. Please try again.';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        saveBtn.disabled = false;
    }}

    async function saveDisplayStatus() {{
        if (!project) return;
        const select = document.getElementById('edit-project-display-status');
        const feedback = document.getElementById('edit-modal-display-status-feedback');
        const saveBtn = document.getElementById('edit-modal-display-status-save-btn');
        if (!select || !feedback || !saveBtn) return;

        const newStatus = select.value;
        if (newStatus !== 'pending' && newStatus !== 'active') {{
            feedback.textContent = 'Please pick Pending or Active.';
            feedback.className = 'small text-danger';
            return;
        }}

        saveBtn.disabled = true;
        feedback.textContent = 'Saving...';
        feedback.className = 'small text-muted';

        try {{
            const res = await fetch('/api/layers/' + project.id + '/display-status/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ display_status: newStatus }}),
            }});
            const data = await res.json().catch(function () {{ return {{}}; }});
            if (res.ok) {{
                feedback.textContent = 'Saved – layer is now ' + newStatus + '.';
                feedback.className = 'small text-success';
                project.display_status = newStatus;
            }} else {{
                feedback.textContent = data.error || 'Failed to save.';
                feedback.className = 'small text-danger';
            }}
        }} catch (e) {{
            feedback.textContent = 'Network error.';
            feedback.className = 'small text-danger';
        }}
        saveBtn.disabled = false;
    }}

    async function createWorkgroup() {{
        const modalHtml = `
            <div class="modal fade" id="projectCreateWorkgroupModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create Workgroup</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="project-wg-alert-container"></div>
                            <form id="projectCreateWorkgroupForm">
                                <div class="mb-3">
                                    <label for="project-wg-name" class="form-label">Workgroup Name *</label>
                                    <input type="text" class="form-control" id="project-wg-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="project-wg-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="project-wg-description" rows="3" required></textarea>
                                </div>
                                <p class="text-muted small">New workgroups require approval from the layer admin before becoming active.</p>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="projectSubmitWorkgroupBtn">
                                <i class="fas fa-plus me-2"></i>Create Workgroup
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('projectCreateWorkgroupModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('project-wg-alert-container').innerHTML = '';
        document.getElementById('project-wg-name').value = '';
        document.getElementById('project-wg-description').value = '';
        const modal = new bootstrap.Modal(document.getElementById('projectCreateWorkgroupModal'));
        modal.show();
        document.getElementById('projectSubmitWorkgroupBtn').onclick = async () => {{
            const name = document.getElementById('project-wg-name').value.trim();
            const description = document.getElementById('project-wg-description').value.trim();
            if (!name || !description) {{
                document.getElementById('project-wg-alert-container').innerHTML = '<div class="alert alert-danger">Name and description are required.</div>';
                return;
            }}
            const btn = document.getElementById('projectSubmitWorkgroupBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            try {{
                const response = await fetch('/api/layers/' + project.id + '/workgroups/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description }})
                }});
                const data = await response.json();
                if (response.ok) {{
                    modal.hide();
                    loadWorkgroups();
                    await GhDialog.alert({{
                        title: 'Workgroup created',
                        message: 'Your workgroup was submitted. It will be visible once approved by the layer admin.',
                        variant: 'success',
                    }});
                }} else {{
                    throw new Error(data.error || 'Failed to create workgroup');
                }}
            }} catch (err) {{
                document.getElementById('project-wg-alert-container').innerHTML = '<div class="alert alert-danger">' + (err.message || 'Failed to create workgroup') + '</div>';
            }}
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Workgroup';
        }};
    }}
    
    async function createRole() {{
        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="createRoleModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create New Role</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="role-alert-container"></div>
                            
                            <form id="createRoleForm">
                                <div class="mb-3">
                                    <label for="role-title-guild" class="form-label">Guild Title *</label>
                                    <input type="text" class="form-control" id="role-title-guild" required>
                                    <div class="form-text">The formal/ceremonial title (e.g., "Keeper of the Keys")</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-title-operational" class="form-label">Operational Title</label>
                                    <input type="text" class="form-control" id="role-title-operational">
                                    <div class="form-text">Optional: The practical title (e.g., "Security Lead")</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="role-description" rows="4" required></textarea>
                                    <div class="form-text">Describe the role's responsibilities and purpose</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-cluster" class="form-label">Cluster</label>
                                    <select class="form-select" id="role-cluster">
                                        <option value="">No cluster</option>
                                    </select>
                                    <div class="form-text">Optional: Group this role with others</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-image-url" class="form-label">Image URL</label>
                                    <input type="url" class="form-control" id="role-image-url">
                                    <div class="form-text">Optional: URL to role image/icon</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-order" class="form-label">Display Order</label>
                                    <input type="number" class="form-control" id="role-order" value="0">
                                    <div class="form-text">Lower numbers appear first</div>
                                </div>
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-public-visible" checked>
                                        <label class="form-check-label" for="role-public-visible">
                                            Public Visible
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-claim-approval">
                                        <label class="form-check-label" for="role-claim-approval">
                                            Claims Require Approval
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-requires-election">
                                        <label class="form-check-label" for="role-requires-election">
                                            Requires Election (role filled via vote)
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-badge-enabled" checked>
                                        <label class="form-check-label" for="role-badge-enabled">
                                            Badge Enabled
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-badge-approval">
                                        <label class="form-check-label" for="role-badge-approval">
                                            Badges Require Approval
                                        </label>
                                    </div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitRoleBtn">
                                <i class="fas fa-plus me-2"></i>Create Role
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page if not exists
        if (!document.getElementById('createRoleModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        
        // Load clusters for dropdown
        fetch('/api/layers/' + project.id + '/clusters/')
            .then(r => r.json())
            .then(data => {{
                const select = document.getElementById('role-cluster');
                (data.clusters || []).forEach(cluster => {{
                    if (!cluster) return;
                    const option = document.createElement('option');
                    option.value = cluster.id || '';
                    option.textContent = (cluster.name != null && cluster.name !== '') ? cluster.name : 'Unnamed';
                    select.appendChild(option);
                }});
            }});
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('createRoleModal'));
        modal.show();
        
        // Handle form submission
        document.getElementById('submitRoleBtn').onclick = async () => {{
            const titleGuild = document.getElementById('role-title-guild').value.trim();
            const titleOperational = document.getElementById('role-title-operational').value.trim();
            const description = document.getElementById('role-description').value.trim();
            
            if (!titleGuild || !description) {{
                document.getElementById('role-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Guild title and description are required
                    </div>
                `;
                return;
            }}
            
            const submitBtn = document.getElementById('submitRoleBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            
            const formData = {{
                title_guild: titleGuild,
                title_operational: titleOperational || null,
                description: description,
                cluster_id: document.getElementById('role-cluster').value || null,
                image_url: document.getElementById('role-image-url').value || null,
                order: parseInt(document.getElementById('role-order').value) || 0,
                public_visible: document.getElementById('role-public-visible').checked,
                claim_requires_approval: document.getElementById('role-claim-approval').checked,
                requires_election: document.getElementById('role-requires-election').checked,
                badge_enabled: document.getElementById('role-badge-enabled').checked,
                badge_requires_approval: document.getElementById('role-badge-approval').checked
            }};
            
            try {{
                const response = await fetch('/api/layers/' + project.id + '/roles/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(formData)
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    modal.hide();
                    loadRoles(); // Reload roles list
                    await GhDialog.alert({{ title: 'Notice', message: ('Role created successfully!'), variant: 'info' }});
                }} else {{
                    throw new Error(data.error || 'Failed to create role');
                }}
            }} catch (error) {{
                document.getElementById('role-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Role';
            }}
        }};
    }}
    
    async function createCluster() {{
        const modalHtml = `
            <div class="modal fade" id="createClusterModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create New Cluster</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="cluster-alert-container"></div>
                            
                            <form id="createClusterForm">
                                <div class="mb-3">
                                    <label for="cluster-name" class="form-label">Cluster Name *</label>
                                    <input type="text" class="form-control" id="cluster-name" required>
                                    <div class="form-text">A descriptive name for this role group</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="cluster-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="cluster-description" rows="3"></textarea>
                                    <div class="form-text">Optional: Describe the purpose of this cluster</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="cluster-order" class="form-label">Display Order</label>
                                    <input type="number" class="form-control" id="cluster-order" value="0">
                                    <div class="form-text">Lower numbers appear first</div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitClusterBtn">
                                <i class="fas fa-plus me-2"></i>Create Cluster
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        if (!document.getElementById('createClusterModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        
        // Reset form and button so each open is fresh (and not stuck from a previous submit)
        document.getElementById('cluster-name').value = '';
        document.getElementById('cluster-description').value = '';
        document.getElementById('cluster-order').value = '0';
        document.getElementById('cluster-alert-container').innerHTML = '';
        const submitClusterBtn = document.getElementById('submitClusterBtn');
        submitClusterBtn.disabled = false;
        submitClusterBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
        
        const modal = new bootstrap.Modal(document.getElementById('createClusterModal'));
        modal.show();
        
        document.getElementById('submitClusterBtn').onclick = async () => {{
            const name = document.getElementById('cluster-name').value.trim();
            const description = document.getElementById('cluster-description').value.trim();
            const order = parseInt(document.getElementById('cluster-order').value) || 0;
            
            if (!name) {{
                document.getElementById('cluster-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Cluster name is required
                    </div>
                `;
                return;
            }}
            
            const submitBtn = document.getElementById('submitClusterBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            
            try {{
                const response = await fetch('/api/layers/' + project.id + '/clusters/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description, order }})
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    document.getElementById('cluster-name').value = '';
                    document.getElementById('cluster-description').value = '';
                    document.getElementById('cluster-order').value = '0';
                    document.getElementById('cluster-alert-container').innerHTML = '';
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
                    modal.hide();
                    loadClusters();
                    await GhDialog.alert({{ title: 'Notice', message: ('Cluster created successfully!'), variant: 'info' }});
                }} else {{
                    throw new Error(data.error || 'Failed to create cluster');
                }}
            }} catch (error) {{
                document.getElementById('cluster-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
            }}
        }};
    }}
    
    async function editCluster(clusterId) {{
        try {{
            const response = await fetch('/api/clusters/' + clusterId + '/');
            const data = await response.json();
            const cluster = data.cluster || data;
            if (!cluster) {{
                throw new Error('Cluster not found');
            }}
            const cName = (cluster.name != null && cluster.name !== '') ? String(cluster.name) : '';
            const cDesc = (cluster.description != null) ? String(cluster.description) : '';
            const cOrder = (cluster.order != null && cluster.order !== '') ? cluster.order : 0;
            const cNameEsc = escapeHtmlBasic(cName);
            const cDescEsc = escapeHtml(cDesc);
            
            const modalHtml = '<div class="modal fade" id="editClusterModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Edit Cluster</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="edit-cluster-alert-container"></div><form id="editClusterForm"><div class="mb-3"><label for="edit-cluster-name" class="form-label">Cluster Name *</label><input type="text" class="form-control" id="edit-cluster-name" value="' + cNameEsc + '" required></div><div class="mb-3"><label for="edit-cluster-description" class="form-label">Description</label><textarea class="form-control" id="edit-cluster-description" rows="3">' + cDescEsc + '</textarea></div><div class="mb-3"><label for="edit-cluster-order" class="form-label">Display Order</label><input type="number" class="form-control" id="edit-cluster-order" value="' + cOrder + '"></div></form></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-primary" id="updateClusterBtn"><i class="fas fa-save me-2"></i>Save Changes</button></div></div></div></div>';
            
            if (document.getElementById('editClusterModal')) {{
                document.getElementById('editClusterModal').remove();
            }}
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            const modal = new bootstrap.Modal(document.getElementById('editClusterModal'));
            modal.show();
            
            document.getElementById('updateClusterBtn').onclick = async () => {{
                const name = document.getElementById('edit-cluster-name').value.trim();
                const description = document.getElementById('edit-cluster-description').value.trim();
                const order = parseInt(document.getElementById('edit-cluster-order').value) || 0;
                
                if (!name) {{
                    document.getElementById('edit-cluster-alert-container').innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Cluster name is required
                        </div>
                    `;
                    return;
                }}
                
                const submitBtn = document.getElementById('updateClusterBtn');
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
                
                try {{
                    const response = await fetch('/api/clusters/' + clusterId + '/', {{
                        method: 'PATCH',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ name, description, order }})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        modal.hide();
                        loadClusters();
                        await GhDialog.alert({{ title: 'Notice', message: ('Cluster updated successfully!'), variant: 'info' }});
                    }} else {{
                        throw new Error(data.error || 'Failed to update cluster');
                    }}
                }} catch (error) {{
                    document.getElementById('edit-cluster-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
                }}
            }};
        }} catch (error) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Error loading cluster: ' + error.message), variant: 'info' }});
        }}
    }}
    
    async function deleteCluster(clusterId, clusterName) {{
        if (!(await GhDialog.confirm({{ title: 'Delete cluster', message: 'Are you sure you want to delete the cluster "' + clusterName + '"? This will unassign all roles from this cluster.', variant: 'warning' }}))) {{
            return;
        }}
        
        try {{
            const response = await fetch('/api/clusters/' + clusterId + '/', {{
                method: 'DELETE'
            }});
            
            const data = await response.json();
            
            if (response.ok) {{
                loadClusters();
                await GhDialog.alert({{ title: 'Notice', message: ('Cluster deleted successfully!'), variant: 'info' }});
            }} else {{
                throw new Error(data.error || 'Failed to delete cluster');
            }}
        }} catch (error) {{
            await GhDialog.alert({{ title: 'Notice', message: ('Error deleting cluster: ' + error.message), variant: 'info' }});
        }}
    }}
    
    // ------------------------------------------------------------------------
    // Per-layer two-letter draft prefixes (admin UI)
    // ------------------------------------------------------------------------
    function renderPrefixesCard() {{
        return (
            '<div class="card mb-4" id="layer-prefixes-card">' +
                '<div class="card-header d-flex justify-content-between align-items-center">' +
                    '<h5 class="mb-0"><i class="fas fa-tag me-2"></i>Draft prefixes</h5>' +
                    '<div class="btn-group btn-group-sm">' +
                        '<button type="button" class="btn btn-outline-secondary" onclick="loadPrefixes()" title="Refresh"><i class="fas fa-sync-alt"></i></button>' +
                        '<button type="button" class="btn btn-primary" onclick="showAddPrefixModal()"><i class="fas fa-plus me-1"></i>Add prefix</button>' +
                    '</div>' +
                '</div>' +
                '<div class="card-body">' +
                    '<p class="text-muted small mb-3">Two-letter prefix prepended to draft identifiers in this layer (e.g. <code>ML-001</code>, <code>CL-013</code>). ' +
                    'Prefixes are <strong>globally unique across the entire Gov Hub</strong> – pick a code another layer isn\\'t using.</p>' +
                    '<div id="layer-prefixes-list"><div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>' +
                    '<p class="small text-muted mt-2 mb-0">The active prefix is the one shown in the header chip. Make sure every layer has at least one prefix so admins can always switch.</p>' +
                '</div>' +
            '</div>' +
            '<div class="modal fade" id="addPrefixModal" tabindex="-1" aria-hidden="true">' +
                '<div class="modal-dialog modal-dialog-centered">' +
                    '<div class="modal-content">' +
                        '<div class="modal-header">' +
                            '<h5 class="modal-title"><i class="fas fa-tag me-2"></i>Add draft prefix</h5>' +
                            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
                        '</div>' +
                        '<div class="modal-body">' +
                            '<div id="add-prefix-alert" class="alert d-none" role="alert"></div>' +
                            '<label for="add-prefix-input" class="form-label">Prefix (2 uppercase letters)</label>' +
                            '<input type="text" id="add-prefix-input" class="form-control text-uppercase" maxlength="3" placeholder="ML" autocomplete="off">' +
                            '<div class="form-text">Letters will be uppercased. Reserved: ML (legacy meta-layer default).</div>' +
                        '</div>' +
                        '<div class="modal-footer">' +
                            '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>' +
                            '<button type="button" class="btn btn-primary" id="add-prefix-submit" onclick="submitAddPrefix()"><i class="fas fa-plus me-1"></i>Add</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
            '</div>'
        );
    }}

    async function loadPrefixes() {{
        const container = document.getElementById('layer-prefixes-list');
        if (!container || !project) return;
        container.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/', {{ credentials: 'same-origin' }});
            if (res.status === 403) {{
                container.innerHTML = '<div class="alert alert-warning small mb-0">You do not have permission to view prefixes.</div>';
                return;
            }}
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load prefixes');
            const items = data.prefixes || [];
            if (!items.length) {{
                container.innerHTML = '<p class="text-muted small mb-0">No prefixes yet – add one to get started.</p>';
                return;
            }}
            let html = '<div class="list-group">';
            items.forEach(function (p) {{
                const isDefault = !!p.is_default;
                const idAttr = escapeForJsAttr(String(p.id || ''));
                const prefixAttr = escapeForJsAttr(String(p.prefix || ''));
                const badge = isDefault
                    ? '<span class="badge bg-success ms-2">Default</span>'
                    : '';
                const defaultAction = isDefault
                    ? ''
                    : '<button type="button" class="btn btn-outline-success btn-sm me-1" onclick="setDefaultPrefix(\\'' + idAttr + '\\')" title="Make this the default"><i class="fas fa-check"></i></button>';
                const renameAction = '<button type="button" class="btn btn-outline-secondary btn-sm me-1" onclick="showRenamePrefixPrompt(\\'' + idAttr + '\\', \\'' + prefixAttr + '\\')" title="Rename"><i class="fas fa-pen"></i></button>';
                const deleteAction = '<button type="button" class="btn btn-outline-danger btn-sm" onclick="deletePrefix(\\'' + idAttr + '\\', ' + isDefault + ')" title="Delete"><i class="fas fa-trash"></i></button>';
                html += '<div class="list-group-item d-flex justify-content-between align-items-center">' +
                    '<div><span class="font-monospace fs-5 fw-bold">' + escapeHtmlBasic(p.prefix || '') + '</span>' + badge +
                    (isDefault ? '<span class="ms-2 small text-success"><i class="fas fa-star me-1"></i>Active draft prefix</span>' : '') +
                    '</div>' +
                    '<div class="btn-group btn-group-sm">' + defaultAction + renameAction + deleteAction + '</div>' +
                    '</div>';
            }});
            html += '</div>';
            container.innerHTML = html;
        }} catch (e) {{
            container.innerHTML = '<div class="alert alert-danger small mb-0">Could not load prefixes: ' + escapeHtml(e.message || '') + '</div>';
        }}
    }}

    function showAddPrefixModal() {{
        const input = document.getElementById('add-prefix-input');
        if (input) {{ input.value = ''; }}
        const alert = document.getElementById('add-prefix-alert');
        if (alert) {{ alert.classList.add('d-none'); alert.innerHTML = ''; }}
        const modalEl = document.getElementById('addPrefixModal');
        if (!modalEl) return;
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
        setTimeout(function () {{
            if (input) input.focus();
        }}, 200);
    }}

    async function submitAddPrefix() {{
        const input = document.getElementById('add-prefix-input');
        const alertEl = document.getElementById('add-prefix-alert');
        const submitBtn = document.getElementById('add-prefix-submit');
        if (!input || !alertEl) return;
        const value = (input.value || '').trim();
        if (!/^[A-Za-z]{{2}}$/.test(value)) {{
            alertEl.className = 'alert alert-danger small';
            alertEl.textContent = 'Enter exactly two letters.';
            alertEl.classList.remove('d-none');
            return;
        }}
        alertEl.classList.add('d-none');
        if (submitBtn) submitBtn.disabled = true;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ prefix: value }}),
            }});
            const data = await res.json().catch(function () {{ return {{}}; }});
            if (!res.ok) throw new Error(data.error || 'Failed to add prefix');
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{
                    title: 'Prefix added',
                    message: 'Prefix "' + value.toUpperCase() + '" was added to this layer.',
                    variant: 'success',
                }});
            }}
            const modalEl = document.getElementById('addPrefixModal');
            if (modalEl) {{
                const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
                modal.hide();
            }}
            loadPrefixes();
        }} catch (e) {{
            alertEl.className = 'alert alert-danger small';
            alertEl.textContent = e.message || 'Could not add prefix.';
            alertEl.classList.remove('d-none');
        }} finally {{
            if (submitBtn) submitBtn.disabled = false;
        }}
    }}

    async function setDefaultPrefix(prefixId) {{
        if (!prefixId) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/default/', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{}}),
            }});
            const data = await res.json().catch(function () {{ return {{}}; }});
            if (!res.ok) throw new Error(data.error || 'Failed to set default');
            loadPrefixes();
        }} catch (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{ title: 'Could not set default', message: e.message || 'Unknown error', variant: 'danger' }});
            }}
        }}
    }}

    async function deletePrefix(prefixId, isDefault) {{
        if (!prefixId) return;
        const message = isDefault
            ? 'This is the current default prefix. Mark another prefix as default first, then delete this one.'
            : 'Delete this prefix? Drafts already created will keep their existing identifier.';
        if (typeof GhDialog !== 'undefined') {{
            const ok = await GhDialog.confirm({{
                title: 'Delete prefix',
                message: message,
                variant: isDefault ? 'warning' : 'danger',
                confirmLabel: 'Delete',
            }});
            if (!ok) return;
        }}
        try {{
            const res = await fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/', {{
                method: 'DELETE',
                credentials: 'same-origin',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{}}),
            }});
            const data = await res.json().catch(function () {{ return {{}}; }});
            if (!res.ok) throw new Error(data.error || 'Failed to delete');
            loadPrefixes();
        }} catch (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{ title: 'Could not delete prefix', message: e.message || 'Unknown error', variant: 'danger' }});
            }}
        }}
    }}

    async function showRenamePrefixPrompt(prefixId, currentPrefix) {{
        if (!prefixId) return;
        var next = await GhDialog.prompt({{ title: 'Input required', message: ('New prefix (2 uppercase letters):'), defaultValue: (currentPrefix || ''), confirmLabel: 'OK', inputType: 'text' }});
        if (next == null) return;
        const value = next.trim().toUpperCase();
        if (!/^[A-Z]{{2}}$/.test(value)) {{
            if (typeof GhDialog !== 'undefined') {{
                GhDialog.alert({{ title: 'Invalid prefix', message: 'Prefix must be exactly two uppercase ASCII letters.', variant: 'danger' }});
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: ('Invalid prefix format'), variant: 'info' }});
            }}
            return;
        }}
        fetch('/api/layers/' + project.id + '/prefixes/' + prefixId + '/', {{
            method: 'PATCH',
            credentials: 'same-origin',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ prefix: value }}),
        }}).then(function (res) {{ return res.json().then(function (data) {{ return {{ ok: res.ok, data: data }}; }}); }})
        .then(async function (resp) {{
            if (!resp.ok) throw new Error(resp.data.error || 'Failed to rename');
            loadPrefixes();
        }}).catch(async function (e) {{
            if (typeof GhDialog !== 'undefined') {{
                await GhDialog.alert({{ title: 'Could not rename prefix', message: e.message || 'Unknown error', variant: 'danger' }});
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: ('Rename failed: ' + e.message), variant: 'info' }});
            }}
        }});
    }}

    // Wire the add-prefix input to uppercase + live-validate. Triggers after
    // the modal becomes visible.
    document.addEventListener('DOMContentLoaded', function () {{
        const input = document.getElementById('add-prefix-input');
        if (!input) return;
        input.addEventListener('input', function () {{
            // Strip non-letters and cap at 2 chars.
            const cleaned = (input.value || '').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 2);
            if (cleaned !== input.value) input.value = cleaned;
        }});
        input.addEventListener('keydown', function (ev) {{
            if (ev.key === 'Enter') {{
                ev.preventDefault();
                submitAddPrefix();
            }}
        }});
    }});

    // Load project on page load
    loadProject();
    </script>
    """
    
    if standalone and project_obj:
        layer_name = project_obj.name or project_slug
        layer_image_url = project_obj.image_url or ''
        html = render_layer_standalone_page(
            f"{layer_name} Gov-Hub",
            content,
            layer_name=layer_name,
            layer_slug=project_slug,
            layer_image_url=layer_image_url,
            theme=current_theme,
            user_menu=user_menu,
        )
    else:
        html = render_page(f"Layer: {project_slug} - GovHub", content, theme=current_theme, user_menu=user_menu)
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp
