"""Tests for DP artwork URL helpers."""
from services.dp_images import (
    dp_badge_image_url,
    dp_card_image_url,
    dp_full_image_url,
    dp_number_from_workgroup,
    normalize_dp_number,
    resolve_image_url_from_slug,
    resolve_workgroup_image_url,
)
from services.workgroup_links import is_dp_discovery_workgroup


class _Wg:
    def __init__(self, *, acronym='', slug='', name='', image_url=None):
        self.acronym = acronym
        self.slug = slug
        self.name = name
        self.image_url = image_url


def test_normalize_dp_number():
    assert normalize_dp_number('DP1') == 1
    assert normalize_dp_number('dp 23') == 23
    assert normalize_dp_number('DP99') is None


def test_dp_card_image_url():
    assert dp_card_image_url(1) == '/static/images/dps/card/DP1.webp'
    assert dp_card_image_url(23) == '/static/images/dps/card/DP23.webp'
    assert dp_card_image_url(99) is None


def test_dp_full_and_badge_urls():
    assert dp_full_image_url(22) == '/static/images/dps/full/DP22.webp'
    assert dp_badge_image_url(3) == '/static/images/dps/badge/dp03.webp'
    assert dp_badge_image_url(21) == '/static/images/dps/badge/dp21.webp'


def test_resolve_from_slug():
    assert resolve_image_url_from_slug('dp1-federated-auth') == (
        '/static/images/dps/card/DP1.webp'
    )
    assert resolve_image_url_from_slug('dp-discovery', 'DP Discovery') is None


def test_resolve_workgroup_image_url_dp23():
    wg = _Wg(acronym='dp23-universal-participation-linguistic-interoperability')
    assert resolve_workgroup_image_url(wg) == '/static/images/dps/card/DP23.webp'


def test_resolve_workgroup_image_url_non_dp_uses_stored():
    wg = _Wg(acronym='ml-governance', image_url='https://example.com/logo.png')
    assert resolve_workgroup_image_url(wg) == 'https://example.com/logo.png'


def test_dp_number_from_workgroup_title_fallback():
    wg = _Wg(acronym='custom-slug', name='DP11 - Safe and Ethical AI')
    assert dp_number_from_workgroup(wg) == 11


def test_dp_discovery_has_no_artwork():
    wg = _Wg(acronym='dp-discovery', slug='dp-discovery', name='DP Discovery')
    assert is_dp_discovery_workgroup(wg)
    assert resolve_workgroup_image_url(wg) is None
