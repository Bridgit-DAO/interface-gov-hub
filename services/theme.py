"""Theme preference helpers (light / dark / auto)."""
from __future__ import annotations

from typing import Dict, Optional

VALID_THEME_PREFERENCES = frozenset({'light', 'dark', 'auto'})


def normalize_theme_preference(value: Optional[str], *, default: str = 'dark') -> str:
    pref = (value or '').strip().lower()
    if pref in VALID_THEME_PREFERENCES:
        return pref
    return default if default in VALID_THEME_PREFERENCES else 'dark'


def effective_theme_from_preference(preference: str) -> str:
    """Map stored preference to data-theme value used by CSS (light or dark only)."""
    pref = normalize_theme_preference(preference)
    if pref == 'auto':
        # SSR default; client head script + gh-theme.js apply OS preference.
        return 'dark'
    return pref


def theme_template_context(
    *,
    explicit_preference: Optional[str] = None,
    current_user: Optional[dict] = None,
    session_theme: Optional[str] = None,
) -> Dict[str, str]:
    pref = 'dark'
    if current_user and current_user.get('theme') in VALID_THEME_PREFERENCES:
        pref = current_user['theme']
    elif session_theme in VALID_THEME_PREFERENCES:
        pref = session_theme
    elif explicit_preference in VALID_THEME_PREFERENCES:
        pref = explicit_preference
    effective = effective_theme_from_preference(pref)
    return {
        'theme_preference': pref,
        'theme_effective': effective,
        'theme': effective,
        'user_theme_preference_meta': pref if current_user else '',
    }
