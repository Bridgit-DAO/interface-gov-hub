"""HTML rendering for public campaign pages."""
from __future__ import annotations

import html as html_mod
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote as url_quote, urlparse

from flask import g, has_request_context, request

from config import IS_DEVELOPMENT
from services.campaign_auth import (
    campaign_for_vanity_host,
    campaign_login_url,
    gov_hub_public_url,
    hub_login_url,
    vanity_absolute_url,
)
from services.campaign_pages import CampaignConfig, campaign_href, normalize_hero_config, resolve_document_embed
from services.campaign_thumbnails import resolve_campaign_card_thumbnail


def _esc(value: Any) -> str:
    return html_mod.escape(str(value or ''))


_YOUTUBE_ID_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|embed/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})'
)


def _youtube_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = _YOUTUBE_ID_RE.search(url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    if 'youtube.com' in parsed.netloc and parsed.path == '/watch':
        vid = (parse_qs(parsed.query).get('v') or [None])[0]
        if vid and len(vid) == 11:
            return vid
    return None


_DOC_TYPE_ICONS = {
    'paper': 'document',
    'statement': 'quote',
    'slide_deck': 'slides',
    'slides': 'slides',
}

_ICON_SVGS = {
    'document': (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>'
        '<line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>'
    ),
    'quote': (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 21c3 0 7-1 7-8V5H3v8c0 3-1 5-3 5z"/>'
        '<path d="M14 21c3 0 7-1 7-8V5h-7v8c0 3-1 5-3 5z"/></svg>'
    ),
    'slides': (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/>'
        '<line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>'
    ),
    'link': (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
    ),
}


def _resolve_card_icon(item: Dict[str, Any], *, external: bool = False) -> str:
    icon = (item.get('icon') or '').strip().lower()
    if icon and icon in _ICON_SVGS:
        return icon
    doc_type = (item.get('type') or '').strip().lower()
    if doc_type in _DOC_TYPE_ICONS:
        return _DOC_TYPE_ICONS[doc_type]
    return 'link' if external else 'document'


def _campaign_card_thumb(thumbnail_url: Optional[str]) -> str:
    if not thumbnail_url:
        return ''
    return (
        f'<img class="gh-campaign-card-thumb" src="{_esc(thumbnail_url)}" alt="" loading="lazy">'
    )


def _campaign_card_icon(icon_key: str) -> str:
    svg = _ICON_SVGS.get(icon_key) or _ICON_SVGS['document']
    return (
        f'<div class="gh-campaign-card-thumb gh-campaign-card-icon" aria-hidden="true">{svg}</div>'
    )


def _campaign_card_visual(
    item: Dict[str, Any],
    *,
    external: bool = False,
    cfg: Optional[CampaignConfig] = None,
) -> str:
    thumb = resolve_campaign_card_thumbnail(cfg, item, external=external)
    if thumb:
        return _campaign_card_thumb(thumb)
    return _campaign_card_icon(_resolve_card_icon(item, external=external))


def _nav_link(cfg: CampaignConfig, label: str, path: str, active: bool = False) -> str:
    cls = 'gh-campaign-nav-link active' if active else 'gh-campaign-nav-link'
    return f'<a class="{cls}" href="{_esc(campaign_href(cfg.slug, path))}">{_esc(label)}</a>'


def _campaign_absolute_asset_url(path: str) -> str:
    """Absolute URL for same-origin assets on campaign vanity hosts (uploads, static)."""
    if not path:
        return path
    if path.startswith('http://') or path.startswith('https://'):
        return path
    if has_request_context():
        host = (
            request.headers.get('X-Forwarded-Host')
            or request.host
            or ''
        ).split(',')[0].strip().split(':')[0].lower()
        if campaign_for_vanity_host(host):
            rel = path if path.startswith('/') else f'/{path}'
            return f'https://{host}{rel}'
    return path


def _campaign_auth_header_html(cfg: CampaignConfig, sign_in_url: str) -> tuple[str, bool]:
    """Return (header auth HTML, is_authenticated)."""
    from services.identity import get_current_user

    user = get_current_user()
    if user:
        from services.avatar import get_avatar_url

        display_name = (
            user.get('displayName')
            or user.get('oauthName')
            or user.get('name')
            or user['username']
        )
        avatar = _campaign_absolute_asset_url(get_avatar_url(user, 32))
        username = user.get('username') or ''
        on_vanity = campaign_for_vanity_host()
        hub_base = gov_hub_public_url().rstrip('/')
        profile_href = (
            f'{hub_base}/profile/{html_mod.escape(username)}/'
            if on_vanity
            else f'/profile/{html_mod.escape(username)}/'
        )
        return_path = '/'
        if has_request_context():
            return_path = (request.path or '/').rstrip('/') or '/'
        logout_next = url_quote(
            vanity_absolute_url(cfg, return_path) if on_vanity else return_path,
            safe='',
        )
        return (
            f'''<div class="dropdown gh-campaign-user-menu">
      <button class="btn gh-campaign-user-toggle dropdown-toggle" type="button"
        data-bs-toggle="dropdown" aria-expanded="false"
        title="{_esc(display_name)}" aria-label="{_esc(display_name)}">
        <img src="{_esc(avatar)}" alt="" class="gh-campaign-user-avatar" width="32" height="32"
          onerror="this.onerror=null;this.src='{_esc(_campaign_absolute_asset_url('/static/images/default-avatar.png'))}'">
      </button>
      <ul class="dropdown-menu dropdown-menu-end gh-campaign-user-dropdown">
        <li><a class="dropdown-item" href="{_esc(profile_href)}">Profile on Gov Hub</a></li>
        <li><hr class="dropdown-divider"></li>
        <li><a class="dropdown-item" href="/logout/?next={logout_next}">Sign out</a></li>
      </ul>
    </div>''',
            True,
        )
    return (
        f'<a class="btn btn-sm btn-outline-light" href="{_esc(sign_in_url)}">Sign in</a>',
        False,
    )


def _campaign_dev_hub_banner_html() -> str:
    if not IS_DEVELOPMENT or not campaign_for_vanity_host():
        return ''
    hub = gov_hub_public_url()
    return (
        f'<div class="gh-campaign-dev-banner" role="status">'
        f'Sign-in uses <a href="{_esc(hub)}/login/">dev.hub.themetalayer.org</a>. '
        f'A session on <strong>hub.themetalayer.org</strong> (production) does not carry over here.'
        f'</div>'
    )


def _campaign_hub_handoff_script(cfg: CampaignConfig, *, is_authenticated: bool, enabled: bool) -> str:
    """One-shot redirect to hub login so an existing dev-hub session can hand off silently."""
    if not enabled or is_authenticated or not campaign_for_vanity_host():
        return ''
    if has_request_context() and request.args.get('gh_handoff') == '0':
        return ''
    return_path = vanity_absolute_url(cfg, (request.path if has_request_context() else '/') or '/')
    hub_login = hub_login_url(return_path)
    return f'''<script>
(function () {{
  try {{
    if (sessionStorage.getItem('ghCampaignHubHandoff')) return;
    sessionStorage.setItem('ghCampaignHubHandoff', String(Date.now()));
  }} catch (_e) {{ return; }}
  window.location.replace({json.dumps(hub_login)});
}})();
</script>'''


def campaign_shell(
    cfg: CampaignConfig,
    *,
    page_title: str,
    main_html: str,
    doc_slug: Optional[str] = None,
    extra_head: str = '',
    attempt_hub_handoff: bool = False,
) -> str:
    nav_parts = [_nav_link(cfg, 'Home', '/', active=not doc_slug)]
    if (cfg.structure or {}).get('nodes'):
        nav_parts.append(_nav_link(cfg, 'Monument', '/monument/', active=doc_slug == 'monument'))
    for doc in sorted(cfg.documents, key=lambda d: d.get('displayOrder', 0)):
        slug = doc.get('slug') or ''
        if not slug:
            continue
        nav_parts.append(
            _nav_link(cfg, doc.get('label') or slug, f'/docs/{slug}', active=doc_slug == slug)
        )
    nav_html = '\n'.join(nav_parts)
    sign_in = campaign_login_url(cfg, '/docs/statement')
    auth_html, is_authenticated = _campaign_auth_header_html(cfg, sign_in)
    dev_banner = _campaign_dev_hub_banner_html()
    handoff_script = _campaign_hub_handoff_script(
        cfg,
        is_authenticated=is_authenticated,
        enabled=attempt_hub_handoff,
    )
    authed_attr = '1' if is_authenticated else '0'

    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark" data-gh-authed="{authed_attr}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(page_title)} – {_esc(cfg.title)}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
  <link href="/static/css/campaign-pages.css?v=13" rel="stylesheet">
  {extra_head}
