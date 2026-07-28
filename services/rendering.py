"""Rendering services: _format_base_template, render_page, generate_user_menu."""
import html
import json
from flask import g, has_request_context, session, url_for

# Configured at app init (called from main file after BASE_TEMPLATE is defined)
_base_template = None
_font_awesome_link = ''
_build_number = 0


def configure_rendering(base_template, font_awesome_link, build_number):
    """Set template and constants for rendering. Call once at app init."""
    global _base_template, _font_awesome_link, _build_number
    _base_template = base_template
    _font_awesome_link = font_awesome_link
    _build_number = build_number


def render_flash_messages_html():
    """Render flashed messages for injection into BASE_TEMPLATE."""
    if not has_request_context():
        return ''
    from flask import get_flashed_messages

    category_class = {
        'success': 'flash-success',
        'error': 'flash-error',
        'warning': 'flash-info',
        'info': 'flash-info',
    }
    parts = []
    for category, message in get_flashed_messages(with_categories=True):
        css = category_class.get(category, 'flash-info')
        parts.append(
            f'<div class="flash-message {css}">{html.escape(message)}</div>'
        )
    return ''.join(parts)


def generate_lang_menu_html():
    """Language dropdown items: ?lang= on current path."""
    from flask import g, has_request_context, request, session
    from services.locale import SUPPORTED_LOCALES, locale_to_i18n_key_suffix

    path = request.path or '/'
    current = 'en'
    if has_request_context():
        current = getattr(g, 'locale', None) or session.get('locale') or 'en'
    if current not in SUPPORTED_LOCALES:
        current = 'en'

    # Stable order for the menu
    order = ['en', 'ar', 'fr', 'pt', 'zh-Hans', 'ja', 'ru']
    lines = []
    for code in order:
        if code not in SUPPORTED_LOCALES:
            continue
        sk = locale_to_i18n_key_suffix(code)
        active = code == current
        item_cls = 'dropdown-item active' if active else 'dropdown-item'
        aria = ' aria-current="true"' if active else ''
        check = ' <i class="fas fa-check ms-2 text-primary" aria-hidden="true"></i>' if active else ''
        lines.append(
            f'<li><a class="{item_cls}" href="{path}?lang={code}"{aria} '
            f'data-gh-i18n="lang.names.{sk}">{code}{check}</a></li>'
        )
    return '\n'.join(lines)


def generate_prefix_chip_html():
    """Render the #gh-prefix-chip-wrap dropdown for the navbar.

    The chip has been intentionally disabled and now always returns an
    empty string. The function is retained for backward compatibility
    with imports/tests; callers substitute ``''`` into their navbar
    slots via ``{prefix_chip_html}``. The dynamic-update script
    (``gh-layer-prefix.js``) is a safe no-op when the chip is absent.
    """
    return ''


def _product_rollout_flags():
    """Defaults all True when outside request or before g is set."""
    try:
        if has_request_context() and getattr(g, 'product_rollout', None) is not None:
            return g.product_rollout
    except Exception:
        pass
    from services.product_rollout import FEATURE_KEYS
    return {k: True for k in FEATURE_KEYS}


def _rollout_for_layer_slug(layer_slug=None):
    """Effective product flags for nav: per-layer when slug known, else request g.product_rollout."""
    if layer_slug:
        from models import Layer
        from services.layer_features import get_effective_features

        layer = Layer.query.filter_by(slug=layer_slug).first()
        if layer:
            return get_effective_features(layer)
    return _product_rollout_flags()


