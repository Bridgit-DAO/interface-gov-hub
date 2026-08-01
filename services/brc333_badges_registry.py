"""BRC333 badges project registry (Metaweb layer and future layers)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from config import PROJECT_ROOT

REGISTRY_PATH = os.path.join(PROJECT_ROOT, 'data', 'brc333_badges_projects.json')

LAYER_ADMIN_PROTECTED_FILES = frozenset({
    'logic.htm',
    'badge-experience.js',
    'brc333badges.js',
})

SUPER_ADMIN_ONLY_CONFIG_KEYS = frozenset({
    'attestorProofInscriptionId',
    'sourceId',
    'chain',
    'medium',
    'protocolLabel',
    'hookSat',
})

LAYER_ADMIN_CONFIG_KEYS = frozenset({
    'primary',
    'infoTitle',
    'description',
    'brc333message',
    'defaultCohort',
})

SUPER_ADMIN_ONLY_SCRIPTS = frozenset({
    'Logic',
    'Badges',
    'BadgeExperience',
    'Oracle',
    'TimeTravel',
    'Data',
})

PROTECTED_DOC_FIELDS = frozenset({
    'protocol',
    'operation',
    'schemaVersion',
    'project',
    'workId',
})


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    with open(REGISTRY_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def reload_registry() -> None:
    _load_registry.cache_clear()


def list_projects() -> list[dict[str, Any]]:
    reg = _load_registry()
    out = []
    for pid, meta in (reg.get('projects') or {}).items():
        if not meta.get('enabled', True):
            continue
        out.append({'id': pid, **meta})
    return out


def get_project(project_id: str) -> dict[str, Any] | None:
    reg = _load_registry()
    meta = (reg.get('projects') or {}).get(project_id)
    if not meta or not meta.get('enabled', True):
        return None
    return {'id': project_id, **meta}


def project_root(project_id: str) -> str | None:
    proj = get_project(project_id)
    if not proj:
        return None
    return os.path.normpath(
        os.path.join(proj['monorepoRoot'], proj['projectDir'])
    )


def git_repo_root(project_id: str) -> str | None:
    proj = get_project(project_id)
    if not proj:
        return None
    return os.path.normpath(proj['monorepoRoot'])


def project_for_layer(layer_slug: str) -> dict[str, Any] | None:
    for proj in list_projects():
        if proj.get('layerSlug') == layer_slug:
            return proj
    return None


def rel_project_path(project_id: str, rel_path: str) -> str | None:
    root = project_root(project_id)
    if not root:
        return None
    rel_path = rel_path.replace('\\', '/').lstrip('/')
    full = os.path.normpath(os.path.join(root, rel_path))
    if not full.startswith(root + os.sep) and full != root:
        return None
    return full


def is_protected_file(rel_path: str, super_admin: bool) -> bool:
    if super_admin:
        return False
    base = os.path.basename(rel_path.replace('\\', '/'))
    return base in LAYER_ADMIN_PROTECTED_FILES


def editable_json_paths() -> frozenset[str]:
    return frozenset({
        'sources-sat.json',
        'config.json',
        'data/certifications.json',
    })
