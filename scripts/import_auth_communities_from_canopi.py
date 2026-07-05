#!/usr/bin/env python3
"""
Import Canopi auth MetaCommunities into Gov Hub as auth_community layers and link 1:1.

Requires: Flask app context (run from gov-hub-dev root):
  python scripts/import_auth_communities_from_canopi.py

Env:
  CANOPI_INTERNAL_API_URL – Canopi API base (for optional post-import provision)
  GOV_HUB_API_KEY – shared secret for Canopi internal routes
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    from app import app
    from extensions import db
    from models import Layer, User
    from services.utils import create_slug
    from services.canopi_community_sync import provision_or_sync_layer

    try:
        import requests
    except ImportError:
        print('requests is required')
        sys.exit(1)

    canopi_base = os.environ.get('CANOPI_INTERNAL_API_URL', 'http://127.0.0.1:3001').rstrip('/')
    # List auth communities via Canopi DB is not exposed; use direct SQL URL or pass JSON file.
    # This script expects CANOPI_AUTH_IMPORT_JSON or queries Postgres if DATABASE_URL points at Canopi.
    import json

    raw = os.environ.get('CANOPI_AUTH_IMPORT_JSON', '').strip()
    if not raw:
        print(
            'Set CANOPI_AUTH_IMPORT_JSON to a JSON array of '
            '{id,name,auth_provider,description} from Canopi MetaCommunity.'
        )
        sys.exit(1)

    rows = json.loads(raw)
    if not isinstance(rows, list):
        print('CANOPI_AUTH_IMPORT_JSON must be a JSON array')
        sys.exit(1)

    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User.query.first()
        if not admin:
            print('No Gov Hub user found to set as layer initiator')
            sys.exit(1)

        created = 0
        linked = 0
        for row in rows:
            mc_id = str(row.get('id') or '').strip()
            provider = str(row.get('auth_provider') or row.get('authProvider') or '').strip()
            name = str(row.get('name') or f'{provider} Auth').strip()
            if not mc_id or not provider:
                continue

            existing = Layer.query.filter_by(canopi_meta_community_id=mc_id).first()
            if existing:
                linked += 1
                provision_or_sync_layer(existing, force=True)
                continue

            by_provider = Layer.query.filter_by(
                layer_kind='auth_community', auth_provider=provider
            ).first()
            if by_provider:
                by_provider.canopi_meta_community_id = mc_id
                db.session.commit()
                provision_or_sync_layer(by_provider, force=True)
                linked += 1
                continue

            slug_base = create_slug(name)
            slug = slug_base
            n = 1
            while Layer.query.filter_by(slug=slug).first():
                slug = f'{slug_base}-auth-{n}'
                n += 1

            layer = Layer(
                name=name,
                slug=slug,
                initiator_id=admin.id,
                mission=row.get('description') or f'Auth community for {provider}',
                status='active',
                approval_status='approved',
                listing_visibility='private',
                join_policy='open',
                layer_kind='auth_community',
                auth_provider=provider,
                stewardship='unmanaged',
                canopi_meta_community_id=mc_id,
            )
            db.session.add(layer)
            db.session.commit()
            provision_or_sync_layer(layer, canopi_meta_community_id=mc_id, force=True)
            created += 1
            print(f'✅ {name} ({provider}) → layer {layer.id}')

        print(f'Done: created={created} linked={linked}')


if __name__ == '__main__':
    main()
