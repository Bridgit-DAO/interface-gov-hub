"""Per-layer product feature overrides."""
import pytest

from app import app
from extensions import db
from models import Layer, SiteConfig
from services.layer_features import (
    LAYER_FEATURE_ORDER,
    get_effective_features,
    is_layer_tab_enabled,
    merge_rollout_with_layer,
    parse_layer_enabled_features,
    resolve_layer_from_path,
    validate_layer_features_patch,
)
from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY, set_rollout_config


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        from migrations import migrate_layer_enabled_features, migrate_layer_nav_pill_config

        migrate_layer_enabled_features(app)
        migrate_layer_nav_pill_config(app)
    with app.test_client() as c:
        yield c


def test_parse_layer_enabled_features_empty():
    layer = Layer(name='T', slug='t-test-parse', initiator_id='u1')
    assert parse_layer_enabled_features(layer) == {}


def test_merge_rollout_with_layer_disables():
    layer = Layer(
        name='T2',
        slug='t-test-merge',
        initiator_id='u1',
        enabled_features='{"votes": false, "artifacts": true}',
    )
    global_cfg = {k: True for k in ('layers', 'docs', 'roles', 'workgroups', 'votes', 'artifacts')}
    merged = merge_rollout_with_layer(global_cfg, layer)
    assert merged['votes'] is False
    assert merged['artifacts'] is True


def test_is_layer_tab_enabled():
    eff = {'roles': False, 'votes': True}
    assert is_layer_tab_enabled('clusters', eff) is False
    assert is_layer_tab_enabled('votes', eff) is True


def test_validate_layer_features_patch_accepts_all_features():
    with app.app_context():
        gcfg = {k: True for k in LAYER_FEATURE_ORDER}
        out, err = validate_layer_features_patch(
            {'waitlists': False, 'guilds': True}, global_cfg=gcfg
        )
    assert err is None
    assert out == {'waitlists': False}


def test_validate_layer_features_patch_rejects_unknown():
    with app.app_context():
        gcfg = {k: True for k in LAYER_FEATURE_ORDER}
        out, err = validate_layer_features_patch({'not_a_feature': False}, global_cfg=gcfg)
    assert out is None
    assert 'not_a_feature' in (err or '')


def test_waitlists_path_requires_flag():
    from services.product_rollout import path_requires_feature_flags

    need = path_requires_feature_flags('/api/layers/abc/waitlists/')
    assert 'waitlists' in need
    assert 'layers' in need


def test_layer_page_hides_votes_tab_when_disabled(client):
    with app.app_context():
        SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).delete()
        db.session.commit()
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            layer = Layer(
                name='Test Layer Features',
                slug='test-layer-features',
                initiator_id='admin',
                enabled_features='{"votes": false}',
            )
            db.session.add(layer)
        else:
            layer.enabled_features = '{"votes": false}'
        db.session.commit()
        slug = layer.slug

    r = client.get(f'/layers/{slug}/')
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert 'id="votes-tab"' not in text
    assert 'id="overview-tab"' in text


def test_api_layer_artifacts_blocked_when_disabled(client):
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            pytest.skip('test layer missing')
        layer.enabled_features = '{"artifacts": false}'
        db.session.commit()
        lid = layer.id

    r = client.get(f'/api/layers/{lid}/artifacts/')
    assert r.status_code == 403
    data = r.get_json()
    assert data.get('error_code') == 'FEATURE_DISABLED'


def test_api_layer_quests_empty_when_disabled(client):
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            pytest.skip('test layer missing')
        layer.enabled_features = '{"quests": false}'
        db.session.commit()
        lid = layer.id

    r = client.get(f'/api/layers/{lid}/quests/')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('quests') == []


def test_api_layer_roles_empty_when_disabled(client):
    """Global directories aggregate layers; disabled layer returns empty list, not 403."""
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            pytest.skip('test layer missing')
        layer.enabled_features = '{"roles": false}'
        db.session.commit()
        lid = layer.id

    r = client.get(f'/api/layers/{lid}/roles/')
    assert r.status_code == 200
    data = r.get_json()
    assert data.get('roles') == []
    assert data.get('count') == 0


