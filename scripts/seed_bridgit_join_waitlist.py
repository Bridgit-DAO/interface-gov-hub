#!/usr/bin/env python3
"""Idempotent seed: Bridgit DAO join waitlist on layer bridgit-dao.

Usage (from gov-hub-prod, with prod .env loaded as usual via app):
  PYTHONPATH=/home/ubuntu/gov-hub-prod python3 scripts/seed_bridgit_join_waitlist.py

Creates:
  - Waitlist "Bridgit DAO join" on layer slug `bridgit-dao`
  - Email join via POST /api/waitlists/<id>/join-email/
"""
from __future__ import annotations

from datetime import datetime

from app import app
from extensions import db
from models import Layer, Waitlist

LAYER_SLUG = "bridgit-dao"
WAITLIST_NAME = "Bridgit DAO join"


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
                    "Join interest for Bridgit DAO: Build Good, Agents Among Us, "
                    "Overweb, governance, and estate coordination."
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
                "layer_id": layer.id,
                "layer_slug": layer.slug,
                "waitlist_id": waitlist.id,
                "join_email": (
                    "https://interfacehub.net/api/waitlists/"
                    f"{waitlist.id}/join-email/"
                ),
            }
        )


if __name__ == "__main__":
    main()
