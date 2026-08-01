"""BRC333 badges admin: read/write project files, validate, sanitize, git commit."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import bleach

from services.brc333_badges_registry import (
    PROTECTED_DOC_FIELDS,
    LAYER_ADMIN_CONFIG_KEYS,
    editable_json_paths,
    get_project,
    git_repo_root,
    is_protected_file,
    project_root,
    rel_project_path,
)

HTML_ALLOWED_TAGS = [
    'span', 'h2', 'h3', 'br', 'strong', 'b', 'em', 'i', 'p', 'a', 'code',
]
HTML_ALLOWED_ATTRS = {
    '*': ['class'],
    'a': ['href', 'title', 'rel', 'target'],
}
HTML_ALLOWED_CLASSES = frozenset({
    'bold', 'normal', 'title-text', 'subtitle-text',
})

CONFIG_RICH_TEXT_KEYS = frozenset({'description', 'brc333message'})


def _css_sanitizer():
    return bleach.css_sanitizer.CSSSanitizer(allowed_css_properties=[])


def sanitize_config_html(value: str) -> str:
    if not value:
        return ''
    cleaned = bleach.clean(
        value,
        tags=HTML_ALLOWED_TAGS,
        attributes=HTML_ALLOWED_ATTRS,
        css_sanitizer=_css_sanitizer(),
        strip=True,
    )
    # Drop disallowed class tokens
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(cleaned, 'html.parser')
    for el in soup.find_all(True):
        classes = el.get('class') or []
        kept = [c for c in classes if c in HTML_ALLOWED_CLASSES]
        if kept:
            el['class'] = kept
        elif 'class' in el.attrs:
            del el['class']
    return str(soup)


def read_text_file(project_id: str, rel_path: str) -> dict[str, Any]:
    full = rel_project_path(project_id, rel_path)
    if not full or not os.path.isfile(full):
        raise FileNotFoundError(rel_path)
    with open(full, encoding='utf-8') as fh:
        content = fh.read()
    return {'path': rel_path.replace('\\', '/'), 'content': content}


def read_json_file(project_id: str, rel_path: str) -> dict[str, Any]:
    data = read_text_file(project_id, rel_path)
    try:
        data['json'] = json.loads(data['content'])
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON in {rel_path}: {exc}') from exc
    return data


def _normalize_sources_sat(doc: dict[str, Any]) -> dict[str, Any]:
    rails = []
    for row in doc.get('sources') or []:
        key = (row or {}).get('railKey')
        if key and key not in rails:
            rails.append(key)
    doc['infrastructureRails'] = rails
    return doc


def _sanitize_config_doc(
    doc: dict[str, Any],
    super_admin: bool,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing_sources = (existing or {}).get('sources') or []
    existing_by_key = {
        e['key']: e for e in existing_sources if isinstance(e, dict) and e.get('key')
    }
    if super_admin:
        sources = doc.get('sources') or []
        cleaned_sources = []
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            key = entry.get('key')
            row = dict(entry)
            if key in CONFIG_RICH_TEXT_KEYS and isinstance(entry.get('value'), str):
                row['value'] = sanitize_config_html(entry['value'])
            cleaned_sources.append(row)
        doc = dict(doc)
        doc['sources'] = cleaned_sources
        return doc

    # Layer admin: allowlist key edits; preserve infrastructure entries from existing.
    incoming = doc.get('sources') or []
    incoming_by_key = {
        e['key']: e for e in incoming if isinstance(e, dict) and e.get('key')
    }
    cleaned_sources = []
    for entry in existing_sources:
        if not isinstance(entry, dict):
            continue
        key = entry.get('key')
        script = entry.get('script')
        if script:
            cleaned_sources.append(dict(entry))
            continue
        if entry.get('sources') or entry.get('oracle') or entry.get('system'):
            cleaned_sources.append(dict(entry))
            continue
        if key not in LAYER_ADMIN_CONFIG_KEYS:
            cleaned_sources.append(dict(entry))
            continue
        updated = incoming_by_key.get(key, entry)
        row = dict(updated)
        if key in CONFIG_RICH_TEXT_KEYS and isinstance(row.get('value'), str):
            row['value'] = sanitize_config_html(row['value'])
        cleaned_sources.append(row)
    doc = dict(doc)
    doc['sources'] = cleaned_sources
    return doc


def validate_json_doc(rel_path: str, doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    norm = rel_path.replace('\\', '/')
    for req in ('protocol', 'operation', 'project'):
        if req not in doc:
            errors.append(f'Missing required field: {req}')
    if norm == 'sources-sat.json':
        keys = set()
        for row in doc.get('sources') or []:
            rk = (row or {}).get('railKey')
            if not rk:
                errors.append('Each source row needs railKey')
            elif rk in keys:
                errors.append(f'Duplicate railKey: {rk}')
            else:
                keys.add(rk)
    if norm == 'data/certifications.json':
        seen = set()
        for cert in doc.get('certifications') or []:
            idx = (cert or {}).get('badgeIndex')
            if idx is None:
                errors.append('Certification missing badgeIndex')
            elif idx in seen:
                errors.append(f'Duplicate badgeIndex: {idx}')
            else:
                seen.add(idx)
    return errors


def write_json_file(
    project_id: str,
    rel_path: str,
    doc: dict[str, Any],
    *,
    super_admin: bool,
) -> dict[str, Any]:
    norm = rel_path.replace('\\', '/')
    if norm not in editable_json_paths():
        raise PermissionError(f'Not an editable JSON path: {norm}')
    if is_protected_file(norm, super_admin):
        raise PermissionError('Protected file')

    if not super_admin:
        try:
            existing_doc = read_json_file(project_id, norm)['json']
            for field in PROTECTED_DOC_FIELDS:
                if field in existing_doc:
                    doc[field] = existing_doc[field]
        except FileNotFoundError:
            existing_doc = None
    else:
        existing_doc = None

    if norm == 'sources-sat.json':
        doc = _normalize_sources_sat(doc)
    elif norm == 'config.json':
        doc = _sanitize_config_doc(doc, super_admin, existing_doc)

    errors = validate_json_doc(norm, doc)
    if errors:
        raise ValueError('; '.join(errors))

    content = json.dumps(doc, indent=2, ensure_ascii=False) + '\n'
    return write_text_file(project_id, norm, content, super_admin=super_admin)


def write_text_file(
    project_id: str,
    rel_path: str,
    content: str,
    *,
    super_admin: bool,
) -> dict[str, Any]:
    norm = rel_path.replace('\\', '/')
    if is_protected_file(norm, super_admin):
        raise PermissionError('Protected file — super-admin only')

    full = rel_project_path(project_id, norm)
    if not full:
        raise PermissionError('Invalid path')

    root = project_root(project_id)
    assert root
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)

    tmp = full + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(content)
    os.replace(tmp, full)

    commit = git_commit_file(project_id, norm, f'brc333-badges: update {norm}')
    maybe_deploy_project(project_id)
    return {'path': norm, 'commit': commit}


def maybe_deploy_project(project_id: str) -> None:
    proj = get_project(project_id)
    if not proj:
        return
    target = (proj.get('deployTarget') or '').strip()
    root = project_root(project_id)
    if not target or not root or not os.path.isdir(target):
        return
    try:
        subprocess.run(
            ['rsync', '-a', root + '/', target + '/'],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return


def git_commit_file(project_id: str, rel_path: str, message: str) -> str | None:
    proj = get_project(project_id)
    repo = git_repo_root(project_id)
    if not proj or not repo:
        return None
    git_rel = os.path.join(proj['projectDir'], rel_path.replace('\\', '/'))
    try:
        add = subprocess.run(
            ['git', 'add', '--', git_rel],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if add.returncode != 0:
            return None
        status = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=repo,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if status.returncode == 0:
            return None
        commit = subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if commit.returncode != 0:
            return None
        rev = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        return rev.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return None


def git_diff_file(project_id: str, rel_path: str) -> dict[str, Any]:
    proj = get_project(project_id)
    repo = git_repo_root(project_id)
    if not proj or not repo:
        return {'path': rel_path, 'diff': ''}
    git_rel = os.path.join(proj['projectDir'], rel_path.replace('\\', '/'))
    result = subprocess.run(
        ['git', 'diff', '--', git_rel],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {'path': rel_path.replace('\\', '/'), 'diff': result.stdout or ''}


def list_rail_files(project_id: str) -> list[dict[str, Any]]:
    data = read_json_file(project_id, 'sources-sat.json')
    rows = []
    for row in data['json'].get('sources') or []:
        local = (row or {}).get('local')
        if not local:
            continue
        rows.append({
            'railKey': row.get('railKey'),
            'label': row.get('label'),
            'local': local,
            'protected': is_protected_file(local, super_admin=False),
        })
    return rows


def save_upload(
    project_id: str,
    rel_path: str,
    raw: bytes,
    *,
    super_admin: bool,
) -> dict[str, Any]:
    norm = rel_path.replace('\\', '/')
    if not norm.startswith('assets/'):
        raise PermissionError('Uploads only allowed under assets/')
    lower = norm.lower()
    if not (lower.endswith('.png') or lower.endswith('.webp')):
        raise PermissionError('Only PNG or WebP uploads allowed')
    full = rel_project_path(project_id, norm)
    if not full:
        raise PermissionError('Invalid path')
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as fh:
        fh.write(raw)
    commit = git_commit_file(project_id, norm, f'brc333-badges: upload {norm}')
    maybe_deploy_project(project_id)
    return {'path': norm, 'commit': commit, 'size': len(raw)}