def test_resolve_layer_from_path():
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            pytest.skip('test layer missing')
        found = resolve_layer_from_path(f'/layers/{layer.slug}/votes/')
        assert found is not None
        assert found.id == layer.id


def _ensure_test_layer():
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            layer = Layer(
                name='Test Layer Features',
                slug='test-layer-features',
                initiator_id='admin',
            )
            db.session.add(layer)
            db.session.commit()
        return layer.slug


def test_layer_page_living_design_markup(client):
    slug = _ensure_test_layer()
    r = client.get(f'/layers/{slug}/')
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert 'living-layer-hero' in text
    assert 'layer-feature-pills' in text
    assert 'living-modules-grid' in text
    assert 'buildLayerPulseStrip' in text


def test_layer_page_waitlists_group_hidden_when_disabled(client):
    slug = _ensure_test_layer()
    with app.app_context():
        layer = Layer.query.filter_by(slug=slug).first()
        layer.enabled_features = '{"waitlists": false}'
        db.session.commit()
    r = client.get(f'/layers/{slug}/')
    text = r.get_data(as_text=True)
    assert 'id="waitlist-tabs-marker"' not in text


def test_layer_page_single_tablist_with_overview(client):
    slug = _ensure_test_layer()
    r = client.get(f'/layers/{slug}/')
    text = r.get_data(as_text=True)
    assert 'id="projectTabs"' in text
    assert 'id="overview-tab"' in text
    assert text.count('role="tablist"') >= 1


def test_validate_layer_features_rejects_site_disabled_key():
    with app.app_context():
        gcfg = {k: True for k in LAYER_FEATURE_ORDER}
        gcfg['votes'] = False
        out, err = validate_layer_features_patch({'votes': False}, global_cfg=gcfg)
        assert out is None
        assert 'site-wide' in (err or '').lower()


def test_validate_layer_features_accepts_false_for_site_enabled():
    with app.app_context():
        gcfg = {k: True for k in LAYER_FEATURE_ORDER}
        out, err = validate_layer_features_patch({'votes': False}, global_cfg=gcfg)
        assert err is None
        assert out == {'votes': False}


def test_layers_directory_map_tiles(client):
    r = client.get('/layers/')
    assert r.status_code == 200
    assert 'layer-map-tile' in r.get_data(as_text=True)


def test_nav_hides_guilds_when_rollout_disabled(client):
    with app.app_context():
        from services.product_rollout import FEATURE_KEYS, get_rollout_config

        prev = get_rollout_config()
        cfg = {k: True for k in FEATURE_KEYS}
        cfg['guilds'] = False
        set_rollout_config(cfg)
    try:
        r = client.get('/person/')
        assert r.status_code == 200
        text = r.get_data(as_text=True)
        assert 'data-gh-i18n="nav.guilds"' not in text
    finally:
        with app.app_context():
            set_rollout_config(prev)


def test_waitlist_deep_link_hoists_enabled_waitlists(client):
    """Waitlist referral URLs set initialWaitlistId; enabledWaitlists must be in outer scope."""
    waitlist_id = 'ed3f6ea9-562a-40f7-9ec4-2443cf8ff127'
    with app.app_context():
        layer = Layer.query.filter_by(slug='test-layer-features').first()
        if not layer:
            layer = Layer(
                name='Test Layer Features',
                slug='test-layer-features',
                initiator_id='admin',
            )
            db.session.add(layer)
            db.session.commit()
        slug = layer.slug

    r = client.get(f'/layers/{slug}/waitlist/{waitlist_id}/')
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert waitlist_id in text
    assert 'let enabledWaitlists = []' in text
    assert 'enabledWaitlists.find(w => w.id === initialWaitlistId)' in text
