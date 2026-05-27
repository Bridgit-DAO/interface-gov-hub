"""Tests for nav pill config and tips."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_normalize_site_nav_pill_config():
    from services.nav_pills import normalize_site_nav_pill_config

    cfg = normalize_site_nav_pill_config({
        'pages': {'layer': False, 'badges': True},
        'tooltips_enabled': False,
        'default_animation': 'breathing',
    })
    assert cfg['pages']['layer'] is False
    assert cfg['pages']['badges'] is True
    assert cfg['tooltips_enabled'] is False
    assert cfg['default_animation'] == 'breathing'


def test_validate_layer_nav_pill_patch():
    from services.nav_pills import validate_layer_nav_pill_patch

    out, err = validate_layer_nav_pill_patch({'animation': 'shimmer', 'tooltips_enabled': True})
    assert err is None
    assert out['animation'] == 'shimmer'
    assert out['tooltips_enabled'] is True

    out, err = validate_layer_nav_pill_patch({'animation': 'invalid'})
    assert out is None
    assert 'animation must be' in err


def test_layer_tab_tips_present():
    from services.nav_pills import layer_tab_tip

    assert layer_tab_tip('overview')
    assert 'team' in layer_tab_tip('workgroups').lower()


def test_nav_pills_container_attrs():
    from services.nav_pills import nav_pills_container_attrs

    attrs = nav_pills_container_attrs({
        'enabled': True,
        'animation': 'hover-grow',
        'tooltips_enabled': True,
    }, context_id='demo')
    assert 'data-gh-nav-pills' in attrs
    assert 'hover-grow' in attrs

    assert nav_pills_container_attrs({'enabled': False}) == ''
