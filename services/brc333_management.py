"""BRC333 management layer bindings (control plane activation per layer)."""
from __future__ import annotations

import json
import os
from typing import Any

from config import PROJECT_ROOT

BINDINGS_PATH = os.path.join(PROJECT_ROOT, 'data', 'brc333_management_bindings.json')
REGISTRY_PATH = os.path.join(PROJECT_ROOT, 'data', 'brc333_application_registry.json')


def _load_json(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _save_bindings(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(BINDINGS_PATH), exist_ok=True)
    tmp = BINDINGS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, BINDINGS_PATH)


def management_binding(layer_slug: str) -> dict[str, Any] | None:
    return _load_json(BINDINGS_PATH).get(layer_slug)


def management_enabled(layer_slug: str) -> bool:
    binding = management_binding(layer_slug)
    return bool(binding and binding.get('managementEnabled'))


def activate_management(layer_slug: str, project_id: str, work_id: str, user_id: str) -> dict[str, Any]:
    bindings = _load_json(BINDINGS_PATH)
    from datetime import datetime, timezone
    bindings[layer_slug] = {
        'projectId': project_id,
        'workId': work_id,
        'managementEnabled': True,
        'activatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'activatedBy': user_id,
    }
    _save_bindings(bindings)
    return bindings[layer_slug]


def registry_snapshot() -> dict[str, Any]:
    return _load_json(REGISTRY_PATH)
