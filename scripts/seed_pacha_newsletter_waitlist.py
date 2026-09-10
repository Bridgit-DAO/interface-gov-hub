#!/usr/bin/env python3
"""Idempotent seed: Pacha layer + newsletter waitlist (production Gov Hub).

Usage (from gov-hub-prod, with prod .env loaded as usual via app):
  PYTHONPATH=/home/ubuntu/gov-hub-prod python3 scripts/seed_pacha_newsletter_waitlist.py

Creates:
  - Layer slug `pacha` (approved/active), initiator Daveed
  - Waitlist "Pacha news and family activities" for email join via
    POST /api/waitlists/<id>/join-email/
"""
from __future__ import annotations

from datetime import datetime

from app import app
from extensions import db
from models import Layer, LayerMember, User, Waitlist

INITIATOR_ID = "57e7c23e-29ec-423a-baee-51ddf34a8174"
SLUG = "pacha"
NAME = "Pacha's Pajamas"
WAITLIST_NAME = "Pacha news and family activities"


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
                    "Pacha's Pajamas is a musical storyworld where families listen, "
                    "read, and imagine together."
                ),
                description=(
                    "News and family activities from Pachaverse. Adult email signup "
                    "only; no login required."
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
                    "Optional adult email list for Pacha news and family activities. "
                    "Independent of Majik Kids listening."
                ),
                public=True,
                referrals=False,
                active=True,
                start_date=datetime.utcnow(),
                closing_date=None,
                max_number=None,
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
                "join_email": (
                    "https://interfacehub.net/api/waitlists/"
                    f"{waitlist.id}/join-email/"
                ),
            }
        )


if __name__ == "__main__":
    main()
