"""BRC333 badges admin — Gov Hub routes for Metaweb layer projects."""
from __future__ import annotations

import json
import os

from flask import Blueprint, jsonify, redirect, request, session

from extensions import db
from models import Layer
from services.brc333_badges_admin import (
    git_diff_file,
    list_rail_files,
    read_json_file,
    read_text_file,
    save_upload,
    write_json_file,
    write_text_file,
)
from services.brc333_badges_activation import activate_layer_badges, layer_badges_status
from services.brc333_badges_registry import (
    get_project,
    is_protected_file,
    list_projects,
)
from services.coordination import is_layer_admin
from services.events import emit_event
from services.identity import get_current_user, require_auth

bp = Blueprint('brc333_badges_admin', __name__)


def _render_page():
    from services.rendering import generate_user_menu, render_page
    return render_page, generate_user_menu


def _is_super_admin(user: dict | None) -> bool:
    return bool(user and user.get('role') == 'admin')


def _project_access(project_id: str, user: dict | None) -> tuple[bool, str, dict | None]:
    proj = get_project(project_id)
    if not proj:
        return False, 'Project not found', None
    if not user:
        return False, 'Not authenticated', proj
    if _is_super_admin(user):
        return True, 'super_admin', proj
    layer = Layer.query.filter_by(slug=proj['layerSlug']).first()
    if not layer:
        return False, 'Layer not configured', proj
    if is_layer_admin(layer, user):
        return True, 'layer_admin', proj
    return False, 'Forbidden', proj


def _audit(user: dict, project_id: str, action: str, meta: dict | None = None) -> None:
    payload = {'project_id': project_id, 'action': action}
    if meta:
        payload.update(meta)
    emit_event(
        'brc333_badges_admin',
        actor_type='user',
        actor_id=user.get('id'),
        payload=payload,
    )


def _badges_active_for_project(proj: dict, user: dict | None) -> bool:
    if _is_super_admin(user):
        return True
    status = layer_badges_status(proj.get('layerSlug', ''))
    return bool(status.get('activated'))


@bp.route('/layer/<layer_slug>/brc333-badges/')
@bp.route('/layer/<layer_slug>/brc333-badges/<project_id>/')
@require_auth
def admin_page(layer_slug: str, project_id: str | None = None):
    user = get_current_user()
    projects = [p for p in list_projects() if p.get('layerSlug') == layer_slug]
    if not projects:
        return 'No BRC333 badges projects for this layer', 404
    if not project_id:
        project_id = projects[0]['id']
    ok, _role, proj = _project_access(project_id, user)
    if not ok:
        return 'Access denied', 403
    if not _badges_active_for_project(proj, user):
        return (
            'Badges project is not activated for this layer. '
            'Open the layer Admin tab and choose Activate badges.',
            403,
        )

    render_page, generate_user_menu = _render_page()
    theme = session.get('theme', 'dark')
    user_menu = generate_user_menu()

    preview_base = proj.get('previewBase', '')
    content = f'''
<link rel="stylesheet" href="/static/css/brc333-badges-admin.css?v=2">
<div class="brc333-admin-wrap" id="brc333-admin-app"
     data-project-id="{project_id}"
     data-layer-slug="{layer_slug}"
     data-preview-base="{preview_base}"
     data-super-admin="{'1' if _is_super_admin(user) else '0'}">
  <header class="brc333-admin-header">
    <div>
      <h1>Badges — {proj.get('title', project_id)}</h1>
      <p class="muted">Metaweb Academy project admin. Edits auto-commit to the monorepo and hot-reload preview.</p>
    </div>
    <div class="brc333-admin-header-actions">
      <a class="gh-btn gh-btn-secondary" href="{preview_base}/source-inventory.html" target="_blank" rel="noopener">Inventory</a>
      <a class="gh-btn gh-btn-secondary" href="{preview_base}/mint-preview.html" target="_blank" rel="noopener">Mint preview</a>
    </div>
  </header>
  <nav class="brc333-admin-tabs" role="tablist">
    <button type="button" class="active" data-tab="rails">Rails</button>
    <button type="button" data-tab="config">Config</button>
    <button type="button" data-tab="certifications">Certifications</button>
    <button type="button" data-tab="rails-editor">Rail editor</button>
    <button type="button" data-tab="assets">Assets</button>
    <button type="button" data-tab="diff">Diff</button>
    <button type="button" data-tab="preview">Preview</button>
  </nav>
  <div class="brc333-admin-panels">
    <section class="brc333-panel active" data-panel="rails"></section>
    <section class="brc333-panel" data-panel="config"></section>
    <section class="brc333-panel" data-panel="certifications"></section>
    <section class="brc333-panel" data-panel="rails-editor"></section>
    <section class="brc333-panel" data-panel="assets"></section>
    <section class="brc333-panel" data-panel="diff"></section>
    <section class="brc333-panel brc333-panel-preview" data-panel="preview">
      <iframe id="brc333-preview-frame" title="Badge preview" src="{preview_base}/mint-preview.html?build=instant"></iframe>
    </section>
  </div>
  <footer class="brc333-admin-footer muted">
    <span id="brc333-save-status">Ready</span>
  </footer>
</div>
<script src="/static/js/gh-dialog.js"></script>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js"></script>
<script src="/static/js/brc333-badges-admin.js?v=2"></script>
'''
    return render_page(
        f'Badges — {proj.get("title", project_id)}',
        content,
        theme=theme,
        user_menu=user_menu,
    )


