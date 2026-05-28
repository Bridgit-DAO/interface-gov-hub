"""Tests for hourly page hero copy rotation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_hero_variant_index_cycles_three():
    from services.page_heroes import hero_variant_index

    assert hero_variant_index('workgroups', hour=0) == 0
    assert hero_variant_index('workgroups', hour=1) == 1
    assert hero_variant_index('workgroups', hour=2) == 2
    assert hero_variant_index('workgroups', hour=3) == 0


def test_pick_page_hero_uses_placeholder_when_art_missing():
    from services.page_heroes import HERO_PLACEHOLDER_IMAGE, _resolve_hero_image

    assert _resolve_hero_image('/static/images/does-not-exist.png') == HERO_PLACEHOLDER_IMAGE


def test_pick_page_hero_uses_custom_art_when_present():
    from services.page_heroes import HERO_PLACEHOLDER_IMAGE, pick_page_hero

    for key, fragment in (
        ('submit_draft', 'hero-submit-draft.png'),
        ('workgroups', 'hero-workgroups.png'),
        ('layers', 'hero-layers.png'),
        ('docs_drafts', 'hero-docs-drafts.png'),
        ('guilds', 'hero-guilds.png'),
        ('roles', 'hero-roles.png'),
        ('artifacts', 'hero-artifacts.png'),
        ('waitlists', 'hero-waitlists.png'),
    ):
        hero = pick_page_hero(key, hour=0)
        assert fragment in hero['image'], key
        assert hero['image'] != HERO_PLACEHOLDER_IMAGE, key


def test_all_page_heroes_have_three_messages():
    from services.page_heroes import PAGE_HEROES

    for key, cfg in PAGE_HEROES.items():
        msgs = cfg.get('messages') or []
        assert len(msgs) == 3, key
        for msg in msgs:
            assert msg.get('title'), key
            assert msg.get('text'), key


def test_render_page_hero_html_escapes():
    from services.page_heroes import render_page_hero_html

    html = render_page_hero_html('docs_drafts', hour=0)
    assert 'gh-page-hero' in html
    assert 'hero-docs-drafts.png' in html
    assert '<script' not in html


def test_workgroups_page_includes_hero():
    from app import app

    client = app.test_client()
    r = client.get('/workgroups/')
    assert r.status_code == 200
    assert 'gh-page-hero-title' in r.get_data(as_text=True)


def test_waitlists_page_includes_hero():
    from app import app

    client = app.test_client()
    r = client.get('/waitlists/')
    if r.status_code == 404:
        return  # waitlists rollout disabled in this environment
    assert r.status_code == 200
    assert 'gh-page-hero' in r.get_data(as_text=True)
    assert 'hero-waitlists.png' in r.get_data(as_text=True)
