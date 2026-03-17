"""Layer page routes: /layers/<slug>/, quests, artifacts, create."""
import html as html_mod

from flask import Blueprint, session

from models import (
    Layer, User, Submission, Artifact, ArtifactRelation,
    Quest, QuestSubmission,
)
from services.identity import get_current_user, require_auth
from services.artifact import get_artifact_by_ref

bp = Blueprint('layers_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/layers/<layer_slug>/')
def layer_detail(layer_slug):
    """Layer detail page (formerly project detail)"""
    from routes.layer_detail_render import _render_project_detail
    from flask import current_app
    current_app.logger.info(f"[LAYER] layer_detail route hit: layer_slug={layer_slug!r}")
    return _render_project_detail(layer_slug)


@bp.route('/layers/<layer_slug>/about/')
def layer_about(layer_slug):
    """Layer about page: markdown content from layer.about_content."""
    from services.rendering import render_page, render_layer_standalone_page, generate_user_menu
    from services.ordinals import process_ordinal_markdown

    layer = Layer.query.filter_by(slug=layer_slug).first() or Layer.query.get(layer_slug)
    if not layer:
        return "Layer not found", 404

    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    raw = (layer.about_content or '').strip()
    html_content = process_ordinal_markdown(raw) if raw else '<p class="text-muted">No about content yet.</p>'

    content = f'''
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/layers/{layer_slug}/">{html_mod.escape(layer.name or layer_slug)}</a></li>
                <li class="breadcrumb-item active">About</li>
            </ol>
        </nav>
        <h1 class="mb-4">About {html_mod.escape(layer.name or layer_slug)}</h1>
        <div class="about-content" style="max-width: 720px;">
            {html_content}
        </div>
    </div>
    '''
    title = f"About {layer.name or layer_slug} - MLGH"
    return render_page(title, content, theme=current_theme, user_menu=user_menu)


@bp.route('/layers/<layer_slug>/waitlist/<waitlist_id>/')
def layer_detail_waitlist(layer_slug, waitlist_id):
    """Layer detail with specific waitlist tab (for referral links)"""
    from routes.layer_detail_render import _render_project_detail
    return _render_project_detail(layer_slug, waitlist_id=waitlist_id)