def generate_learn_nav_html(layer_slug=None):
    """Learn nav dropdown: hidden when `docs` rollout is off. Uses g.product_rollout when set."""
    r = _rollout_for_layer_slug(layer_slug)
    if not r.get('docs', True):
        return ''
    if layer_slug:
        href = '/layer/' + layer_slug + '/doc/'
    else:
        href = '/doc/all/'
    return (
        '<li class="nav-item dropdown">'
        '<a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" '
        'aria-expanded="false" data-gh-i18n="nav.learn">Learn</a>'
        '<ul class="dropdown-menu">'
        f'<li><a class="dropdown-item" href="{href}" data-gh-i18n="nav.docsDrafts">Docs &amp; Drafts</a></li>'
        '<li><a class="dropdown-item" href="/workgroups/join/" data-gh-i18n="nav.joinWorkgroup">Join Workgroup</a></li>'
        '</ul></li>'
    )


def generate_participate_nav_html(layer_slug=None):
    """Participate dropdown; waitlists link omitted when `waitlists` is off."""
    r = _rollout_for_layer_slug(layer_slug)
    if layer_slug:
        submit_href = '/layer/' + layer_slug + '/submit/'
        immortalize_href = '/layer/' + layer_slug + '/submit/immortalize/'
        waitlists_href = '/layer/' + layer_slug + '/waitlists/'
    else:
        submit_href = '/submit/'
        immortalize_href = '/immortalize/'
        waitlists_href = '/waitlists/'
    lines = []
    if r.get('patches', False):
        lines.append(
            '<li><a class="dropdown-item" href="/dp-challenge/" data-gh-i18n="nav.dpChallenge">'
            'DP Challenge</a></li>'
        )
        lines.append(
            '<li><a class="dropdown-item" href="/suggest-edit/" data-gh-i18n="nav.suggestEdit">'
            'Propose a Patch</a></li>'
        )
    lines.append(
        f'<li><a class="dropdown-item" href="{submit_href}" data-gh-i18n="nav.submitDraft">Submit Draft</a></li>'
    )
    if r.get('immortalize', True):
        lines.append(
            f'<li><a class="dropdown-item" href="{immortalize_href}" data-gh-i18n="nav.immortalize">Immortalize</a></li>'
        )
    if r.get('waitlists', True):
        lines.append(
            f'<li><a class="dropdown-item" href="{waitlists_href}" data-gh-i18n="nav.waitlists">Waitlists</a></li>'
        )
    return (
        '<li class="nav-item dropdown">'
        '<a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" '
        'aria-expanded="false" data-gh-i18n="nav.participate">Participate</a>'
        '<ul class="dropdown-menu">'
        + '\n'.join(lines)
        + '</ul></li>'
    )


def generate_community_nav_html(layer_slug=None):
    """Community dropdown; guilds link omitted when `guilds` is off."""
    r = _rollout_for_layer_slug(layer_slug)
    conn_slug = layer_slug
    mlgh_layer = False
    if not conn_slug and has_request_context():
        layer = getattr(g, 'layer', None)
        if layer:
            conn_slug = layer.slug
            mlgh_layer = True
    if layer_slug:
        people_href = '/layer/' + layer_slug + '/person/'
        guilds_href = '/layer/' + layer_slug + '/guilds/'
    else:
        people_href = '/person/'
        guilds_href = '/guilds/'
    lines = [
        f'<li><a class="dropdown-item" href="{people_href}" data-gh-i18n="nav.people">People</a></li>',
    ]
    if r.get('guilds', True):
        lines.append(
            f'<li><a class="dropdown-item" href="{guilds_href}" data-gh-i18n="nav.guilds">Guilds</a></li>'
        )
    if conn_slug:
        conn_prefix = '/layers/' if mlgh_layer else '/layer/'
        conn_href = conn_prefix + conn_slug + '/connections/'
        lines.append(
            f'<li><a class="dropdown-item" href="{conn_href}" data-gh-i18n="nav.connections">Connections</a></li>'
        )
    return (
        '<li class="nav-item dropdown">'
        '<a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" '
        'aria-expanded="false" data-gh-i18n="nav.community">Community</a>'
        '<ul class="dropdown-menu">'
        + '\n'.join(lines)
        + '</ul></li>'
    )


