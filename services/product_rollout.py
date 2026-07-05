"""Product rollout: feature toggles stored in `SiteConfig` (key `product_rollout`, JSON object).

Call sites (nav, route decorators, APIs) should use `is_feature_enabled`.
Unknown feature names default to True so new code paths are safe until configured.

Admin UI: /admin/product-rollout/
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from extensions import db
from models import SiteConfig

PRODUCT_ROLLOUT_SITE_CONFIG_KEY = 'product_rollout'

# Known toggles: merge order, DB JSON overrides, then per-key future extension.
# This order is also used when two flags block the same request – the first listed here wins
# in `should_block_path_request` (returned in API/body as `feature`).
FEATURE_KEYS: List[str] = [
    'layers',
    'docs',
    'roles',
    'workgroups',
    'guilds',
    'badges',
    'waitlists',
    'immortalize',
    'admin',
    'civic_mason',
    'soft_launch',
    'votes',
    'artifacts',
    'quests',
    'bridges',
    'opportunities',
    'patches',
]

# Features off until explicitly enabled in Product rollout (site-wide).
_FEATURE_OFF_BY_DEFAULT = frozenset({'immortalize', 'patches'})

# When no `product_rollout` row exists, legacy features stay on; new gated features stay off.
_LEGACY_ALL_ENABLED: Dict[str, bool] = {
    k: (k not in _FEATURE_OFF_BY_DEFAULT) for k in FEATURE_KEYS
}

# When a row exists, merge with this so new keys get sensible defaults
_DEFAULTS_WHEN_ROW_EXISTS: Dict[str, bool] = {
    k: (k not in _FEATURE_OFF_BY_DEFAULT) for k in FEATURE_KEYS
}


# Optional aliases so hand-edited JSON with camelCase still maps to FEATURE_KEYS.
_ROLLOUT_KEY_ALIASES: Dict[str, str] = {
    'softlaunch': 'soft_launch',
    'civicmason': 'civic_mason',
    'dp_proposals': 'patches',
    'document_edits': 'patches',
}


def _normalize_rollout_key(k: Any) -> Optional[str]:
    if not isinstance(k, str) or not k.strip():
        return None
    s = k.strip().lower().replace('-', '_')
    s = _ROLLOUT_KEY_ALIASES.get(s, s)
    if s in FEATURE_KEYS:
        return s
    return None


def _coerce_bool_map(raw: Any) -> Dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, bool] = {}
    for k, v in raw.items():
        nk = _normalize_rollout_key(k)
        if nk is None:
            continue
        if isinstance(v, bool):
            bool_val = v
        elif isinstance(v, (int, float)) and v in (0, 1):
            bool_val = bool(int(v))
        elif isinstance(v, str):
            bool_val = v.strip().lower() in ('1', 'true', 'yes', 'on')
        else:
            continue
        if nk == 'patches' and nk in out:
            out[nk] = out[nk] or bool_val
        else:
            out[nk] = bool_val
    return out


def get_rollout_config() -> Dict[str, bool]:
    """Return merged rollout flags. If no DB row, all known features are True."""
    row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
    if not row or not (row.value or '').strip():
        return dict(_LEGACY_ALL_ENABLED)

    try:
        parsed = json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return dict(_DEFAULTS_WHEN_ROW_EXISTS)

    coerced = _coerce_bool_map(parsed)
    merged = dict(_DEFAULTS_WHEN_ROW_EXISTS)
    merged.update(coerced)
    return merged


def is_feature_enabled(
    name: str,
    *,
    layer_id: Optional[str] = None,
    layer: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> bool:
    """
    True if the named product feature is enabled (global rollout ∧ per-layer overrides).

    Pass `layer` or `layer_id` when checking in layer context; otherwise uses Flask `g.layer`
    when in a request.
    """
    _ = user_id  # reserved for future cohort gating

    if not name or not str(name).strip():
        return True
    key = str(name).strip().lower().replace('-', '_')
    key = _ROLLOUT_KEY_ALIASES.get(key, key)

    from services.layer_features import get_effective_features

    resolved_layer = layer
    if resolved_layer is None and layer_id:
        from models import Layer as LayerModel

        resolved_layer = LayerModel.query.get(layer_id)
        if not resolved_layer:
            resolved_layer = LayerModel.query.filter_by(slug=layer_id).first()

    cfg = get_effective_features(resolved_layer)
    if key in cfg:
        return bool(cfg[key])
    return True


def set_rollout_config(partial: Dict[str, bool]) -> None:
    """
    Replace stored rollout: defaults merged with `partial` (known feature keys, bools only).
    Commits the session.
    """
    base = dict(_DEFAULTS_WHEN_ROW_EXISTS)
    for k in FEATURE_KEYS:
        if k in partial and isinstance(partial[k], bool):
            base[k] = partial[k]
    row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
    payload = json.dumps(base, sort_keys=True)
    if row:
        row.value = payload
    else:
        db.session.add(
            SiteConfig(
                key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY,
                value=payload,
            )
        )
    db.session.commit()


def rollout_config_to_json_stored() -> str:
    """Current effective config as pretty JSON (for display)."""
    return json.dumps(get_rollout_config(), indent=2, sort_keys=True)


# --- HTTP path gating (used by app before_request) ---

# Paths that skip rollout checks entirely (static assets, auth entry points, embeds).
# Admin UI, civic-mason, soft-launch, etc. are gated by feature flags instead.
EXEMPT_ROLLOUT_PATH_PREFIXES: tuple = (
    '/static/',
    '/favicon',
    '/login',
    '/logout',
    '/register',
    '/_deploy/',
    '/embed/',
    '/auth/',  # OAuth callback paths
    '/api/invitations/by-token/',  # invite preview (token is secret)
)

EXEMPT_ROLLOUT_EXACT: frozenset = frozenset({'/favicon.ico'})


def _path_is_strict_prefix(path: str, prefix: str) -> bool:
    """
    True if path is exactly `prefix` or a deeper path under it (prefix + '/' + …).
    Avoids startswith false positives, e.g. /soft-launching must not match /soft-launch.
    """
    p = path or '/'
    if p == prefix:
        return True
    return p.startswith(prefix + '/')


def _is_product_rollout_bootstrap_path(path: str) -> bool:
    """Allow toggling the admin flag off without losing access to this page."""
    base = (path or '/').rstrip('/') or '/'
    return base == '/admin/product-rollout'


def _path_needs_guilds(path: str) -> bool:
    if _path_is_strict_prefix(path, '/guilds'):
        return True
    if _path_is_strict_prefix(path, '/api/guilds'):
        return True
    if path.startswith('/api/layers/') and '/guilds/' in path:
        return True
    return False


def _path_needs_badges_api(path: str) -> bool:
    if not path.startswith('/api/'):
        return False
    if path.startswith('/api/badges/'):
        return True
    if path.startswith('/api/one-time-badges'):
        return True
    if path.startswith('/api/badge-skins'):
        return True
    if '/badges/' in path:
        return True
    return False


def _path_needs_roles_api(path: str) -> bool:
    """Role/cluster/claim APIs (badge grant routes also hit /claims/…/badges/ – they add `badges` via path match)."""
    if not path.startswith('/api/'):
        return False
    if path.startswith('/api/roles/'):
        return True
    if path.startswith('/api/clusters/'):
        return True
    if path.startswith('/api/role-images'):
        return True
    if path.startswith('/api/claims/'):
        return True
    if path.startswith('/api/layers/') and ('/clusters/' in path or '/roles/' in path):
        return True
    return False


def _path_needs_docs(path: str) -> bool:
    p = path or '/'
    if p.startswith('/doc'):
        return True
    if p.startswith('/api/annotations'):
        return True
    if '/doc/' in p:
        return True
    if '/layer/' in p or '/layers/' in p:
        if p.rstrip('/').endswith('/doc'):
            return True
    return False


def _path_needs_civic_mason(p: str) -> bool:
    return _path_is_strict_prefix(p, '/civic-mason') or _path_is_strict_prefix(
        p, '/api/civic-mason'
    )


def _path_needs_soft_launch(p: str) -> bool:
    return _path_is_strict_prefix(p, '/soft-launch') or _path_is_strict_prefix(
        p, '/api/soft-launch'
    )


def _path_needs_votes(p: str) -> bool:
    if _path_is_strict_prefix(p, '/votes'):
        return True
    if _path_is_strict_prefix(p, '/api/votes'):
        return True
    if p.startswith('/api/') and '/votes/' in p:
        return True
    return False


def _path_needs_bridges(p: str) -> bool:
    return _path_is_strict_prefix(p, '/bridges') or _path_is_strict_prefix(
        p, '/api/bridges'
    )


def _path_needs_immortalize(p: str) -> bool:
    if _path_is_strict_prefix(p, '/immortalize'):
        return True
    if _path_is_strict_prefix(p, '/inscribe'):
        return True
    if '/submit/immortalize' in p:
        return True
    # /api/ordinal/preview and /api/ordinal/convert-markdown are used by draft submit
    # ("From Ordinal" tab) and must stay available when only Immortalize is disabled.
    if p.startswith('/api/inscribe'):
        return True
    if p.startswith('/api/inscription'):
        return True
    return False


def _path_needs_waitlists(p: str) -> bool:
    if p == '/waitlists' or p.startswith('/waitlists/'):
        return True
    if p.startswith('/api/waitlists/'):
        return True
    if p.startswith('/waitlist/'):
        return True
    if '/waitlist/' in p and p.startswith('/layers/'):
        return True
    if p.startswith('/layer/') and '/waitlists' in p:
        return True
    if p.startswith('/api/layers/') and '/waitlists/' in p:
        return True
    if p.startswith('/embed/waitlist/'):
        return True
    return False


def _path_needs_opportunities(p: str) -> bool:
    if p == '/opportunities' or p.startswith('/opportunities/'):
        return True
    if p.startswith('/layer/') and '/opportunities/' in p:
        return True
    if p.startswith('/api/layers/') and '/opportunities/' in p:
        return True
    return False


def _path_needs_quests(p: str) -> bool:
    if p.startswith('/api/quests/'):
        return True
    if p.startswith('/api/guilds/') and '/quest-links/' in p:
        return True
    if p.startswith('/api/layers/') and '/quests/' in p:
        return True
    if p.startswith('/layers/') and '/quests/' in p:
        return True
    if p.startswith('/layer/') and '/quests/' in p:
        return True
    return False


def _path_needs_artifacts(p: str) -> bool:
    """Artifact/monument/collection surfaces (quests and opportunities are separate)."""
    if _path_needs_opportunities(p) or _path_needs_quests(p):
        return False
    if p == '/artifacts' or p.startswith('/artifacts/'):
        return True
    if p.startswith('/layer/') and '/artifacts/' in p:
        return True
    if p.startswith('/layers/') and '/artifacts/' in p:
        return True
    if p.startswith('/api/artifacts/'):
        return True
    if p.startswith('/api/monuments/'):
        return True
    if p.startswith('/api/knowledge-layer/'):
        return True
    if p.startswith('/api/submissions/') and 'ensure-artifact' in p:
        return True
    if p.startswith('/api/collections/'):
        return True
    if p.startswith('/api/') and '/collections/' in p:
        return True
    if p.startswith('/api/layers/') and any(
        x in p
        for x in (
            '/artifacts/',
            '/artifact-relations/',
            '/artifact-tags/',
            '/layer-tags/',
            '/monuments/',
        )
    ):
        return True
    return False


def _path_needs_patches(p: str) -> bool:
    if p.startswith('/admin/dp-proposals'):
        return True
    if p.startswith('/dp-challenge'):
        return True
    if p.startswith('/api/dp-challenge'):
        return True
    if p.startswith('/suggest-edit'):
        return True
    if p.startswith('/api/suggest-edit'):
        return True
    if p.startswith('/api/doc/draft/') and ('/proposals/' in p or p.endswith('/read-meta/')):
        return True
    return False


def _path_needs_admin(p: str) -> bool:
    if p in ('/admin', '/admin/'):
        return True
    if not p.startswith('/admin/'):
        return False
    return not _is_product_rollout_bootstrap_path(p)


def path_requires_feature_flags(path: str) -> set:
    """
    Set of product feature names that must be enabled for this path.
    Exempt and bootstrap paths return an empty set (always allowed to proceed).
    """
    p = path or '/'
    if p in EXEMPT_ROLLOUT_EXACT:
        return set()
    for prefix in EXEMPT_ROLLOUT_PATH_PREFIXES:
        if p.startswith(prefix):
            return set()
    if _is_product_rollout_bootstrap_path(p):
        return set()

    need: set = set()
    if _path_needs_admin(p):
        need.add('admin')
    if _path_needs_civic_mason(p):
        need.add('civic_mason')
    if _path_needs_soft_launch(p):
        need.add('soft_launch')
    if _path_needs_votes(p):
        need.add('votes')
    if _path_needs_artifacts(p):
        need.add('artifacts')
    if _path_needs_bridges(p):
        need.add('bridges')
    if _path_needs_opportunities(p):
        need.add('opportunities')
    if _path_needs_quests(p):
        need.add('quests')
    if _path_needs_docs(p):
        need.add('docs')
    if _path_needs_waitlists(p):
        need.add('waitlists')
    if _path_needs_immortalize(p):
        need.add('immortalize')
    if _path_needs_patches(p):
        need.add('patches')
    is_layer = p.startswith('/layer/') or p.startswith('/layers/') or p.startswith('/api/layers/')
    if is_layer:
        need.add('layers')
    if p.startswith('/workgroups/') or '/workgroups/' in p:
        need.add('workgroups')
    if _path_needs_guilds(p):
        need.add('guilds')
    if p.startswith('/badges/') or p.startswith('/admin/badges'):
        need.add('badges')
    if p.startswith('/roles/') or _path_needs_roles_api(p):
        need.add('roles')
    if _path_needs_badges_api(p):
        need.add('badges')
    return need


def _blocked_layer_list_json_response(path: str, feature: str):
    """
    For GET layer list APIs, return an empty collection instead of 403 so global
    directories can aggregate across layers with per-layer features off.
    """
    from flask import jsonify, request

    if request.method != 'GET':
        return None
    p = (path or '').split('?', 1)[0]
    if not p.startswith('/api/layers/'):
        return None
    if feature == 'roles':
        if p.endswith('/roles/'):
            return jsonify({'roles': [], 'count': 0}), 200
        if p.endswith('/clusters/'):
            return jsonify({'clusters': [], 'count': 0}), 200
        if p.endswith('/claims/'):
            return jsonify({'claims': [], 'count': 0}), 200
    if feature == 'workgroups' and p.endswith('/workgroups/'):
        return jsonify({'workgroups': [], 'count': 0}), 200
    if feature == 'waitlists' and p.endswith('/waitlists/'):
        return jsonify({'waitlists': [], 'count': 0}), 200
    if feature == 'guilds' and p.endswith('/guilds/'):
        return jsonify({'guilds': [], 'count': 0}), 200
    if feature == 'quests':
        if p.endswith('/quests/'):
            return jsonify({'quests': [], 'count': 0}), 200
        if p.startswith('/api/guilds/') and p.endswith('/quest-links/'):
            return jsonify({'links': []}), 200
    return None


def should_block_path_request(path: str, cfg: Dict[str, bool]) -> Optional[str]:
    """
    If the path should be blocked, return the first disabled feature name; else None.
    Order follows FEATURE_KEYS so the reported `feature` is deterministic, not set-order.
    """
    need = path_requires_feature_flags(path)
    for feat in FEATURE_KEYS:
        if feat in need and not cfg.get(feat, True):
            return feat
    return None


def apply_product_rollout_before_request() -> Any:
    """
    Intended for Flask before_request: set g.product_rollout, block closed features.
    Returns a Flask response to short-circuit, or None to continue.
    """
    from flask import g, jsonify, make_response, request
    from services.layer_features import get_effective_features, resolve_layer_from_path

    global_cfg = get_rollout_config()
    path = request.path or '/'
    layer = getattr(g, 'layer', None) if hasattr(g, 'layer') else None
    if layer is None:
        layer = resolve_layer_from_path(path)
    cfg = get_effective_features(layer, global_cfg=global_cfg)
    g.product_rollout = cfg
    g.product_rollout_global = global_cfg
    if layer is not None:
        g.layer = layer

    if path.startswith('/static/') or path in EXEMPT_ROLLOUT_EXACT:
        return None
    for prefix in EXEMPT_ROLLOUT_PATH_PREFIXES:
        if path.startswith(prefix):
            return None

    blocked = should_block_path_request(path, cfg)
    if not blocked:
        tab = (request.args.get('tab') or '').strip().lower()
        if tab == 'immortalize' and not cfg.get('immortalize', True):
            blocked = 'immortalize'
    if blocked == 'workgroups' and request.method == 'GET':
        p = (path or '').split('?', 1)[0]
        if p.startswith('/api/layers/') and p.endswith('/workgroups/'):
            from services.workgroup_links import layer_has_secondary_workgroups

            layer_id = layer.id if layer is not None else None
            if layer_id and layer_has_secondary_workgroups(layer_id):
                blocked = None
    if not blocked:
        return None

    if path.startswith('/api/') or request.headers.get('Accept', '').startswith('application/json'):
        empty_list = _blocked_layer_list_json_response(path, blocked)
        if empty_list is not None:
            return empty_list
        return (
            jsonify(
                {
                    'error': 'This feature is not available right now.',
                    'error_code': 'FEATURE_DISABLED',
                    'feature': blocked,
                }
            ),
            403,
        )
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Not available</title>
</head><body class="p-4" style="font-family: system-ui, sans-serif;">
  <h1>Not available</h1>
  <p style="color:#666">This part of the product is not available right now.</p>
  <p><a href="/">Back to home</a></p>
</body></html>"""
    return make_response(page, 403, {'Content-Type': 'text/html; charset=utf-8'})
