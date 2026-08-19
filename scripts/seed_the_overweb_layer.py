#!/usr/bin/env python3
"""Idempotent seed: The Overweb layer for dev/staging Gov Hub.

Usage (from gov-hub-dev, with dev .env loaded as usual via app):
  PYTHONPATH=/home/ubuntu/gov-hub-dev python3 scripts/seed_the_overweb_layer.py

Creates or updates layer slug `the-overweb` so campaign monument imports
(e.g. import_teilhard_monument.py) can attach to the correct layer.
"""
from __future__ import annotations

from datetime import datetime

from app import app
from extensions import db
from models import Layer, LayerMember, User

SLUG = 'the-overweb'
NAME = 'The Overweb'
INITIATOR_EMAIL = 'daveed@bridgit.io'


def main() -> None:
    with app.app_context():
        user = User.query.filter_by(email=INITIATOR_EMAIL).first()
        if not user:
            user = (
                User.query.filter(User.role.in_(('admin', 'editor'))).first()
                or User.query.first()
            )
        if not user:
            raise SystemExit('no user available for layer initiator')

        layer = Layer.query.filter_by(slug=SLUG).first()
        created = False
        if not layer:
            layer = Layer(
                name=NAME,
                slug=SLUG,
                initiator_id=user.id,
                mission=(
                    "To create the world's first safe, decentralized, and pervasive "
                    'public space above the Web, enabling real-time presence, '
                    'contextual collaboration, and community-governed interaction '
                    'wherever people encounter digital content.'
                ),
                description=(
                    'The Overweb is the first major instantiation of the Metaweb: a living, '
                    'participatory public space that exists above all webpages. It operationalizes '
                    "the Metaweb's principles through real-time presence, on-page interaction, "
                    'meta-communities, and programmable governance.'
                ),
                status='active',
                approval_status='approved',
                approved_by_id=user.id,
                approved_at=datetime.utcnow(),
                display_status='active',
                listing_visibility='public',
                join_policy='open',
                layer_kind='standard',
                last_activity=datetime.utcnow(),
            )
            db.session.add(layer)
            db.session.flush()
            created = True
        else:
            layer.approval_status = 'approved'
            layer.display_status = 'active'
            layer.status = 'active'
            if not layer.approved_by_id:
                layer.approved_by_id = user.id
                layer.approved_at = datetime.utcnow()

        member = LayerMember.query.filter_by(layer_id=layer.id, user_id=user.id).first()
        if not member:
            db.session.add(
                LayerMember(
                    layer_id=layer.id,
                    user_id=user.id,
                    role='admin',
                    status='active',
                )
            )
        else:
            member.role = 'admin'
            member.status = 'active'

        db.session.commit()
        print(
            {
                'created_layer': created,
                'layer_id': layer.id,
                'layer_slug': layer.slug,
                'initiator_email': user.email,
            }
        )


if __name__ == '__main__':
    main()
