#!/usr/bin/env python3
"""
Test layer resolution (subdomain + path fallback) per GOV-HUB-3.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_layer_resolution():
    from app import app
    from models import Layer
    from middleware import resolve_layer_from_host
    from services.utils import _is_uuid_like
    
    with app.app_context():
        # Ensure we have at least one layer
        layer = Layer.query.filter(Layer.approval_status == 'approved').first()
        if not layer:
            layer = Layer.query.first()
        if not layer:
            print("⚠️  No layers in DB - skipping path fallback test")
            return True
        
        slug = layer.slug
        public_id = layer.public_id
        client = app.test_client()
        
        print("Testing layer resolution (GOV-HUB-3 path fallback)...")
        
        # 1. Path /layers/<slug>/ should resolve g.layer
        from flask import g
        with app.test_request_context(path=f'/layers/{slug}/'):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is not None, f"g.layer should be set for /layers/{slug}/"
            assert g.layer.slug == slug
        print(f"   ✅ /layers/{slug}/ sets g.layer")
        
        # 2. Path /layer/<slug> serves standalone layer view
        r = client.get(f'/layer/{slug}')
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert slug in r.get_data(as_text=True), "Standalone should contain layer slug"
        print(f"   ✅ /layer/{slug} works (standalone)")
        
        # 3. Path /layer/<public_id> (UUID) serves standalone layer view
        r = client.get(f'/layer/{public_id}')
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert slug in r.get_data(as_text=True), "Standalone should contain layer slug"
        print(f"   ✅ /layer/<uuid> works (standalone)")
        
        # 4. _is_uuid_like helper
        assert _is_uuid_like(public_id) is True
        assert _is_uuid_like(slug) is False
        assert _is_uuid_like('') is False
        print(f"   ✅ _is_uuid_like helper works")
        
        # 5. Gov Hub + dev vanity hosts (BASE_DOMAINS); before HTTP API checks (DB may lag migrations)
        with app.test_request_context('/', headers={'Host': f'{slug}.govhub.live'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.govhub.live"
        print(f"   ✅ Host {slug}.govhub.live resolves layer")
        with app.test_request_context('/', headers={'Host': f'{slug}.dev.govhub.live'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.dev.govhub.live"
        print(f"   ✅ Host {slug}.dev.govhub.live resolves layer")
        with app.test_request_context('/', headers={'Host': f'{slug}.interfacehub.net'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.interfacehub.net"
        print(f"   ✅ Host {slug}.interfacehub.net resolves layer")
        with app.test_request_context('/', headers={'Host': f'{slug}.dev.interfacehub.net'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.dev.interfacehub.net"
        print(f"   ✅ Host {slug}.dev.interfacehub.net resolves layer")
        with app.test_request_context('/', headers={'Host': f'{slug}.hub.themetalayer.org'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.hub.themetalayer.org"
        print(f"   ✅ Host {slug}.hub.themetalayer.org resolves layer")
        with app.test_request_context('/', headers={'Host': f'{slug}.dev.hub.themetalayer.org'}):
            resolve_layer_from_host()
            assert g.layer is not None and g.layer.slug == slug, f"g.layer for {slug}.dev.hub.themetalayer.org"
        print(f"   ✅ Host {slug}.dev.hub.themetalayer.org resolves layer")
        with app.test_request_context('/', headers={'Host': 'dev.govhub.live'}):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is None, "dev.govhub.live must not map to a layer slug"
        print("   ✅ dev.govhub.live has no layer from host (reserved apex)")
        with app.test_request_context('/', headers={'Host': 'interfacehub.net'}):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is None, "interfacehub.net must not map to a layer slug"
        print("   ✅ interfacehub.net has no layer from host (reserved apex)")
        with app.test_request_context('/', headers={'Host': 'dev.interfacehub.net'}):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is None, "dev.interfacehub.net must not map to a layer slug"
        print("   ✅ dev.interfacehub.net has no layer from host (reserved apex)")
        with app.test_request_context('/', headers={'Host': 'hub.themetalayer.org'}):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is None, "hub.themetalayer.org must not map to a layer slug"
        print("   ✅ hub.themetalayer.org has no layer from host (reserved apex)")
        with app.test_request_context('/', headers={'Host': 'dev.hub.themetalayer.org'}):
            resolve_layer_from_host()
            assert getattr(g, 'layer', None) is None, "dev.hub.themetalayer.org must not map to a layer slug"
        print("   ✅ dev.hub.themetalayer.org has no layer from host (reserved apex)")
        
        # 6. Layers API
        r = client.get('/api/layers/')
        assert r.status_code == 200, f"Layers API returned {r.status_code}"
        print(f"   ✅ /api/layers/ works")
        
        # 7. Layer detail page
        r = client.get(f'/layers/{slug}/')
        assert r.status_code == 200, f"Layer detail returned {r.status_code}"
        print(f"   ✅ /layers/{slug}/ page loads")
        
        # 8. Activity feed (EventLog)
        r = client.get(f'/api/layers/{layer.id}/activity/')
        assert r.status_code == 200, f"Activity feed returned {r.status_code}"
        data = r.get_json()
        assert 'events' in data
        print(f"   ✅ /api/layers/<id>/activity/ works ({len(data['events'])} events)")
        
        print("\n✅ All layer resolution tests passed")
        return True

if __name__ == '__main__':
    try:
        ok = test_layer_resolution()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
