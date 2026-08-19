"""Public Gov Hub campaign pages (multi-document landing + participation)."""
from __future__ import annotations

import html as html_mod
import json

from flask import Blueprint, abort, flash, g, get_flashed_messages, redirect, request, send_file

from extensions import db
from models.campaign_endorsement import CampaignEndorsement
from services.auth_redirect import login_url
from services.campaign_pages import (
    campaign_for_host,
    campaign_href,
    find_monument_node,
    get_campaign,
    read_statement_html,
    reload_campaign_cache,
    resolve_project_path,
)
from services.campaign_thumbnails import (
    persist_document_thumbnail,
    resolve_campaign_card_thumbnail,
    save_uploaded_campaign_thumbnail,
    thumb_public_url,
)
from services.campaign_render import (
    render_monument_index,
    render_monument_node,
    render_doc_paper,
    render_doc_slides,
    render_doc_statement,
    render_home,
)
from services.csrf import csrf_form_field
from services.identity import get_current_user, require_auth

bp = Blueprint('campaign_pages', __name__)


def _can_manage_campaign_thumbnails(user, cfg) -> bool:
    if not user:
        return False
    if (user.get('role') or 'user') in ('admin', 'editor'):
        return True
    layer_slug = (cfg.layer_slug or '').strip()
    if not layer_slug:
        return False
    from models import Layer
    from services.coordination import is_layer_admin

    layer = Layer.query.filter_by(slug=layer_slug).first()
    return bool(layer and is_layer_admin(layer, user))


def _cfg_or_404(slug: str):
    cfg = get_campaign(slug)
    if not cfg:
        abort(404)
    return cfg


@bp.route('/campaign/<slug>/')
def campaign_home(slug):
    cfg = _cfg_or_404(slug)
    g.campaign_slug = slug
    return render_home(cfg), 200, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/campaign/<slug>/docs/<doc_slug>/', methods=['GET', 'POST'])
def campaign_doc(slug, doc_slug):
    cfg = _cfg_or_404(slug)
    g.campaign_slug = slug
    doc = cfg.doc_by_slug(doc_slug)
    if not doc:
        abort(404)

    if doc_slug == 'paper':
        draft_ref = doc.get('draftRef') or ''
        if not draft_ref:
            abort(404)
        return render_doc_paper(cfg, doc, draft_ref), 200, {'Content-Type': 'text/html; charset=utf-8'}

    if doc_slug == 'statement':
        if request.method == 'POST':
            return _statement_endorse_post(cfg, doc)
        return _statement_page(cfg, doc)

    if doc_slug == 'slides':
        rel = doc.get('deckPath') or ''
        path = resolve_project_path(rel)
        if not __import__('os').path.isfile(path):
            abort(404)
        pdf_url = campaign_href(slug, f'/docs/slides/file/')
        return render_doc_slides(cfg, doc, pdf_url), 200, {'Content-Type': 'text/html; charset=utf-8'}

    abort(404)


@bp.route('/campaign/<slug>/monument/')
def campaign_monument(slug):
    cfg = _cfg_or_404(slug)
    g.campaign_slug = slug
    return render_monument_index(cfg), 200, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/campaign/<slug>/monument/<node_slug>/')
def campaign_monument_node(slug, node_slug):
    cfg = _cfg_or_404(slug)
    g.campaign_slug = slug
    node = find_monument_node(cfg, node_slug)
    if not node:
        abort(404)
    return render_monument_node(cfg, node), 200, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/campaign/<slug>/docs/slides/file/')
def campaign_slides_file(slug):
    cfg = _cfg_or_404(slug)
    doc = cfg.doc_by_slug('slides')
    if not doc:
        abort(404)
    path = resolve_project_path(doc.get('deckPath') or '')
    if not __import__('os').path.isfile(path):
        abort(404)
    return send_file(path, mimetype='application/pdf', conditional=True)


def _statement_page(cfg, doc):
    body_html = read_statement_html(cfg, doc)
    endorsements_html = _approved_endorsements_html(cfg.slug)
    form_html = _endorsement_form_html(cfg.slug, doc)
    return render_doc_statement(cfg, doc, body_html, endorsements_html, form_html), 200, {
        'Content-Type': 'text/html; charset=utf-8',
    }


