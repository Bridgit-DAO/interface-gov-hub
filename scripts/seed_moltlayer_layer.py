#!/usr/bin/env python3
"""Idempotent seed: Moltlayer layer + early-access waitlist (production Gov Hub).

Usage (from gov-hub-prod, with prod .env loaded as usual via app):
  python3 scripts/seed_moltlayer_layer.py

Creates:
  - Layer slug `moltlayer` (approved/active), initiator Daveed
  - Waitlist "Moltlayer early access" for email join via
    POST /api/waitlists/<id>/join-email/

Vanity hosts (wildcard nginx already covers these once slug exists):
  https://moltlayer.interfacehub.net/ → /layers/moltlayer/
  https://moltlayer.themetalayer.org/
"""
from __future__ import annotations

from datetime import datetime

from app import app
from extensions import db
from models import Layer, LayerMember, User, Waitlist

INITIATOR_ID = "57e7c23e-29ec-423a-baee-51ddf34a8174"
SLUG = "moltlayer"
NAME = "Moltlayer"
WAITLIST_NAME = "Moltlayer early access"


def main() -> None:
    with app.app_context():
        user = User.query.get(INITIATOR_ID)
        if not user:
            raise SystemExit(f"initiator user missing: {INITIATOR_ID}")

        layer = Layer.query.filter_by(slug=SLUG).first()
        created_layer = False
        if not layer:
            layer = Layer(
                name=NAME,
                slug=SLUG,
                initiator_id=INITIATOR_ID,
                mission=(
                    "Moltlayer is the agent-native face of Canopi: presence and "
                    "action on real URLs, with humans as first-class observers."
                ),
                description=(
                    "Interest and early access for Moltlayer operators and humans. "
                    "Public agent onboarding is not live yet — join the waitlist "
                    "for notice."
                ),
                status="active",
                approval_status="approved",
                approved_by_id=INITIATOR_ID,
                approved_at=datetime.utcnow(),
                display_status="active",
                listing_visibility="public",
                join_policy="open",
                layer_kind="standard",
                last_activity=datetime.utcnow(),
            )
            db.session.add(layer)
            db.session.flush()
            created_layer = True
        else:
            layer.approval_status = "approved"
            layer.display_status = "active"
            layer.status = "active"
            if not layer.approved_by_id:
                layer.approved_by_id = INITIATOR_ID
                layer.approved_at = datetime.utcnow()

        member = LayerMember.query.filter_by(
            layer_id=layer.id, user_id=INITIATOR_ID
        ).first()
        if not member:
            db.session.add(
                LayerMember(
                    layer_id=layer.id,
                    user_id=INITIATOR_ID,
                    role="admin",
                    status="active",
                )
            )
        else:
            member.role = "admin"
            member.status = "active"

        waitlist = Waitlist.query.filter_by(
            layer_id=layer.id, name=WAITLIST_NAME
        ).first()
        created_wl = False
        if not waitlist:
            waitlist = Waitlist(
                layer_id=layer.id,
                name=WAITLIST_NAME,
                description=(
                    "For humans and operators interested in Moltlayer. "
                    "We email when agent onboarding / early access opens."
                ),
                public=True,
                referrals=True,
                active=True,
                start_date=datetime.utcnow(),
                closing_date=None,
                max_number=5000,
                archived=False,
                milestones=False,
                show_milestones="all",
            )
            db.session.add(waitlist)
            created_wl = True
        else:
            waitlist.active = True
            waitlist.archived = False
            waitlist.public = True

        db.session.commit()
        print(
            {
                "created_layer": created_layer,
                "created_waitlist": created_wl,
                "layer_id": layer.id,
                "layer_slug": layer.slug,
                "waitlist_id": waitlist.id,
                "layer_url": f"https://interfacehub.net/layers/{layer.slug}/",
                "vanity_hub": f"https://{layer.slug}.interfacehub.net/",
                "join_email": (
                    "https://interfacehub.net/api/waitlists/"
                    f"{waitlist.id}/join-email/"
                ),
            }
        )


if __name__ == "__main__":
    main()
