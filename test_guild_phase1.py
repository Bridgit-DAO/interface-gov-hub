#!/usr/bin/env python3
"""Smoke tests for Unified Phase I guild ↔ layer / guild ↔ artifact links."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_layer_guild_links_list_ok():
    from app import app
    from models import Layer

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer – skip')
            return
        lid = layer.id

    with app.test_client() as c:
        r = c.get(f'/api/layers/{lid}/guilds/')
        assert r.status_code == 200, r.get_data(as_text=True)
        d = r.get_json()
        assert 'links' in d and isinstance(d['links'], list)


def test_artifact_guild_links_404():
    from app import app

    with app.test_client() as c:
        r = c.get('/api/artifacts/nonexistent-uuid-00000000/guild-links/')
        assert r.status_code == 404


def test_guild_layers_list_ok():
    from app import app
    from models import Guild

    with app.app_context():
        g = Guild.query.first()
        if not g:
            print('⚠️  No guild – skip')
            return
        gid = g.id

    with app.test_client() as c:
        r = c.get(f'/api/guilds/{gid}/layers/')
        assert r.status_code == 200
        d = r.get_json()
        assert 'links' in d


if __name__ == '__main__':
    test_layer_guild_links_list_ok()
    print('✅ test_layer_guild_links_list_ok')
    test_artifact_guild_links_404()
    print('✅ test_artifact_guild_links_404')
    test_guild_layers_list_ok()
    print('✅ test_guild_layers_list_ok')