@bp.route('/layers/<layer_slug>/quests/<quest_id>/')
def layer_quest_detail(layer_slug, quest_id):
    """Quest detail page (GOV-HUB-3 Phase 2.1): show quest info, submissions, and submit form."""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_user = get_current_user()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    layer = Layer.query.filter_by(slug=layer_slug).first() or Layer.query.get(layer_slug)
    if not layer:
        return "Layer not found", 404
    quest = Quest.query.filter_by(id=quest_id, layer_id=layer.id).first()
    if not quest:
        return "Quest not found", 404
    submissions = QuestSubmission.query.filter_by(quest_id=quest_id).order_by(QuestSubmission.created_at.desc()).all()
    layer_name_esc = html_mod.escape(layer.name or layer_slug)
    title_esc = html_mod.escape(quest.title or 'Untitled Quest')
    desc_esc = html_mod.escape(quest.description or '') if quest.description else ''
    criteria_esc = html_mod.escape(quest.acceptance_criteria or '') if quest.acceptance_criteria else ''
    status_badge = 'success' if quest.status == 'open' else 'secondary' if quest.status == 'closed' else 'warning'
    created_str = quest.created_at.strftime('%Y-%m-%d %H:%M') if quest.created_at else '—'
    creator_name = None
    if quest.creator_user_id:
        u = User.query.get(quest.creator_user_id)
        creator_name = (u.displayName or u.username or u.oauthName) if u else None
    creator_block = f'<li>Created by: {html_mod.escape(creator_name)}</li>' if creator_name else ''
    sub_rows = []
    for qs in submissions:
        art = Artifact.query.get(qs.artifact_id) if qs.artifact_id else None
        sub = Submission.query.filter_by(artifact_id=qs.artifact_id).first() if qs.artifact_id else None
        submitter_name = None
        if qs.submitter_user_id:
            su = User.query.get(qs.submitter_user_id)
            submitter_name = (su.displayName or su.username or su.oauthName) if su else None
        art_title = (art.title or art.id[:8]) if art else (qs.artifact_id[:8] + '...' if qs.artifact_id else '—')
        art_link = f'<a href="/layers/{layer_slug}/artifacts/{qs.artifact_id}/">{html_mod.escape(art_title[:50])}</a>' if qs.artifact_id and art else (qs.artifact_id[:12] + '...' if qs.artifact_id else '—')
        draft_link = f' <a href="/submit/status/{sub.id}/" class="badge bg-outline-primary text-decoration-none">Draft</a>' if sub else ''
        status_cls = 'success' if qs.status == 'approved' else 'warning' if qs.status == 'pending_review' else 'secondary'
        sub_rows.append(f'<tr><td>{art_link}{draft_link}</td><td>{html_mod.escape(submitter_name or "—")}</td><td><span class="badge bg-{status_cls}">{qs.status}</span></td><td>{qs.created_at.strftime("%Y-%m-%d") if qs.created_at else "—"}</td></tr>')
    submissions_html = ''.join(sub_rows) if sub_rows else '<tr><td colspan="4" class="text-muted">No submissions yet.</td></tr>'
    back_link = f'<a href="/layers/{layer_slug}/#opportunities" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Back to Opportunities</a>'
    submit_form_html = ''
    if quest.status == 'open' and current_user:
        sub_options = []
        for s in Submission.query.filter(Submission.layer_id == layer.id, Submission.artifact_id.isnot(None)).order_by(Submission.submitted_at.desc()).limit(50):
            lbl = (s.ml_number or s.draft_name or s.title or s.id)[:60]
            sub_options.append(f'<option value="{html_mod.escape(s.artifact_id)}">{html_mod.escape(lbl)}</option>')
        opts = ''.join(sub_options) if sub_options else '<option value="">No drafts in this layer</option>'
        submit_form_html = f'''
            <div class="card mt-3">
                <div class="card-body">
                    <h6 class="card-title"><i class="fas fa-paper-plane me-1"></i>Submit for this quest</h6>
                    <p class="text-muted small mb-2">Link one of your drafts (artifacts) to this quest.</p>
                    <div class="mb-2">
                        <label for="quest-submit-artifact" class="form-label">Draft / Artifact</label>
                        <select class="form-select" id="quest-submit-artifact"><option value="">Select a draft...</option>{opts}</select>
                    </div>
                    <div id="quest-submit-alert" class="alert d-none"></div>
                    <button type="button" class="btn btn-primary btn-sm" id="quest-submit-btn"><i class="fas fa-check me-1"></i>Submit</button>
                </div>
            </div>
            <script>
            (function() {{
                document.getElementById('quest-submit-btn').addEventListener('click', async function() {{
                    const btn = this; const aid = document.getElementById('quest-submit-artifact').value;
                    const alert = document.getElementById('quest-submit-alert');
                    alert.classList.add('d-none');
                    if (!aid) {{ alert.textContent = 'Select a draft.'; alert.className = 'alert alert-warning'; alert.classList.remove('d-none'); return; }}
                    btn.disabled = true;
                    try {{
                        const r = await fetch('/api/quests/{quest_id}/submit/', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ artifact_id: aid }}), credentials: 'same-origin' }});
                        const d = await r.json().catch(() => ({{}}));
                        if (r.ok) {{ location.reload(); }} else {{ alert.textContent = d.error || 'Failed'; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                    }} catch (e) {{ alert.textContent = e.message; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                    btn.disabled = false;
                }});
            }})();
            </script>
        '''
    elif quest.status == 'open':
        submit_form_html = '<p class="text-muted small mt-3"><a href="/login/">Sign in</a> to submit for this quest.</p>'
    content = f'''
<div class="container mt-4">
    <nav aria-label="breadcrumb"><ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="/layers/">Layers</a></li>
        <li class="breadcrumb-item"><a href="/layers/{layer_slug}/">{layer_name_esc}</a></li>
        <li class="breadcrumb-item"><a href="/layers/{layer_slug}/#opportunities">Opportunities</a></li>
        <li class="breadcrumb-item active">{title_esc}</li>
    </ol></nav>
    <div class="d-flex justify-content-between align-items-start mb-3">
        <h1>{title_esc}</h1>
        {back_link}
    </div>
    <p class="text-muted"><span class="badge bg-secondary">{quest.quest_type}</span> <span class="badge bg-{status_badge}">{quest.status}</span> <span class="badge bg-secondary">{quest.difficulty}</span></p>
    {f'<p class="lead">{desc_esc}</p>' if desc_esc else ''}
    <div class="row mt-4">
        <div class="col-lg-8">
            <div class="mb-4">
                <h5>Details</h5>
                <ul class="list-unstyled">
                    <li>Created: {created_str}</li>
                    {creator_block}
                    {f'<li>Acceptance criteria: {criteria_esc}</li>' if criteria_esc else ''}
                </ul>
            </div>
            <div class="mb-4">
                <h5>Submissions</h5>
                <table class="table table-sm">
                    <thead><tr><th>Artifact / Draft</th><th>Submitter</th><th>Status</th><th>Date</th></tr></thead>
                    <tbody>{submissions_html}</tbody>
                </table>
            </div>
            {submit_form_html}
        </div>
        <div class="col-lg-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title">Quick links</h6>
                    <a href="/layers/{layer_slug}/" class="d-block mb-2"><i class="fas fa-layer-group me-1"></i>Layer</a>
                    <a href="/layers/{layer_slug}/#opportunities" class="d-block"><i class="fas fa-tasks me-1"></i>All opportunities</a>
                </div>
            </div>
        </div>
    </div>
</div>
'''
    return render_page(f"{title_esc} - Quest", content, theme=current_theme, user_menu=user_menu)