def generate_recognition_nav_html(layer_slug=None):
    """Recognition dropdown; hidden when badges and civic_mason are both off."""
    r = _rollout_for_layer_slug(layer_slug)
    lines = []
    if r.get('badges', True):
        href = '/layer/' + layer_slug + '/badges/' if layer_slug else '/badges/'
        lines.append(
            f'<li><a class="dropdown-item" href="{href}" data-gh-i18n="nav.badges">Badges</a></li>'
        )
    if r.get('civic_mason', True):
        lines.append(
            '<li><a class="dropdown-item" href="/civic-mason/" data-gh-i18n="nav.civicMason">Civic Mason</a></li>'
        )
    if not lines:
        return ''
    return (
        '<li class="nav-item dropdown">'
        '<a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" '
        'aria-expanded="false" data-gh-i18n="nav.recognition">Recognition</a>'
        '<ul class="dropdown-menu">'
        + '\n'.join(lines)
        + '</ul></li>'
    )


def generate_governance_nav(layer_slug=None, standalone=False):
    """Build Governance dropdown HTML. When layer_slug is set, use layer-scoped links and omit Layers.
    standalone=True: use /layer/<slug>/ URLs so nav stays in layer view.
    Respects product rollout (layers, docs, roles, workgroups, votes, …) via g.product_rollout."""
    r = _rollout_for_layer_slug(layer_slug)
    if layer_slug:
        base = '/layer/' + layer_slug if standalone else '/layers/' + layer_slug
        about_href = base + '/about/'
        docs_href = base + '/doc/' if standalone else '/doc/all/'
        lines = [
            '<li><a class="dropdown-item" href="' + about_href + '" data-gh-i18n="gov.about">About</a></li>',
        ]
        if r.get('roles', True):
            lines.append(
                '<li><a class="dropdown-item" href="' + base + '/roles/" data-gh-i18n="gov.roles">Roles</a></li>'
            )
        if r.get('workgroups', True):
            lines.append(
                '<li><a class="dropdown-item" href="' + base + '/workgroups/" data-gh-i18n="gov.workgroups">Workgroups</a></li>'
            )
        if r.get('votes', True):
            lines.append(
                '<li><a class="dropdown-item" href="'
                + base
                + '/votes/" data-gh-i18n="gov.votes">Votes</a></li>'
            )
        if r.get('artifacts', True):
            lines.append(
                '<li><a class="dropdown-item" href="'
                + base
                + '/artifacts/" data-gh-i18n="gov.artifacts">Artifacts</a></li>'
            )
        if r.get('opportunities', True):
            lines.append(
                '<li><a class="dropdown-item" href="'
                + base
                + '/opportunities/" data-gh-i18n="gov.opportunities">Opportunities</a></li>'
            )
        if r.get('docs', True):
            lines.append(
                '<li><a class="dropdown-item" href="' + docs_href + '" data-gh-i18n="gov.docs">Docs</a></li>'
            )
        return '\n'.join(lines)
    lines = []
    if r.get('layers', True):
        lines.append(
            '<li><a class="dropdown-item" href="/layers/" data-gh-i18n="gov.layers">Layers</a></li>'
        )
    if r.get('bridges', True):
        lines.append(
            '<li><a class="dropdown-item" href="/bridges/" data-gh-i18n="gov.bridges">Bridges</a></li>'
        )
    if r.get('roles', True):
        lines.append(
            '<li><a class="dropdown-item" href="/roles/" data-gh-i18n="gov.roles">Roles</a></li>'
        )
    if r.get('workgroups', True):
        lines.append(
            '<li><a class="dropdown-item" href="/workgroups/" data-gh-i18n="gov.workgroups">Workgroups</a></li>'
        )
    if r.get('votes', True):
        lines.append(
            '<li><a class="dropdown-item" href="/votes/" data-gh-i18n="gov.votes">Votes</a></li>'
        )
    if r.get('artifacts', True):
        lines.append(
            '<li><a class="dropdown-item" href="/artifacts/" data-gh-i18n="gov.artifacts">Artifacts</a></li>'
        )
    if r.get('opportunities', True):
        lines.append(
            '<li><a class="dropdown-item" href="/opportunities/" data-gh-i18n="gov.opportunities">Opportunities</a></li>'
        )
    if r.get('docs', True):
        lines.append(
            '<li><a class="dropdown-item" href="/doc/all/" data-gh-i18n="gov.docs">Docs</a></li>'
        )
    return '\n'.join(lines)


