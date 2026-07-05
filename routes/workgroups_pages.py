"""Workgroup page routes: /workgroups/<workgroup_slug>/."""
import html
import json

import requests
from flask import Blueprint, session

from services.identity import get_current_user

bp = Blueprint('workgroups_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


def _get_workgroup_positions():
    """Late import to avoid circular imports."""
    from services.workgroup_positions import WORKGROUP_POSITIONS
    return WORKGROUP_POSITIONS


# The Metaweb layer is the canonical home of the public-facing DP workgroups.
METAWEB_LAYER_ID = '22d90c89-2783-4726-a8b6-220dca505402'

# Hardcoded fallback if the local API is unreachable (e.g. during tests).
NOMINATE_FALLBACK_WG_SLUG = 'dp1-federated-auth'


def _fetch_approved_workgroups_for_layer(layer_id):
    """Fetch approved workgroups for a layer. Returns a list of dicts."""
    try:
        resp = requests.get(
            f'http://127.0.0.1:8000/api/layers/{layer_id}/workgroups/',
            timeout=3,
        )
        if not resp.ok:
            return []
        workgroups = resp.json().get('workgroups', []) or []
        return [
            {
                'slug': w.get('slug', ''),
                'name': w.get('name', ''),
                'description': w.get('description', '') or '',
                'status': w.get('status', 'active'),
                'state': w.get('state'),
                'approval_status': w.get('approval_status'),
                'image_url': w.get('image_url'),
            }
            for w in workgroups
            if w.get('approval_status') == 'approved' and w.get('slug')
        ][:12]
    except Exception:
        return []


def _escape_text(value):
    return html.escape(str(value or ''), quote=True)


@bp.route('/workgroups/join/')
def workgroups_join_landing():
    """Public landing page: explains workgroups, lists roles, CTAs, workgroup cards, FAQ."""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    # Roles from the canonical config (server-side rendered, no HTTP needed)
    WORKGROUP_POSITIONS = _get_workgroup_positions()
    positions = [
        {
            'key': key,
            'label': meta['label'],
            'description': meta['description'],
            'icon': meta.get('icon', 'fa-user'),
        }
        for key, meta in WORKGROUP_POSITIONS.items()
    ]

    # Live workgroup cards for the Metaweb layer
    cards = _fetch_approved_workgroups_for_layer(METAWEB_LAYER_ID)
    first_card_slug = cards[0]['slug'] if cards else NOMINATE_FALLBACK_WG_SLUG

    # FAQ items
    faq = [
        {
            'q': 'How do I know which workgroup is right for me?',
            'a': "Read each DP's short description and pick the one whose purpose resonates with your interests and skills. You can always join a different workgroup later.",
        },
        {
            'q': "What if I don't have time for ongoing commitments?",
            'a': "Some roles are flexible and low-touch. Roles like Recorder or Liaison can be episodic – contribute when you have capacity.",
        },
        {
            'q': 'Can I be a member of more than one workgroup?',
            'a': "Yes. Many community members participate across multiple workgroups. Each workgroup runs independently and you can join as many as your time allows.",
        },
        {
            'q': 'How are Coordinators chosen?',
            'a': "Coordinators can be nominated by anyone in the community, or you can nominate yourself. The layer admin reviews and approves each nomination. Nominations go through a transparent review process.",
        },
    ]

    # Build the content
    role_cards_html = ''.join(
        '<div class="col-md-6 col-lg-4">'
        '<div class="card h-100 living-module">'
        '<div class="card-body">'
        f'<div class="living-module-icon mb-2"><i class="fas {_escape_text(pos["icon"])} fa-2x text-primary" aria-hidden="true"></i></div>'
        f'<h5 class="card-title mb-1">{_escape_text(pos["label"])}</h5>'
        f'<p class="card-text text-muted mb-0">{_escape_text(pos["description"])}</p>'
        '</div>'
        '</div>'
        '</div>'
        for pos in positions
    )

    if cards:
        cards_html_parts = []
        for wg in cards:
            slug_esc = _escape_text(wg['slug'])
            name_esc = _escape_text(wg['name'])
            desc_esc = _escape_text(wg['description']) or 'No description provided.'
            status_esc = _escape_text(wg['status'])
            status_class = 'success' if wg['status'] == 'active' else 'secondary'
            cards_html_parts.append(
                '<div class="col-md-6 col-lg-4">'
                '<div class="card h-100">'
                '<div class="card-body d-flex flex-column">'
                f'<h5 class="card-title mb-1"><a href="/workgroups/{slug_esc}/">{name_esc}</a></h5>'
                f'<p class="card-text text-muted small mb-2 flex-grow-1">{desc_esc}</p>'
                '<div class="d-flex justify-content-between align-items-center">'
                f'<span class="badge bg-{status_class}">{status_esc}</span>'
                f'<a href="/workgroups/{slug_esc}/" class="btn btn-sm btn-primary">View workgroup</a>'
                '</div>'
                '</div>'
                '</div>'
                '</div>'
            )
        cards_html = ''.join(cards_html_parts)
    else:
        cards_html = '<div class="col-12"><div class="alert alert-info mb-0">No approved workgroups yet. Check back soon.</div></div>'

    faq_html = ''.join(
        f'<div class="accordion-item">'
        f'<h2 class="accordion-header">'
        f'<button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#faq-{i}" aria-expanded="false" aria-controls="faq-{i}">'
        f'{_escape_text(item["q"])}'
        f'</button>'
        f'</h2>'
        f'<div id="faq-{i}" class="accordion-collapse collapse" data-bs-parent="#workgroup-faq">'
        f'<div class="accordion-body">{_escape_text(item["a"])}</div>'
        f'</div>'
        f'</div>'
        for i, item in enumerate(faq)
    )

    first_card_slug_esc = _escape_text(first_card_slug)

    content = f"""
    <div class="gh-page container mt-4">
        <section class="gh-hero mb-5">
            <h1 class="display-5 mb-3"><i class="fas fa-users-cog me-2 text-primary" aria-hidden="true"></i>Join a Workgroup</h1>
            <p class="lead text-muted mb-0">
                Workgroups are the heart of how The Metaweb coordinates contributions.
                Each workgroup advances one Design Principle (DP) – pick yours and join an active community of contributors.
            </p>
        </section>

        <section class="mb-5">
            <h2 class="h3 mb-3"><i class="fas fa-info-circle me-2 text-info" aria-hidden="true"></i>What are workgroups?</h2>
            <p class="mb-0">
                Workgroups are small, focused teams that move a single Design Principle (DP) from concept to working draft.
                Each workgroup has a charter, a coordinator, and a flexible roster of members who contribute as their time allows.
                There is no requirement to attend every meeting or write every line – workgroups run on async collaboration, with synchronous time reserved for moments that need it.
            </p>
        </section>

        <section class="mb-5">
            <h2 class="h3 mb-3"><i class="fas fa-user-tag me-2 text-success" aria-hidden="true"></i>Workgroup roles</h2>
            <p class="text-muted mb-3">
                Every workgroup has seven named positions. Pick the role that fits the contribution you want to make.
            </p>
            <div class="row g-3">
                {role_cards_html}
            </div>
        </section>

        <section class="mb-5">
            <h2 class="h3 mb-3"><i class="fas fa-bullhorn me-2 text-warning" aria-hidden="true"></i>Join or nominate</h2>
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-body">
                            <h3 class="h5 mb-2"><i class="fas fa-user-plus me-1 text-primary" aria-hidden="true"></i>Join as a member</h3>
                            <p class="text-muted mb-3">
                                Already a GovHub member? Pick a workgroup below and click "View workgroup," then use the Join button on the workgroup page.
                                You can join as many workgroups as you have time for.
                            </p>
                            <a href="/workgroups/" class="btn btn-primary">
                                <i class="fas fa-list me-2" aria-hidden="true"></i>Browse workgroups
                            </a>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card h-100">
                        <div class="card-body">
                            <h3 class="h5 mb-2"><i class="fas fa-hand-pointer me-1 text-success" aria-hidden="true"></i>Nominate someone (or yourself)</h3>
                            <p class="text-muted mb-3">
                                Want to step into a Coordinator, Editor, or other leadership role?
                                Open any workgroup below and use the Nominate button – you can nominate yourself or someone else, and the nominee reviews the nomination before it goes to layer admins.
                            </p>
                            <a href="/workgroups/{first_card_slug_esc}/" class="btn btn-success">
                                <i class="fas fa-arrow-right me-2" aria-hidden="true"></i>Open a workgroup to nominate
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <section class="mb-5">
            <h2 class="h3 mb-3"><i class="fas fa-layer-group me-2 text-primary" aria-hidden="true"></i>Active Metaweb workgroups</h2>
            <p class="text-muted mb-3">
                These are the approved workgroups on The Metaweb layer.
                Click any card to view details, members, and the Join button.
            </p>
            <div class="row g-3">
                {cards_html}
            </div>
        </section>

        <section class="mb-5">
            <h2 class="h3 mb-3"><i class="fas fa-question-circle me-2 text-secondary" aria-hidden="true"></i>Frequently asked questions</h2>
            <div class="accordion" id="workgroup-faq">
                {faq_html}
            </div>
        </section>

        <section class="mb-5">
            <div class="card border-0 bg-light">
                <div class="card-body py-4 px-4">
                    <h2 class="h4 mb-2"><i class="fas fa-rocket me-2 text-primary" aria-hidden="true"></i>Ready to contribute?</h2>
                    <p class="mb-3">
                        Pick a workgroup, click Join, and start contributing at the level that fits your time.
                        If you want to lead, nominate yourself – the path from member to coordinator is open to everyone.
                    </p>
                    <a href="/workgroups/" class="btn btn-primary">
                        <i class="fas fa-arrow-right me-2" aria-hidden="true"></i>Browse all workgroups
                    </a>
                </div>
            </div>
        </section>
    </div>
    """

    return render_page(
        title='Join a Workgroup – GovHub',
        content=content,
        theme=current_theme,
        user_menu=user_menu,
    )


@bp.route('/workgroups/<workgroup_slug>/')
def workgroup_detail(workgroup_slug):
    """Workgroup detail page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    current_user_json = json.dumps({
        'id': current_user['id'],
        'name': current_user.get('displayName') or current_user.get('name') or current_user.get('username'),
        'email': current_user.get('email') or '',
        'username': current_user.get('username') or '',
    }) if current_user else 'null'

    content = f"""
    <div class="gh-page container mt-4">
        <div id="workgroup-header" class="gh-detail-hero mb-0">
            <div class="d-flex justify-content-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>

        <div class="gh-detail-layout mt-4">
            <div class="gh-detail-main">
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-align-left"></i></div>
                        <h5 class="living-module-title">About</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-about">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-star"></i></div>
                        <h5 class="living-module-title">Positions & Nominations</h5>
                        {'<button class="btn btn-sm btn-success ms-auto" onclick="nominateForChair()" id="nominate-btn" style="display:none;"><i class="fas fa-user-plus me-1"></i>Nominate</button>' if current_user else ''}
                    </div>
                    <div class="living-module-body" id="workgroup-chairs">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-users"></i></div>
                        <h5 class="living-module-title">Members</h5>
                        {(
                            '<button class="btn btn-sm btn-outline-secondary ms-auto me-2" onclick="inviteWorkgroupMember()" '
                            'id="invite-member-btn" style="display:none;"><i class="fas fa-envelope me-1"></i>Invite</button>'
                            '<button class="btn btn-sm btn-primary" onclick="joinWorkgroup()" id="join-btn" style="display:none;">'
                            '<i class="fas fa-user-plus me-1"></i>Join</button>'
                        ) if current_user else ''}
                    </div>
                    <div class="living-module-body" id="workgroup-members">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-folder-open"></i></div>
                        <h5 class="living-module-title">Assigned documents</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-assigned-docs">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>

            <div class="gh-detail-sidebar">
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-info-circle"></i></div>
                        <h5 class="living-module-title">Details</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-details">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-scroll"></i></div>
                        <h5 class="living-module-title">Charter & Goals</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-charter">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Position Nomination Modal -->
    <div class="modal fade" id="nominateChairModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Nominate for a position</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="nominateChairForm">
                        <div class="mb-3">
                            <label class="form-label">Workgroup</label>
                            <p class="form-control-plaintext" id="modal-workgroup-name"></p>
                        </div>
                        <div class="mb-3">
                            <label for="nomination-position" class="form-label">Position <span class="text-danger">*</span></label>
                            <select id="nomination-position" class="form-select" required></select>
                            <div class="form-text" id="nomination-position-desc"></div>
                        </div>
                        <div class="mb-3">
                            <label class="form-label d-block">Who are you nominating?</label>
                            <div class="btn-group" role="group" aria-label="Nomination target">
                                <input type="radio" class="btn-check" name="nomination-target" id="nomination-target-self" value="self" checked>
                                <label class="btn btn-outline-primary" for="nomination-target-self">Myself</label>
                                <input type="radio" class="btn-check" name="nomination-target" id="nomination-target-other" value="other">
                                <label class="btn btn-outline-primary" for="nomination-target-other">Someone else</label>
                            </div>
                        </div>
                        <div id="nomination-other-search-wrap" class="mb-3" style="display:none;">
                            <label for="nomination-user-search" class="form-label">Find on GovHub <span class="text-muted">(optional)</span></label>
                            <input type="search" class="form-control" id="nomination-user-search" placeholder="Search by name or username..." autocomplete="off">
                            <div id="nomination-user-results" class="mt-2"></div>
                            <div class="form-text">If they are not on GovHub yet, enter their details below.</div>
                        </div>
                        <div class="mb-3">
                            <label for="nomination-name" class="form-label">Nominee name <span class="text-danger">*</span></label>
                            <input type="text" class="form-control" id="nomination-name" required placeholder="Full name">
                        </div>
                        <div class="mb-3">
                            <label for="nomination-email" class="form-label">Nominee email <span class="text-danger">*</span></label>
                            <input type="email" class="form-control" id="nomination-email" required placeholder="name@example.com">
                        </div>
                        <div class="mb-3">
                            <label for="nomination-profile-url" class="form-label">CV or LinkedIn URL <span class="text-danger">*</span></label>
                            <input type="url" class="form-control" id="nomination-profile-url" required placeholder="https://linkedin.com/in/... or link to CV">
                        </div>
                        <div class="mb-3">
                            <label for="nomination-statement" class="form-label">Statement <span class="text-danger">*</span></label>
                            <textarea
                                class="form-control"
                                id="nomination-statement"
                                rows="4"
                                required
                                placeholder="Why is this person a good fit for this position?"
                            ></textarea>
                            <div class="form-text">Share relevant experience and commitment for this role.</div>
                        </div>
                        <input type="hidden" id="nomination-user-id" value="">
                        <div class="alert alert-info mb-0">
                            <i class="fas fa-info-circle me-2"></i>
                            The nominee receives your statement by email and must accept before administrators review. You will be copied on updates.
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-success" onclick="submitChairNomination()">
                        <i class="fas fa-paper-plane me-2"></i>Submit Nomination
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let workgroup = null;
    let project = null;
    const workgroupSlug = '{workgroup_slug}';
    const isAuthenticated = {'true' if current_user else 'false'};
    const currentUserId = {json.dumps(current_user['id']) if current_user else 'null'};
    const currentUserProfile = {current_user_json};
    let selectedNomineeUserId = null;
    let nominationSearchResults = [];
    let workgroupPositions = [];

    async function loadWorkgroupPositions() {{
        try {{
            const resp = await fetch('/api/workgroups/positions/');
            const data = await resp.json();
            workgroupPositions = data.positions || [];
            const sel = document.getElementById('nomination-position');
            if (!sel) return;
            sel.innerHTML = workgroupPositions.map(function(p) {{
                return '<option value="' + p.key + '">' + p.label + '</option>';
            }}).join('');
            sel.addEventListener('change', updatePositionDescription);
            updatePositionDescription();
        }} catch (e) {{
            console.warn('Could not load positions', e);
        }}
    }}

    function updatePositionDescription() {{
        const key = document.getElementById('nomination-position')?.value;
        const pos = workgroupPositions.find(p => p.key === key);
        const descEl = document.getElementById('nomination-position-desc');
        if (descEl) descEl.textContent = pos ? pos.description : '';
    }}

    async function loadWorkgroup() {{
        try {{
            // Cache-bust to avoid stale HTML on repeat visits.
            const cacheBuster = '?_=' + Date.now();

            // Fast path: slug-direct lookup (avoids the up-to-8 sequential
            // layer-by-layer search the page used to do).
            let found = null;
            const directResp = await fetch(
                '/api/workgroups/by-slug/' + encodeURIComponent(workgroupSlug) + '/' + cacheBuster
            );
            if (directResp.ok) {{
                found = await directResp.json();
            }} else {{
                // Fallback: layer-by-layer search (kept for environments
                // that haven't deployed the by-slug endpoint yet).
                const projectsResp = await fetch('/api/layers/' + cacheBuster);
                const projectsData = await projectsResp.json();
                for (const proj of (projectsData.layers || [])) {{
                    const wgResp = await fetch(
                        '/api/layers/' + proj.id + '/workgroups/' + cacheBuster
                    );
                    const wgData = await wgResp.json();
                    const candidate = (wgData.workgroups || []).find(wg => wg.slug === workgroupSlug);
                    if (candidate) {{
                        found = candidate;
                        project = proj;
                        break;
                    }}
                }}
                if (!found) {{
                    document.getElementById('workgroup-header').innerHTML =
                        '<div class="alert alert-danger">Workgroup not found</div>';
                    return;
                }}
            }}

            workgroup = found;
            if (!project && workgroup.layer_id) {{
                // Fetch the layer list to identify the parent project (used
                // for the sidebar/breadcrumb). Non-fatal if it fails.
                try {{
                    const projectsResp = await fetch('/api/layers/' + cacheBuster);
                    const projectsData = await projectsResp.json();
                    project = (projectsData.layers || []).find(l => l.id === workgroup.layer_id) || null;
                }} catch (_) {{ /* non-fatal */ }}
            }}

            // Load full workgroup details
            const detailResp = await fetch(
                '/api/workgroups/' + workgroup.id + '/' + cacheBuster
            );
            if (!detailResp.ok) {{
                throw new Error('Workgroup detail request failed');
            }}
            workgroup = await detailResp.json();

            displayWorkgroupHeader();
            displayWorkgroupAbout();
            displayWorkgroupCharter();
            displayWorkgroupDetails();
            loadChairs();
            loadMembers();
            loadAssignedDocuments();
        }} catch (error) {{
            console.error('Error loading workgroup:', error);
            document.getElementById('workgroup-header').innerHTML =
                '<div class="alert alert-danger">Error loading workgroup</div>';
        }}
    }}

    function displayWorkgroupHeader() {{
        const statusBadge = getStatusBadge(workgroup.status);
        const approvalBadge = getApprovalBadge(workgroup.approval_status);
        const projectSlug = project ? project.slug : '';
        const projectName = project ? project.name : (workgroup.layer_name || 'Layer');
        const linkBtns = (workgroup.external_url ? '<a href="' + workgroup.external_url + '" class="btn btn-outline-primary btn-sm w-100 mb-2" target="_blank" rel="noopener noreferrer"><i class="fas fa-external-link-alt me-2"></i>Website</a>' : '') +
            (workgroup.document_href ? '<a href="' + workgroup.document_href + '" class="btn btn-outline-primary btn-sm w-100 mb-2"><i class="fas fa-file-alt me-2"></i>Document</a>' : '');
        const bc = '<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb">' +
            '<li class="breadcrumb-item"><a href="/layers/">Layers</a></li>' +
            (projectSlug ? '<li class="breadcrumb-item"><a href="/layers/' + projectSlug + '/">' + projectName + '</a></li>' : '<li class="breadcrumb-item">' + projectName + '</li>') +
            '<li class="breadcrumb-item active">' + (workgroup.name || '') + '</li></ol></nav>';
        const mediaHtml = workgroup.image_url
            ? '<div class="gh-detail-hero-media"><img src="' + workgroup.image_url + '" alt=""></div>'
            : '<div class="gh-detail-hero-media"><i class="fas fa-users-cog fa-2x text-muted opacity-50"></i></div>';
        const backBtn = projectSlug
            ? '<a href="/layers/' + projectSlug + '/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-2"></i>Back</a>'
            : '<a href="/workgroups/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-2"></i>Back</a>';
        document.getElementById('workgroup-header').innerHTML =
            '<div class="gh-detail-hero-inner">' +
                mediaHtml +
                '<div class="gh-detail-hero-body flex-grow-1">' +
                    bc +
                    '<h1>' + (workgroup.name || '') + '</h1>' +
                    '<div class="mb-0">' + statusBadge + ' ' + approvalBadge + '</div>' +
                '</div>' +
                '<div class="gh-detail-hero-actions">' +
                    linkBtns +
                    (workgroup.can_edit ? '<button type="button" class="btn btn-secondary btn-sm w-100 mb-2" onclick="editWorkgroup()"><i class="fas fa-edit me-2"></i>Edit</button>' : '') +
                    backBtn +
                '</div>' +
            '</div>';
    }}

    function displayWorkgroupAbout() {{
        document.getElementById('workgroup-about').innerHTML = `
            <p>${{workgroup.description || 'No description provided'}}</p>
        `;
    }}

    function displayWorkgroupCharter() {{
        const canEdit = workgroup.can_edit === true;
        let html = '';

        if (workgroup.charter) {{
            html += renderCharterSection(workgroup.charter);
        }} else {{
            html += '<div class="wg-charter-block mb-3">';
            html += '<h6 class="wg-sidebar-section-title">Charter</h6>';
            html += '<p class="text-muted small mb-0">No charter defined yet.</p>';
            if (canEdit) {{
                html += '<button type="button" class="btn btn-link btn-sm wg-expand-toggle p-0 mt-1" onclick="editWorkgroup()">Add charter</button>';
            }}
            html += '</div>';
        }}

        if (workgroup.goals) {{
            html += renderGoalsSection(workgroup.goals);
        }} else if (workgroup.charter) {{
            html += '<div class="wg-goals-block">';
            html += '<h6 class="wg-sidebar-section-title">Goals</h6>';
            html += '<p class="text-muted small mb-0">No goals defined yet.</p>';
            if (canEdit) {{
                html += '<button type="button" class="btn btn-link btn-sm wg-expand-toggle p-0 mt-1" onclick="editWorkgroup()">Add goals</button>';
            }}
            html += '</div>';
        }} else if (!workgroup.charter && canEdit) {{
            html += '<div class="wg-goals-block mt-3">';
            html += '<h6 class="wg-sidebar-section-title">Goals</h6>';
            html += '<p class="text-muted small mb-0">No goals defined yet.</p>';
            html += '<button type="button" class="btn btn-link btn-sm wg-expand-toggle p-0 mt-1" onclick="editWorkgroup()">Add goals</button>';
            html += '</div>';
        }}

        if (!workgroup.charter && !workgroup.goals && !canEdit) {{
            html = '<p class="text-muted small mb-0">No charter or goals defined yet.</p>';
        }}

        document.getElementById('workgroup-charter').innerHTML = html;
    }}

    function charterNeedsExpand(text) {{
        const raw = String(text || '');
        if (raw.length > 220) return true;
        return raw.split(/\\r?\\n/).length > 3;
    }}

    function renderCharterSection(text) {{
        const body = formatMultilineHtml(text);
        const expandable = charterNeedsExpand(text);
        let html = '<div class="wg-charter-block mb-3">';
        html += '<h6 class="wg-sidebar-section-title">Charter</h6>';
        html += '<div class="wg-expandable' + (expandable ? ' wg-expandable--collapsed' : '') + '" data-expand-label="Read full charter" data-collapse-label="Show less">';
        html += '<div class="wg-expandable-body wg-charter-text">' + body + '</div>';
        if (expandable) {{
            html += '<button type="button" class="btn btn-link btn-sm wg-expand-toggle p-0 mt-1" onclick="toggleWgExpand(this)">Read full charter</button>';
        }}
        html += '</div></div>';
        return html;
    }}

    function parseGoalLines(text) {{
        return String(text || '').split(/\\r?\\n/).map(function(line) {{ return line.trim(); }}).filter(Boolean);
    }}

    function renderGoalsSection(text) {{
        const lines = parseGoalLines(text);
        const expandable = lines.length > 3;
        let html = '<div class="wg-goals-block">';
        html += '<h6 class="wg-sidebar-section-title">Goals</h6>';
        html += '<div class="wg-expandable' + (expandable ? ' wg-expandable--collapsed' : '') + '" data-expand-label="Show all goals (' + lines.length + ')" data-collapse-label="Show fewer goals">';
        html += '<ul class="wg-goals-list mb-0">';
        lines.forEach(function(line) {{
            html += '<li>' + escapeHtml(line) + '</li>';
        }});
        html += '</ul>';
        if (expandable) {{
            html += '<button type="button" class="btn btn-link btn-sm wg-expand-toggle p-0 mt-1" onclick="toggleWgExpand(this)">Show all goals (' + lines.length + ')</button>';
        }}
        html += '</div></div>';
        return html;
    }}

    function formatMultilineHtml(text) {{
        return escapeHtml(text).replace(/\\n/g, '<br>');
    }}

    function toggleWgExpand(btn) {{
        const wrap = btn.closest('.wg-expandable');
        if (!wrap) return;
        const collapsed = wrap.classList.toggle('wg-expandable--collapsed');
        const expandLabel = wrap.getAttribute('data-expand-label') || 'Show more';
        const collapseLabel = wrap.getAttribute('data-collapse-label') || 'Show less';
        btn.textContent = collapsed ? expandLabel : collapseLabel;
        btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    }}

    function escapeHtml(text) {{
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }}

    function displayWorkgroupDetails() {{
        const projectSlug = project ? project.slug : '';
        const projectName = project ? project.name : (workgroup.layer_name || 'Unknown Project');
        const urlRow = workgroup.external_url
            ? `<p><strong>Website:</strong> <a href="${{workgroup.external_url}}" target="_blank" rel="noopener noreferrer">${{workgroup.external_url}}</a></p>`
            : '';
        const docRow = workgroup.document_href
            ? `<p><strong>Document:</strong> <a href="${{workgroup.document_href}}">${{workgroup.document_label || 'View draft'}}</a></p>`
            : '';

        document.getElementById('workgroup-details').innerHTML = `
            <p><strong>Layer:</strong> ${{projectSlug ? `<a href="/layers/${{projectSlug}}/">${{projectName}}</a>` : projectName}}</p>
            <p><strong>Status:</strong> ${{workgroup.status}}</p>
            <p><strong>Approval:</strong> ${{workgroup.approval_status}}</p>
            <p><strong>Created:</strong> ${{new Date(workgroup.created_at).toLocaleDateString()}}</p>
            ${{workgroup.coordinator_name ? `<p><strong>Coordinator:</strong> ${{workgroup.coordinator_name}}</p>` : ''}}
            <p class="small text-muted mb-2"><strong>Permissions:</strong> Leads and co-leads can edit and invite; members participate after joining.</p>
            ${{urlRow}}
            ${{docRow}}
        `;
    }}

    function getStatusBadge(status) {{
        const badges = {{
            'active': '<span class="badge bg-success">Active</span>',
            'inactive': '<span class="badge bg-warning">Inactive</span>',
            'completed': '<span class="badge bg-primary">Completed</span>',
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

    async function loadChairs() {{
        try {{
            // Load chairs from working_group_chair table using acronym
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/chairs/?_=${{Date.now()}}`);
            const data = await response.json();

            // Show nominate button for any signed-in user on approved workgroups
            const nominateBtn = document.getElementById('nominate-btn');
            if (nominateBtn) {{
                if (isAuthenticated && workgroup.approval_status === 'approved') {{
                    nominateBtn.style.display = 'block';
                }} else {{
                    nominateBtn.style.display = 'none';
                }}
            }}

            let html = '';
            if (data.chairs && data.chairs.length > 0) {{
                html = '<div class="list-group">';
                data.chairs.forEach(chair => {{
                    const statusBadge = chair.approved
                        ? '<span class="badge bg-success ms-2">Approved</span>'
                        : '<span class="badge bg-warning text-dark ms-2">' + (chair.status_label || 'Pending') + '</span>';
                    const posLabel = chair.position_label || 'Chair';
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${{chair.chair_name}}</strong>
                                    <span class="badge bg-primary ms-2">${{posLabel}}</span>
                                    ${{statusBadge}}
                                </div>
                            </div>
                        </div>
                    `;
                }});
                html += '</div>';
            }} else {{
                html = '<p class="text-muted">No approved positions or active nominations yet</p>';
            }}

            document.getElementById('workgroup-chairs').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading chairs:', error);
            document.getElementById('workgroup-chairs').innerHTML = '<p class="text-muted">No approved positions or active nominations yet</p>';
        }}
    }}

    async function loadMembers() {{
        try {{
            // Load members from working_group_member table using acronym
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/members/?_=${{Date.now()}}`);
            const data = await response.json();

            // Check if current user is already a member
            let isCurrentUserMember = false;
            if (isAuthenticated && currentUserId && data.members) {{
                isCurrentUserMember = data.members.some(m => m.user_id === currentUserId);
            }}

            const joinBtn = document.getElementById('join-btn');
            const inviteBtn = document.getElementById('invite-member-btn');
            if (joinBtn) {{
                if (isAuthenticated && !isCurrentUserMember && workgroup.approval_status === 'approved') {{
                    joinBtn.style.display = 'block';
                }} else {{
                    joinBtn.style.display = 'none';
                }}
            }}
            if (inviteBtn) {{
                var canInvite = workgroup && workgroup.can_invite_members === true;
                inviteBtn.style.display = (isAuthenticated && (isCurrentUserMember || canInvite))
                    ? 'block'
                    : 'none';
            }}

            let html = '';
            if (data.members && data.members.length > 0) {{
                html = `<p class="text-muted mb-2">${{data.members.length}} member(s)</p>`;
                html += '<div class="list-group">';
                data.members.forEach(member => {{
                    html += `
                        <div class="list-group-item">
                            <strong>${{member.user_name}}</strong>
                            <small class="text-muted d-block">Joined: ${{new Date(member.joined_at).toLocaleDateString()}}</small>
                        </div>
                    `;
                }});
                html += '</div>';
            }} else {{
                html = '<p class="text-muted">No members yet</p>';
            }}

            document.getElementById('workgroup-members').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading members:', error);
            document.getElementById('workgroup-members').innerHTML = '<p class="text-muted">No members yet</p>';
        }}
    }}

    async function loadAssignedDocuments() {{
        const container = document.getElementById('workgroup-assigned-docs');
        if (!container || !workgroup || !workgroup.id) return;
        try {{
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/assigned-documents/?_=${{Date.now()}}`);
            const data = await response.json();
            const docs = data.documents || [];
            let html = '<p class="text-muted small mb-3">Drafts linked at submission time (separate from the primary document in Edit).</p>';
            if (!docs.length) {{
                html += '<p class="text-muted mb-0">No additional assigned documents yet.</p>';
            }} else {{
                html += '<div class="row g-3">';
                docs.forEach(function(doc) {{
                    const idLabel = escapeHtml(doc.ml_number || doc.id || '');
                    const title = escapeHtml(doc.title || doc.label || '');
                    const status = escapeHtml(doc.status || '');
                    const href = doc.href || ('/doc/draft/' + encodeURIComponent(doc.id) + '/');
                    html += '<div class="col-md-6"><div class="card h-100"><div class="card-body">';
                    html += '<h6 class="card-title mb-1"><a href="' + href + '">' + idLabel + '</a></h6>';
                    html += '<p class="card-text small mb-2">' + title + '</p>';
                    html += '<span class="badge bg-secondary">' + status + '</span>';
                    html += '<div class="mt-2"><a href="' + href + 'read/" class="btn btn-sm btn-outline-primary me-1">Read</a>';
                    html += '<a href="' + href + '" class="btn btn-sm btn-outline-secondary">Details</a></div>';
                    html += '</div></div></div>';
                }});
                html += '</div>';
            }}
            container.innerHTML = html;
        }} catch (error) {{
            console.error('Error loading assigned documents:', error);
            container.innerHTML = '<p class="text-muted mb-0">Unable to load assigned documents.</p>';
        }}
    }}

    async function inviteWorkgroupMember() {{
        if (!window.GhInvite) {{
            if (window.GhDialog) {{
                await GhDialog.alert({{ title: 'Invite unavailable', message: 'Please refresh the page and try again.', variant: 'warning' }});
            }}
            return;
        }}
        window.GhInvite.open({{
            type: 'join_workgroup',
            title: 'Invite to workgroup',
            hint: 'They will receive an email to join ' + (workgroup.name || 'this workgroup') + '.',
            target: {{ workgroup_id: workgroup.id }},
        }});
    }}

    async function joinWorkgroup() {{
        if (!isAuthenticated) {{
            await GhDialog.alert({{ title: 'Sign in required', message: 'Please sign in to join this workgroup.', variant: 'info' }});
            return;
        }}

        const confirmed = await GhDialog.confirm({{
            title: 'Join workgroup',
            message: 'Join this workgroup as a member?',
            confirmLabel: 'Join',
            variant: 'info',
        }});
        if (!confirmed) return;

        try {{
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/join/`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }});

            const data = await response.json();

            if (response.ok) {{
                const pending = data.pending_approval === true;
                await GhDialog.alert({{
                    title: pending ? 'Request submitted' : 'Welcome',
                    message: pending ? 'Your membership request is pending approval.' : 'You joined this workgroup.',
                    variant: pending ? 'info' : 'success',
                }});
                loadMembers();
            }} else {{
                await GhDialog.alert({{ title: 'Could not join', message: data.error || 'Failed to join workgroup', variant: 'danger' }});
            }}
        }} catch (error) {{
            console.error('Error joining workgroup:', error);
            await GhDialog.alert({{ title: 'Error', message: 'Failed to join workgroup.', variant: 'danger' }});
        }}
    }}

    function setNominationTarget(target) {{
        const isSelf = target === 'self';
        document.getElementById('nomination-other-search-wrap').style.display = isSelf ? 'none' : 'block';
        document.getElementById('nomination-name').readOnly = false;
        selectedNomineeUserId = null;
        document.getElementById('nomination-user-id').value = '';
        document.getElementById('nomination-user-search').value = '';
        document.getElementById('nomination-user-results').innerHTML = '';
        if (isSelf && currentUserProfile) {{
            document.getElementById('nomination-name').value = currentUserProfile.name || '';
            document.getElementById('nomination-email').value = currentUserProfile.email || '';
            selectedNomineeUserId = currentUserProfile.id || null;
            document.getElementById('nomination-user-id').value = selectedNomineeUserId || '';
        }} else {{
            document.getElementById('nomination-name').value = '';
            document.getElementById('nomination-email').value = '';
            document.getElementById('nomination-profile-url').value = '';
        }}
    }}

    function bindNominationTargetControls() {{
        document.querySelectorAll('input[name="nomination-target"]').forEach(function(radio) {{
            radio.addEventListener('change', function() {{
                setNominationTarget(this.value);
            }});
        }});
        const searchInput = document.getElementById('nomination-user-search');
        if (searchInput) {{
            searchInput.addEventListener('input', searchNominationUsers);
        }}
    }}

    async function searchNominationUsers() {{
        const q = document.getElementById('nomination-user-search').value.trim();
        const resultsEl = document.getElementById('nomination-user-results');
        if (q.length < 2) {{
            resultsEl.innerHTML = '';
            return;
        }}
        try {{
            const response = await fetch('/api/users/search/?q=' + encodeURIComponent(q));
            const data = await response.json();
            if (!data.users || data.users.length === 0) {{
                resultsEl.innerHTML = '<p class="text-muted small mb-0">No GovHub users found. Enter their details manually below.</p>';
                return;
            }}
            resultsEl.innerHTML = data.users.map(function(u, index) {{
                const label = (u.display_name || u.username || '').replace(/</g, '&lt;');
                const username = (u.username || '').replace(/</g, '&lt;');
                return '<button type="button" class="list-group-item list-group-item-action py-2" onclick="selectNominationUser(' + index + ')">' +
                    label + ' <small class="text-muted">@' + username + '</small></button>';
            }}).join('');
            nominationSearchResults = data.users;
            resultsEl.innerHTML = '<div class="list-group">' + resultsEl.innerHTML + '</div>';
        }} catch (error) {{
            resultsEl.innerHTML = '<p class="text-danger small mb-0">Could not search users.</p>';
        }}
    }}

    async function selectNominationUser(index) {{
        const u = nominationSearchResults[index];
        if (!u) return;
        selectedNomineeUserId = u.id;
        document.getElementById('nomination-user-id').value = u.id;
        document.getElementById('nomination-name').value = u.display_name || u.username || '';
        document.getElementById('nomination-user-results').innerHTML =
            '<div class="alert alert-success py-2 mb-0"><small>Selected @' + (u.username || '') + '</small></div>';
        try {{
            const response = await fetch('/api/user/' + encodeURIComponent(u.username) + '/');
            if (response.ok) {{
                const profile = await response.json();
                const links = profile.social_links || [];
                let profileUrl = '';
                links.forEach(function(link) {{
                    const platform = String(link.platform || '').toLowerCase();
                    const url = String(link.url || '').trim();
                    if (!profileUrl && url && (platform.indexOf('linkedin') !== -1 || url.indexOf('linkedin.com') !== -1)) {{
                        profileUrl = url;
                    }}
                }});
                if (!profileUrl) {{
                    links.forEach(function(link) {{
                        const url = String(link.url || '').trim();
                        if (!profileUrl && url) profileUrl = url;
                    }});
                }}
                if (profileUrl) {{
                    document.getElementById('nomination-profile-url').value = profileUrl;
                }}
            }}
        }} catch (error) {{
            console.warn('Could not load nominee profile hints', error);
        }}
    }}

    async function nominateForChair() {{
        if (!isAuthenticated) {{
            await GhDialog.alert({{ title: 'Sign in required', message: 'Please sign in to submit a nomination.', variant: 'info' }});
            return;
        }}

        document.getElementById('modal-workgroup-name').textContent = workgroup.name;
        document.getElementById('nomination-statement').value = '';
        document.getElementById('nomination-profile-url').value = '';
        document.getElementById('nomination-target-self').checked = true;
        document.getElementById('nomination-target-other').checked = false;
        setNominationTarget('self');

        const modal = new bootstrap.Modal(document.getElementById('nominateChairModal'));
        modal.show();
    }}

    async function submitChairNomination() {{
        const nomineeName = document.getElementById('nomination-name').value.trim();
        const nomineeEmail = document.getElementById('nomination-email').value.trim();
        const nomineeProfileUrl = document.getElementById('nomination-profile-url').value.trim();
        const statement = document.getElementById('nomination-statement').value.trim();
        const nomineeUserId = document.getElementById('nomination-user-id').value.trim() || null;
        const target = document.querySelector('input[name="nomination-target"]:checked')?.value || 'self';

        if (!nomineeName) {{
            await GhDialog.alert({{ title: 'Missing name', message: 'Please enter the nominee name.', variant: 'warning' }});
            return;
        }}
        if (!nomineeEmail) {{
            await GhDialog.alert({{ title: 'Missing email', message: 'Please enter the nominee email.', variant: 'warning' }});
            return;
        }}
        if (!nomineeProfileUrl) {{
            await GhDialog.alert({{ title: 'Missing profile link', message: 'Please enter a CV or LinkedIn URL.', variant: 'warning' }});
            return;
        }}
        if (!statement) {{
            await GhDialog.alert({{ title: 'Missing statement', message: 'Please provide a statement for this nomination.', variant: 'warning' }});
            return;
        }}

        const payload = {{
            position_key: document.getElementById('nomination-position')?.value || 'chair',
            nominee_name: nomineeName,
            nominee_email: nomineeEmail,
            nominee_profile_url: nomineeProfileUrl,
            statement: statement,
        }};
        if (target === 'other' && nomineeUserId) {{
            payload.nominee_user_id = nomineeUserId;
        }} else if (target === 'self' && currentUserProfile?.id) {{
            payload.nominee_user_id = currentUserProfile.id;
        }}

        try {{
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/nominate/`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload)
            }});

            const data = await response.json();

            if (response.ok) {{
                const modal = bootstrap.Modal.getInstance(document.getElementById('nominateChairModal'));
                modal.hide();
                await GhDialog.alert({{
                    title: 'Nomination submitted',
                    message: (data.message || 'Your nomination was submitted.') + '\\n\\nNominees must accept before administrators can approve. You will receive email updates.',
                    variant: 'success',
                    confirmLabel: 'Got it',
                }});
                loadChairs();
            }} else {{
                await GhDialog.alert({{ title: 'Submission failed', message: data.error || 'Failed to submit nomination', variant: 'danger' }});
            }}
        }} catch (error) {{
            console.error('Error nominating for chair:', error);
            await GhDialog.alert({{ title: 'Error', message: 'Failed to submit nomination.', variant: 'danger' }});
        }}
    }}

    bindNominationTargetControls();
    loadWorkgroupPositions();

    async function uploadWorkgroupImage() {{
        const fileInput = document.getElementById('edit-wg-image-file');
        const statusEl = document.getElementById('edit-wg-image-upload-status');
        const urlInput = document.getElementById('edit-wg-image-url');

        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'workgroup');

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
                statusEl.innerHTML = `<small class="text-danger">${{data.error || 'Upload failed'}}</small>`;
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}

    function editWorkgroup() {{
        const modalHtml = `
            <div class="modal fade" id="editWorkgroupModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Workgroup</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="edit-workgroup-alert-container"></div>
                            <form id="editWorkgroupForm">
                                <div class="mb-3">
                                    <label for="edit-wg-name" class="form-label">Name *</label>
                                    <input type="text" class="form-control" id="edit-wg-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="edit-wg-description" rows="3"></textarea>
                                    <div class="form-text">Short summary shown in About</div>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-charter" class="form-label">Charter</label>
                                    <textarea class="form-control" id="edit-wg-charter" rows="4" placeholder="Scope, responsibilities, and operating principles for this workgroup"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-goals" class="form-label">Goals</label>
                                    <textarea class="form-control" id="edit-wg-goals" rows="3" placeholder="What this workgroup aims to achieve (one per line is fine)"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-image-url" class="form-label">Image (optional)</label>
                                    <input type="url" class="form-control mb-2" id="edit-wg-image-url" placeholder="https://example.com/image.png or upload below">
                                    <div class="input-group">
                                        <input type="file" class="form-control" id="edit-wg-image-file" accept="image/*">
                                        <button class="btn btn-outline-primary" type="button" onclick="uploadWorkgroupImage()">
                                            <i class="fas fa-upload"></i> Upload
                                        </button>
                                    </div>
                                    <div class="form-text">Workgroup logo or banner. Max 600×600px, 5MB. Upload or paste URL above.</div>
                                    <div id="edit-wg-image-upload-status" class="mt-1"></div>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-external-url" class="form-label">Workgroup URL (optional)</label>
                                    <input type="url" class="form-control" id="edit-wg-external-url" placeholder="https://example.com/workgroup">
                                    <div class="form-text">External site, wiki, or meeting link for this workgroup.</div>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-document-ref" class="form-label">Document (optional)</label>
                                    <select class="form-select" id="edit-wg-document-ref">
                                        <option value="">– None –</option>
                                    </select>
                                    <div class="form-text">Link this workgroup to a specific draft document.</div>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-status" class="form-label">Status</label>
                                    <select class="form-select" id="edit-wg-status">
                                        <option value="active">Active</option>
                                        <option value="inactive">Inactive</option>
                                        <option value="completed">Completed</option>
                                        <option value="archived">Archived</option>
                                    </select>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="editWorkgroupSubmitBtn">
                                <i class="fas fa-save me-2"></i>Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('editWorkgroupModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('edit-wg-name').value = workgroup.name || '';
        document.getElementById('edit-wg-description').value = workgroup.description || '';
        document.getElementById('edit-wg-charter').value = workgroup.charter || '';
        document.getElementById('edit-wg-goals').value = workgroup.goals || '';
        const wgImgEl = document.getElementById('edit-wg-image-url');
        if (wgImgEl) wgImgEl.value = workgroup.image_url || '';
        const wgImgFileEl = document.getElementById('edit-wg-image-file');
        if (wgImgFileEl) wgImgFileEl.value = '';
        const wgImgStatusEl = document.getElementById('edit-wg-image-upload-status');
        if (wgImgStatusEl) wgImgStatusEl.innerHTML = '';
        document.getElementById('edit-wg-status').value = workgroup.status || 'active';
        const urlEl = document.getElementById('edit-wg-external-url');
        if (urlEl) urlEl.value = workgroup.external_url || '';
        document.getElementById('edit-workgroup-alert-container').innerHTML = '';
        const selectedDoc = workgroup.document_draft_name || workgroup.document_draft_ref || '';
        populateWorkgroupDocumentSelect(selectedDoc);
        const modal = new bootstrap.Modal(document.getElementById('editWorkgroupModal'));
        modal.show();
        document.getElementById('editWorkgroupSubmitBtn').onclick = async () => {{
            const name = document.getElementById('edit-wg-name').value.trim();
            const description = document.getElementById('edit-wg-description').value.trim();
            const charter = document.getElementById('edit-wg-charter').value.trim();
            const goals = document.getElementById('edit-wg-goals').value.trim();
            const image_url = document.getElementById('edit-wg-image-url') ? document.getElementById('edit-wg-image-url').value.trim() : '';
            const external_url = document.getElementById('edit-wg-external-url') ? document.getElementById('edit-wg-external-url').value.trim() : '';
            const document_draft_name = document.getElementById('edit-wg-document-ref') ? document.getElementById('edit-wg-document-ref').value.trim() : '';
            const status = document.getElementById('edit-wg-status').value;
            if (!name) {{
                document.getElementById('edit-workgroup-alert-container').innerHTML = '<div class="alert alert-danger">Name is required.</div>';
                return;
            }}
            const btn = document.getElementById('editWorkgroupSubmitBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
            try {{
                const response = await fetch(`/api/workgroups/${{workgroup.id}}/`, {{
                    method: 'PATCH',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description, charter: charter || null, goals: goals || null, image_url: image_url || null, external_url: external_url || null, document_draft_name: document_draft_name || null, status }})
                }});
                if (!response.ok) {{
                    const data = await response.json();
                    throw new Error(data.error || 'Failed to update workgroup');
                }}
                const data = await response.json();
                workgroup = data.workgroup;
                modal.hide();
                displayWorkgroupHeader();
                displayWorkgroupAbout();
                displayWorkgroupCharter();
                displayWorkgroupDetails();
            }} catch (err) {{
                document.getElementById('edit-workgroup-alert-container').innerHTML = '<div class="alert alert-danger">' + (err.message || 'Failed to update workgroup') + '</div>';
            }}
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
        }};
    }}

    async function populateWorkgroupDocumentSelect(selectedId) {{
        const sel = document.getElementById('edit-wg-document-ref');
        if (!sel) return;
        sel.innerHTML = '<option value="">Loading documents...</option>';
        sel.disabled = true;
        try {{
            const url = workgroup.id
                ? ('/api/documents/?workgroup_id=' + encodeURIComponent(workgroup.id))
                : ((workgroup.layer_id || (project && project.id))
                    ? ('/api/documents/?layer_id=' + encodeURIComponent(workgroup.layer_id || project.id))
                    : '/api/documents/');
            const resp = await fetch(url, {{ credentials: 'same-origin' }});
            const data = await resp.json();
            if (!resp.ok) {{
                throw new Error(data.error || ('Could not load documents (' + resp.status + ')'));
            }}
            const docs = data.documents || [];
            let html = '<option value="">– None –</option>';
            docs.forEach(function(d) {{
                const label = d.label || d.title || d.id;
                const selected = selectedId && d.id === selectedId ? ' selected' : '';
                html += '<option value="' + String(d.id).replace(/"/g, '&quot;') + '"' + selected + '>' + label.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</option>';
            }});
            sel.innerHTML = html;
            if (selectedId && !Array.from(sel.options).some(function(o) {{ return o.value === selectedId; }})) {{
                sel.innerHTML += '<option value="' + String(selectedId).replace(/"/g, '&quot;') + '" selected>Linked document (' + selectedId + ')</option>';
            }}
        }} catch (e) {{
            console.warn('Workgroup document picker:', e);
            sel.innerHTML = '<option value="">– None –</option>';
            if (selectedId) {{
                sel.innerHTML += '<option value="' + String(selectedId).replace(/"/g, '&quot;') + '" selected>Linked document (' + selectedId + ')</option>';
            }}
            sel.innerHTML += '<option value="" disabled>Could not load draft list – refresh and try again</option>';
        }}
        sel.disabled = false;
    }}

    // Load workgroup on page load
    loadWorkgroup();
    </script>
    """

    return render_page(f"Workgroup: {workgroup_slug} - GovHub", content, theme=current_theme, user_menu=user_menu)
