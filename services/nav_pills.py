"""Nav pill micro-animations, newcomer tips, and per-layer / site-wide configuration."""
from __future__ import annotations

import html as html_mod
import json
from typing import Any, Dict, List, Optional, Tuple

from models import Layer

NAV_PILL_SITE_CONFIG_KEY = 'nav_pill_config'

PILL_ANIMATIONS: Dict[str, Dict[str, str]] = {
    'none': {
        'label': 'None',
        'description': 'Static pills — no motion.',
    },
    'hover-grow': {
        'label': 'Grow on hover',
        'description': 'Pills scale up slightly when hovered.',
    },
    'hover-glow': {
        'label': 'Glow on hover',
        'description': 'Soft blue glow appears on hover.',
    },
    'hover-lift': {
        'label': 'Lift on hover',
        'description': 'Pills rise slightly on hover.',
    },
    'breathing': {
        'label': 'Breathing (continuous)',
        'description': 'Active pill gently pulses; others breathe on hover.',
    },
    'shimmer': {
        'label': 'Shimmer (continuous)',
        'description': 'Active pill has a slow gradient shimmer.',
    },
}

PILL_ANIMATION_IDS: Tuple[str, ...] = tuple(PILL_ANIMATIONS.keys())

DEFAULT_SITE_NAV_PILL_CONFIG: Dict[str, Any] = {
    'pages': {
        'layer': True,
        'badges': True,
    },
    'tooltips_enabled': True,
    'default_animation': 'hover-grow',
}

LAYER_TAB_TIPS: Dict[str, str] = {
    'overview': 'Your layer home — overview stats, carousel highlights, and quick entry points.',
    'workgroups': 'Teams that organize ongoing work inside this layer.',
    'docs': 'Every draft and document submitted to this layer — approved, pending, or in revision.',
    'clusters': 'Role clusters group related positions and responsibilities.',
    'roles': 'Operational roles people can discover, claim, or be assigned.',
    'claims': 'Track who holds which roles and pending role claims.',
    'votes': 'Elections and decision votes for this layer.',
    'artifacts': 'Knowledge objects — proposals, evidence, and submissions.',
    'opportunities': 'Open drafts, quests, and ways to contribute right now.',
    'admin': 'Layer administration — features, admins, waitlists, and settings.',
}

BADGE_TAB_TIPS: Dict[str, str] = {
    'all': 'Browse every badge in the directory.',
    'mine': 'Badges you have earned or been awarded.',
    'layer': 'Badges associated with this layer.',
}


def _coerce_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(val, (int, float)) and val in (0, 1):
        return bool(int(val))
    return default


def parse_nav_pill_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def normalize_site_nav_pill_config(raw: Any) -> Dict[str, Any]:
    src = parse_nav_pill_config(raw)
    pages_src = src.get('pages') if isinstance(src.get('pages'), dict) else {}
    animation = str(src.get('default_animation') or DEFAULT_SITE_NAV_PILL_CONFIG['default_animation'])
    if animation not in PILL_ANIMATIONS:
        animation = DEFAULT_SITE_NAV_PILL_CONFIG['default_animation']
    return {
        'pages': {
            'layer': _coerce_bool(pages_src.get('layer'), True),
            'badges': _coerce_bool(pages_src.get('badges'), True),
        },
        'tooltips_enabled': _coerce_bool(
            src.get('tooltips_enabled'),
            DEFAULT_SITE_NAV_PILL_CONFIG['tooltips_enabled'],
        ),
        'default_animation': animation,
    }


def normalize_layer_nav_pill_config(raw: Any) -> Dict[str, Any]:
    src = parse_nav_pill_config(raw)
    animation = src.get('animation')
    out: Dict[str, Any] = {}
    if isinstance(animation, str) and animation in PILL_ANIMATIONS:
        out['animation'] = animation
    if 'tooltips_enabled' in src:
        out['tooltips_enabled'] = _coerce_bool(src.get('tooltips_enabled'))
    return out


def get_site_nav_pill_config() -> Dict[str, Any]:
    from models import SiteConfig

    row = SiteConfig.query.filter_by(key=NAV_PILL_SITE_CONFIG_KEY).first()
    if not row or not (row.value or '').strip():
        return dict(DEFAULT_SITE_NAV_PILL_CONFIG)
    return normalize_site_nav_pill_config(row.value)


def set_site_nav_pill_config(cfg: Dict[str, Any]) -> None:
    from extensions import db
    from models import SiteConfig

    normalized = normalize_site_nav_pill_config(cfg)
    payload = json.dumps(normalized, sort_keys=True)
    row = SiteConfig.query.filter_by(key=NAV_PILL_SITE_CONFIG_KEY).first()
    if row:
        row.value = payload
    else:
        db.session.add(SiteConfig(key=NAV_PILL_SITE_CONFIG_KEY, value=payload))
    db.session.commit()


def parse_layer_nav_pill_config(layer: Optional[Layer]) -> Dict[str, Any]:
    if not layer:
        return {}
    return normalize_layer_nav_pill_config(getattr(layer, 'nav_pill_config', None))


def get_effective_nav_pill_settings(
    *,
    page: str,
    layer: Optional[Layer] = None,
) -> Dict[str, Any]:
    """Resolved animation + tooltip flags for a nav pill surface."""
    site = get_site_nav_pill_config()
    pages = site.get('pages') or {}
    enabled = bool(pages.get(page, True))
    layer_cfg = parse_layer_nav_pill_config(layer)
    animation = layer_cfg.get('animation') or site.get('default_animation') or 'hover-grow'
    if animation not in PILL_ANIMATIONS:
        animation = 'hover-grow'
    tooltips = site.get('tooltips_enabled', True)
    if 'tooltips_enabled' in layer_cfg:
        tooltips = bool(layer_cfg['tooltips_enabled'])
    return {
        'enabled': enabled,
        'animation': animation,
        'tooltips_enabled': tooltips,
        'page': page,
    }


def layer_tab_tip(tab_id: str) -> str:
    return LAYER_TAB_TIPS.get(tab_id, '')


def validate_layer_nav_pill_patch(data: Any) -> Tuple[Optional[dict], Optional[str]]:
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, 'nav_pill_config must be a JSON object'
    out = normalize_layer_nav_pill_config(data)
    if 'animation' in data:
        anim = data.get('animation')
        if anim is not None and str(anim) not in PILL_ANIMATIONS:
            return None, f'animation must be one of: {", ".join(PILL_ANIMATION_IDS)}'
    return out, None


def nav_pills_container_attrs(settings: Dict[str, Any], *, context_id: str = '') -> str:
    if not settings.get('enabled'):
        return ''
    anim = html_mod.escape(str(settings.get('animation') or 'hover-grow'), quote=True)
    tips = 'true' if settings.get('tooltips_enabled') else 'false'
    ctx = html_mod.escape(context_id or '', quote=True)
    return (
        f' data-gh-nav-pills data-gh-nav-animation="{anim}"'
        f' data-gh-nav-tooltips="{tips}" data-gh-nav-context="{ctx}"'
    )


def nav_pill_button_attrs(tab_id: str, tip: str) -> str:
    if not tip:
        return f' data-gh-pill-id="{html_mod.escape(tab_id, quote=True)}"'
    tip_esc = html_mod.escape(tip, quote=True)
    tab_esc = html_mod.escape(tab_id, quote=True)
    return f' data-gh-pill-id="{tab_esc}" data-gh-pill-tip="{tip_esc}"'