def _home_hub_card(href, icon, title, desc, btn_label, primary=False):
    btn_cls = 'btn-primary' if primary else 'btn-outline-primary'
    return (
        f'<a href="{href}" class="gh-home-hub-card text-decoration-none">'
        f'<div class="gh-home-hub-icon"><i class="fas {icon}"></i></div>'
        f'<h2>{title}</h2>'
        f'<p>{desc}</p>'
        f'<span class="btn btn-sm {btn_cls}">{btn_label}</span>'
        f'</a>'
    )


def build_home_hub_cards_html():
    """Home hub grid cards, omitting sections disabled in product rollout."""
    r = _product_rollout_flags()
    cards = []
    if r.get('docs', True):
        cards.append(_home_hub_card(
            '/doc/all/', 'fa-file-alt', 'Documents',
            'Drafts, RFCs, and layer documentation.',
            'View Docs', primary=True,
        ))
    if r.get('layers', True):
        cards.append(_home_hub_card(
            '/layers/', 'fa-layer-group', 'Layers',
            'Browse layers, workgroups, and living layer maps.',
            'View Layers', primary=True,
        ))
    if r.get('workgroups', True):
        cards.append(_home_hub_card(
            '/workgroups/', 'fa-users-cog', 'Workgroups',
            'Find workgroups across layers and their activities.',
            'View Workgroups', primary=True,
        ))
    if r.get('guilds', True):
        cards.append(_home_hub_card(
            '/guilds/', 'fa-shield-halved', 'Guilds',
            'Cross-project collaboration groups and communities.',
            'View Guilds', primary=True,
        ))
    if r.get('roles', True):
        cards.append(_home_hub_card(
            '/roles/', 'fa-user-tag', 'Roles',
            'Explore and claim roles across all layers.',
            'Browse Roles',
        ))
    cards.append(_home_hub_card(
        '/person/', 'fa-user-friends', 'People',
        'Directory of Gov Hub participants and contributors.',
        'View People',
    ))
    if r.get('badges', True):
        cards.append(_home_hub_card(
            '/badges/', 'fa-medal', 'Badges',
            'Visual representations and galleries for roles.',
            'View Badges',
        ))
    if r.get('waitlists', True):
        cards.append(_home_hub_card(
            '/waitlists/', 'fa-list-ol', 'Waitlists',
            'Join waitlists for upcoming features and opportunities.',
            'View Waitlists', primary=True,
        ))
    return '\n'.join(cards)


def build_home_hero_subtitle():
    """Hero tagline listing only rollout-enabled areas."""
    r = _product_rollout_flags()
    labels = []
    for key, label in (
        ('docs', 'docs'),
        ('layers', 'layers'),
        ('roles', 'roles'),
        ('workgroups', 'workgroups'),
        ('guilds', 'guilds'),
    ):
        if r.get(key, True):
            labels.append(label)
    if not labels:
        return 'Welcome to the Interface Governance Hub. Coordination in one place.'
    if len(labels) == 1:
        joined = labels[0]
    elif len(labels) == 2:
        joined = f'{labels[0]} and {labels[1]}'
    else:
        joined = ', '.join(labels[:-1]) + f', and {labels[-1]}'
    return f'Welcome to the Interface Governance Hub. {joined.capitalize()}, and coordination in one place.'