@bp.route('/layers/<layer_slug>/artifacts/<artifact_id>/')
def artifact_detail(layer_slug, artifact_id):
    """Artifact detail page (GOV-HUB-3 Phase 1.4): provenance, relations, link to submission.
    artifact_id can be UUID, public_id, or short public_ref (e.g. ed3f6ea9io)."""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    layer = Layer.query.filter_by(slug=layer_slug).first()
    if not layer:
        layer = Layer.query.get(layer_slug)
    if not layer:
        return "Layer not found", 404
    artifact = get_artifact_by_ref(layer.id, artifact_id)
    if not artifact:
        return "Artifact not found", 404
    artifact_id = artifact.id  # canonical id for queries/URLs
    outgoing = ArtifactRelation.query.filter(
        ArtifactRelation.from_object_type == 'artifact',
        ArtifactRelation.from_object_id == artifact_id,
    ).order_by(ArtifactRelation.created_at.desc()).all()
    incoming = ArtifactRelation.query.filter(
        ArtifactRelation.to_object_type == 'artifact',
        ArtifactRelation.to_object_id == artifact_id,
    ).order_by(ArtifactRelation.created_at.desc()).all()
    supports = [r for r in incoming if r.relation_type == 'supports']
    opposes = [r for r in incoming if r.relation_type == 'opposes']
    other_incoming = [r for r in incoming if r.relation_type not in ('supports', 'opposes')]
    submission = Submission.query.filter_by(artifact_id=artifact_id).first()
    current_user = get_current_user()
    def _support_oppose_row(r):
        a = Artifact.query.get(r.from_object_id)
        t = (a.title or (a.public_ref if a else None) or (a.id[:8] if a else r.from_object_id[:8]))
        t_esc = html_mod.escape(str(t)[:60])
        ref = (a.public_ref or a.id) if a else r.from_object_id
        return f'<li class="list-group-item"><a href="/layers/{layer_slug}/artifacts/{ref}/" class="text-primary">{t_esc}</a> <code class="ms-1 small text-muted">{ref}</code></li>'
    supports_html = ''.join(_support_oppose_row(r) for r in supports) if supports else '<li class="list-group-item text-muted">No support yet</li>'
    opposes_html = ''.join(_support_oppose_row(r) for r in opposes) if opposes else '<li class="list-group-item text-muted">No opposition yet</li>'
    creator_name = None
    if artifact.creator_user_id:
        u = User.query.get(artifact.creator_user_id)
        creator_name = (u.displayName or u.username or u.oauthName) if u else None
    title_esc = html_mod.escape(artifact.title or 'Untitled')
    summary_esc = html_mod.escape(artifact.summary or '') if artifact.summary else ''
    layer_name_esc = html_mod.escape(layer.name or layer_slug)
    rel_types = {'builds_on': 'Builds on', 'references': 'References', 'supports': 'Supports', 'opposes': 'Opposes', 'amends': 'Amends', 'implements': 'Implements', 'awarded_for': 'Awarded for'}
    def rel_row(r, direction):
        lbl = rel_types.get(r.relation_type, r.relation_type)
        if direction == 'outgoing' and r.to_object_type == 'artifact':
            a = Artifact.query.get(r.to_object_id)
            ref = (a.public_ref or a.id) if a else r.to_object_id
            title = (a.title or a.public_ref or ref)[:40] if a else r.to_object_id[:8] + '...'
            return f'<li class="list-group-item d-flex justify-content-between align-items-center"><span>{lbl}</span><a href="/layers/{layer_slug}/artifacts/{ref}/" class="text-primary">{html_mod.escape(str(title))}</a> <code class="ms-1 small text-muted">{ref}</code></li>'
        if direction == 'incoming' and r.from_object_type == 'artifact':
            a = Artifact.query.get(r.from_object_id)
            ref = (a.public_ref or a.id) if a else r.from_object_id
            title = (a.title or a.public_ref or ref)[:40] if a else r.from_object_id[:8] + '...'
            return f'<li class="list-group-item d-flex justify-content-between align-items-center"><span>{lbl}</span><a href="/layers/{layer_slug}/artifacts/{ref}/" class="text-primary">{html_mod.escape(str(title))}</a> <code class="ms-1 small text-muted">{ref}</code></li>'
        target = f"{r.to_object_type}:{r.to_object_id}" if direction == 'outgoing' else f"{r.from_object_type}:{r.from_object_id}"
        return f'<li class="list-group-item"><span>{lbl}</span> <code>{html_mod.escape(target[:40])}</code></li>'
    outgoing_html = ''.join(rel_row(r, 'outgoing') for r in outgoing) if outgoing else '<li class="list-group-item text-muted">No outgoing relations</li>'
    other_incoming_html = ''.join(rel_row(r, 'incoming') for r in other_incoming) if other_incoming else '<li class="list-group-item text-muted">None</li>'
    submission_link = f'<a href="/submit/status/{submission.id}/" class="btn btn-outline-primary btn-sm">View Submission</a>' if submission else ''
    summary_block = f'<p class="lead">{summary_esc}</p>' if summary_esc else ''
    creator_block = f'<li>Creator: {html_mod.escape(creator_name)}</li>' if creator_name else ''
    status_badge_map = {'draft': 'secondary', 'submitted': 'info', 'under_review': 'warning', 'reviewed': 'success',
        'open_for_comment': 'info', 'vote_scheduled': 'warning', 'vote_open': 'primary', 'adopted': 'success',
        'approved': 'success', 'rejected': 'danger', 'implemented': 'success', 'superseded': 'secondary', 'archived': 'secondary'}
    status_badge = status_badge_map.get((artifact.status or '').lower(), 'secondary')
    created_str = artifact.created_at.strftime('%Y-%m-%d %H:%M') if artifact.created_at else '—'
    if current_user:
        add_support_oppose_forms = f'''
                <div class="card mt-3">
                    <div class="card-body">
                        <h6 class="card-title">Add support or opposition</h6>
                        <div class="d-flex gap-2 flex-wrap">
                            <button type="button" class="btn btn-outline-success btn-sm" data-bs-toggle="modal" data-bs-target="#addSupportModal"><i class="fas fa-thumbs-up me-1"></i>Add support</button>
                            <button type="button" class="btn btn-outline-danger btn-sm" data-bs-toggle="modal" data-bs-target="#addOppositionModal"><i class="fas fa-thumbs-down me-1"></i>Add opposition</button>
                        </div>
                    </div>
                </div>
                <div class="modal fade" id="addSupportModal" tabindex="-1">
                    <div class="modal-dialog"><div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Add support</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-2"><label class="form-label">Title</label><input type="text" class="form-control" id="support-title" placeholder="Support for this proposal"></div>
                            <div class="mb-2"><label class="form-label">Summary (optional)</label><textarea class="form-control" id="support-summary" rows="2"></textarea></div>
                            <div id="support-alert" class="alert d-none"></div>
                        </div>
                        <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-success" id="support-submit-btn">Add support</button></div>
                    </div></div>
                </div>
                <div class="modal fade" id="addOppositionModal" tabindex="-1">
                    <div class="modal-dialog"><div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Add opposition</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-2"><label class="form-label">Title</label><input type="text" class="form-control" id="opposition-title" placeholder="Opposition to this proposal"></div>
                            <div class="mb-2"><label class="form-label">Summary (optional)</label><textarea class="form-control" id="opposition-summary" rows="2"></textarea></div>
                            <div id="opposition-alert" class="alert d-none"></div>
                        </div>
                        <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-danger" id="opposition-submit-btn">Add opposition</button></div>
                    </div></div>
                </div>
                <script>
                (function() {{
                    const aid = '{artifact_id}';
                    document.getElementById('support-submit-btn').addEventListener('click', async function() {{
                        const btn = this; btn.disabled = true;
                        const alert = document.getElementById('support-alert'); alert.classList.add('d-none');
                        try {{
                            const r = await fetch('/api/artifacts/' + aid + '/support/', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ title: document.getElementById('support-title').value, summary: document.getElementById('support-summary').value }}), credentials: 'same-origin' }});
                            const d = await r.json();
                            if (r.ok) {{ location.reload(); }} else {{ alert.textContent = d.error || 'Failed'; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                        }} catch (e) {{ alert.textContent = e.message; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                        btn.disabled = false;
                    }});
                    document.getElementById('opposition-submit-btn').addEventListener('click', async function() {{
                        const btn = this; btn.disabled = true;
                        const alert = document.getElementById('opposition-alert'); alert.classList.add('d-none');
                        try {{
                            const r = await fetch('/api/artifacts/' + aid + '/opposition/', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ title: document.getElementById('opposition-title').value, summary: document.getElementById('opposition-summary').value }}), credentials: 'same-origin' }});
                            const d = await r.json();
                            if (r.ok) {{ location.reload(); }} else {{ alert.textContent = d.error || 'Failed'; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                        }} catch (e) {{ alert.textContent = e.message; alert.className = 'alert alert-danger'; alert.classList.remove('d-none'); }}
                        btn.disabled = false;
                    }});
                }})();
                </script>
'''
    else:
        add_support_oppose_forms = '<p class="text-muted small mt-2"><a href="/login/">Sign in</a> to add support or opposition.</p>'
    public_ref_esc = html_mod.escape(artifact.public_ref or '')
    public_ref_block = f'<code class="text-muted ms-2" title="Public reference (artifact_specification)">{public_ref_esc}</code>' if public_ref_esc else ''
    content = f'''
<div class="container mt-4">
    <nav aria-label="breadcrumb"><ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="/layers/">Layers</a></li>
        <li class="breadcrumb-item"><a href="/layers/{layer_slug}/">{layer_name_esc}</a></li>
        <li class="breadcrumb-item active">Artifact</li>
    </ol></nav>
    <div class="row">
        <div class="col-lg-8">
            <h1>{title_esc}{public_ref_block}</h1>
            <p class="text-muted"><span class="badge bg-secondary">{artifact.artifact_type}</span> <span class="badge bg-{status_badge}">{artifact.status or "draft"}</span></p>
            {summary_block}
            <div class="mb-4">
                <h5>Provenance</h5>
                <ul class="list-unstyled">
                    <li>Created: {created_str}</li>
                    {creator_block}
                </ul>
            </div>
            <div class="mb-4">
                <h5>Support &amp; Opposition</h5>
                <p class="text-muted small">Structured support and opposition artifacts (GOV-HUB-3)</p>
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="text-success">Support ({len(supports)})</h6>
                        <ul class="list-group list-group-flush">{supports_html}</ul>
                    </div>
                    <div class="col-md-6">
                        <h6 class="text-danger">Opposition ({len(opposes)})</h6>
                        <ul class="list-group list-group-flush">{opposes_html}</ul>
                    </div>
                </div>
                {add_support_oppose_forms}
            </div>
            <div class="mb-4">
                <h5>Other Relations</h5>
                <div class="row">
                    <div class="col-md-6">
                        <h6>Outgoing</h6>
                        <ul class="list-group list-group-flush">{outgoing_html}</ul>
                    </div>
                    <div class="col-md-6">
                        <h6>Incoming</h6>
                        <ul class="list-group list-group-flush">{other_incoming_html}</ul>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-lg-4">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title">Links</h6>
                    {submission_link}
                    <a href="/api/artifacts/{artifact_id}/relations/" class="btn btn-outline-secondary btn-sm mt-2">API: Relations</a>
                    <a href="/api/artifacts/{artifact_id}/lineage/" class="btn btn-outline-secondary btn-sm mt-2">API: Lineage</a>
                    <button type="button" class="btn btn-outline-primary btn-sm mt-2 d-block" data-bs-toggle="modal" data-bs-target="#lineageModal"><i class="fas fa-project-diagram me-1"></i>Lineage Graph</button>
                </div>
            </div>
        </div>
    </div>
</div>
<div class="modal fade" id="lineageModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header"><h5 class="modal-title">Artifact Lineage</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
            <div class="modal-body">
                <div id="lineage-graph" style="min-height:320px;"></div>
                <p class="text-muted small mt-2">Ancestors (incoming) and descendants (outgoing) from artifact relations.</p>
            </div>
        </div>
    </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<script>
(function() {{
    const aid = '{artifact_id}';
    const layerSlug = '{layer_slug}';
    document.getElementById('lineageModal').addEventListener('shown.bs.modal', async function() {{
        const el = document.getElementById('lineage-graph');
        if (el.dataset.loaded) return;
        el.innerHTML = '<div class="text-center py-5"><span class="spinner-border"></span></div>';
        try {{
            const r = await fetch('/api/artifacts/' + aid + '/lineage/?depth=3', {{credentials:'same-origin'}});
            const d = await r.json();
            if (!r.ok) {{ el.innerHTML = '<p class="text-danger">Failed to load lineage</p>'; return; }}
            el.innerHTML = '';
            el.dataset.loaded = '1';
            const nodes = [{{ id: d.artifact.id, public_ref: d.artifact.public_ref, title: d.artifact.title || 'This artifact', type: 'center' }}];
            const links = [];
            const idToNode = {{}};
            idToNode[d.artifact.id] = nodes[0];
            d.ancestors.forEach(a => {{
                if (!idToNode[a.id]) {{ idToNode[a.id] = {{ id: a.id, public_ref: a.public_ref, title: a.title, type: 'ancestor' }}; nodes.push(idToNode[a.id]); }}
                links.push({{ source: a.id, target: d.artifact.id, relation_type: a.relation_type }});
            }});
            d.descendants.forEach(a => {{
                if (!idToNode[a.id]) {{ idToNode[a.id] = {{ id: a.id, public_ref: a.public_ref, title: a.title, type: 'descendant' }}; nodes.push(idToNode[a.id]); }}
                links.push({{ source: d.artifact.id, target: a.id, relation_type: a.relation_type }});
            }});
            if (nodes.length <= 1) {{ el.innerHTML = '<p class="text-muted">No lineage relations yet.</p>'; return; }}
            const w = el.offsetWidth || 600, h = 320;
            const svg = d3.select(el).append('svg').attr('width', w).attr('height', h);
            const g = svg.append('g');
            const simulation = d3.forceSimulation(nodes).force('link', d3.forceLink(links).id(x=>x.id).distance(80))
                .force('charge', d3.forceManyBody().strength(-200)).force('center', d3.forceCenter(w/2, h/2));
            const link = g.append('g').selectAll('line').data(links).join('line').attr('stroke', '#666').attr('stroke-opacity', 0.5);
            const node = g.append('g').selectAll('g').data(nodes).join('g').attr('cursor','pointer').call(d3.drag().on('start',(e,d)=>{{e.sourceEvent.stopPropagation(); simulation.alpha(0.3).restart(); d.fx=d.x; d.fy=d.y;}}).on('drag',(e,d)=>{{d.fx=e.x; d.fy=e.y;}}).on('end',(e,d)=>{{d.fx=null; d.fy=null;}}));
            node.append('circle').attr('r', d=>d.type==='center'?10:6).attr('fill', d=>d.type==='center'?'#0d6efd':d.type==='ancestor'?'#6c757d':'#198754');
            node.append('text').attr('dx', 12).attr('dy', 4).text(d=>(d.title||d.public_ref||d.id).slice(0,25)).attr('font-size', 10).attr('fill', '#ccc');
            node.on('click', (ev,d)=>{{ window.location='/layers/'+layerSlug+'/artifacts/'+(d.public_ref||d.id)+'/'; }});
            simulation.on('tick', ()=>{{ link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y); node.attr('transform', d=>'translate('+d.x+','+d.y+')'); }});
        }} catch (e) {{ el.innerHTML = '<p class="text-danger">' + (e.message||'Error') + '</p>'; }}
    }});
}})();
</script>
'''
    return render_page(f"{title_esc} - Artifact", content, theme=current_theme, user_menu=user_menu)


