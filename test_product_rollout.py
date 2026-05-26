"""Tests for product rollout SiteConfig + admin page."""
import pytest

from app import app
from extensions import db
from models import SiteConfig
from services.product_rollout import (
    PRODUCT_ROLLOUT_SITE_CONFIG_KEY,
    FEATURE_KEYS,
    get_rollout_config,
    is_feature_enabled,
    path_requires_feature_flags,
    set_rollout_config,
    should_block_path_request,
)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_get_rollout_defaults_all_true_without_row():
    with app.app_context():
        SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
        db.session.commit()
        cfg = get_rollout_config()
        assert cfg['layers'] is True
        assert cfg['docs'] is True
        assert cfg['immortalize'] is False
        assert is_feature_enabled('roles') is True
        assert is_feature_enabled('workgroups') is True
        assert is_feature_enabled('immortalize') is False


def test_immortalize_paths_require_flag():
    need = path_requires_feature_flags('/immortalize/')
    assert 'immortalize' in need
    need = path_requires_feature_flags('/api/inscribe/create-payment/')
    assert 'immortalize' in need


def test_ordinal_preview_not_gated_by_immortalize():
    """Draft submit 'From Ordinal' uses preview/convert APIs; not part of Immortalize."""
    need = path_requires_feature_flags('/api/ordinal/preview')
    assert 'immortalize' not in need
    need = path_requires_feature_flags('/api/ordinal/convert-markdown')
    assert 'immortalize' not in need


def test_ordinal_preview_allowed_when_immortalize_disabled(client):
    with app.app_context():
        cfg = {k: True for k in FEATURE_KEYS}
        cfg['immortalize'] = False
        set_rollout_config(cfg)
    try:
        r = client.post(
            '/api/ordinal/preview',
            json={'inscriptionId': 'e3edc22a4d8faefc81693775449b86a5201989224b44b7b6c8i0'},
        )
        assert r.status_code != 403, r.get_data(as_text=True)
        data = r.get_json() or {}
        assert data.get('error_code') != 'FEATURE_DISABLED'
    finally:
        with app.app_context():
            SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
            db.session.commit()


def test_immortalize_blocked_when_disabled(client):
    with app.app_context():
        cfg = {k: True for k in FEATURE_KEYS}
        cfg['immortalize'] = False
        set_rollout_config(cfg)
    try:
        r = client.get('/immortalize/', follow_redirects=False)
        assert r.status_code == 403
        r2 = client.get('/submit/?tab=immortalize', follow_redirects=False)
        assert r2.status_code == 403
    finally:
        with app.app_context():
            SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
            db.session.commit()


def test_set_rollout_persists():
    with app.app_context():
        set_rollout_config(
            {
                'layers': True,
                'docs': True,
                'roles': False,
                'workgroups': False,
            }
        )
        cfg = get_rollout_config()
        assert cfg['roles'] is False
        assert is_feature_enabled('workgroups') is False
        # reset for other tests
        SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
        db.session.commit()


def test_product_rollout_page_requires_auth(client):
    r = client.get('/admin/product-rollout/', follow_redirects=False)
    assert r.status_code in (302, 401)


def test_product_rollout_page_200_for_admin(client):
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
    r = client.get('/admin/product-rollout/')
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert 'Product rollout' in text
    assert 'name="feature_layers"' in text


def test_doc_path_blocked_when_docs_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'docs' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/doc/all/')
    assert r.status_code == 403


def test_layers_path_blocked_when_layers_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'layers' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/layers/')
    assert r.status_code == 403


def test_admin_path_blocked_when_admin_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'admin' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/admin/', follow_redirects=False)
    assert r.status_code == 403


def test_product_rollout_page_ok_when_admin_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'admin' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    with client.session_transaction() as sess:
        sess['user'] = 'admin'
    r = client.get('/admin/product-rollout/')
    assert r.status_code == 200


def test_soft_launch_blocked_when_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'soft_launch' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/soft-launch/', follow_redirects=False)
    assert r.status_code == 403


def test_soft_launch_gated_path_does_not_use_prefix_false_positive():
    """URL segment /soft-launch must not match path /soft-launching-..."""
    assert 'soft_launch' not in path_requires_feature_flags('/soft-launching-demo/')


def test_guilds_blocked_when_guilds_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'guilds' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/guilds/', follow_redirects=False)
    assert r.status_code == 403


def test_badges_directory_blocked_when_badges_disabled(client, monkeypatch):
    from services import product_rollout as pr

    def _cfg():
        return {k: k != 'badges' for k in pr.FEATURE_KEYS}

    monkeypatch.setattr(pr, 'get_rollout_config', _cfg)
    r = client.get('/badges/', follow_redirects=False)
    assert r.status_code == 403


def test_votes_directory_no_trailing_slash_requires_votes():
    assert 'votes' in path_requires_feature_flags('/votes')


def test_should_block_is_deterministic_first_feature_key_order():
    """When several required flags are off, report the first in FEATURE_KEYS."""
    cfg = {k: False for k in FEATURE_KEYS}
    path = '/layers/some/doc/'  # needs layers + docs
    blocked = should_block_path_request(path, cfg)
    lix = FEATURE_KEYS.index('layers')
    dix = FEATURE_KEYS.index('docs')
    assert lix < dix
    assert blocked == 'layers'


def test_get_rollout_accepts_alternate_json_key_casing():
    with app.app_context():
        SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
        row = SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value='{"Soft_Launch": false}')
        db.session.add(row)
        db.session.commit()
        try:
            cfg = get_rollout_config()
            assert cfg['soft_launch'] is False
            assert is_feature_enabled('soft-launch') is False
            assert is_feature_enabled('Soft_Launch') is False
        finally:
            SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
            db.session.commit()
