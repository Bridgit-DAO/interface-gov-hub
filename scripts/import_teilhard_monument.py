#!/usr/bin/env python3
"""Import the Teilhard campaign seed into the Overweb Monument record."""
from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from app import app
from database import init_db
from extensions import db
from models import Layer, Monument, User
from services.campaign_pages import (
    build_monument_presentation_from_seed,
    build_monument_structure_from_seed,
    reload_campaign_cache,
)


SEED_PATH = os.path.join(
    app.root_path,
    'static',
    'campaign',
    'teilhard',
    'campaign-seed.json',
)


def _steward_user_id() -> str | None:
    user = (
        User.query.filter(User.email == 'daveed@bridgit.io').first()
        or User.query.filter(User.role.in_(('admin', 'editor'))).first()
        or User.query.first()
    )
    return getattr(user, 'id', None) if user else None


def main() -> None:
    with app.app_context():
        init_db(app)
        with open(SEED_PATH, encoding='utf-8') as handle:
            seed = json.load(handle)

        layer_slug = seed.get('layerSlug') or 'the-overweb'
        layer = Layer.query.filter_by(slug=layer_slug).first()
        if not layer:
            raise SystemExit(f'Layer not found: {layer_slug}')

        campaign_slug = seed.get('slug') or 'teilhard'
        monument = Monument.query.filter_by(campaign_slug=campaign_slug).first()
        if not monument:
            monument = Monument(
                layer_id=layer.id,
                title=seed.get('title') or 'The Teilhard Test',
                monument_type='book',
                campaign_slug=campaign_slug,
                steward_user_id=_steward_user_id(),
                status='active',
            )
            db.session.add(monument)

        presentation = build_monument_presentation_from_seed(seed)
        structure = build_monument_structure_from_seed(seed)

        monument.layer_id = layer.id
        monument.title = seed.get('title') or monument.title
        monument.description = seed.get('subtitle') or seed.get('heroQuestion')
        monument.monument_type = 'book'
        monument.campaign_slug = campaign_slug
        monument.custom_domains_json = json.dumps(seed.get('customDomains') or [], indent=2)
        monument.presentation_json = json.dumps(presentation, indent=2)
        monument.structure_json = json.dumps(structure, indent=2)
        monument.uri = (seed.get('customDomains') or [''])[0] or seed.get('devHost')
        if not monument.steward_user_id:
            monument.steward_user_id = _steward_user_id()

        db.session.commit()
        reload_campaign_cache()

        print(f'Imported monument: {monument.title}')
        print(f'  id: {monument.id}')
        print(f'  campaign_slug: {monument.campaign_slug}')
        print(f'  nodes: {len(structure.get("nodes") or [])}')


if __name__ == '__main__':
    main()