def generate_civic_mason_nav_li():
    """Recognition dropdown: Civic Mason link, hidden when `civic_mason` rollout is off."""
    r = _product_rollout_flags()
    if not r.get('civic_mason', True):
        return ''
    return (
        '<li><a class="dropdown-item" href="/civic-mason/" data-gh-i18n="nav.civicMason">Civic Mason</a></li>'
    )


def _base_template_for_request():
    """Use live BASE_TEMPLATE in development so CSS/markup edits apply without restart."""
    try:
        from config import DEBUG, IS_DEVELOPMENT
        if DEBUG or IS_DEVELOPMENT:
            import importlib
            from templates import html_templates
            importlib.reload(html_templates)
            return html_templates.BASE_TEMPLATE
    except Exception:
        pass
    return _base_template


def _format_base_template(**kwargs):
    """Format BASE_TEMPLATE with defaults for font_awesome_link."""
    template = _base_template_for_request()
    kwargs.setdefault('font_awesome_link', _font_awesome_link)
    kwargs.setdefault('build_number', _build_number)
    kwargs.setdefault('body_attrs', '')
    locale = getattr(g, 'locale', None) or 'en'
    kwargs.setdefault('html_lang', locale)
    kwargs.setdefault('site_locale_json', json.dumps(locale))
    layer_slug = getattr(g, 'layer_slug', None)
    kwargs.setdefault('governance_nav', generate_governance_nav(layer_slug))
    kwargs.setdefault('participate_nav_html', generate_participate_nav_html(layer_slug))
    kwargs.setdefault('community_nav_html', generate_community_nav_html(layer_slug))
    kwargs.setdefault('recognition_nav_html', generate_recognition_nav_html(layer_slug))
    kwargs.setdefault('learn_nav_html', generate_learn_nav_html(layer_slug))
    kwargs.setdefault('civic_mason_nav_li', generate_civic_mason_nav_li())
    kwargs.setdefault('lang_menu', generate_lang_menu_html())
    kwargs.setdefault('prefix_chip_html', generate_prefix_chip_html())
    kwargs.setdefault('flash_messages', render_flash_messages_html())
    if has_request_context():
        from services.csrf import get_or_create_csrf_token
        kwargs.setdefault('csrf_token', get_or_create_csrf_token())
    else:
        kwargs.setdefault('csrf_token', '')
    from services.web3auth_config import get_web3auth_settings
    web3auth = get_web3auth_settings()
    kwargs.setdefault('web3auth_client_id', web3auth['client_id'])
    kwargs.setdefault('web3auth_network', web3auth['network'])
    kwargs.setdefault('web3auth_google_verifier', web3auth['google_verifier'])
    try:
        from config import CANOPI_API_URL
        kwargs.setdefault('canopi_api_url', CANOPI_API_URL)
    except ImportError:
        kwargs.setdefault('canopi_api_url', 'https://api.canopi.live')
    try:
        kwargs.setdefault('govhub_i18n_js', url_for('static', filename='js/govhub-i18n.js'))
    except RuntimeError:
        kwargs.setdefault('govhub_i18n_js', '/static/js/govhub-i18n.js')
    from services.identity import get_current_user
    from services.theme import theme_template_context

    session_theme = session.get('theme') if has_request_context() else None
    theme_ctx = theme_template_context(
        explicit_preference=kwargs.get('theme'),
        current_user=get_current_user(),
        session_theme=session_theme,
    )
    kwargs.update(theme_ctx)
    return template.format(**kwargs)


