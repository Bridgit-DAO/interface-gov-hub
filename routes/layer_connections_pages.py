"""Layer organizational connections pages."""
import html as html_mod
import json

from flask import Blueprint, session

from models import Guild, Layer, LayerConnection
from services.coordination import is_layer_admin
from services.identity import get_current_user
from services.layer_connections import enrich_connection, list_connection_types, resolve_layer
from services.directory_ui import gh_page_header, gh_breadcrumb

bp = Blueprint('layer_connections_pages', __name__)


def _render(layer_slug: str, standalone: bool = False):
    from services.rendering import render_page, render_layer_standalone_page, generate_user_menu

    layer = resolve_layer(layer_slug)
    if not layer:
        return 'Layer not found', 404

    user = get_current_user()
    admin = bool(user and is_layer_admin(layer, user))
    types = list_connection_types(layer.id, active_only=not admin)
    active = LayerConnection.query.filter_by(layer_id=layer.id, status='active').order_by(
        LayerConnection.created_at.desc()
    ).all()
    pending = []
    if admin:
        pending = LayerConnection.query.filter_by(layer_id=layer.id, status='pending').order_by(
            LayerConnection.created_at.desc()
        ).all()

    layer_name = html_mod.escape(layer.name or layer.slug)
    slug = layer.slug

    active_cards = []
    for c in active:
        ec = enrich_connection(c)
        title = html_mod.escape(ec.get('display_name') or 'Connection')
        ctype = html_mod.escape((ec.get('connection_type') or {}).get('title') or '')
        url = ec.get('display_url')
        link = f'<a href="{html_mod.escape(url)}" class="stretched-link"></a>' if url and url.startswith('/') else ''
        ext = (
            f'<a href="{html_mod.escape(url)}" target="_blank" rel="noopener" class="small">{html_mod.escape(url)}</a>'
            if url and url.startswith('http')
            else ''
        )
        active_cards.append(
            f'<div class="col-md-6 col-lg-4"><div class="card h-100 position-relative">'
            f'<div class="card-body"><span class="badge text-bg-secondary mb-2">{ctype}</span>'
            f'<h3 class="h6 card-title mb-1">{title}</h3>{ext}{link}</div></div></div>'
        )
    active_html = (
        ''.join(active_cards)
        if active_cards
        else '<p class="text-muted">No organizational connections yet.</p>'
    )

    open_types = [t for t in types if t.is_open]
    type_options = ''.join(
        f'<option value="{html_mod.escape(t.id)}">{html_mod.escape(t.title)}</option>'
        for t in open_types
    )

    # Build requirements section visible to everyone
    requirements_cards = []
    for t in open_types:
        desc = html_mod.escape(t.description or '')
        agreement = html_mod.escape(t.agreement_text or '')
        approval_badge = (
            '<span class="badge text-bg-warning ms-2">Requires approval</span>'
            if t.requires_approval
            else '<span class="badge text-bg-success ms-2">Auto-approved</span>'
        )
        card = (
            f'<div class="card mb-3 border-secondary">'
            f'<div class="card-body">'
            f'<h3 class="h6 card-title mb-1">{html_mod.escape(t.title)}{approval_badge}</h3>'
        )
        if desc:
            card += f'<p class="text-muted small mb-2">{desc}</p>'
        if agreement:
            card += (
                f'<div class="mt-2 p-3 rounded" style="background: var(--bs-tertiary-bg, rgba(255,255,255,0.03)); border: 1px solid var(--bs-border-color-translucent, rgba(255,255,255,0.1));">'
                f'<p class="small fw-semibold mb-1"><i class="fas fa-file-contract me-1"></i>Requirements & commitments</p>'
                f'<p class="small mb-0">{agreement}</p>'
                f'</div>'
            )
        card += '</div></div>'
        requirements_cards.append(card)

    requirements_section = ''
    if requirements_cards:
        requirements_section = (
            '<div class="living-module mt-4">'
            '<div class="living-module-header"><h2 class="h5 mb-0"><i class="fas fa-clipboard-list me-2"></i>Connection Types &amp; Requirements</h2></div>'
            '<div class="living-module-body">'
            + ''.join(requirements_cards)
            + '</div></div>'
        )

    # JSON map of type_id -> agreement text for dynamic display in form
    type_agreements_json = json.dumps({
        t.id: t.agreement_text or '' for t in open_types
    })

    guilds = Guild.query.filter_by(status='active').order_by(Guild.name.asc()).limit(200).all()
    guild_opts = ''.join(
        f'<option value="{html_mod.escape(g.id)}">{html_mod.escape(g.name)}</option>' for g in guilds
    )
    from services.layer_prefixes import visible_layers_for_user
    layers = [
        l for l in visible_layers_for_user((user or {}).get('id'))
        if l.id != layer.id
    ][:200]
    layer_opts = ''.join(
        f'<option value="{html_mod.escape(l.id)}">{html_mod.escape(l.name)}</option>' for l in layers
    )

    apply_section = ''
    if user and type_options:
        apply_section = f'''
        <div class="living-module mt-4" id="apply-connection">
          <div class="living-module-header"><h2 class="h5 mb-0">Apply for a connection</h2></div>
          <div class="living-module-body">
            <form id="connectionApplyForm" class="row g-3">
              <div class="col-md-6">
                <label class="form-label">Connection type</label>
                <select class="form-select" name="connection_type_id" id="connectionTypeSelect" required>{type_options}</select>
              </div>
              <div class="col-md-6">
                <label class="form-label">I am applying as</label>
                <select class="form-select" name="connector_kind" id="connectorKind" required>
                  <option value="individual">Individual</option>
                  <option value="guild">Guild</option>
                  <option value="layer">Another layer</option>
                  <option value="external">External organization</option>
                </select>
              </div>
              <div class="col-md-6 d-none" id="fieldGuild">
                <label class="form-label">Guild</label>
                <select class="form-select" name="guild_id"><option value="">Select…</option>{guild_opts}</select>
              </div>
              <div class="col-md-6 d-none" id="fieldLayer">
                <label class="form-label">Connecting layer</label>
                <select class="form-select" name="source_layer_id"><option value="">Select…</option>{layer_opts}</select>
                <div class="form-text">Child layers connecting to this layer require approval.</div>
              </div>
              <div class="col-md-6 d-none" id="fieldExternalName">
                <label class="form-label">Organization name</label>
                <input class="form-control" name="external_name" maxlength="255">
              </div>
              <div class="col-md-6 d-none" id="fieldExternalUrl">
                <label class="form-label">Organization URL</label>
                <input class="form-control" name="external_url" type="url" maxlength="500">
              </div>
              <div class="col-12">
                <label class="form-label">Message (optional)</label>
                <textarea class="form-control" name="message" rows="2" maxlength="2000"></textarea>
              </div>
              <div class="col-12" id="agreementDisplay" style="display:none;">
                <div class="p-3 rounded" style="background: var(--bs-tertiary-bg, rgba(255,255,255,0.03)); border: 1px solid var(--bs-border-color-translucent, rgba(255,255,255,0.1));">
                  <p class="small fw-semibold mb-1"><i class="fas fa-file-contract me-1"></i>You are agreeing to the following:</p>
                  <p class="small mb-0" id="agreementText"></p>
                </div>
              </div>
              <div class="col-12">
                <div class="form-check">
                  <input class="form-check-input" type="checkbox" name="agreement_accepted" id="agreementAccepted" value="1">
                  <label class="form-check-label" for="agreementAccepted">I agree to the requirements for the selected connection type.</label>
                </div>
              </div>
              <div class="col-12">
                <button type="submit" class="btn btn-primary">Submit application</button>
              </div>
            </form>
          </div>
        </div>
        <script>
        (function() {{
          const typeAgreements = {type_agreements_json};
          const typeSelect = document.getElementById('connectionTypeSelect');
          const agreementDisplay = document.getElementById('agreementDisplay');
          const agreementText = document.getElementById('agreementText');

          function syncAgreement() {{
            const text = typeAgreements[typeSelect.value] || '';
            if (text) {{
              agreementText.textContent = text;
              agreementDisplay.style.display = '';
            }} else {{
              agreementDisplay.style.display = 'none';
            }}
          }}
          typeSelect.addEventListener('change', syncAgreement);
          syncAgreement();

          const kind = document.getElementById('connectorKind');
          const fields = {{
            guild: document.getElementById('fieldGuild'),
            layer: document.getElementById('fieldLayer'),
            external: [document.getElementById('fieldExternalName'), document.getElementById('fieldExternalUrl')],
          }};
          function syncFields() {{
            fields.guild.classList.toggle('d-none', kind.value !== 'guild');
            fields.layer.classList.toggle('d-none', kind.value !== 'layer');
            fields.external.forEach(el => el.classList.toggle('d-none', kind.value !== 'external'));
          }}
          kind.addEventListener('change', syncFields);
          syncFields();

          document.getElementById('connectionApplyForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const fd = new FormData(e.target);
            const body = Object.fromEntries(fd.entries());
            body.agreement_accepted = fd.get('agreement_accepted') === '1';
            try {{
              const res = await fetch('/api/layers/{html_mod.escape(slug)}/connections/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body),
              }});
              const data = await res.json();
              if (!res.ok) throw new Error(data.error || 'Submit failed');
              await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Submitted', message: data.connection.status === 'active' ? 'Your connection is now active.' : 'Your application is pending review.', variant: 'success' }}), variant: 'info' }});
              location.reload();
            }} catch (err) {{
              await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Could not submit', message: err.message || 'Submit failed', variant: 'danger' }}), variant: 'info' }});
            }}
          }});
        }})();
        </script>
        '''
    elif not user:
        apply_section = '<p class="text-muted mt-4"><a href="/login/">Sign in</a> to apply for an organizational connection.</p>'

    admin_section = ''
    if admin:
        pending_rows = []
        for c in pending:
            ec = enrich_connection(c, include_admin=True)
            pending_rows.append(
                f'<tr><td>{html_mod.escape(ec.get("display_name") or "")}</td>'
                f'<td>{html_mod.escape((ec.get("connection_type") or {}).get("title") or "")}</td>'
                f'<td>{html_mod.escape(c.connector_kind)}</td>'
                f'<td class="text-end">'
                f'<button type="button" class="btn btn-sm btn-success me-1" data-approve="{c.id}">Approve</button>'
                f'<button type="button" class="btn btn-sm btn-outline-danger" data-reject="{c.id}">Reject</button>'
                f'</td></tr>'
            )
        pending_table = (
            '<table class="table table-sm align-middle"><thead><tr><th>Org</th><th>Type</th><th>Kind</th><th></th></tr></thead><tbody>'
            + (''.join(pending_rows) if pending_rows else '<tr><td colspan="4" class="text-muted">No pending applications.</td></tr>')
            + '</tbody></table>'
        )
        type_admin_rows = ''.join(
            f'<li class="mb-2"><strong>{html_mod.escape(t.title)}</strong>'
            f' – {"approval required" if t.requires_approval else "auto-approve"}'
            f' – {"open" if t.is_open else "closed"}</li>'
            for t in types
        )
        admin_section = f'''
        <div class="living-module mt-4">
          <div class="living-module-header"><h2 class="h5 mb-0">Admin – pending applications</h2></div>
          <div class="living-module-body">{pending_table}</div>
        </div>
        <div class="living-module mt-4">
          <div class="living-module-header"><h2 class="h5 mb-0">Admin – connection types</h2></div>
          <div class="living-module-body">
            <ul class="mb-3">{type_admin_rows or '<li class="text-muted">No types yet.</li>'}</ul>
            <form id="newConnectionTypeForm" class="row g-2">
              <div class="col-md-4"><input class="form-control" name="title" placeholder="Title (e.g. Partner)" required></div>
              <div class="col-md-4"><input class="form-control" name="description" placeholder="Short description"></div>
              <div class="col-md-4"><button type="submit" class="btn btn-outline-primary w-100">Add type</button></div>
              <div class="col-12"><textarea class="form-control" name="agreement_text" rows="2" placeholder="Requirements / agreement text"></textarea></div>
              <div class="col-auto form-check"><input class="form-check-input" type="checkbox" name="requires_approval" id="reqAppr" checked><label class="form-check-label" for="reqAppr">Requires approval</label></div>
              <div class="col-auto form-check"><input class="form-check-input" type="checkbox" name="is_open" id="isOpen" checked><label class="form-check-label" for="isOpen">Open for applications</label></div>
            </form>
          </div>
        </div>
        <script>
        (function() {{
          document.querySelectorAll('[data-approve]').forEach(btn => btn.addEventListener('click', async () => {{
            const id = btn.getAttribute('data-approve');
            const res = await fetch(`/api/layers/{html_mod.escape(slug)}/connections/${{id}}/approve/`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: '{{}}' }});
            const data = await res.json();
            if (!res.ok) return GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Error', message: data.error || 'Failed', variant: 'danger' }}), variant: 'info' }});
            location.reload();
          }}));
          document.querySelectorAll('[data-reject]').forEach(btn => btn.addEventListener('click', async () => {{
            const ok = await GhDialog.confirm({{ title: 'Reject application', message: 'Reject this connection application?', variant: 'warning' }});
            if (!ok) return;
            const id = btn.getAttribute('data-reject');
            const res = await fetch(`/api/layers/{html_mod.escape(slug)}/connections/${{id}}/reject/`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ rejected_reason: 'Rejected by layer admin' }}) }});
            const data = await res.json();
            if (!res.ok) return GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Error', message: data.error || 'Failed', variant: 'danger' }}), variant: 'info' }});
            location.reload();
          }}));
          document.getElementById('newConnectionTypeForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const fd = new FormData(e.target);
            const body = {{
              title: fd.get('title'),
              description: fd.get('description'),
              agreement_text: fd.get('agreement_text'),
              requires_approval: fd.get('requires_approval') === 'on',
              is_open: fd.get('is_open') === 'on',
            }};
            const res = await fetch('/api/layers/{html_mod.escape(slug)}/connection-types/', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
            const data = await res.json();
            if (!res.ok) return GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Error', message: data.error || 'Failed', variant: 'danger' }}), variant: 'info' }});
            location.reload();
          }});
        }})();
        </script>
        '''

    back_href = f'/layer/{slug}/' if standalone else f'/layers/{slug}/'
    content = f'''
    <div class="gh-page container mt-4">
      {gh_page_header(
          f'Connections – {layer_name}',
          'Organizational partners, endorsers, and representatives.',
          'fa-handshake',
          actions_html=f'<a href="{back_href}" class="btn btn-outline-secondary btn-sm">Layer</a>',
          breadcrumb_html=gh_breadcrumb([('Home', '/'), (layer.name or slug, back_href), ('Connections', None)]),
      )}
      <div class="living-module">
        <div class="living-module-header"><h2 class="h5 mb-0">Active connections</h2></div>
        <div class="living-module-body"><div class="row g-3">{active_html}</div></div>
      </div>
      {requirements_section}
      {apply_section}
      {admin_section}
    </div>
    '''

    title = f'Connections – {layer.name or slug} - GovHub'
    user_menu = generate_user_menu()
    theme = session.get('theme', 'dark')
    if standalone:
        return render_layer_standalone_page(
            title,
            content,
            layer_name=layer.name or slug,
            layer_slug=slug,
            layer_image_url=layer.image_url,
            theme=theme,
            user_menu=user_menu,
        )
    return render_page(title, content, theme=theme, user_menu=user_menu)


@bp.route('/layers/<layer_slug>/connections/')
def layer_connections_mlgh(layer_slug):
    return _render(layer_slug, standalone=False)


@bp.route('/layer/<layer_ref>/connections/')
def layer_connections_standalone(layer_ref):
    layer = resolve_layer(layer_ref)
    if not layer:
        return 'Layer not found', 404
    return _render(layer.slug, standalone=True)
