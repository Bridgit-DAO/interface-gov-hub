#!/usr/bin/env python3
"""Tests for layer email invitations (any active member may invite)."""
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _auth_client(app, username):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = username
    return client


def test_layer_invitation_preview_404():
    from app import app

    with app.test_client() as c:
        r = c.get('/api/layer-invitations/by-token/not-a-real-token/')
        assert r.status_code == 404


def test_layer_invite_landing_page():
    from app import app

    with app.test_client() as c:
        r = c.get('/layer/invite/bad-token/')
        assert r.status_code == 200
        text = r.get_data(as_text=True)
        assert 'Layer invitation' in text


def test_create_invitation_requires_member():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, User

    with app.app_context():
        from services.coordination import is_layer_admin
        from services.layer_invitations import can_send_layer_invitations

        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer — skip')
            return
        outsider = None
        for user in User.query.filter(User.role.notin_(['admin', 'editor'])).all():
            if can_send_layer_invitations(layer.id, user.id):
                continue
            outsider = user
            break
        if not outsider:
            print('⚠️  No non-inviter user — skip')
            return
        layer_id = layer.id
        outsider_username = outsider.username

    client = _auth_client(app, outsider_username)
    r = client.post(
        f'/api/layers/{layer_id}/invitations/',
        json={'email': 'newperson@example.com'},
    )
    assert r.status_code == 403, r.get_data(as_text=True)


def test_create_invitation_allows_layer_initiator():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, User

    with app.app_context():
        layer = Layer.query.filter(Layer.slug == 'nevada-isoc').first()
        if not layer:
            layer = Layer.query.first()
        if not layer or not layer.initiator_id:
            print('⚠️  Need layer with initiator — skip')
            return
        initiator = User.query.get(layer.initiator_id)
        if not initiator:
            print('⚠️  Initiator missing — skip')
            return
        layer_id = layer.id
        username = initiator.username
        LayerMember.query.filter_by(layer_id=layer.id, user_id=initiator.id).delete()
        db.session.commit()

    client = _auth_client(app, username)
    r = client.post(
        f'/api/layers/{layer_id}/invitations/',
        json={'email': 'prospect@example.com', 'message': 'Join us'},
    )
    assert r.status_code in (200, 201), r.get_data(as_text=True)


def test_create_invitation_duplicate_member():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, User

    with app.app_context():
        layer = Layer.query.first()
        users = User.query.filter(User.email.isnot(None)).limit(2).all()
        if not layer or len(users) < 2:
            print('⚠️  Need layer + 2 users with email — skip')
            return
        inviter, existing = users[0], users[1]
        layer_id = layer.id
        inviter_username = inviter.username
        existing_email = existing.email.strip().lower()
        for u in (inviter, existing):
            member = LayerMember.query.filter_by(layer_id=layer.id, user_id=u.id).first()
            if not member:
                db.session.add(
                    LayerMember(
                        id=str(uuid4()),
                        layer_id=layer.id,
                        user_id=u.id,
                        status='active',
                        role='contributor',
                    )
                )
            else:
                member.status = 'active'
                member.left_at = None
        db.session.commit()

    client = _auth_client(app, inviter_username)
    r = client.post(
        f'/api/layers/{layer_id}/invitations/',
        json={'email': existing_email},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    d = r.get_json()
    assert d.get('duplicate') is True


def test_accept_invitation_sets_referrer():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, LayerInvitation, User
    from datetime import datetime, timedelta
    from services.utils import generate_invitation_token

    with app.app_context():
        layer = Layer.query.first()
        users = User.query.filter(User.email.isnot(None)).limit(2).all()
        if not layer or len(users) < 2:
            print('⚠️  Need layer + 2 users with email — skip')
            return
        inviter, invitee = users[0], users[1]
        for u in (inviter, invitee):
            m = LayerMember.query.filter_by(layer_id=layer.id, user_id=u.id).first()
            if not m:
                db.session.add(
                    LayerMember(
                        id=str(uuid4()),
                        layer_id=layer.id,
                        user_id=u.id,
                        status='active',
                        role='contributor',
                    )
                )
            elif u.id == invitee.id:
                m.status = 'left'
                m.left_at = datetime.utcnow()
        db.session.commit()

        token = generate_invitation_token()
        inv = LayerInvitation(
            layer_id=layer.id,
            inviter_id=inviter.id,
            invitee_email=invitee.email.strip().lower(),
            invitee_id=invitee.id,
            status='pending',
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(inv)
        db.session.commit()
        token_val = token
        invitee_username = invitee.username
        layer_id = layer.id
        inviter_id = inviter.id
        invitee_id = invitee.id

    client = _auth_client(app, invitee_username)
    r = client.post(f'/api/layer-invitations/by-token/{token_val}/accept/', json={})
    assert r.status_code == 200, r.get_data(as_text=True)

    with app.app_context():
        from models.referral_attribution import ReferralAttribution

        member = LayerMember.query.filter_by(layer_id=layer_id, user_id=invitee_id).first()
        assert member is not None
        assert member.status == 'active'
        assert member.referred_by_id == inviter_id
        att = ReferralAttribution.query.filter_by(
            referrer_user_id=inviter_id,
            converted_user_id=invitee_id,
            scope_type='layer',
            scope_id=layer_id,
            conversion_type='layer_member_join',
        ).first()
        assert att is not None
        assert att.channel == 'invitation'
        assert att.referral_token == f'invite:{token_val}'


def test_preview_includes_layer_mission_and_description():
    from app import app
    from extensions import db
    from models import Layer, LayerInvitation, User
    from datetime import datetime, timedelta
    from services.utils import generate_invitation_token

    with app.app_context():
        layer = Layer.query.first()
        user = User.query.filter(User.email.isnot(None)).first()
        if not layer or not user:
            print('⚠️  Need layer + user — skip')
            return
        layer.mission = 'Test mission for invite preview'
        layer.description = 'Test description for invite preview'
        token = generate_invitation_token()
        inv = LayerInvitation(
            layer_id=layer.id,
            inviter_id=user.id,
            invitee_email='preview-test@example.com',
            status='pending',
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(inv)
        db.session.commit()
        token_val = token

    with app.test_client() as c:
        r = c.get(f'/api/layer-invitations/by-token/{token_val}/')
        assert r.status_code == 200, r.get_data(as_text=True)
        d = r.get_json()
        assert d['layer']['mission'] == 'Test mission for invite preview'
        assert d['layer']['description'] == 'Test description for invite preview'


if __name__ == '__main__':
    test_layer_invitation_preview_404()
    print('✅ test_layer_invitation_preview_404')
    test_layer_invite_landing_page()
    print('✅ test_layer_invite_landing_page')
    test_create_invitation_requires_member()
    print('✅ test_create_invitation_requires_member')
    test_create_invitation_allows_layer_initiator()
    print('✅ test_create_invitation_allows_layer_initiator')
    test_create_invitation_duplicate_member()
    print('✅ test_create_invitation_duplicate_member')
    test_accept_invitation_sets_referrer()
    print('✅ test_accept_invitation_sets_referrer')
    test_preview_includes_layer_mission_and_description()
    print('✅ test_preview_includes_layer_mission_and_description')
