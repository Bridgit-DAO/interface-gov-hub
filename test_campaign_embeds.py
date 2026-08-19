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
    assert cfg.hero_image_url == '/static/campaign/teilhard/assets/hero.jpg'
    assert cfg.hero_question == 'Can humanity grow into the intelligence it has created?'


def test_campaign_draft_embed_url():
    from services.campaign_render import campaign_draft_embed_url

    assert campaign_draft_embed_url('8a37qe9r') == '/embed/draft/8a37qe9r/read/'


def test_campaign_slides_embed_url():
    from services.campaign_render import campaign_slides_embed_url

    assert campaign_slides_embed_url('teilhard') == '/embed/campaign/teilhard/slides/'


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


def test_embed_slides_route():
    from app import app

    client = app.test_client()
    r = client.get('/embed/campaign/teilhard/slides/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'gh-embed-pdf-reader' in html
    assert '/campaign/teilhard/docs/slides/file/' in html


def test_home_renders_hero_image():
    from app import app

    client = app.test_client()
    r = client.get('/campaign/teilhard/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'gh-campaign-hero-has-image' in html
    assert '/static/campaign/teilhard/assets/hero.jpg' in html
    assert 'Can humanity grow into the intelligence it has created?' in html
