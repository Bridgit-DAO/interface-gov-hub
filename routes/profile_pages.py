"""Profile page routes: /profile/<username>/, /profile/edit/."""
import html as html_mod
import json
from datetime import datetime

from flask import Blueprint, redirect, request, session
from sqlalchemy import text

from extensions import db
from models import User, Workgroup, Submission, Comment, LayerMember, UserLinkedAccount, DpProposal

from services.identity import get_current_user, require_auth
from services.avatar import get_avatar_url
from services.directory_ui import gh_page_open, gh_page_close, gh_page_header
from services.utils import coerce_storage_bool
from services.dp_proposals import (
    submission_draft_ref,
    submission_display_label,
    submission_profile_href,
    submission_for_reader_ref,
)
from services.site_roles import site_role_label, site_role_badge_class

bp = Blueprint('profile_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


def _format_activity_items(projects, submissions):
    """Helper function to format activity items"""
    items = []

    for project in projects:
        date = project[2]
        if isinstance(date, str):
            try:
                date = datetime.fromisoformat(date.replace('Z', '+00:00'))
            except Exception:
                date = datetime.utcnow()
        items.append((date, 'project', f'Created project <strong>{project[0]}</strong>', f'/layers/{project[1]}/'))

    for submission in submissions:
        if hasattr(submission, 'status'):
            s = submission
            date = s.submitted_at or datetime.utcnow()
            approved = (s.status or '').lower() == 'approved'
            label = html_mod.escape(submission_display_label(s))
            status = 'Approved' if approved else (s.status or 'Draft').title()
            badge = 'success' if approved else 'secondary'
            link = submission_profile_href(s)
            text_val = (
                f'Submitted <strong>{label}</strong> '
                f'<span class="badge bg-{badge}">{html_mod.escape(status)}</span>'
            )
            items.append((date, 'submission', text_val, link))
            continue
        draft_name = submission[0]
        date = submission[1] if submission[1] else datetime.utcnow()
        submission_id = submission[2]
        approved = submission[3]
        status = 'Approved' if approved else 'Draft'
        items.append((
            date,
            'submission',
            f'Submitted <strong>{html_mod.escape(str(draft_name))}</strong> '
            f'<span class="badge bg-{"success" if approved else "secondary"}">{status}</span>',
            f'/submit/status/{submission_id}/',
        ))

    items.sort(key=lambda x: x[0], reverse=True)

    html = ''
    for date, type_, text_val, link in items[:10]:
        icon = 'fa-folder' if type_ == 'project' else 'fa-file-alt'
        html += f'''
        <a href="{link}" class="list-group-item list-group-item-action">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <i class="fas {icon} me-2"></i>
                    {text_val}
                </div>
                <small class="text-muted">{date.strftime('%b %d, %Y') if date else ''}</small>
            </div>
        </a>
        '''

    return html if html else '<p class="text-muted">No recent activity.</p>'


def _format_profile_contributions(proposals, comments):
    """Patches and document comments for profile tab."""
    html = ''
    html += '<h5 class="card-title">Patches</h5>'
    if proposals:
        html += '<div class="list-group list-group-flush mb-4">'
        for p in proposals:
            sub = p.submission
            label = submission_display_label(sub) if sub else 'Document'
            kind = 'Patch'
            href = submission_profile_href(sub) if sub else '#'
            excerpt = (p.original_text or '')[:80]
            if len(p.original_text or '') > 80:
                excerpt += '…'
            html += (
                f'<a href="{href}" class="list-group-item list-group-item-action">'
                f'<div class="d-flex justify-content-between"><strong>{html_mod.escape(label)}</strong>'
                f'<span class="badge bg-secondary">{html_mod.escape(kind)}</span></div>'
                f'<small class="text-muted d-block">{html_mod.escape(p.status_label())} · '
                f'{p.created_at.strftime("%b %d, %Y") if p.created_at else ""}</small>'
                f'<small class="text-muted d-block font-monospace">{html_mod.escape(excerpt)}</small>'
                f'</a>'
            )
        html += '</div>'
    else:
        html += '<p class="text-muted mb-4">No patches yet.</p>'

    html += '<h5 class="card-title">Comments</h5>'
    if comments:
        html += '<div class="list-group list-group-flush">'
        for c in comments:
            draft = (c.draft_name or '').strip()
            sub = submission_for_reader_ref(draft) if draft else None
            label = submission_display_label(sub) if sub else (draft or 'Document')
            if sub and (sub.status or '').lower() == 'approved':
                href = submission_profile_href(sub)
            elif draft:
                href = f'/doc/draft/{html_mod.escape(draft)}/comments/'
            else:
                href = '#'
            scope = 'Passage' if getattr(c, 'comment_scope', None) == 'passage' else 'Document'
            if not getattr(c, 'comment_scope', None):
                scope = 'Document'
            preview = (c.text or '')[:120]
            if len(c.text or '') > 120:
                preview += '…'
            html += (
                f'<a href="{href}" class="list-group-item list-group-item-action">'
                f'<div class="d-flex justify-content-between">'
                f'<strong>{html_mod.escape(label)}</strong>'
                f'<span class="badge bg-info">{scope}</span></div>'
                f'<small class="text-muted d-block">'
                f'{c.timestamp.strftime("%b %d, %Y") if c.timestamp else ""}</small>'
                f'<p class="small mb-0 mt-1">{html_mod.escape(preview)}</p>'
                f'</a>'
            )
        html += '</div>'
    else:
        html += '<p class="text-muted">No comments yet.</p>'
    return html


def _render_social_link_inputs(platforms, existing_links):
    """Helper to render social link input fields"""
    html = ''

    for platform in platforms:
        existing = next((link for link in existing_links if link.get('platform') == platform['name']), None)
        value = existing['url'] if existing else ''

        html += f'''
        <div class="mb-3">
            <label class="form-label">
                <i class="fab fa-{platform["icon"]} me-2"></i>{platform["name"]}
            </label>
            <input
                type="url"
                class="form-control"
                data-social-platform="{platform["name"]}"
                data-social-icon="{platform["icon"]}"
                placeholder="{platform["placeholder"]}"
                value="{value}"
            >
        </div>
        '''

    return html


@bp.route('/profile/<username>/')
def user_profile(username):
    """User profile page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    profile_user = User.query.filter_by(username=username).first()
    if not profile_user:
        profile_user = User.query.filter_by(handle=username).first()

    if not profile_user:
        return render_page("User Not Found - MLGH", f"""
            <div class="container mt-5">
                <div class="alert alert-danger">
                    <h4>User Not Found</h4>
                    <p>The user "{username}" does not exist.</p>
                    <a href="/" class="btn btn-primary">Back to Home</a>
                </div>
            </div>
        """, theme=current_theme, user_menu=user_menu)

    is_own_profile = current_user and current_user['id'] == profile_user.id
    is_admin_viewer = bool(current_user and current_user.get('role') == 'admin')

    social_links = []
    if profile_user.social_links:
        try:
            social_links = json.loads(profile_user.social_links)
        except Exception:
            social_links = []
    linked_accounts = UserLinkedAccount.query.filter_by(user_id=profile_user.id).all()
    _provider_icons = {'twitter': 'x-twitter'}
    for acc in linked_accounts:
        if acc.profile_url:
            icon = _provider_icons.get(acc.provider, acc.provider)
            social_links.append({'url': acc.profile_url, 'platform': acc.provider.title(), 'icon': icon})

    projects_count = db.session.execute(text("""
        SELECT COUNT(*) FROM layer WHERE initiator_id = :user_id
    """), {'user_id': profile_user.id}).scalar() or 0

    workgroups_count = db.session.execute(text("""
        SELECT COUNT(*) FROM working_group WHERE coordinator_id = :user_id
    """), {'user_id': profile_user.id}).scalar() or 0

    memberships_count = db.session.execute(text("""
        SELECT COUNT(*) FROM working_group_member WHERE user_id = :user_id
    """), {'user_id': profile_user.id}).scalar() or 0

    chair_count = db.session.execute(text("""
        SELECT COUNT(*) FROM working_group_chair WHERE user_id = :user_id AND approved = 1
    """), {'user_id': profile_user.id}).scalar() or 0

    name_variants = [x for x in (profile_user.name, profile_user.displayName, profile_user.oauthName, profile_user.username) if x]
    submissions_count = Submission.query.filter(Submission.submitted_by.in_(name_variants)).count() if name_variants else 0
    comments_q = Comment.query.filter(Comment.is_deleted == False)  # noqa: E712
    if profile_user.id:
        comments_q = comments_q.filter(
            db.or_(
                Comment.author_user_id == profile_user.id,
                Comment.author.in_(name_variants) if name_variants else db.false(),
            )
        )
    elif name_variants:
        comments_q = comments_q.filter(Comment.author.in_(name_variants))
    else:
        comments_q = comments_q.filter(db.false())
    comments_count = comments_q.count()
    recent_comments = comments_q.order_by(Comment.timestamp.desc()).limit(15).all()
    dp_proposals = (
        DpProposal.query.filter_by(author_user_id=profile_user.id)
        .order_by(DpProposal.created_at.desc())
        .limit(20)
        .all()
    )

    recent_projects = db.session.execute(text("""
        SELECT name, slug, created_at FROM layer
        WHERE initiator_id = :user_id
        ORDER BY created_at DESC LIMIT 5
    """), {'user_id': profile_user.id}).fetchall()

    if name_variants:
        recent_submissions_q = Submission.query.filter(
            Submission.submitted_by.in_(name_variants)
        ).order_by(Submission.submitted_at.desc()).limit(5).all()
        recent_submissions = list(recent_submissions_q)
        all_submissions_q = Submission.query.filter(
            Submission.submitted_by.in_(name_variants)
        ).order_by(Submission.submitted_at.desc()).all()
    else:
        recent_submissions = []
        all_submissions_q = []

    coordinated_workgroups = Workgroup.query.filter_by(coordinator_id=profile_user.id).order_by(Workgroup.created_at.desc()).all()

    memberships_q = db.session.execute(text("""
        SELECT wg.name, wg.slug, wgm.joined_at
        FROM working_group_member wgm
        JOIN working_group wg ON wgm.group_acronym = wg.acronym
        WHERE wgm.user_id = :user_id
        ORDER BY wgm.joined_at DESC
    """), {'user_id': profile_user.id}).fetchall()

    chairs_q = db.session.execute(text("""
        SELECT wg.name, wg.slug, wgc.set_at, wgc.approved
        FROM working_group_chair wgc
        JOIN working_group wg ON wgc.group_acronym = wg.acronym
        WHERE wgc.user_id = :user_id
        ORDER BY wgc.set_at DESC
    """), {'user_id': profile_user.id}).fetchall()

    project_memberships = LayerMember.query.filter_by(user_id=profile_user.id, status='active').order_by(LayerMember.joined_at.desc()).all()

    referral_count = 0
    if is_own_profile:
        referral_count = LayerMember.query.filter_by(referred_by_id=profile_user.id).count()

    if is_admin_viewer and profile_user.email:
        email_details_html = (
            f'<p class="mb-1"><strong>Email:</strong> {html_mod.escape(profile_user.email)}</p>'
            f'<p class="text-muted small mb-0">'
            f'<i class="fas fa-shield-alt me-1"></i>Visible to site administrators only.</p>'
        )
    else:
        email_details_html = ''

    content = f"""
    <style>
        .profile-banner {{
            width: 100%;
            height: 300px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            background-size: cover;
            background-position: center;
            position: relative;
        }}

        .profile-header {{
            position: relative;
            margin-top: -80px;
            padding: 0 2rem;
        }}

        .profile-avatar {{
            width: 160px;
            height: 160px;
            border-radius: 50%;
            border: 6px solid var(--bg-primary);
            background: var(--bg-secondary);
            object-fit: cover;
            display: block;
            image-rendering: pixelated;
            image-rendering: -moz-crisp-edges;
            image-rendering: crisp-edges;
        }}


        .social-links a {{
            display: inline-block;
            margin-right: 1rem;
            color: var(--text-secondary);
            font-size: 1.5rem;
            transition: color 0.2s;
        }}

        .social-links a:hover {{
            color: var(--text-primary);
        }}
    </style>

    <!-- Banner -->
    <div class="profile-banner" style="{'background-image: url(' + profile_user.banner_image + ');' if profile_user.banner_image else ''}">
    </div>

    <!-- Profile Header -->
    <div class="gh-page gh-profile-page container">
        <div class="profile-header">
            <div class="row">
                <div class="col-md-8">
                    <img
                        src="{get_avatar_url(profile_user, 200)}"
                        alt="{profile_user.displayName or profile_user.username}"
                        class="profile-avatar"
                        onerror="this.src='/static/images/default-avatar.png'"
                    >
                    <h1 class="mt-3">{profile_user.displayName or profile_user.username}</h1>
                    {f'<p class="text-muted">@{profile_user.handle}</p>' if profile_user.handle else ''}
                    {f'<p class="lead mt-2">{profile_user.headline}</p>' if profile_user.headline else ''}

                    {f'''<div class="social-links mt-3">
                        {''.join([f'<a href="{link.get("url")}" target="_blank" title="{link.get("platform")}"><i class="fab fa-{link.get("icon", "link")}"></i></a>' for link in social_links])}
                    </div>''' if social_links else ''}
                </div>
                <div class="col-md-4 text-end mt-5">
                    {'<a href="/profile/edit/" class="btn btn-primary"><i class="fas fa-edit me-2"></i>Edit Profile</a>' if is_own_profile else ''}
                </div>
            </div>

            <!-- Stats -->
            <div class="profile-stats mt-4">
                <div class="stat-card">
                    <span class="stat-value">{projects_count}</span>
                    <span class="stat-label">Initiated</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{len(project_memberships)}</span>
                    <span class="stat-label">Layers</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{workgroups_count}</span>
                    <span class="stat-label">Coordinating</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{memberships_count}</span>
                    <span class="stat-label">Workgroups</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{chair_count}</span>
                    <span class="stat-label">Chair</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{submissions_count}</span>
                    <span class="stat-label">Submissions</span>
                </div>
                <div class="stat-card">
                    <span class="stat-value">{comments_count}</span>
                    <span class="stat-label">Comments</span>
                </div>
                {f'''<div class="stat-card">
                    <span class="stat-value">{referral_count}</span>
                    <span class="stat-label">Referrals</span>
                </div>''' if is_own_profile else ''}
            </div>

            {'''<!-- Badge wallet (private dashboard) -->
            <div class="card mt-4" id="badge-wallet-card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0"><i class="bi bi-wallet2 me-2"></i>Badge wallet</h5>
                    <span class="text-muted small" id="badge-wallet-address"></span>
                </div>
                <div class="card-body">
                    <p class="text-muted small">Bitcoin ordinals in your Gov Hub custodial badge wallet (Taproot). Image and HTML inscriptions are shown below.</p>
                    <div id="badge-wallet-grid" class="row g-3"></div>
                    <p id="badge-wallet-status" class="text-muted small mb-0 mt-2"></p>
                </div>
            </div>''' if is_own_profile else ''}
        </div>

        <!-- Content Tabs -->
        <div class="row mt-5">
            <div class="col-12">
                <ul class="nav nav-tabs" role="tablist">
                    <li class="nav-item">
                        <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#about-tab">About</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#activity-tab">Activity</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#projects-tab">Initiated</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#my-projects-tab" id="my-projects">My Projects</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#coordinating-tab">Coordinating</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#memberships-tab">Memberships</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#chair-tab">Chair</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#submissions-tab">Submissions</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" data-bs-toggle="tab" data-bs-target="#contributions-tab">Edits &amp; comments</button>
                    </li>
                </ul>

                <div class="tab-content mt-4">
                    <!-- About Tab -->
                    <div class="tab-pane fade show active" id="about-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Bio</h5>
                                {f'<p>{profile_user.bio}</p>' if profile_user.bio else '<p class="text-muted">No bio provided yet.</p>'}

                                <h5 class="card-title mt-4">Details</h5>
                                <p><strong>Member since:</strong> {profile_user.created_at.strftime('%B %Y') if profile_user.created_at else 'Unknown'}</p>
                                {email_details_html}
                                {f'<p class="mt-2 mb-0"><strong>Role:</strong> <span class="badge bg-{site_role_badge_class(profile_user.role)}">{site_role_label(profile_user.role)}</span></p>' if profile_user.role else ''}
                            </div>
                        </div>
                    </div>

                    <!-- Activity Tab -->
                    <div class="tab-pane fade" id="activity-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Recent Activity</h5>
                                <div class="list-group list-group-flush">
                                    {_format_activity_items(recent_projects, recent_submissions)}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Projects Tab -->
                    <div class="tab-pane fade" id="projects-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Initiated Projects</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'<a href="/layers/{p[1]}/" class="list-group-item list-group-item-action"><strong>{p[0]}</strong><br><small class="text-muted">Created {p[2]}</small></a>' for p in recent_projects]) if recent_projects else '<p class="text-muted">No projects yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- My Projects Tab -->
                    <div class="tab-pane fade" id="my-projects-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Layer Memberships</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'''<a href="/layers/{pm.layer.slug}/" class="list-group-item list-group-item-action">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>{pm.layer.name}</strong>
                                                <br><small class="text-muted">Role: {pm.role or "Member"} • Joined {pm.joined_at.strftime("%b %Y") if pm.joined_at else "Unknown"}</small>
                                                {f'<br><small class="text-success"><i class="fas fa-user-plus me-1"></i>Referred by {pm.referred_by.displayName or pm.referred_by.username}</small>' if pm.referred_by else ''}
                                            </div>
                                        </div>
                                    </a>''' for pm in project_memberships]) if project_memberships else '<p class="text-muted">Not a member of any projects yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Coordinating Tab -->
                    <div class="tab-pane fade" id="coordinating-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Coordinating Workgroups</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'<a href="/workgroups/{wg.slug}/" class="list-group-item list-group-item-action"><strong>{wg.name}</strong><br><small class="text-muted">Status: {wg.status}</small></a>' for wg in coordinated_workgroups]) if coordinated_workgroups else '<p class="text-muted">Not coordinating any workgroups yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Memberships Tab -->
                    <div class="tab-pane fade" id="memberships-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Workgroup Memberships</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'<a href="/workgroups/{m[1]}/" class="list-group-item list-group-item-action"><strong>{m[0]}</strong><br><small class="text-muted">Joined {m[2]}</small></a>' for m in memberships_q]) if memberships_q else '<p class="text-muted">Not a member of any workgroups yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Chair Tab -->
                    <div class="tab-pane fade" id="chair-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">Chair Positions</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'<a href="/workgroups/{c[1]}/" class="list-group-item list-group-item-action"><strong>{c[0]}</strong><br><small class="text-muted">{"Approved" if coerce_storage_bool(c[3]) else "Pending approval"} - Set {c[2]}</small></a>' for c in chairs_q]) if chairs_q else '<p class="text-muted">No chair positions yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Submissions Tab -->
                    <div class="tab-pane fade" id="submissions-tab">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">All Submissions</h5>
                                <div class="list-group list-group-flush">
                                    {''.join([f'<a href="{html_mod.escape(submission_profile_href(s))}" class="list-group-item list-group-item-action"><strong>{html_mod.escape(submission_display_label(s))}</strong><br><small class="text-muted">{html_mod.escape((s.status or "draft").title())} - Submitted {s.submitted_at.strftime("%Y-%m-%d") if s.submitted_at else "Unknown"}</small></a>' for s in all_submissions_q]) if all_submissions_q else '<p class="text-muted">No submissions yet.</p>'}
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Edits & comments -->
                    <div class="tab-pane fade" id="contributions-tab">
                        <div class="card">
                            <div class="card-body">
                                {_format_profile_contributions(dp_proposals, recent_comments)}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    (function() {{
        var hash = window.location.hash;
        if (hash === '#my-projects') {{
            var tab = document.querySelector('[data-bs-target="#my-projects-tab"]');
            if (tab) bootstrap.Tab.getOrCreateInstance(tab).show();
        }}
    }})();
    {'' if not is_own_profile else '''
    async function loadBadgeWallet() {{
        const grid = document.getElementById('badge-wallet-grid');
        const status = document.getElementById('badge-wallet-status');
        const addrEl = document.getElementById('badge-wallet-address');
        if (!grid) return;
        try {{
            const r = await fetch('/api/user/badge-wallet/', {{ credentials: 'include' }});
            const d = await r.json();
            if (addrEl) {{
                addrEl.textContent = d.badge_wallet ? (d.badge_wallet.slice(0, 8) + '…' + d.badge_wallet.slice(-6)) : 'Not provisioned yet';
            }}
            if (!r.ok) {{
                if (status) status.textContent = d.error || 'Could not load badge wallet';
                return;
            }}
            if (d.error && !d.inscriptions.length) {{
                if (status) status.textContent = d.error;
                return;
            }}
            grid.innerHTML = '';
            (d.inscriptions || []).forEach(function(item) {{
                const col = document.createElement('div');
                col.className = 'col-md-4 col-sm-6';
                let inner = '<div class="card h-100"><div class="card-body p-2">';
                if (item.display === 'image') {{
                    inner += '<img src="' + item.content_url + '" class="img-fluid rounded" alt="Ordinal" loading="lazy">';
                }} else if (item.display === 'html') {{
                    inner += '<iframe src="' + item.content_url + '" class="w-100 rounded" style="height:180px;border:0;" sandbox="allow-scripts" title="Ordinal HTML"></iframe>';
                }} else {{
                    inner += '<p class="small text-muted mb-0">' + (item.content_type || 'Inscription') + '</p>';
                }}
                inner += '<p class="small mt-2 mb-0"><a href="https://ordinals.com/inscription/' + item.inscription_id + '" target="_blank" rel="noopener">#' + (item.inscription_number || item.inscription_id.slice(0, 12)) + '</a></p></div></div>';
                col.innerHTML = inner;
                grid.appendChild(col);
            }});
            if (status) {{
                status.textContent = d.count ? (d.count + ' inscription(s)') : 'No ordinals in this badge wallet yet.';
            }}
        }} catch (e) {{
            if (status) status.textContent = 'Could not load badge wallet';
        }}
    }}
    document.addEventListener('DOMContentLoaded', loadBadgeWallet);
    '''}
    </script>
    """

    return render_page(f"{profile_user.displayName or profile_user.username} - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/profile/edit/')
@require_auth
def profile_edit():
    """Profile edit page"""
    render_page, generate_user_menu = _get_imports()
    current_user_data = get_current_user()
    if not current_user_data:
        return redirect('/login')

    user = User.query.get(current_user_data['id'])
    if not user:
        return redirect('/')

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    social_links = []
    if user.social_links:
        try:
            social_links = json.loads(user.social_links)
        except Exception:
            social_links = []

    linked_accounts = {acc.provider: acc for acc in UserLinkedAccount.query.filter_by(user_id=user.id).all()}
    oauth_providers = [
        ('google', 'google', 'Google'),
        ('github', 'github', 'GitHub'),
        ('twitter', 'x-twitter', 'X (Twitter)'),
        ('discord', 'discord', 'Discord'),
    ]
    connected_html = ''
    for provider, icon, label in oauth_providers:
        acc = linked_accounts.get(provider)
        if acc:
            connected_html += f'''
            <div class="d-flex align-items-center justify-content-between p-2 rounded mb-2" style="background: var(--bs-secondary-bg);">
                <div class="d-flex align-items-center">
                    <i class="fab fa-{icon} fa-2x me-3" style="width:32px;text-align:center;"></i>
                    <div>
                        <strong>{label}</strong>
                        <br><small class="text-muted">{acc.display_name or acc.provider_user_id}</small>
                    </div>
                </div>
                <form method="POST" action="/profile/connect/{provider}/disconnect/" class="d-inline" onsubmit="return confirm('Disconnect {label}?');">
                    <button type="submit" class="btn btn-outline-danger btn-sm">Disconnect</button>
                </form>
            </div>'''
        else:
            connected_html += f'''
            <div class="d-flex align-items-center justify-content-between p-2 rounded mb-2" style="background: var(--bs-secondary-bg);">
                <div class="d-flex align-items-center">
                    <i class="fab fa-{icon} fa-2x me-3" style="width:32px;text-align:center;"></i>
                    <strong>{label}</strong>
                </div>
                <a href="/profile/connect/{provider}/" class="btn btn-primary btn-sm">Connect</a>
            </div>'''

    platforms = [
        {'name': 'Website', 'icon': 'globe', 'placeholder': 'https://yourwebsite.com'},
    ]

    content = f"""
    {gh_page_open()}
    {gh_page_header('Edit Profile', 'Update your profile information', 'fa-user-edit')}
    <div class="row">
        <div class="col-lg-8 mx-auto">

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-image"></i></div>
                        <h5 class="living-module-title">Profile images</h5>
                    </div>
                    <div class="living-module-body">
                        <div class="row">
                            <div class="col-md-6">
                                <label class="form-label">Profile Picture</label>
                                <div class="text-center mb-3">
                                    <img
                                        id="profile-image-preview"
                                        src="{get_avatar_url(user, 150)}"
                                        class="img-thumbnail rounded-circle"
                                        style="width: 150px; height: 150px; object-fit: cover;"
                                        onerror="this.src='/static/images/default-avatar.png'"
                                    >
                                </div>
                                <input
                                    type="file"
                                    class="form-control"
                                    id="profile-image-file"
                                    accept="image/*"
                                    onchange="previewImage(this, 'profile-image-preview')"
                                >
                                <div class="form-text">Max 600×600px, 5MB. PNG, JPG, GIF, WebP, SVG</div>
                                <button class="btn btn-primary btn-sm mt-2 w-100" onclick="uploadProfileImage()">
                                    <i class="fas fa-upload me-2"></i>Upload Profile Picture
                                </button>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Banner Image</label>
                                <div class="mb-3" style="height: 150px; overflow: hidden; border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                                    <img
                                        id="banner-image-preview"
                                        src="{user.banner_image or ''}"
                                        class="w-100"
                                        style="height: 150px; object-fit: cover; display: {'block' if user.banner_image else 'none'};"
                                    >
                                </div>
                                <input
                                    type="file"
                                    class="form-control"
                                    id="banner-image-file"
                                    accept="image/*"
                                    onchange="previewBannerImage(this)"
                                >
                                <div class="form-text">Max 5MB. PNG, JPG, GIF, WebP, SVG. Recommended: wide/landscape format.</div>
                                <button class="btn btn-primary btn-sm mt-2 w-100" onclick="uploadBannerImage()">
                                    <i class="fas fa-upload me-2"></i>Upload Banner
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-id-card"></i></div>
                        <h5 class="living-module-title">Basic information</h5>
                    </div>
                    <div class="living-module-body">
                        <form id="profile-form">
                            <div class="mb-3">
                                <label for="headline" class="form-label">Headline</label>
                                <input
                                    type="text"
                                    class="form-control"
                                    id="headline"
                                    maxlength="200"
                                    placeholder="Your professional headline..."
                                    value="{user.headline or ''}"
                                >
                                <div class="form-text">A short description of what you do (max 200 characters)</div>
                            </div>

                            <div class="mb-3">
                                <label for="bio" class="form-label">Bio</label>
                                <textarea
                                    class="form-control"
                                    id="bio"
                                    rows="4"
                                    placeholder="Tell us about yourself..."
                                >{user.bio or ''}</textarea>
                                <div class="form-text">A longer description of your background and interests</div>
                            </div>
                        </form>
                    </div>
                </div>

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-shield-halved"></i></div>
                        <h5 class="living-module-title">Security</h5>
                    </div>
                    <div class="living-module-body">
                        <p class="text-muted small mb-2">Two-factor authentication with an authenticator app and backup codes.</p>
                        <a href="/profile/security/" class="btn btn-outline-primary btn-sm"><i class="fas fa-lock me-1"></i>Manage two-factor auth</a>
                    </div>
                </div>

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-bell"></i></div>
                        <h5 class="living-module-title">Notifications</h5>
                    </div>
                    <div class="living-module-body">
                        <p class="text-muted small mb-2">In-app feed, per-draft subscriptions, and email channels (requires email opt-in).</p>
                        <a href="/notifications/" class="btn btn-outline-primary btn-sm"><i class="fas fa-bell me-1"></i>Open notifications hub</a>
                    </div>
                </div>

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-link"></i></div>
                        <h5 class="living-module-title">Connected accounts</h5>
                    </div>
                    <div class="living-module-body">
                        <p class="text-muted small mb-3">Connect your accounts to show them on your profile. Use 32×32 or larger icons.</p>
                        {connected_html}
                    </div>
                </div>

                <div class="living-module mb-4">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-share-alt"></i></div>
                        <h5 class="living-module-title">Social links</h5>
                    </div>
                    <div class="living-module-body">
                        <p class="text-muted small mb-3">Add links to your website or other profiles.</p>
                        <div id="social-links-container">
                            {_render_social_link_inputs(platforms, social_links)}
                        </div>
                    </div>
                </div>

                <div class="d-flex justify-content-between">
                    <a href="/profile/{user.username}/" class="btn btn-secondary">
                        <i class="fas fa-times me-2"></i>Cancel
                    </a>
                    <button class="btn btn-primary" onclick="saveProfile()">
                        <i class="fas fa-save me-2"></i>Save Changes
                    </button>
                </div>
            </div>
        </div>
    {gh_page_close()}

    <script>
    async function ghNotify(opts) {{
        if (window.GhDialog && typeof window.GhDialog.alert === 'function') {{
            await window.GhDialog.alert(opts);
            return;
        }}
        window.alert((opts.title ? opts.title + '\\n\\n' : '') + (opts.message || ''));
    }}

    function previewImage(input, previewId) {{
        if (input.files && input.files[0]) {{
            const reader = new FileReader();
            reader.onload = function(e) {{
                document.getElementById(previewId).src = e.target.result;
            }};
            reader.readAsDataURL(input.files[0]);
        }}
    }}

    function previewBannerImage(input) {{
        if (input.files && input.files[0]) {{
            const reader = new FileReader();
            const preview = document.getElementById('banner-image-preview');
            reader.onload = function(e) {{
                preview.src = e.target.result;
                preview.style.display = 'block';
            }};
            reader.readAsDataURL(input.files[0]);
        }}
    }}

    async function uploadProfileImage() {{
        const fileInput = document.getElementById('profile-image-file');
        if (!fileInput.files || !fileInput.files[0]) {{
            await ghNotify({{ title: 'No image selected', message: 'Please select an image first.', variant: 'warning' }});
            return;
        }}

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('type', 'profile');

        try {{
            const response = await fetch('/api/user/upload-image', {{
                method: 'POST',
                credentials: 'include',
                body: formData
            }});

            const data = await response.json();
            if (response.ok) {{
                await ghNotify({{ title: 'Profile picture updated', message: 'Your profile picture was uploaded successfully.', variant: 'success' }});
                location.reload();
            }} else {{
                await ghNotify({{ title: 'Upload failed', message: data.error || 'Failed to upload image', variant: 'danger' }});
            }}
        }} catch (error) {{
            console.error('Error uploading image:', error);
            await ghNotify({{ title: 'Upload failed', message: 'Failed to upload image.', variant: 'danger' }});
        }}
    }}

    async function uploadBannerImage() {{
        const fileInput = document.getElementById('banner-image-file');
        if (!fileInput.files || !fileInput.files[0]) {{
            await ghNotify({{ title: 'No image selected', message: 'Please select an image first.', variant: 'warning' }});
            return;
        }}

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('type', 'banner');

        try {{
            const response = await fetch('/api/user/upload-image', {{
                method: 'POST',
                credentials: 'include',
                body: formData
            }});

            const data = await response.json();
            if (response.ok) {{
                await ghNotify({{ title: 'Banner updated', message: 'Your banner image was uploaded successfully.', variant: 'success' }});
                location.reload();
            }} else {{
                await ghNotify({{ title: 'Upload failed', message: data.error || 'Failed to upload image', variant: 'danger' }});
            }}
        }} catch (error) {{
            console.error('Error uploading image:', error);
            await ghNotify({{ title: 'Upload failed', message: 'Failed to upload image.', variant: 'danger' }});
        }}
    }}

    async function saveProfile() {{
        const headline = document.getElementById('headline').value;
        const bio = document.getElementById('bio').value;

        // Collect social links
        const socialLinks = [];
        document.querySelectorAll('[data-social-platform]').forEach(input => {{
            const url = input.value.trim();
            if (url) {{
                socialLinks.push({{
                    platform: input.dataset.socialPlatform,
                    icon: input.dataset.socialIcon,
                    url: url
                }});
            }}
        }});

        try {{
            const response = await fetch('/api/user/profile/', {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    headline: headline,
                    bio: bio,
                    social_links: socialLinks
                }})
            }});

            const data = await response.json();
            if (response.ok) {{
                await ghNotify({{ title: 'Profile updated', message: 'Your profile was saved successfully.', variant: 'success' }});
                window.location.href = '/profile/{user.username}/';
            }} else {{
                await ghNotify({{ title: 'Update failed', message: data.error || 'Failed to update profile', variant: 'danger' }});
            }}
        }} catch (error) {{
            console.error('Error updating profile:', error);
            await ghNotify({{ title: 'Update failed', message: 'Failed to update profile.', variant: 'danger' }});
        }}
    }}
    </script>
    """

    return render_page("Edit Profile - MLGH", content, theme=current_theme, user_menu=user_menu)