@bp.route('/layers/create/')
@require_auth
def create_project_page():
    """Create project form page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = """
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8 offset-md-2">
                <h1 class="mb-4">Create New Layer</h1>

                <div id="alert-container"></div>

                <form id="createProjectForm">
                    <div class="mb-3">
                        <label for="name" class="form-label">Layer Name *</label>
                        <input type="text" class="form-control" id="name" required>
                        <div class="form-text">A clear, descriptive name for your layer</div>
                    </div>

                    <div class="mb-3">
                        <label for="mission" class="form-label">Mission</label>
                        <textarea class="form-control" id="mission" rows="3" style="white-space: pre-wrap;"></textarea>
                        <div class="form-text">Optional: The layer's core purpose and values (line breaks preserved)</div>
                    </div>

                    <div class="mb-3">
                        <label for="description" class="form-label">Description *</label>
                        <textarea class="form-control" id="description" rows="4" required style="white-space: pre-wrap;"></textarea>
                        <div class="form-text">Explain what this layer is about and its goals (line breaks preserved)</div>
                    </div>

                    <div class="mb-3">
                        <label for="repo_url" class="form-label">Repository URL</label>
                        <input type="url" class="form-control" id="repo_url" placeholder="https://github.com/...">
                    </div>

                    <div class="mb-3">
                        <label for="website_url" class="form-label">Website URL</label>
                        <input type="url" class="form-control" id="website_url" placeholder="https://...">
                    </div>

                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>Note:</strong> New layers start with "proposed" status and require admin approval before becoming active.
                        You will be the layer owner; you can add more admins after creation via <strong>Edit</strong> on the layer page.
                    </div>

                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary" id="submitBtn">
                            <i class="fas fa-plus me-2"></i>Create Layer
                        </button>
                        <a href="/layers/" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
    document.getElementById('createProjectForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';

        const formData = {
            name: document.getElementById('name').value,
            mission: document.getElementById('mission').value,
            description: document.getElementById('description').value,
            repo_url: document.getElementById('repo_url').value,
            website_url: document.getElementById('website_url').value
        };

        try {
            const response = await fetch('/api/layers/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok) {
                document.getElementById('alert-container').innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        Layer created successfully! Redirecting...
                    </div>
                `;
                const slug = data.layer?.slug || data.project?.slug;
                if (slug) {
                    setTimeout(() => { window.location.href = `/layers/${slug}/`; }, 1500);
                } else {
                    setTimeout(() => { window.location.href = '/layers/'; }, 1500);
                }
            } else {
                throw new Error(data.error || 'Failed to create project');
            }
        } catch (error) {
            document.getElementById('alert-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${error.message}
                </div>
            `;
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Layer';
        }
    });
    </script>
    """

    return render_page("Create Layer - MLGH", content, theme=current_theme, user_menu=user_menu)