</head>
<body class="gh-campaign-body">
  {dev_banner}
  <header class="gh-campaign-header">
    <div class="gh-campaign-header-inner">
      <a class="gh-campaign-brand" href="{_esc(campaign_href(cfg.slug, '/'))}">
        <span class="gh-campaign-brand-title">{_esc(cfg.title)}</span>
        <span class="gh-campaign-brand-sub">{_esc(cfg.subtitle)}</span>
      </a>
      <nav class="gh-campaign-nav">{nav_html}</nav>
      {auth_html}
    </div>
  </header>
  <div class="gh-campaign-body-gradient">
    <main class="gh-campaign-main">{main_html}</main>
    <footer class="gh-campaign-footer">
      <p class="mb-0 small">Hosted on <a href="{"https://dev.govhub.live/" if IS_DEVELOPMENT else "https://hub.themetalayer.org/"}">Gov Hub</a> · The Overweb</p>
    </footer>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="/static/js/campaign-nav.js?v=1"></script>
  {handoff_script}
</body>
</html>'''


def campaign_draft_embed_url(cfg: CampaignConfig, doc: Dict[str, Any]) -> str:
    """Same-origin embed URL for the Gov Hub draft reader (iframe-safe)."""
    embed = resolve_document_embed(cfg, doc)
    return embed.get('src') or f'/embed/draft/{html_mod.escape(doc.get("draftRef") or "")}/read/'


def campaign_slides_embed_url(cfg: CampaignConfig, doc: Dict[str, Any]) -> str:
    """Same-origin embed URL for inline slide-deck PDF viewing."""
    embed = resolve_document_embed(cfg, doc)
    return embed.get('src') or f'/embed/campaign/{html_mod.escape(cfg.slug)}/slides/'


def campaign_slides_pdf_url(cfg: CampaignConfig, doc: Dict[str, Any]) -> str:
    """Iframe-safe PDF file URL (under /embed/ for SAMEORIGIN framing)."""
    embed = resolve_document_embed(cfg, doc)
    return (
        embed.get('pdfSrc')
        or f'/embed/campaign/{html_mod.escape(cfg.slug)}/slides/file/'
    )


def _campaign_presentation_value(cfg: CampaignConfig, key: str, default: str = '') -> str:
    pres = cfg.presentation or {}
    raw = cfg.raw or {}
    for source in (pres, raw):
        value = source.get(key)
        if value:
            return str(value).strip()
    return default


def _campaign_hero_settings(cfg: CampaignConfig) -> Dict[str, Any]:
    hero = dict(cfg.hero or {})
    if not hero.get('imageUrl') and not hero.get('headline'):
        hero = normalize_hero_config(cfg.raw or {}, cfg.presentation or {})
    return hero


def _campaign_hero_kicker(cfg: CampaignConfig) -> str:
    hero = _campaign_hero_settings(cfg)
    return hero.get('kicker') or cfg.title or 'The Overweb'


def _campaign_hero_headline(cfg: CampaignConfig) -> str:
    hero = _campaign_hero_settings(cfg)
    return hero.get('headline') or cfg.hero_question or cfg.title


def _campaign_hero_quote_html(cfg: CampaignConfig) -> str:
    hero = _campaign_hero_settings(cfg)
    quote = hero.get('quote') or _campaign_presentation_value(cfg, 'heroQuote')
    if not quote:
        return ''
    attribution = hero.get('quoteAttribution') or _campaign_presentation_value(cfg, 'heroQuoteAttribution')
    cite_html = f'\n        <cite>{_esc(attribution)}</cite>' if attribution else ''
    return f'''
        <blockquote class="gh-campaign-hero-quote">
          <p>{_esc(quote)}</p>{cite_html}
        </blockquote>'''


def _campaign_hero_ghost_links_html(cfg: CampaignConfig, *, max_links: int = 2) -> str:
    hero = _campaign_hero_settings(cfg)
    overlay = hero.get('overlay') or {}
    links = list(overlay.get('ghostLinks') or [])
    if not links:
        pres = cfg.presentation or {}
        raw = cfg.raw or {}
        links = pres.get('heroGhostLinks') or raw.get('heroGhostLinks') or []
    if not links:
        links = [
            {'label': cta.get('label'), 'href': cta.get('href')}
            for cta in (cfg.secondary_ctas or [])[:max_links]
            if cta.get('href')
        ]
    ghost_links = []
    for link in links[:max_links]:
        href = link.get('href') or '#'
        if href.startswith('/'):
            href = campaign_href(cfg.slug, href)
        label = link.get('label') or 'Learn more'
        ghost_links.append(
            f'<a class="gh-campaign-hero-ghost" href="{_esc(href)}">{_esc(label)}</a>'
        )
    if not ghost_links:
        return ''
    return f'<div class="gh-campaign-hero-ghosts">{"".join(ghost_links)}</div>'


def _campaign_hero_nav_only(hero: Dict[str, Any]) -> bool:
    overlay = hero.get('overlay') or {}
    mode = str(overlay.get('mode') or 'full').strip().lower().replace('_', '-')
    return mode in {'nav-only', 'none', 'nav'}


def _campaign_hero_section(cfg: CampaignConfig, *, primary_href: str, primary: Dict[str, Any]) -> str:
    hero = _campaign_hero_settings(cfg)
    hero_url = (hero.get('imageUrl') or cfg.hero_image_url or '').strip()
    full_bleed = bool(hero.get('fullBleed', True))
    fit = (hero.get('fit') or 'cover').strip().lower()
    overlay = hero.get('overlay') or {}
    nav_only = _campaign_hero_nav_only(hero)
    scrim = (overlay.get('scrim') or ('none' if nav_only else 'gradient-left')).strip()
    text_align = (overlay.get('textAlign') or 'left').strip().lower()

    hero_classes = ['gh-campaign-hero']
    if hero_url:
        hero_classes.append('gh-campaign-hero-has-image')
    if full_bleed and hero_url:
        hero_classes.append('gh-campaign-hero-full-bleed')
    if fit == 'contain':
        hero_classes.append('gh-campaign-hero-fit-contain')
    if nav_only:
        hero_classes.append('gh-campaign-hero-nav-only')
    elif scrim == 'panel-left':
        hero_classes.append('gh-campaign-hero-scrim-panel')

    media_html = ''
    if hero_url:
        scrim_html = ''
        if scrim and scrim != 'none':
            scrim_class = f'gh-campaign-hero-scrim gh-campaign-hero-scrim-{scrim.replace("_", "-")}'
            scrim_html = f'\n      <div class="{_esc(scrim_class)}"></div>'
        media_html = f'''
      <div class="gh-campaign-hero-media" aria-hidden="true">
        <img class="gh-campaign-hero-image" src="{_esc(hero_url)}" alt="">
      </div>{scrim_html}'''

    if nav_only:
        return f'''
    <section class="{" ".join(hero_classes)}">{media_html}
    </section>'''

    content_classes = ['gh-campaign-hero-content']
    if text_align in {'left', 'center', 'right'}:
        content_classes.append(f'gh-campaign-hero-align-{text_align}')

    quote_html = _campaign_hero_quote_html(cfg)
    ghost_links_html = _campaign_hero_ghost_links_html(cfg)
    return f'''
    <section class="{" ".join(hero_classes)}">{media_html}
      <div class="{" ".join(content_classes)}">
        <p class="gh-campaign-eyebrow">{_esc(_campaign_hero_kicker(cfg))}</p>
        <h1>{_esc(_campaign_hero_headline(cfg))}</h1>{quote_html}
        <div class="gh-campaign-hero-ctas">
          <a class="btn btn-primary btn-lg" href="{_esc(primary_href)}">{_esc(primary.get("label") or "Read")}</a>
          {ghost_links_html}
        </div>
      </div>
    </section>'''


def render_home(cfg: CampaignConfig) -> str:
    doc_cards = []
    for doc in sorted(cfg.documents, key=lambda d: d.get('displayOrder', 0)):
        slug = doc.get('slug') or ''
        href = campaign_href(cfg.slug, f'/docs/{slug}')
        visual_html = _campaign_card_visual(doc, cfg=cfg)
        doc_cards.append(f'''
        <a class="gh-campaign-card" href="{_esc(href)}">
          {visual_html}
          <div class="gh-campaign-card-label">{_esc(doc.get("label"))}</div>
          <div class="gh-campaign-card-type text-muted small">{_esc(doc.get("type"))}</div>
        </a>''')
    for link in sorted(cfg.external_links, key=lambda x: x.get('displayOrder', 0)):
        visual_html = _campaign_card_visual(link, external=True, cfg=cfg)
        doc_cards.append(f'''
        <a class="gh-campaign-card gh-campaign-card-external" href="{_esc(link.get("url"))}" target="_blank" rel="noopener">
          {visual_html}
          <div class="gh-campaign-card-label">{_esc(link.get("label"))}</div>
          <div class="gh-campaign-card-type text-muted small">External</div>
        </a>''')
    cards_html = '\n'.join(doc_cards)
    monument_preview = _monument_tree_html(cfg, compact=True)
    primary = cfg.primary_cta or {}
    hero = _campaign_hero_settings(cfg)
    overlay = hero.get('overlay') or {}
    primary = dict(overlay.get('primaryCta') or primary or {})
    primary_href = primary.get('href') or campaign_href(cfg.slug, '/docs/paper')
    if primary_href.startswith('/'):
        primary_href = campaign_href(cfg.slug, primary_href)
    main = f'''
    {_campaign_hero_section(cfg, primary_href=primary_href, primary=primary)}
    <section class="gh-campaign-hook">
      <h2>From the Turing Test to the Teilhard Test</h2>
      <blockquote class="gh-campaign-quote">
        <p>The Turing Test evaluates the machine.</p>
        <p>The Teilhard Test evaluates us.</p>
      </blockquote>
      <p class="text-muted">The noosphere is treated here not as a mystical destination, but as an empirical capacity for planetary-scale coordination and responsibility.</p>
    </section>
    <section class="gh-campaign-criteria">
      <h2>Four criteria</h2>
      <div class="row g-3">
        <div class="col-md-6"><div class="gh-criterion"><h3>Reflexivity</h3><p>Feedback on actions, incentives, and consequences.</p></div></div>
        <div class="col-md-6"><div class="gh-criterion"><h3>Convergence without coercion</h3><p>Coordination across difference without forced uniformity.</p></div></div>
        <div class="col-md-6"><div class="gh-criterion"><h3>Preservation of differentiation</h3><p>Agency, role diversity, and contextual meaning.</p></div></div>
        <div class="col-md-6"><div class="gh-criterion"><h3>Power matched by responsibility</h3><p>Accountability and repair scale with capability.</p></div></div>
      </div>
    </section>
    <section class="gh-campaign-docs">
      <h2>Read, watch, discuss</h2>
      <div class="gh-campaign-card-grid">{cards_html}</div>
    </section>
    <section class="gh-campaign-monument-preview">
      <div class="d-flex flex-wrap justify-content-between gap-2 align-items-end">
        <div>
          <h2>Digital Monument structure</h2>
          <p class="text-muted mb-0">The campaign is now a presentation layer over a living Overweb monument.</p>
        </div>
        <a class="btn btn-outline-light" href="{_esc(campaign_href(cfg.slug, '/monument/'))}">Explore the monument</a>
      </div>
      {monument_preview}
    </section>
    '''
    return campaign_shell(cfg, page_title='Home', main_html=main)


def _monument_tree_html(cfg: CampaignConfig, *, compact: bool = False) -> str:
    nodes = list((cfg.structure or {}).get('nodes') or [])
    if not nodes:
        return '<p class="text-muted">No monument structure is defined yet.</p>'
    children = {}
    by_id = {}
    for node in sorted(nodes, key=lambda item: item.get('displayOrder') or 0):
        node_id = node.get('id') or node.get('slug')
        by_id[node_id] = node
        parent = node.get('parentId') or ''
        children.setdefault(parent, []).append(node)

    def render_items(parent_id: str, depth: int = 0) -> str:
        items = []
        for node in children.get(parent_id, []):
            if compact and depth > 1:
                continue
            slug = node.get('slug') or node.get('id')
            status = node.get('status') or 'stub'
            kind = node.get('kind') or 'page'
            label = _esc(node.get('label') or slug)
            href = campaign_href(cfg.slug, f'/monument/{slug}')
            badge = f'<span class="gh-monument-status gh-monument-status-{_esc(status)}">{_esc(status)}</span>'
            child_html = render_items(node.get('id') or slug, depth + 1)
            items.append(
                f'<li><a href="{_esc(href)}">{label}</a> '
                f'<span class="text-muted small">{_esc(kind)}</span> {badge}{child_html}</li>'
            )
        if not items:
            return ''
        return '<ul class="gh-monument-tree">' + ''.join(items) + '</ul>'

    return render_items('')


def render_monument_index(cfg: CampaignConfig) -> str:
    main = f'''
    <section class="gh-campaign-doc-header">
      <p class="gh-campaign-eyebrow">Digital Monument</p>
      <h1>{_esc(cfg.title)}</h1>
      <p class="lead text-muted">A living knowledge structure for public refinement, commentary, and future inscriptions.</p>
    </section>
    {_monument_tree_html(cfg)}
    '''
    return campaign_shell(cfg, page_title='Monument', main_html=main, doc_slug='monument')


def render_monument_node(cfg: CampaignConfig, node: Dict[str, Any]) -> str:
    binding = node.get('binding') or {}
    status = node.get('status') or 'stub'
    slug = node.get('slug') or node.get('id')
    route = node.get('routeLegacy')
    action = ''
    if route:
        action = f'<p><a class="btn btn-primary" href="{_esc(campaign_href(cfg.slug, route))}">Open live page</a></p>'
    elif binding.get('type') == 'external' and binding.get('url'):
        action = f'<p><a class="btn btn-primary" href="{_esc(binding.get("url"))}" target="_blank" rel="noopener">Open external source</a></p>'
    parent = node.get('parentId') or ''
    parent_html = f'<p class="small text-muted">Parent: {_esc(parent)}</p>' if parent else ''
    main = f'''
    <section class="gh-campaign-doc-header">
      <p class="gh-campaign-eyebrow">{_esc(node.get('kind') or 'Monument node')}</p>
      <h1>{_esc(node.get('label') or slug)}</h1>
      <p><span class="gh-monument-status gh-monument-status-{_esc(status)}">{_esc(status)}</span></p>
      {parent_html}
      {action}
    </section>
    <section class="gh-campaign-prose">
      <p>This monument section is {'active and backed by a live Gov Hub route' if route else 'being developed'}.</p>
      <p class="text-muted">Future participation here will support comments, patches, and inscription drafts attached to this monument node.</p>
    </section>
    '''
    return campaign_shell(cfg, page_title=node.get('label') or 'Monument Node', main_html=main, doc_slug='monument')


def render_doc_paper(cfg: CampaignConfig, doc: Dict[str, Any], draft_ref: str) -> str:
    embed_url = campaign_draft_embed_url(cfg, doc)
    read_url = (
        f'/doc/draft/{html_mod.escape(draft_ref)}/read/?return_to='
        f'{url_quote(campaign_href(cfg.slug, "/docs/paper"), safe="")}'
    )
    ordinal = doc.get('ordinalInscriptionUrl') or ''
    ordinal_link = ''
    if ordinal:
        ordinal_link = f'<a class="btn btn-sm btn-outline-secondary" href="{_esc(ordinal)}" target="_blank" rel="noopener">View on-chain inscription</a>'
    main = f'''
    <section class="gh-campaign-doc-header">
      <h1>{_esc(doc.get("label"))}</h1>
      <p class="text-muted">Read, comment, and propose patches inline below. Open the full reader for invite and moderation tools.</p>
      <div class="d-flex flex-wrap gap-2 mb-3">
        <a class="btn btn-primary" href="{read_url}">Open full reader</a>
        {ordinal_link}
      </div>
    </section>
    <div class="gh-campaign-embed-wrap">
      <iframe class="gh-campaign-reader-frame" title="Paper reader" src="{embed_url}" loading="lazy"></iframe>
    </div>
    '''
    return campaign_shell(
        cfg,
        page_title=doc.get('label') or 'Paper',
        main_html=main,
        doc_slug='paper',
    )


def render_doc_statement(cfg: CampaignConfig, doc: Dict[str, Any], body_html: str, endorsements_html: str, form_html: str) -> str:
    main = f'''
    <section class="gh-campaign-doc-header">
      <h1>{_esc(doc.get("label"))}</h1>
    </section>
    <article class="gh-campaign-prose">{body_html}</article>
    <section class="gh-campaign-endorse mt-5">
      <h2>Support the development</h2>
      <p class="text-muted">Endorsements are reviewed before they appear publicly. Sign in required.</p>
      {form_html}
      <div class="mt-4">{endorsements_html}</div>
    </section>
    '''
    return campaign_shell(
        cfg,
        page_title='Statement',
        main_html=main,
        doc_slug='statement',
        attempt_hub_handoff=True,
    )


def render_doc_slides(cfg: CampaignConfig, doc: Dict[str, Any], pdf_url: str) -> str:
    embed_url = campaign_slides_embed_url(cfg, doc)
    main = f'''
    <section class="gh-campaign-doc-header">
      <h1>{_esc(doc.get("label"))}</h1>
      <p class="text-muted">
        <a href="{_esc(pdf_url)}" target="_blank" rel="noopener">Open PDF in new tab</a>
        · <a href="{_esc(embed_url)}" target="_blank" rel="noopener">Full-screen viewer</a>
      </p>
    </section>
    <div class="gh-campaign-embed-wrap">
      <iframe class="gh-campaign-pdf-frame" title="Slide deck" src="{_esc(embed_url)}" loading="lazy"></iframe>
    </div>
    '''
    return campaign_shell(
        cfg,
        page_title=doc.get('label') or 'Slides',
        main_html=main,
        doc_slug='slides',
    )


def render_embed_draft_reader(draft_ref: str, *, modal_theme: str = 'dark') -> tuple[str, int]:
    """Minimal draft reader page for campaign iframe embeds."""
    from config import BUILD_NUMBER
    from services.draft_reader import build_draft_context, draft_display_id, load_draft_document_body
    from services.dp_proposal_reader import render_dp_proposal_reader_assets, render_reader_onboarding_assets

    draft, submission = build_draft_context(draft_ref, prefer_latest_revision=True)
    if not draft:
        return '<!DOCTYPE html><html><body><p>Document not found</p></body></html>', 404

    body_ref = str(draft.get('name') or draft_ref)
    document_content, render_html, _pages, _words = load_draft_document_body(
        draft,
        submission,
        body_ref,
        pdf_iframe_height='calc(100vh - 3rem)',
    )
    if render_html:
        body_block = (
            f'<div class="draft-reader-body prose" id="dp-reader-selectable-body">'
            f'{document_content}</div>'
        )
    else:
        body_block = (
            f'<pre class="draft-reader-body draft-reader-pre" id="dp-reader-selectable-body">'
            f'{_esc(document_content)}</pre>'
        )

    dp_assets = render_dp_proposal_reader_assets(
        submission,
        draft_ref,
        render_html=render_html,
        document_content=document_content if isinstance(document_content, str) else '',
    )
    onboarding = ''
    if submission and (submission.status or '').lower() == 'approved':
        onboarding = render_reader_onboarding_assets()

    display_id = _esc(draft_display_id(draft))
    title = _esc(draft.get('title') or '')
    doc_href = html_mod.escape(str(draft.get('name') or draft_ref), quote=True)
    read_url = f'/doc/draft/{doc_href}/read/'

    theme_class = 'gh-embed-modal-dark' if (modal_theme or 'dark').lower() == 'dark' else ''

    html = f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{display_id} – Reader</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
  <link href="/static/css/govhub-design.css?v={BUILD_NUMBER}" rel="stylesheet">
  <link href="/static/css/dp-proposals-reader.css?v={BUILD_NUMBER}" rel="stylesheet">
  <link href="/static/css/campaign-pages.css?v=13" rel="stylesheet">
</head>
<body class="gh-embed-draft-reader {theme_class}">
  <header class="gh-embed-reader-toolbar">
    <div class="gh-embed-reader-toolbar-inner">
      <span class="gh-embed-reader-title"><strong>{display_id}</strong> · {title}</span>
      <a class="btn btn-sm btn-outline-light" href="{read_url}" target="_top" rel="noopener">Open full reader</a>
    </div>
  </header>
  <main class="gh-embed-reader-main">{body_block}</main>
  {onboarding}
  {dp_assets}
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''
    return html, 200


def render_embed_slides_pdf(pdf_url: str, *, title: str = 'Slide deck') -> str:
    """Minimal PDF viewer for campaign iframe embeds (native + PDF.js fallback)."""
    pdf_esc = _esc(pdf_url)
    title_esc = _esc(title)
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title_esc}</title>
  <link href="/static/css/campaign-pages.css?v=13" rel="stylesheet">
</head>
<body class="gh-embed-pdf-reader">
  <div class="gh-embed-pdf-native">
    <iframe class="gh-embed-pdf-frame" title="{title_esc}" src="{pdf_esc}#view=FitH&toolbar=1"></iframe>
  </div>
  <div class="gh-embed-pdf-fallback" hidden>
    <p class="gh-embed-pdf-fallback-msg">Your browser cannot display this PDF inline.</p>
    <a class="btn btn-primary btn-sm" href="{pdf_esc}" target="_blank" rel="noopener">Open PDF</a>
  </div>
  <script>
  (function () {{
    var frame = document.querySelector('.gh-embed-pdf-frame');
    if (!frame) return;
    var isMobile = window.matchMedia('(max-width: 767px)').matches;
    var ua = navigator.userAgent || '';
    var ios = /iPad|iPhone|iPod/.test(ua);
    if (isMobile || ios) {{
      var fallback = document.querySelector('.gh-embed-pdf-fallback');
      var nativeWrap = document.querySelector('.gh-embed-pdf-native');
      if (fallback && nativeWrap) {{
        nativeWrap.hidden = true;
        fallback.hidden = false;
      }}
    }}
  }})();
  </script>
</body>
</html>'''
