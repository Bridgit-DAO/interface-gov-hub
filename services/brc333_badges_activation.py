"""Activate and bind Gov Hub layers to ordinal badges projects."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from config import PROJECT_ROOT
from extensions import db
from models import Layer
from services.brc333_badges_registry import list_projects
from services.brc333_management import management_enabled
from services.events import emit_event
from services.layer_features import (
    layer_enabled_features_to_json,
    merge_rollout_with_layer,
    parse_layer_enabled_features,
)
from services.product_rollout import get_rollout_config

BINDINGS_PATH = os.path.join(PROJECT_ROOT, 'data', 'brc333_layer_bindings.json')
TEMPLATE_PROJECT_ID = 'metaweb-academy-ordinal'


def _load_bindings() -> dict[str, Any]:
    if not os.path.isfile(BINDINGS_PATH):
        return {}
    with open(BINDINGS_PATH, encoding='utf-8') as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def _save_bindings(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(BINDINGS_PATH), exist_ok=True)
    tmp = BINDINGS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, BINDINGS_PATH)


def project_for_layer(layer_slug: str) -> dict[str, Any] | None:
    for proj in list_projects():
        if proj.get('layerSlug') == layer_slug:
            return proj
    return None


def layer_badges_status(layer_slug: str) -> dict[str, Any]:
    layer = Layer.query.filter_by(slug=layer_slug).first()
    proj = project_for_layer(layer_slug)
    bindings = _load_bindings()
    binding = bindings.get(layer_slug)
    global_cfg = get_rollout_config()
    effective = merge_rollout_with_layer(global_cfg, layer) if layer else global_cfg
    badges_on = bool(effective.get('badges', True))
    project_id = (binding or {}).get('projectId') or (proj or {}).get('id')
    admin_url = None
    if project_id and layer_slug and binding:
        admin_url = f'/layer/{layer_slug}/brc333-badges/{project_id}/'
    return {
        'layerSlug': layer_slug,
        'available': bool(proj),
        'activated': bool(binding),
        'managementEnabled': management_enabled(layer_slug),
        'projectId': project_id,
        'projectTitle': (proj or {}).get('title'),
        'adminUrl': admin_url,
        'previewBase': (proj or {}).get('previewBase'),
        'inventoryUrl': (
            f'{(proj or {}).get("previewBase")}/source-inventory.html' if proj else None
        ),
        'badgesFeatureEnabled': badges_on,
        'canActivate': bool(proj and layer),
    }


def activate_layer_badges(layer_slug: str, user_id: str) -> dict[str, Any]:
    layer = Layer.query.filter_by(slug=layer_slug).first()
    if not layer:
        raise ValueError('Layer not found')

    proj = project_for_layer(layer_slug)
    if not proj:
        raise ValueError(
            'No badges project is configured for this layer yet. '
            f'v1 supports the Metaweb Academy preset ({TEMPLATE_PROJECT_ID}).'
        )

    overrides = parse_layer_enabled_features(layer)
    if overrides.get('badges') is False:
        del overrides['badges']
    layer.enabled_features = layer_enabled_features_to_json(
        {k: v for k, v in overrides.items() if v is False}
    )
    layer.updated_at = datetime.utcnow()

    bindings = _load_bindings()
    bindings[layer_slug] = {
        'projectId': proj['id'],
        'activatedAt': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'activatedBy': user_id,
    }
    _save_bindings(bindings)

    work_id = proj.get('workId') or 'metaweb-academy'
    activate_management(layer_slug, proj['id'], work_id, user_id)

    emit_event(
        'brc333_badges_admin',
        actor_type='user',
        actor_id=user_id,
        subject_type='layer',
        subject_id=layer.id,
        layer_id=layer.id,
        payload={
            'action': 'badges_activated',
            'layer_slug': layer_slug,
            'project_id': proj['id'],
        },
    )
    db.session.commit()
    return layer_badges_status(layer_slug)
