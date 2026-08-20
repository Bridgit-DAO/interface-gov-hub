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
    assert cfg.hero.get('overlay', {}).get('scrim') == 'panel-left'
    assert cfg.hero_question == 'Can humanity grow into the intelligence it has created?'
    assert cfg.hero.get('quote') == (
        'No distinct center of superhuman consciousness has yet appeared on earth.'
    )
    assert cfg.hero.get('overlay', {}).get('primaryCta', {}).get('label') == (
        'Read and Comment on the Paper'
    )


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
    assert 'gh-campaign-hero-scrim-panel' in html
    assert 'gh-campaign-hero-image' in html
    assert '/static/campaign/teilhard/assets/hero.png' in html
    assert 'Can humanity grow into the intelligence it has created?' in html
    assert 'No distinct center of superhuman consciousness has yet appeared on earth.' in html
    assert 'Teilhard de Chardin' in html
    assert '--gh-campaign-hero-position' not in html
    assert 'heroImagePosition' not in html
    hero_html = html.split('gh-campaign-hero-content')[1].split('</section>')[0]
    assert 'The Teilhard Test' in hero_html
    assert 'The Overweb' not in hero_html
    assert 'gh-campaign-hero-quote' in hero_html
    assert 'btn-outline-light' not in hero_html
