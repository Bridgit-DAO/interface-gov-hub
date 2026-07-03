"""Per-layer product feature overrides merged with global product rollout."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from flask import abort

from models import Layer
from services.product_rollout import FEATURE_KEYS, get_rollout_config

# Every site-wide product feature can be turned off per layer.
LAYER_OVERRIDABLE_FEATURES = frozenset(FEATURE_KEYS)

LAYER_FEATURE_LABELS: Dict[str, str] = {
    'layers': 'Layer surfaces (detail tabs, scoped nav)',
    'docs': 'Docs & drafts',
    'roles': 'Roles, clusters & claims',
    'workgroups': 'Workgroups',
    'guilds': 'Guilds (affiliation, directory)',
    'badges': 'Badges',
    'waitlists': 'Waitlists (tabs, admin, embed)',
    'immortalize': 'Immortalize (Bitcoin inscription, submit tab, /immortalize/)',
    'votes': 'Votes',
    'artifacts': 'Artifacts & monuments',
    'quests': 'Quests (create, list, guild links, open quests in opportunities)',
    'opportunities': 'Opportunities',
    'bridges': 'Bridges',
    'admin': 'Site admin UI (global; rarely off per layer)',
    'civic_mason': 'Civic Mason',
    'soft_launch': 'Soft-launch demo',
}

# Stable display order in layer Admin → Product features
LAYER_FEATURE_ORDER: List[str] = list(FEATURE_KEYS)

# Layer detail tab id → product feature key
LAYER_TAB_FEATURE: Dict[str, str] = {
    'workgroups': 'workgroups',
    'docs': 'docs',
    'clusters': 'roles',
    'roles': 'roles',
    'claims': 'roles',
    'votes': 'votes',
    'artifacts': 'artifacts',
    'opportunities': 'opportunities',
}


def _normalize_rollout_key(k: Any) -> Optional[str]:
    if not isinstance(k, str) or not k.strip():
        return None
    s = k.strip().lower().replace('-', '_')
    if s in FEATURE_KEYS:
        return s
    return None


def parse_layer_enabled_features(layer: Optional[Layer]) -> Dict[str, bool]:
    """
    Layer-stored overrides. Empty/null → no overrides (all layer-local flags True).
    Only explicit false values disable; unknown keys ignored.
    """
    if not layer:
        return {}
    raw = getattr(layer, 'enabled_features', None)
    if not raw or not str(raw).strip():
        return {}
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    out: Dict[str, bool] = {}
    for k, v in parsed.items():
        nk = _normalize_rollout_key(k)
        if nk is None or nk not in LAYER_OVERRIDABLE_FEATURES:
            continue
        if isinstance(v, bool):
            out[nk] = v
        elif isinstance(v, str):
            out[nk] = v.strip().lower() in ('1', 'true', 'yes', 'on')
        elif isinstance(v, (int, float)) and v in (0, 1):
            out[nk] = bool(int(v))
    return out


def layer_enabled_features_to_json(overrides: Dict[str, bool]) -> Optional[str]:
    """Persist only explicit overrides (typically false). None = clear all overrides."""
    if not overrides:
        return None
    clean = {
        k: bool(overrides[k])
        for k in sorted(overrides)
        if k in LAYER_OVERRIDABLE_FEATURES
    }
    if not clean:
        return None
    return json.dumps(clean, sort_keys=True)


def merge_rollout_with_layer(
    global_cfg: Dict[str, bool],
    layer: Optional[Layer],
) -> Dict[str, bool]:
    """effective[feat] = global[feat] AND layer_override[feat] (default True at layer)."""
    merged = dict(global_cfg)
    if not layer:
        return merged
    overrides = parse_layer_enabled_features(layer)
    for feat in FEATURE_KEYS:
        if feat in overrides and not overrides[feat]:
            merged[feat] = False
    return merged


def get_effective_features(
    layer: Optional[Layer] = None,
    *,
    global_cfg: Optional[Dict[str, bool]] = None,
) -> Dict[str, bool]:
    """Merged global + per-layer flags for the current request context."""
    gcfg = global_cfg if global_cfg is not None else get_rollout_config()
    if layer is None:
        try:
            from flask import g, has_request_context

            if has_request_context():
                layer = getattr(g, 'layer', None)
        except Exception:
            layer = None
    return merge_rollout_with_layer(gcfg, layer)


def is_feature_enabled_for_layer(
    name: str,
    layer: Optional[Layer] = None,
    *,
    global_cfg: Optional[Dict[str, bool]] = None,
) -> bool:
    key = _normalize_rollout_key(name)
    if not key:
        return True
    eff = get_effective_features(layer, global_cfg=global_cfg)
    return bool(eff.get(key, True))


def is_layer_tab_enabled(tab_key: str, effective: Dict[str, bool]) -> bool:
    """tab_key: workgroups, clusters, roles, claims, votes, artifacts, opportunities."""
    feat = LAYER_TAB_FEATURE.get(tab_key)
    if not feat:
        return True
    return bool(effective.get(feat, True))


def require_layer_feature(
    name: str,
    layer: Optional[Layer] = None,
    *,
    http_status: int = 404,
) -> None:
    """Abort with 404 if feature disabled (global or layer)."""
    if not is_feature_enabled_for_layer(name, layer):
        abort(http_status)


def resolve_layer_from_path(path: str) -> Optional[Layer]:
    """Best-effort layer for rollout when g.layer is not set yet."""
    p = (path or '/').rstrip('/') or '/'
    parts = [x for x in p.split('/') if x]
    if not parts:
        return None
    slug_or_id = None
    if parts[0] == 'layer' and len(parts) >= 2:
        slug_or_id = parts[1]
    elif parts[0] == 'layers' and len(parts) >= 2 and parts[1] not in ('create',):
        slug_or_id = parts[1]
    elif parts[0] == 'api' and len(parts) >= 3 and parts[1] == 'layers':
        slug_or_id = parts[2]
    if not slug_or_id:
        return None
    from services.utils import _is_uuid_like

    if _is_uuid_like(slug_or_id):
        return Layer.query.filter_by(public_id=slug_or_id).first() or Layer.query.get(slug_or_id)
    return Layer.query.filter_by(slug=slug_or_id).first()


def validate_layer_features_patch(
    data: Any,
    *,
    global_cfg: Optional[Dict[str, bool]] = None,
) -> Tuple[Optional[Dict[str, bool]], Optional[str]]:
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, 'enabled_features must be a JSON object'
    gcfg = global_cfg if global_cfg is not None else get_rollout_config()
    out: Dict[str, bool] = {}
    for k, v in data.items():
        nk = _normalize_rollout_key(k)
        if nk is None or nk not in LAYER_OVERRIDABLE_FEATURES:
            return None, f'Unknown or non-overridable feature: {k!r}'
        if not isinstance(v, bool):
            return None, f'Feature {nk!r} must be a boolean'
        if not gcfg.get(nk, True):
            return None, f'Feature {nk!r} is not enabled site-wide'
        if v is False:
            out[nk] = False
    return out, None