def render_page(title, content, theme=None, user_menu=None, font_awesome=True, body_attrs=''):
    """Helper to render a page with BASE_TEMPLATE including build number"""
    from services.identity import get_current_user

    if theme is None:
        theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    if user_menu is None:
        user_menu = generate_user_menu()
    font_awesome_link = '' if not font_awesome else _font_awesome_link
    layer_slug = getattr(g, 'layer_slug', None)
    return _format_base_template(
        title=title,
        theme=theme,
        user_menu=user_menu,
        content=content,
        build_number=_build_number,
        font_awesome_link=font_awesome_link,
        governance_nav=generate_governance_nav(layer_slug),
        body_attrs=body_attrs,
    )


def render_layer_standalone_page(title, content, layer_name, layer_slug, layer_image_url=None,
                                 theme=None, user_menu=None, font_awesome=True):
    """Render page with layer branding: layer logo+name in navbar, View in GovHub button."""
    from services.identity import get_current_user
    from templates.html_templates import LAYER_STANDALONE_BASE_TEMPLATE

    if theme is None:
        theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    font_awesome_link = '' if not font_awesome else _font_awesome_link
    img_html = ''
    if layer_image_url:
        img_html = (
            f'<img id="layer-navbar-brand-img" class="navbar-brand-logo" src="{html.escape(layer_image_url, quote=True)}" '
            f'alt="{html.escape(layer_name or "", quote=True)}" style="height:24px;width:auto;object-fit:contain;" />'
        )
    else:
        img_html = '<img class="navbar-brand-logo navbar-brand-logo-invert" src="/static/images/overweb_logo.png" alt="" style="height:24px;width:auto;" />'
    user_menu = generate_user_menu(view_in_mlgh_slug=layer_slug)
    safe_layer_attr = html.escape(layer_name or '', quote=True)
    locale = getattr(g, 'locale', None) or 'en'
    try:
        govhub_js = url_for('static', filename='js/govhub-i18n.js')
    except RuntimeError:
        govhub_js = '/static/js/govhub-i18n.js'
    if has_request_context():
        from services.csrf import get_or_create_csrf_token
        csrf_token = get_or_create_csrf_token()
    else:
        csrf_token = ''
    from services.web3auth_config import get_web3auth_settings
    web3auth = get_web3auth_settings()
    try:
        from config import CANOPI_API_URL
        canopi_api_url = CANOPI_API_URL
    except ImportError:
        canopi_api_url = 'https://api.canopi.live'
    from services.theme import theme_template_context
    session_theme = session.get('theme') if has_request_context() else None
    theme_ctx = theme_template_context(
        explicit_preference=theme,
        current_user=get_current_user(),
        session_theme=session_theme,
    )
    return LAYER_STANDALONE_BASE_TEMPLATE.format(
        title=title,
        theme=theme_ctx['theme'],
        theme_preference=theme_ctx['theme_preference'],
        theme_effective=theme_ctx['theme_effective'],
        user_theme_preference_meta=theme_ctx['user_theme_preference_meta'],
        user_menu=user_menu,
        content=content,
        build_number=_build_number,
        font_awesome_link=font_awesome_link,
        layer_name=layer_name,
        layer_slug=layer_slug,
        layer_image_html=img_html,
        governance_nav=generate_governance_nav(layer_slug, standalone=True),
        participate_nav_html=generate_participate_nav_html(layer_slug),
        community_nav_html=generate_community_nav_html(layer_slug),
        recognition_nav_html=generate_recognition_nav_html(layer_slug),
        learn_nav_html=generate_learn_nav_html(layer_slug),
        layer_name_attr=safe_layer_attr,
        html_lang=locale,
        site_locale_json=json.dumps(locale),
        lang_menu=generate_lang_menu_html(),
        prefix_chip_html=generate_prefix_chip_html(),
        govhub_i18n_js=govhub_js,
        civic_mason_nav_li=generate_civic_mason_nav_li(),
        flash_messages=render_flash_messages_html(),
        body_attrs='',
        csrf_token=csrf_token,
        canopi_api_url=canopi_api_url,
        web3auth_client_id=web3auth['client_id'],
        web3auth_network=web3auth['network'],
        web3auth_google_verifier=web3auth['google_verifier'],
    )


