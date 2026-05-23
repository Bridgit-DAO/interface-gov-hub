"""Site locale: session + ?lang= query (client JSON i18n)."""
from __future__ import annotations

# BCP-47 style tags used in /static/i18n/shell/{locale}.json filenames
SUPPORTED_LOCALES: frozenset[str] = frozenset(
    {'en', 'ar', 'fr', 'pt', 'zh-Hans', 'ja', 'ru'}
)


def normalize_lang_param(raw: str | None) -> str | None:
    """Map query ?lang= value to a supported locale tag, or None."""
    if not raw:
        return None
    s = raw.strip().replace('_', '-')
    low = s.lower()

    # Mandarin / Simplified Chinese aliases
    if low in ('zh', 'zh-cn', 'zhcn', 'cmn', 'zh-hans-cn', 'zh-hans', 'zh-hans-cn'):
        return 'zh-Hans'

    # Portuguese (any region → pt bundle)
    if low == 'pt' or low.startswith('pt-'):
        return 'pt'

    if low in ('en', 'ar', 'fr', 'ja', 'ru'):
        return low

    # Exact supported tags with correct casing
    for loc in SUPPORTED_LOCALES:
        if loc.lower() == low:
            return loc

    return None


def locale_to_i18n_key_suffix(locale: str) -> str:
    """JSON key segment for lang.names.* (no hyphens in dotted keys)."""
    return locale.replace('-', '_')


def resolve_request_locale() -> str:
    """Read ?lang=, update session, set flask.g.locale. Call from before_request."""
    from flask import g, request, session

    lang = request.args.get('lang')
    if lang:
        norm = normalize_lang_param(lang)
        if norm:
            session['locale'] = norm
            session.modified = True

    # Migrate legacy Civic Mason–only session key
    if not session.get('locale') and session.get('cm_locale'):
        cm = normalize_lang_param(session.get('cm_locale') or '') or session.get('cm_locale')
        if cm in SUPPORTED_LOCALES:
            session['locale'] = cm
            session.modified = True

    loc = session.get('locale') or 'en'
    if loc not in SUPPORTED_LOCALES:
        loc = 'en'
    g.locale = loc
    return loc