@bp.route('/api/brc333-badges/<project_id>/files/<path:rel_path>', methods=['GET'])
@require_auth
def api_read_file(project_id: str, rel_path: str):
    user = get_current_user()
    ok, role, _ = _project_access(project_id, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        if rel_path.endswith('.json'):
            data = read_json_file(project_id, rel_path)
            return jsonify({
                'path': data['path'],
                'content': data['content'],
                'json': data['json'],
                'protected': is_protected_file(rel_path, _is_super_admin(user)),
                'role': role,
            })
        data = read_text_file(project_id, rel_path)
        return jsonify({
            'path': data['path'],
            'content': data['content'],
            'protected': is_protected_file(rel_path, _is_super_admin(user)),
            'role': role,
        })
    except FileNotFoundError:
        return jsonify({'error': 'Not found'}), 404
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@bp.route('/api/brc333-badges/<project_id>/files/<path:rel_path>', methods=['PUT'])
@require_auth
def api_write_file(project_id: str, rel_path: str):
    user = get_current_user()
    ok, role, _ = _project_access(project_id, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    proj = get_project(project_id)
    if proj and not _badges_active_for_project(proj, user):
        return jsonify({'error': 'Badges not activated for this layer'}), 403
    super_admin = _is_super_admin(user)
    body = request.get_json(silent=True) or {}
    try:
        if rel_path.endswith('.json') and 'json' in body:
            result = write_json_file(
                project_id, rel_path, body['json'], super_admin=super_admin
            )
        elif 'content' in body:
            result = write_text_file(
                project_id, rel_path, body['content'], super_admin=super_admin
            )
        else:
            return jsonify({'error': 'Provide json or content'}), 400
        _audit(user, project_id, 'file_saved', {
            'path': rel_path,
            'commit': result.get('commit'),
            'role': role,
        })
        return jsonify({'ok': True, **result})
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400


@bp.route('/api/brc333-badges/<project_id>/rails', methods=['GET'])
@require_auth
def api_list_rails(project_id: str):
    user = get_current_user()
    ok, _, _ = _project_access(project_id, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify({'rails': list_rail_files(project_id)})


@bp.route('/api/brc333-badges/<project_id>/diff/<path:rel_path>', methods=['GET'])
@require_auth
def api_diff(project_id: str, rel_path: str):
    user = get_current_user()
    ok, _, _ = _project_access(project_id, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(git_diff_file(project_id, rel_path))


@bp.route('/api/brc333-badges/<project_id>/upload', methods=['POST'])
@require_auth
def api_upload(project_id: str):
    user = get_current_user()
    ok, role, _ = _project_access(project_id, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    rel_path = (request.form.get('path') or '').strip()
    file = request.files.get('file')
    if not file or not rel_path:
        return jsonify({'error': 'path and file required'}), 400
    try:
        result = save_upload(
            project_id,
            rel_path,
            file.read(),
            super_admin=_is_super_admin(user),
        )
        _audit(user, project_id, 'asset_uploaded', {
            'path': rel_path,
            'commit': result.get('commit'),
            'role': role,
        })
        return jsonify({'ok': True, **result})
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403


@bp.route('/api/brc333-badges/projects', methods=['GET'])
@require_auth
def api_projects():
    user = get_current_user()
    out = []
    for proj in list_projects():
        ok, role, _ = _project_access(proj['id'], user)
        if ok:
            out.append({
                'id': proj['id'],
                'title': proj.get('title'),
                'layerSlug': proj.get('layerSlug'),
                'previewBase': proj.get('previewBase'),
                'role': role,
            })
    return jsonify({'projects': out})


def _layer_admin_access(layer_slug: str, user: dict | None) -> tuple[bool, Layer | None]:
    if not user:
        return False, None
    if _is_super_admin(user):
        layer = Layer.query.filter_by(slug=layer_slug).first()
        return bool(layer), layer
    layer = Layer.query.filter_by(slug=layer_slug).first()
    if layer and is_layer_admin(layer, user):
        return True, layer
    return False, layer


@bp.route('/api/brc333-badges/layer/<layer_slug>/status', methods=['GET'])
@require_auth
def api_layer_badges_status(layer_slug: str):
    user = get_current_user()
    ok, _ = _layer_admin_access(layer_slug, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(layer_badges_status(layer_slug))


@bp.route('/api/brc333-badges/layer/<layer_slug>/activate', methods=['POST'])
@require_auth
def api_layer_badges_activate(layer_slug: str):
    user = get_current_user()
    ok, _ = _layer_admin_access(layer_slug, user)
    if not ok:
        return jsonify({'error': 'Forbidden'}), 403
    try:
        result = activate_layer_badges(layer_slug, user['id'])
        return jsonify({'ok': True, **result})
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
