"""HTML rendering for public campaign pages."""
from __future__ import annotations

import html as html_mod
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

from flask import g

from services.campaign_pages import CampaignConfig, campaign_href


def _esc(value: Any) -> str:
    return html_mod.escape(str(value or ''))


def _nav_link(cfg: CampaignConfig, label: str, path: str, active: bool = False) -> str:
    cls = 'gh-campaign-nav-link active' if active else 'gh-campaign-nav-link'
    return f'<a class="{cls}" href="{_esc(campaign_href(cfg.slug, path))}">{_esc(label)}</a>'


def campaign_shell(
    cfg: CampaignConfig,
    *,
    page_title: str,
    main_html: str,
    doc_slug: Optional[str] = None,
    extra_head: str = '',
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
    sign_in = '/login/?next=' + html_mod.escape(campaign_href(cfg.slug, '/docs/statement'), quote=True)

    return f'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(page_title)} — {_esc(cfg.title)}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
  <link href="/static/css/campaign-pages.css?v=1" rel="stylesheet">
  {extra_head}
</head>
<body class="gh-campaign-body">
  <header class="gh-campaign-header">
    <div class="gh-campaign-header-inner">
      <a class="gh-campaign-brand" href="{_esc(campaign_href(cfg.slug, '/'))}">
        <span class="gh-campaign-brand-title">{_esc(cfg.title)}</span>
        <span class="gh-campaign-brand-sub">{_esc(cfg.subtitle)}</span>
      </a>
      <nav class="gh-campaign-nav">{nav_html}</nav>
      <a class="btn btn-sm btn-outline-light" href="{sign_in}">Sign in</a>
    </div>
  </header>
  <main class="gh-campaign-main">{main_html}</main>
  <footer class="gh-campaign-footer">
    <p class="mb-0 small text-muted">Hosted on <a href="https://dev.govhub.live/" class="text-muted">Gov Hub</a> · The Overweb</p>
  </footer>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''


def render_home(cfg: CampaignConfig) -> str:
    doc_cards = []
    for doc in sorted(cfg.documents, key=lambda d: d.get('displayOrder', 0)):
        slug = doc.get('slug') or ''
        href = campaign_href(cfg.slug, f'/docs/{slug}')
        doc_cards.append(f'''
        <a class="gh-campaign-card" href="{_esc(href)}">
          <div class="gh-campaign-card-label">{_esc(doc.get("label"))}</div>
          <div class="gh-campaign-card-type text-muted small">{_esc(doc.get("type"))}</div>
        </a>''')
    for link in sorted(cfg.external_links, key=lambda x: x.get('displayOrder', 0)):
        doc_cards.append(f'''
        <a class="gh-campaign-card gh-campaign-card-external" href="{_esc(link.get("url"))}" target="_blank" rel="noopener">
          <div class="gh-campaign-card-label">{_esc(link.get("label"))}</div>
          <div class="gh-campaign-card-type text-muted small">External</div>
        </a>''')
    cards_html = '\n'.join(doc_cards)
    monument_preview = _monument_tree_html(cfg, compact=True)
    primary = cfg.primary_cta or {}
    primary_href = primary.get('href') or campaign_href(cfg.slug, '/docs/paper')
    if primary_href.startswith('/'):
        primary_href = campaign_href(cfg.slug, primary_href)
    secondary_btns = []
    for cta in cfg.secondary_ctas or []:
        href = cta.get('href') or '#'
        if href.startswith('/'):
            href = campaign_href(cfg.slug, href)
        secondary_btns.append(
            f'<a class="btn btn-outline-light" href="{_esc(href)}">{_esc(cta.get("label"))}</a>'
        )
    secondary_html = '\n'.join(secondary_btns)

    main = f'''
    <section class="gh-campaign-hero">
      <p class="gh-campaign-eyebrow">The Overweb</p>
      <h1>{_esc(cfg.hero_question or cfg.title)}</h1>
      <p class="lead">{_esc(cfg.subtitle)}</p>
      <div class="gh-campaign-hero-ctas">
        <a class="btn btn-primary btn-lg" href="{_esc(primary_href)}">{_esc(primary.get("label") or "Read")}</a>
        {secondary_html}
      </div>
    </section>
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
      <p class="text-muted">Comment and propose patches in the Gov Hub reader. The on-chain inscription is the same work.</p>
      <div class="d-flex flex-wrap gap-2 mb-3">
        <a class="btn btn-primary" href="{read_url}" target="_blank" rel="noopener">Open reader (comment &amp; patch)</a>
        {ordinal_link}
      </div>
    </section>
    <iframe class="gh-campaign-reader-frame" title="Paper reader" src="{read_url}"></iframe>
    '''
    return campaign_shell(cfg, page_title=doc.get('label') or 'Paper', main_html=main, doc_slug='paper', extra_head='<style>.gh-campaign-reader-frame{min-height:80vh;width:100%;border:0;border-radius:8px;}</style>')


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
    return campaign_shell(cfg, page_title='Statement', main_html=main, doc_slug='statement')


def render_doc_slides(cfg: CampaignConfig, doc: Dict[str, Any], pdf_url: str) -> str:
    main = f'''
    <section class="gh-campaign-doc-header">
      <h1>{_esc(doc.get("label"))}</h1>
      <p class="text-muted"><a href="{_esc(pdf_url)}" target="_blank" rel="noopener">Open PDF in new tab</a></p>
    </section>
    <iframe class="gh-campaign-pdf-frame" title="Slide deck" src="{_esc(pdf_url)}"></iframe>
    '''
    return campaign_shell(
        cfg,
        page_title=doc.get('label') or 'Slides',
        main_html=main,
        doc_slug='slides',
        extra_head='<style>.gh-campaign-pdf-frame{min-height:85vh;width:100%;border:0;border-radius:8px;}</style>',
    )
