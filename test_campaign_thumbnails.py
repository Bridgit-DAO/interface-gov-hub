"""Tests for campaign card thumbnail resolution and PDF extract."""
from __future__ import annotations

import os
import tempfile

import pytest

from config import PROJECT_ROOT


@pytest.fixture
def teilhard_pdf_path():
    path = os.path.join(
        PROJECT_ROOT,
        'static/campaign/teilhard/incoming/The_Teilhard_Test_Synthesis.pdf',
    )
    if not os.path.isfile(path):
        pytest.skip('Teilhard synthesis PDF not present')
    return path


def test_extract_pdf_first_page_thumbnail_creates_webp(teilhard_pdf_path):
    from services.campaign_thumbnails import extract_pdf_first_page_thumbnail

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'slides-thumb.webp')
        assert extract_pdf_first_page_thumbnail(teilhard_pdf_path, out) is True
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 1000


def test_explicit_thumbnail_wins_over_pdf_extract():
    from services.campaign_pages import CampaignConfig
    from services.campaign_thumbnails import resolve_campaign_card_thumbnail

    cfg = CampaignConfig(
        slug='teilhard',
        title='Test',
        subtitle='',
        hero_question='',
        layer_slug='the-overweb',
        custom_domains=[],
        dev_host='',
        documents=[],
        external_links=[],
        primary_cta={},
        secondary_ctas=[],
        raw={},
    )
    item = {
        'slug': 'slides',
        'type': 'slide_deck',
        'deckPath': 'static/campaign/teilhard/incoming/The_Teilhard_Test_Synthesis.pdf',
        'thumbnailUrl': '/static/campaign/teilhard/assets/custom.jpg',
    }
    assert resolve_campaign_card_thumbnail(cfg, item) == item['thumbnailUrl']


def test_draft_hero_scaffold_field_names():
    from services.campaign_thumbnails import _DRAFT_HERO_SCAFFOLD_KEYS

    assert 'heroImageUrl' in _DRAFT_HERO_SCAFFOLD_KEYS
    assert 'coverImageUrl' in _DRAFT_HERO_SCAFFOLD_KEYS


def test_hero_from_text_content_book_cover():
    from services.campaign_thumbnails import _hero_from_text_content

    md = '![Cover](/assets/cover.png)\n\n# Title'
    assert _hero_from_text_content(md) == '/static/images/book/cover.png'


def test_draft_8a37qe9r_has_no_hero_yet():
    """Document current state: ordinal draft has no cover until scaffold/hero is set."""
    from app import app
    from database import init_db

    with app.app_context():
        init_db(app)
        from services.campaign_thumbnails import resolve_draft_hero_url

        assert resolve_draft_hero_url('8a37qe9r') is None
