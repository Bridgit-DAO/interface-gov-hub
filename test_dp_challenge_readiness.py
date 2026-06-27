"""Focused tests for DP Challenge readiness helpers."""
from uuid import uuid4

from app import app
from extensions import db
from middleware.dp_challenge_host_wsgi import DpChallengeHostRewriteMiddleware
from models import Layer, User, Workgroup, WorkingGroupChair, WorkgroupMemberRequest


def _unique(prefix):
    return f'{prefix}-{uuid4().hex[:10]}'


def test_desirableproperties_host_rewrites_root_to_dp_challenge():
    seen = {}

    def app_stub(environ, start_response):
        seen['path'] = environ['PATH_INFO']
        start_response('200 OK', [])
        return [b'ok']

    wrapped = DpChallengeHostRewriteMiddleware(app_stub, hosts=('desirableproperties.org',))
    environ = {'HTTP_HOST': 'desirableproperties.org', 'PATH_INFO': '/'}
    list(wrapped(environ, lambda status, headers: None))
    assert seen['path'] == '/dp-challenge/'


def test_co_lead_can_manage_and_invite_workgroup():
    from services.platform_invitations import can_invite
    from services.workgroup_authority import can_invite_workgroup_member, can_manage_workgroup

    with app.app_context():
        slug = _unique('dp-readiness-layer')
        user = User(
            username=_unique('colead'),
            handle=_unique('colead'),
            email=f'{_unique("colead")}@example.com',
            role='user',
        )
        layer = Layer(name=_unique('DP Readiness Layer'), slug=slug, initiator_id=user.id)
        db.session.add(user)
        db.session.flush()
        layer.initiator_id = user.id
        db.session.add(layer)
        db.session.flush()
        wg = Workgroup(
            acronym=_unique('dp99'),
            name='DP99 Test Workgroup',
            slug=_unique('dp99-test'),
            layer_id=layer.id,
            approval_status='approved',
        )
        db.session.add(wg)
        db.session.flush()
        chair = WorkingGroupChair(
            group_acronym=wg.acronym,
            position_key='co_lead',
            chair_name='Co Lead',
            user_id=user.id,
            approved=True,
            status='approved',
        )
        db.session.add(chair)
        db.session.commit()

        try:
            assert can_manage_workgroup(wg, {'id': user.id, 'role': user.role})
            assert can_invite_workgroup_member(wg, {'id': user.id, 'role': user.role})
            ok, err = can_invite(user.id, 'join_workgroup', {'workgroup_id': wg.id})
            assert ok is True, err
        finally:
            db.session.delete(chair)
            db.session.delete(wg)
            db.session.delete(layer)
            db.session.delete(user)
            db.session.commit()


def test_membership_helper_reuses_pending_request():
    from services.workgroup_membership import join_or_request_workgroup_membership

    with app.app_context():
        user = User(
            username=_unique('pending-member'),
            handle=_unique('pending-member'),
            email=f'{_unique("pending-member")}@example.com',
            role='user',
        )
        db.session.add(user)
        db.session.commit()
        acronym = _unique('dp-pending')

        try:
            first = join_or_request_workgroup_membership(
                acronym=acronym,
                user=user,
                require_approval=True,
            )
            db.session.commit()
            second = join_or_request_workgroup_membership(
                acronym=acronym,
                user=user,
                require_approval=True,
            )
            db.session.commit()
            assert first['status'] == 'requested'
            assert second['status'] == 'already_pending'
            assert WorkgroupMemberRequest.query.filter_by(
                group_acronym=acronym,
                user_id=user.id,
                status='pending',
            ).count() == 1
        finally:
            WorkgroupMemberRequest.query.filter_by(group_acronym=acronym).delete()
            db.session.delete(user)
            db.session.commit()