def _endorsement_form_html(campaign_slug: str, doc: dict) -> str:
    if not doc.get('allowEndorsement'):
        return ''
    user = get_current_user()
    if not user:
        return (
            f'<p><a class="btn btn-primary" href="{html_mod.escape(login_url(campaign_href(campaign_slug, "/docs/statement")))}">'
            f'Sign in to endorse</a></p>'
        )
    options = [
        ('support_direction', 'Support the direction'),
        ('endorse_current_draft', 'Endorse current draft'),
        ('support_with_reservations', 'Support with reservations'),
        ('sign_statement', 'Sign public statement'),
        ('institutional_endorsement', 'Institutional endorsement'),
        ('follow_updates', 'Follow updates'),
    ]
    opts = ''.join(
        f'<option value="{html_mod.escape(v)}">{html_mod.escape(lbl)}</option>' for v, lbl in options
    )
    return f'''
    <form method="POST" class="gh-endorse-form card card-body">
      {csrf_form_field()}
      <input type="hidden" name="action" value="endorse">
      <div class="mb-2">
        <label class="form-label">Type of support</label>
        <select class="form-select" name="endorsement_type" required>{opts}</select>
      </div>
      <div class="mb-2">
        <label class="form-label">Display name</label>
        <input class="form-control" name="display_name" required value="{html_mod.escape(user.get("name") or "")}">
      </div>
      <div class="mb-2">
        <label class="form-label">Affiliation (optional)</label>
        <input class="form-control" name="affiliation">
      </div>
      <div class="mb-2">
        <label class="form-label">Comment (optional)</label>
        <textarea class="form-control" name="comment" rows="3"></textarea>
      </div>
      <button type="submit" class="btn btn-primary">Submit for review</button>
      <p class="small text-muted mt-2 mb-0">Your endorsement will be reviewed before it appears publicly.</p>
    </form>
    '''


def _statement_endorse_post(cfg, doc):
    if not doc.get('allowEndorsement'):
        abort(403)
    user = get_current_user()
    if not user:
        flash('Please sign in to endorse.', 'error')
        return redirect(login_url(campaign_href(cfg.slug, '/docs/statement')))
    if request.form.get('action') != 'endorse':
        abort(400)
    etype = (request.form.get('endorsement_type') or '').strip()
    if etype not in CampaignEndorsement.ENDORSEMENT_TYPES:
        flash('Invalid endorsement type.', 'error')
        return redirect(campaign_href(cfg.slug, '/docs/statement'))
    display_name = (request.form.get('display_name') or '').strip()
    if not display_name:
        flash('Display name is required.', 'error')
        return redirect(campaign_href(cfg.slug, '/docs/statement'))
    row = CampaignEndorsement(
        campaign_slug=cfg.slug,
        user_id=user['id'],
        endorsement_type=etype,
        display_name=display_name,
        affiliation=(request.form.get('affiliation') or '').strip() or None,
        comment=(request.form.get('comment') or '').strip() or None,
        status='pending',
    )
    db.session.add(row)
    db.session.commit()
    flash('Thank you. Your endorsement was submitted for review.', 'success')
    return redirect(campaign_href(cfg.slug, '/docs/statement'))


def _approved_endorsements_html(campaign_slug: str) -> str:
    rows = (
        CampaignEndorsement.query.filter_by(campaign_slug=campaign_slug, status='approved')
        .order_by(CampaignEndorsement.created_at.desc())
        .limit(100)
        .all()
    )
    if not rows:
        return '<p class="text-muted">No public endorsements yet.</p>'
    items = []
    for row in rows:
        aff = f' <span class="text-muted">· {html_mod.escape(row.affiliation)}</span>' if row.affiliation else ''
        comment = f'<p class="small mb-0">{html_mod.escape(row.comment)}</p>' if row.comment else ''
        items.append(
            f'<li class="list-group-item">'
            f'<strong>{html_mod.escape(row.display_name)}</strong>{aff}'
            f'<span class="badge bg-secondary ms-2">{html_mod.escape(row.endorsement_type.replace("_", " "))}</span>'
            f'{comment}</li>'
        )
    return '<ul class="list-group">' + ''.join(items) + '</ul>'


@bp.route('/campaign/<slug>/admin/endorsements/')
@require_auth
def campaign_endorsements_admin(slug):
    """Moderate pending endorsements (site admin/editor)."""
    user = get_current_user()
    role = (user or {}).get('role', 'user')
    if role not in ('admin', 'editor'):
        abort(403)
    cfg = _cfg_or_404(slug)
    pending = (
        CampaignEndorsement.query.filter_by(campaign_slug=slug, status='pending')
        .order_by(CampaignEndorsement.created_at.asc())
        .all()
    )
    rows = []
    for row in pending:
        rows.append(f'''
        <tr>
          <td>{html_mod.escape(row.display_name)}</td>
          <td>{html_mod.escape(row.endorsement_type)}</td>
          <td>{html_mod.escape((row.comment or "")[:120])}</td>
          <td>
            <form method="POST" action="{html_mod.escape(campaign_href(slug, f"/admin/endorsements/{row.id}/approve"))}" style="display:inline">{csrf_form_field()}<button class="btn btn-sm btn-success">Approve</button></form>
            <form method="POST" action="{html_mod.escape(campaign_href(slug, f"/admin/endorsements/{row.id}/reject"))}" style="display:inline">{csrf_form_field()}<button class="btn btn-sm btn-outline-danger">Reject</button></form>
          </td>
        </tr>''')
    table = ''.join(rows) or '<tr><td colspan="4" class="text-muted">No pending endorsements.</td></tr>'
    html = f'''<!DOCTYPE html><html><head><title>Moderate endorsements</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="p-4"><h1>Endorsements – {html_mod.escape(cfg.title)}</h1>
    <table class="table"><thead><tr><th>Name</th><th>Type</th><th>Comment</th><th></th></tr></thead><tbody>{table}</tbody></table>
    <p><a href="{html_mod.escape(campaign_href(slug, "/docs/statement"))}">Back to statement</a></p></body></html>'''
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/campaign/<slug>/admin/endorsements/<endorsement_id>/approve/', methods=['POST'])
@bp.route('/campaign/<slug>/admin/endorsements/<endorsement_id>/reject/', methods=['POST'])
@require_auth
def campaign_endorsement_moderate(slug, endorsement_id):
    user = get_current_user()
    if (user or {}).get('role', 'user') not in ('admin', 'editor'):
        abort(403)
    row = CampaignEndorsement.query.filter_by(id=endorsement_id, campaign_slug=slug).first()
    if not row:
        abort(404)
    from datetime import datetime
    if request.path.endswith('/approve/'):
        row.status = 'approved'
    else:
        row.status = 'rejected'
    row.reviewed_at = datetime.utcnow()
    row.reviewed_by_user_id = user['id']
    db.session.commit()
    flash('Endorsement updated.', 'success')
    return redirect(campaign_href(slug, '/admin/endorsements/'))