def generate_user_menu(layer_slug=None, view_in_mlgh_slug=None):
    """Generate user menu HTML for navbar.
    layer_slug: when on a layer page (non-standalone), add View standalone link.
    view_in_mlgh_slug: when on layer standalone page, add View in GovHub link to profile dropdown."""
    from services.identity import get_current_user

    current_user = get_current_user()
    if current_user:
        user_role = current_user.get('role', 'user')
        is_admin = user_role in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']
        r = _product_rollout_flags()
        admin_link = (
            '<li><a class="dropdown-item" href="/admin/" data-gh-i18n="user.adminDashboard">Admin Dashboard</a></li>'
            if (is_admin and r.get('admin', True))
            else ''
        )
        view_standalone_link = ''
        if layer_slug:
            view_standalone_link = (
                f'<li><a class="dropdown-item" href="/layer/{layer_slug}">'
                f'<i class="fas fa-external-link-alt me-1"></i><span data-gh-i18n="user.viewStandalone">View standalone</span></a></li>'
                '<li><hr class="dropdown-divider"></li>'
            )
        view_in_mlgh_link = ''
        if view_in_mlgh_slug:
            view_in_mlgh_link = (
                f'<li><a class="dropdown-item" href="/layers/{view_in_mlgh_slug}/">'
                f'<i class="fas fa-external-link-alt me-1"></i><span data-gh-i18n="user.viewInMLGH">View in GovHub</span></a></li>'
                '<li><hr class="dropdown-divider"></li>'
            )
        # Display name priority: displayName > oauthName > name > username
        from markupsafe import escape

        display_name = (current_user.get('displayName') or
                       current_user.get('oauthName') or
                       current_user.get('name') or
                       current_user['username'])
        display_name_escaped = escape(display_name)
        profile_href = f'/profile/{escape(current_user.get("username") or "")}/'
        from services.avatar import get_avatar_url

        avatar_src = escape(get_avatar_url(current_user, 40))

        return f"""
        <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle gh-user-nav-name gh-user-nav-toggle d-flex align-items-center" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false" data-gh-full-name="{display_name_escaped}" title="{display_name_escaped}" aria-label="{display_name_escaped}">
                <img src="{avatar_src}" alt="" class="gh-profile-nav-icon" onerror="this.onerror=null;this.src='/static/images/default-avatar.png'">
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="{profile_href}" data-gh-i18n="user.profile">Profile</a></li>
                <li><a class="dropdown-item" href="/profile/edit/"><i class="fas fa-edit me-1"></i>Edit profile</a></li>
                <li><a class="dropdown-item" href="/notifications/"><i class="fas fa-bell me-1"></i>Notifications</a></li>
                <li><a class="dropdown-item" href="/my-layers/" data-gh-i18n="user.myLayers">My Layers</a></li>
                <li><a class="dropdown-item" href="/submit/status/" data-gh-i18n="user.mySubmissions">My Submissions</a></li>
                <li><a class="dropdown-item" href="/support/">Support</a></li>
                {view_standalone_link}
                {view_in_mlgh_link}
                {admin_link}
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="/logout/" data-gh-i18n="user.logout">Logout</a></li>
            </ul>
        </li>
        """
    else:
        if view_in_mlgh_slug:
            return f"""
        <li class="nav-item">
            <a class="nav-link" href="#" onclick="event.preventDefault(); loginWithWeb3Auth(); return false;" data-gh-i18n="user.signIn">Sign In</a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/layers/{view_in_mlgh_slug}/"><span data-gh-i18n="user.viewInMLGH">View in GovHub</span></a>
        </li>
        """
        return """
        <li class="nav-item">
            <a class="nav-link" href="#" onclick="event.preventDefault(); loginWithWeb3Auth(); return false;" data-gh-i18n="user.signIn">Sign In</a>
        </li>
        """
