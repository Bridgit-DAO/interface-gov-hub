"""Tests for campaign embed routes and hero image config."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('SECRET_KEY', 'isolated-test-secret-key')


def test_campaign_seed_has_hero_image():
    from services.campaign_pages import get_campaign, reload_campaign_cache

    reload_campaign_cache()
    cfg = get_campaign('teilhard')
    assert cfg is not None
    assert cfg.hero_image_url == '/static/campaign/teilhard/assets/hero.png'
    assert cfg.hero.get('fit') == 'contain'
    assert cfg.hero.get('overlay', {}).get('mode') == 'nav-only'
    assert cfg.hero.get('overlay', {}).get('scrim') == 'none'
    assert cfg.hero_question == ''
    assert cfg.hero.get('quote') == ''
    assert cfg.hero.get('overlay', {}).get('primaryCta', {}) == {}


def test_campaign_seed_has_theme_config():
    from services.campaign_pages import get_campaign, reload_campaign_cache

    reload_campaign_cache()
    cfg = get_campaign('teilhard')
    theme = cfg.theme
    assert theme['pageBackground'] == '#020408'
    assert theme['footerBackground'] == '#0a1224'
    stops = theme['gradient']['stops']
    assert stops[0]['color'] == '#020408'
    assert stops[-1]['color'] == '#0a1224'
    assert theme['gradient']['heightVh'] == 300


def test_campaign_embeds_auto_derived():
    from services.campaign_pages import get_campaign, reload_campaign_cache, resolve_document_embed

    reload_campaign_cache()
    cfg = get_campaign('teilhard')
    paper = cfg.doc_by_slug('paper')
    slides = cfg.doc_by_slug('slides')
    paper_embed = resolve_document_embed(cfg, paper)
    slides_embed = resolve_document_embed(cfg, slides)
    assert paper_embed['src'] == '/embed/draft/8a37qe9r/read/'
    assert paper_embed['modalTheme'] == 'dark'
    assert slides_embed['src'] == '/embed/campaign/teilhard/slides/'
    assert slides_embed['pdfSrc'] == '/embed/campaign/teilhard/slides/file/'


def test_campaign_draft_embed_url():
    from services.campaign_pages import get_campaign, reload_campaign_cache
    from services.campaign_render import campaign_draft_embed_url

    reload_campaign_cache()
    cfg = get_campaign('teilhard')
    doc = cfg.doc_by_slug('paper')
    assert campaign_draft_embed_url(cfg, doc) == '/embed/draft/8a37qe9r/read/'


def test_campaign_slides_embed_url():
    from services.campaign_pages import get_campaign, reload_campaign_cache
    from services.campaign_render import campaign_slides_embed_url, campaign_slides_pdf_url

    reload_campaign_cache()
    cfg = get_campaign('teilhard')
    doc = cfg.doc_by_slug('slides')
    assert campaign_slides_embed_url(cfg, doc) == '/embed/campaign/teilhard/slides/'
    assert campaign_slides_pdf_url(cfg, doc) == '/embed/campaign/teilhard/slides/file/'


def test_paper_page_embeds_draft_reader():
    from app import app

    client = app.test_client()
    r = client.get('/campaign/teilhard/docs/paper/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '/embed/draft/8a37qe9r/read/' in html
    assert 'gh-campaign-reader-frame' in html


def test_slides_page_embeds_pdf_viewer():
    from app import app

    client = app.test_client()
    r = client.get('/campaign/teilhard/docs/slides/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '/embed/campaign/teilhard/slides/' in html
    assert 'gh-campaign-pdf-frame' in html


def test_embed_draft_reader_route():
    from app import app

    client = app.test_client()
    r = client.get('/embed/draft/8a37qe9r/read/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'gh-embed-draft-reader' in html
    assert 'gh-embed-modal-dark' in html


def test_embed_slides_route():
    from app import app

    client = app.test_client()
    r = client.get('/embed/campaign/teilhard/slides/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'gh-embed-pdf-reader' in html
    assert '/embed/campaign/teilhard/slides/file/' in html


def test_embed_slides_pdf_allows_framing():
    from app import app

    client = app.test_client()
    r = client.get('/embed/campaign/teilhard/slides/file/')
    assert r.status_code == 200
    assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert 'application/pdf' in (r.headers.get('Content-Type') or '')


def test_home_renders_hero_image():
    from app import app

    client = app.test_client()
    r = client.get('/campaign/teilhard/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'gh-campaign-hero-has-image' in html
    assert 'gh-campaign-hero-full-bleed' in html
    assert 'gh-campaign-hero-fit-contain' in html
    assert 'gh-campaign-hero-nav-only' in html
    assert 'gh-campaign-hero-image' in html
    assert '/static/campaign/teilhard/assets/hero.png' in html
    assert 'gh-campaign-hero-content' not in html
    assert 'gh-campaign-hero-quote' not in html
    assert 'gh-campaign-hero-ctas' not in html
    assert 'gh-campaign-hero-scrim' not in html
    assert 'Can humanity grow into the intelligence it has created?' not in html
    assert '--gh-campaign-hero-position' not in html
    assert 'heroImagePosition' not in html
    assert 'gh-campaign-nav-link' in html
    assert 'campaign-nav.js' in html
    assert 'campaign-pages.css?v=17' in html
    assert '--gh-campaign-footer-bg: #0a1224' in html
    assert 'background-color: #0a1224' in html
    assert 'gh-campaign-nav-scrolled' not in html
