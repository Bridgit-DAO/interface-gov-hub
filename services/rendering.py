"""Rendering services: _format_base_template, render_page, generate_user_menu."""
from flask import session, g


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


def generate_governance_nav(layer_slug=None, standalone=False):
    """Build Governance dropdown HTML. When layer_slug is set, use layer-scoped links and omit Layers.
    standalone=True: use /layer/<slug>/ URLs so nav stays in layer view."""
    if layer_slug:
        base = '/layer/' + layer_slug if standalone else '/layers/' + layer_slug
        about_href = base + '/about/'
        docs_href = base + '/doc/' if standalone else '/doc/all/'
        return '\n'.join([
            '<li><a class="dropdown-item" href="' + about_href + '">About</a></li>',
            '<li><a class="dropdown-item" href="' + base + '/roles/">Roles</a></li>',
            '<li><a class="dropdown-item" href="' + base + '/workgroups/">Workgroups</a></li>',
            '<li><a class="dropdown-item" href="' + base + '/votes/">Votes</a></li>',
            '<li><a class="dropdown-item" href="' + base + '/artifacts/">Artifacts</a></li>',
            '<li><a class="dropdown-item" href="' + base + '/opportunities/">Opportunities</a></li>',
            '<li><a class="dropdown-item" href="' + docs_href + '">Docs</a></li>',
        ])
    return '\n'.join([
        '<li><a class="dropdown-item" href="/layers/">Layers</a></li>',
        '<li><a class="dropdown-item" href="/bridges/">Bridges</a></li>',
        '<li><a class="dropdown-item" href="/roles/">Roles</a></li>',
        '<li><a class="dropdown-item" href="/workgroups/">Workgroups</a></li>',
        '<li><a class="dropdown-item" href="/votes/">Votes</a></li>',
        '<li><a class="dropdown-item" href="/artifacts/">Artifacts</a></li>',
        '<li><a class="dropdown-item" href="/opportunities/">Opportunities</a></li>',
        '<li><a class="dropdown-item" href="/doc/all/">Docs</a></li>',
    ])


def _format_base_template(**kwargs):
    """Format BASE_TEMPLATE with defaults for font_awesome_link."""
    kwargs.setdefault('font_awesome_link', _font_awesome_link)
    kwargs.setdefault('hypothesis_config', '')
    kwargs.setdefault('build_number', _build_number)
    layer_slug = getattr(g, 'layer_slug', None)
    kwargs.setdefault('governance_nav', generate_governance_nav(layer_slug))
    return _base_template.format(**kwargs)


def render_page(title, content, theme=None, user_menu=None, font_awesome=True):
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
    )


def render_layer_standalone_page(title, content, layer_name, layer_slug, layer_image_url=None,
                                 theme=None, user_menu=None, font_awesome=True):
    """Render page with layer branding: layer logo+name in navbar, View in MLGH button."""
    from services.identity import get_current_user
    from templates.html_templates import LAYER_STANDALONE_BASE_TEMPLATE

    if theme is None:
        theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    if user_menu is None:
        user_menu = generate_user_menu()
    font_awesome_link = '' if not font_awesome else _font_awesome_link
    img_html = ''
    if layer_image_url:
        img_html = f'<img class="navbar-brand-logo" src="{layer_image_url}" alt="{layer_name}" style="height:24px;width:auto;object-fit:contain;" />'
    else:
        img_html = '<img class="navbar-brand-logo navbar-brand-logo-invert" src="/static/images/overweb_logo.png" alt="" style="height:24px;width:auto;" />'
    user_menu = generate_user_menu(view_in_mlgh_slug=layer_slug)
    return LAYER_STANDALONE_BASE_TEMPLATE.format(
        title=title,
        theme=theme,
        user_menu=user_menu,
        content=content,
        build_number=_build_number,
        font_awesome_link=font_awesome_link,
        hypothesis_config='',
        layer_name=layer_name,
        layer_slug=layer_slug,
        layer_image_html=img_html,
        governance_nav=generate_governance_nav(layer_slug, standalone=True),
    )


def generate_user_menu(layer_slug=None, view_in_mlgh_slug=None):
    """Generate user menu HTML for navbar.
    layer_slug: when on a layer page (non-standalone), add View standalone link.
    view_in_mlgh_slug: when on layer standalone page, add View in MLGH link to profile dropdown."""
    from services.identity import get_current_user

    current_user = get_current_user()
    if current_user:
        user_role = current_user.get('role', 'user')
        is_admin = user_role in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']
        admin_link = '<li><a class="dropdown-item" href="/admin/">Admin Dashboard</a></li>' if is_admin else ''
        view_standalone_link = ''
        if layer_slug:
            view_standalone_link = f'<li><a class="dropdown-item" href="/layer/{layer_slug}"><i class="fas fa-external-link-alt me-1"></i>View standalone</a></li><li><hr class="dropdown-divider"></li>'
        view_in_mlgh_link = ''
        if view_in_mlgh_slug:
            view_in_mlgh_link = f'<li><a class="dropdown-item" href="/layers/{view_in_mlgh_slug}/"><i class="fas fa-external-link-alt me-1"></i>View in MLGH</a></li><li><hr class="dropdown-divider"></li>'
        # Display name priority: displayName > oauthName > name > username
        display_name = (current_user.get('displayName') or
                       current_user.get('oauthName') or
                       current_user.get('name') or
                       current_user['username'])

        return f"""
        <div class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                {display_name}
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="/profile/">Profile</a></li>
                <li><a class="dropdown-item" href="/my-layers/">My Layers</a></li>
                <li><a class="dropdown-item" href="/submit/status/">My Submissions</a></li>
                {view_standalone_link}
                {view_in_mlgh_link}
                {admin_link}
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item" href="/logout/">Logout</a></li>
            </ul>
        </div>
        """
    else:
        if view_in_mlgh_slug:
            return f"""
        <div class="nav-item">
            <a class="nav-link" href="#" onclick="event.preventDefault(); loginWithWeb3Auth(); return false;">Sign In</a>
        </div>
        <li class="nav-item">
            <a class="nav-link" href="/layers/{view_in_mlgh_slug}/">View in MLGH</a>
        </li>
        """
        return """
        <div class="nav-item">
            <a class="nav-link" href="#" onclick="event.preventDefault(); loginWithWeb3Auth(); return false;">Sign In</a>
        </div>
        """
