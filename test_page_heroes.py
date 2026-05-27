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


def test_pick_page_hero_uses_placeholder_image():
    from services.page_heroes import HERO_PLACEHOLDER_IMAGE, pick_page_hero

    hero = pick_page_hero('submit_draft', hour=0)
    assert hero['image'] == HERO_PLACEHOLDER_IMAGE
    assert hero['title']
    assert hero['text']


def test_pick_page_hero_uses_custom_art_when_present():
    from services.page_heroes import pick_page_hero

    hero = pick_page_hero('guilds', hour=0)
    assert 'hero-guilds.png' in hero['image']
    hero = pick_page_hero('roles', hour=0)
    assert 'hero-roles.png' in hero['image']


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
    assert 'hero-placeholder.png' in html
    assert '<script' not in html


def test_workgroups_page_includes_hero():
    from app import app

    client = app.test_client()
    r = client.get('/workgroups/')
    assert r.status_code == 200
    assert 'gh-page-hero-title' in r.get_data(as_text=True)
