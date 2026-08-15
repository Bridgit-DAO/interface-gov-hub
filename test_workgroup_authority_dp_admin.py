"""DP site admin workgroup invite permissions."""
from uuid import uuid4

from app import app
from extensions import db
from models import Layer, User, Workgroup


def _unique(prefix):
    return f'{prefix}-{uuid4().hex[:10]}'


def test_dp_site_admin_can_invite_without_membership(monkeypatch):
    from services.platform_invitations import can_invite
    from services.workgroup_authority import can_invite_workgroup_member

    admin_email = f'{_unique("dp-admin")}@example.com'
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', (admin_email,))

    with app.app_context():
        slug = _unique('dp-admin-layer')
        admin = User(
            username=_unique('dp-admin-user'),
            handle=_unique('dp-admin-user'),
            email=admin_email,
            role='user',
        )
        layer = Layer(name=_unique('DP Admin Layer'), slug=slug, initiator_id=admin.id)
        db.session.add(admin)
        db.session.flush()
        layer.initiator_id = admin.id
        db.session.add(layer)
        db.session.flush()
        wg = Workgroup(
            acronym=_unique('dp42'),
            name='DP42 Test Workgroup',
            slug=_unique('dp42-test'),
            layer_id=layer.id,
            approval_status='approved',
        )
        db.session.add(wg)
        db.session.commit()

        try:
            user_dict = {'id': admin.id, 'role': admin.role, 'email': admin.email}
            assert can_invite_workgroup_member(wg, user_dict)
            ok, err = can_invite(admin.id, 'join_workgroup', {'workgroup_id': wg.id})
            assert ok is True, err
        finally:
            db.session.delete(wg)
            db.session.delete(layer)
            db.session.delete(admin)
            db.session.commit()
