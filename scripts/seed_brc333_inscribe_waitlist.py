#!/usr/bin/env python3
"""Idempotent seed: BRC333 Studio inscribe access waitlist on The Overweb layer.

Usage (from gov-hub-prod, with prod .env loaded as usual via app):
  PYTHONPATH=/home/ubuntu/gov-hub-prod python3 scripts/seed_brc333_inscribe_waitlist.py

Creates:
  - Waitlist "BRC333 Studio inscribe access" on layer slug `the-overweb`
  - Authenticated join via POST /api/waitlists/<id>/join/
  - Public page: https://hub.themetalayer.org/waitlists/<id>/
"""
from __future__ import annotations

from datetime import datetime

from app import app
from extensions import db
from models import Layer, Waitlist

LAYER_SLUG = "the-overweb"
WAITLIST_NAME = "BRC333 Studio inscribe access"


def main() -> None:
    with app.app_context():
        layer = Layer.query.filter_by(slug=LAYER_SLUG).first()
        if not layer:
            raise SystemExit(f"layer missing: {LAYER_SLUG}")

        waitlist = Waitlist.query.filter_by(
            layer_id=layer.id, name=WAITLIST_NAME
        ).first()
        created = False
        if not waitlist:
            waitlist = Waitlist(
                layer_id=layer.id,
                name=WAITLIST_NAME,
                description=(
                    "Early access to inscribe forever badges, blogs, books, and "
                    "InfoMonuments with BRC333 Studio on Bitcoin. Join the waitlist "
                    "and we will notify you when general inscribing opens."
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
            created = True
        else:
            waitlist.active = True
            waitlist.archived = False
            waitlist.public = True

        db.session.commit()
        print(
            {
                "created_waitlist": created,
                "layer_slug": LAYER_SLUG,
                "waitlist_id": waitlist.id,
                "waitlist_url": f"https://hub.themetalayer.org/waitlists/{waitlist.id}/",
                "join_api": f"https://hub.themetalayer.org/api/waitlists/{waitlist.id}/join/",
            }
        )


if __name__ == "__main__":
    main()