@bp.route('/campaign/<slug>/admin/thumbnails/', methods=['GET'])
@require_auth
def campaign_thumbnails_admin(slug):
    """Upload custom card thumbnails for campaign documents (site or layer admin)."""
    user = get_current_user()
    cfg = _cfg_or_404(slug)
    if not _can_manage_campaign_thumbnails(user, cfg):
        abort(403)

    rows = []
    items = list(cfg.documents or []) + list(cfg.external_links or [])
    items.sort(key=lambda row: row.get('displayOrder') or 0)
    for item in items:
        doc_slug = item.get('slug') or ''
        if not doc_slug:
            continue
        thumb = resolve_campaign_card_thumbnail(cfg, item, external=bool(item.get('url')))
        thumb_html = (
            f'<img src="{html_mod.escape(thumb)}" alt="" '
            f'style="max-width:160px;border-radius:6px;aspect-ratio:16/9;object-fit:cover;">'
            if thumb
            else '<span class="text-muted small">Icon fallback</span>'
        )
        rows.append(f'''
        <tr>
          <td>{html_mod.escape(item.get("label") or doc_slug)}</td>
          <td><code>{html_mod.escape(doc_slug)}</code></td>
          <td>{thumb_html}</td>
          <td>
            <form method="POST" enctype="multipart/form-data"
                  action="{html_mod.escape(campaign_href(slug, f"/admin/thumbnails/{doc_slug}/"))}">
              {csrf_form_field()}
              <input type="file" name="thumbnail" accept="image/png,image/jpeg,image/webp,image/gif" required>
              <button type="submit" class="btn btn-sm btn-primary mt-1">Upload</button>
            </form>
          </td>
        </tr>''')

    table = ''.join(rows) or '<tr><td colspan="4" class="text-muted">No documents configured.</td></tr>'
    flash_script = ''
    for category, message in get_flashed_messages(with_categories=True):
        variant = 'success' if category == 'success' else 'danger'
        flash_script += f'''
    <script src="/static/js/gh-dialog.js"></script>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
      if (window.GhDialog) {{
        GhDialog.alert({{
          title: {json.dumps("Upload" if variant == "success" else "Upload failed")},
          message: {json.dumps(message)},
          variant: {json.dumps(variant)},
        }});
      }}
    }});
    </script>'''

    html = f'''<!DOCTYPE html><html><head><title>Campaign thumbnails</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="p-4">
    <h1>Card thumbnails – {html_mod.escape(cfg.title)}</h1>
    <p class="text-muted">Upload replaces the cached JPG under <code>/static/campaign/{html_mod.escape(slug)}/assets/</code>
    and updates the monument node <code>thumbnailUrl</code>. PDF auto-extract runs when no explicit thumb is set.</p>
    <table class="table align-middle"><thead><tr><th>Label</th><th>Slug</th><th>Current</th><th>Upload</th></tr></thead>
    <tbody>{table}</tbody></table>
    <p><a href="{html_mod.escape(campaign_href(slug, "/"))}">Back to campaign home</a></p>
    {flash_script}
    </body></html>'''
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@bp.route('/campaign/<slug>/admin/thumbnails/<doc_slug>/', methods=['POST'])
@require_auth
def campaign_thumbnail_upload(slug, doc_slug):
    user = get_current_user()
    cfg = _cfg_or_404(slug)
    if not _can_manage_campaign_thumbnails(user, cfg):
        abort(403)
    file = request.files.get('thumbnail')
    public_url, err = save_uploaded_campaign_thumbnail(slug, doc_slug, file)
    if err:
        flash(err, 'error')
        return redirect(campaign_href(slug, '/admin/thumbnails/'))
    persist_document_thumbnail(cfg, doc_slug, public_url or thumb_public_url(slug, doc_slug))
    reload_campaign_cache()
    flash(f'Thumbnail saved for {doc_slug}.', 'success')
    return redirect(campaign_href(slug, '/admin/thumbnails/'))
