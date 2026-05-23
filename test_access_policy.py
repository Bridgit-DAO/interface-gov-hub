"""Unit tests for access_policy (quest join rules, listing visibility)."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_can_user_submit_quest_open_allows():
    from services.access_policy import can_user_submit_quest

    quest = SimpleNamespace(
        id='q1', layer_id='lay1', join_policy='open', creator_user_id=None
    )
    ok, err = can_user_submit_quest(quest, {'id': 'u1'})
    assert ok and err is None


def test_can_user_submit_quest_open_to_layer_requires_membership():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, User
    from services.access_policy import can_user_submit_quest
    from uuid import uuid4

    with app.app_context():
        layer = Layer.query.first()
        user = User.query.first()
        if not layer or not user:
            return
        quest = SimpleNamespace(
            id=str(uuid4()),
            layer_id=layer.id,
            join_policy='open_to_layer',
            creator_user_id=None,
        )
        LayerMember.query.filter_by(layer_id=layer.id, user_id=user.id).delete()
        db.session.commit()
        ok, err = can_user_submit_quest(quest, {'id': user.id})
        assert not ok
        assert 'layer' in (err or '').lower()
        db.session.add(
            LayerMember(
                id=str(uuid4()),
                layer_id=layer.id,
                user_id=user.id,
                status='active',
                role='member',
            )
        )
        db.session.commit()
        ok2, err2 = can_user_submit_quest(quest, {'id': user.id})
        assert ok2 and err2 is None


def test_quest_listing_private_hides_from_anonymous():
    from app import app
    from models import Layer, Quest
    from services.access_policy import quest_listing_visible
    from uuid import uuid4

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            return
        q = Quest(
            id=str(uuid4()),
            public_id=str(uuid4()),
            layer_id=layer.id,
            title='Private quest test',
            listing_visibility='private',
            join_policy='open',
            status='open',
        )
        assert not quest_listing_visible(q, None)
        assert quest_listing_visible(q, {'id': layer.initiator_id})
