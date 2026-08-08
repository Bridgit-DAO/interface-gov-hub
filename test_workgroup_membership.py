"""Tests for services.workgroup_membership.user_workgroup_status and its API."""
import json
from uuid import uuid4

from app import app
from extensions import db
from models import (
    EventLog,
    Layer,
    User,
    Workgroup,
    WorkingGroupChair,
    WorkingGroupMember,
    WorkgroupMemberRequest,
)
from services.workgroup_membership import (
    join_or_request_workgroup_membership,
    leave_workgroup_membership,
    user_workgroup_status,
)


def _unique(prefix):
    return f'{prefix}-{uuid4().hex[:10]}'


def _auth_client(username):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = username
    return client


def _make_user(prefix):
    user = User(
        username=_unique(prefix),
        handle=_unique(prefix),
        email=f'{_unique(prefix)}@example.com',
        role='user',
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_user_workgroup_status_defaults_when_unrelated():
    with app.app_context():
        user = _make_user('wgstatus-none')
        acronym = _unique('wg-none')
        try:
            status = user_workgroup_status(user.id, acronym)
            assert status == {
                'member': False,
                'positions': [],
                'pending_request': False,
                'can_join': True,
                'can_self_nominate': True,
            }
        finally:
            db.session.delete(user)
            db.session.commit()


def test_user_workgroup_status_missing_user_or_acronym():
    with app.app_context():
        assert user_workgroup_status(None, 'some-acronym')['can_join'] is False
        assert user_workgroup_status('some-user-id', '')['can_join'] is False


def test_user_workgroup_status_reports_membership():
    with app.app_context():
        user = _make_user('wgstatus-member')
        acronym = _unique('wg-member')
        member = WorkingGroupMember(
            id=str(uuid4()),
            group_acronym=acronym,
            user_id=user.id,
            user_name=user.username,
        )
        db.session.add(member)
        db.session.commit()
        try:
            status = user_workgroup_status(user.id, acronym)
            assert status['member'] is True
            assert status['positions'] == []
            assert status['can_join'] is False
        finally:
            db.session.delete(member)
            db.session.delete(user)
            db.session.commit()


def test_user_workgroup_status_reports_positions_and_pending_request():
    with app.app_context():
        user = _make_user('wgstatus-chair')
        acronym = _unique('wg-chair')
        chair = WorkingGroupChair(
            group_acronym=acronym,
            position_key='co_lead',
            chair_name=user.username,
            user_id=user.id,
            approved=True,
            status='approved',
        )
        request_row = WorkgroupMemberRequest(
            group_acronym=acronym,
            user_id=user.id,
            user_name=user.username,
            status='pending',
        )
        db.session.add(chair)
        db.session.add(request_row)
        db.session.commit()
        try:
            status = user_workgroup_status(user.id, acronym)
            # Holding a position counts as membership even without a member row.
            assert status['member'] is True
            assert status['positions'] == ['co_lead']
            assert status['pending_request'] is True
            assert status['can_join'] is False
            # Other positions remain available to self-nominate for.
            assert status['can_self_nominate'] is True
        finally:
            db.session.delete(chair)
            db.session.delete(request_row)
            db.session.delete(user)
            db.session.commit()


def test_api_workgroup_my_status_requires_auth():
    with app.app_context():
        layer = Layer.query.first()
        acronym = _unique('wg-api-noauth')
        assert layer is not None

    with app.test_client() as client:
        r = client.get(f'/api/workgroups/{acronym}/me/status')
        # require_auth redirects unauthenticated requests to the login page.
        assert r.status_code in (302, 401)


def test_api_workgroup_my_status_returns_status_for_member():
    with app.app_context():
        user = _make_user('wgstatus-api')
        acronym = _unique('wg-api-member')
        member = WorkingGroupMember(
            id=str(uuid4()),
            group_acronym=acronym,
            user_id=user.id,
            user_name=user.username,
        )
        db.session.add(member)
        db.session.commit()
        username = user.username

    client = _auth_client(username)
    try:
        r = client.get(f'/api/workgroups/{acronym}/me/status')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['member'] is True
        assert data['can_join'] is False
    finally:
        with app.app_context():
            WorkingGroupMember.query.filter_by(group_acronym=acronym).delete()
            User.query.filter_by(username=username).delete()
            db.session.commit()


def _make_workgroup(prefix='wg-leave'):
    layer = Layer.query.first()
    assert layer is not None
    acronym = _unique(prefix)
    wg = Workgroup(
        id=str(uuid4()),
        name=f'Test {acronym}',
        acronym=acronym,
        slug=acronym,
        layer_id=layer.id,
        approval_status='approved',
        status='active',
    )
    db.session.add(wg)
    db.session.commit()
    return wg


def test_leave_workgroup_membership_removes_row_and_emits_event():
    with app.app_context():
        user = _make_user('wgleave')
        wg = _make_workgroup('wg-leave-svc')
        join = join_or_request_workgroup_membership(acronym=wg.acronym, user=user)
        assert join.get('joined') is True
        db.session.commit()

        joined_events = EventLog.query.filter_by(
            event_type='workgroup_member_joined',
            subject_id=wg.id,
        ).all()
        assert len(joined_events) == 1

        result = leave_workgroup_membership(workgroup=wg, user=user)
        assert result['ok'] is True
        assert result['left'] is True
        db.session.commit()

        assert WorkingGroupMember.query.filter_by(
            group_acronym=wg.acronym, user_id=user.id,
        ).first() is None
        left_events = EventLog.query.filter_by(
            event_type='workgroup_member_left',
            subject_id=wg.id,
        ).all()
        assert len(left_events) == 1

        EventLog.query.filter_by(subject_id=wg.id).delete()
        db.session.delete(wg)
        db.session.delete(user)
        db.session.commit()


def test_leave_workgroup_membership_not_a_member():
    with app.app_context():
        user = _make_user('wgleave-none')
        wg = _make_workgroup('wg-leave-none')
        try:
            result = leave_workgroup_membership(workgroup=wg, user=user)
            assert result['ok'] is False
            assert result['status_code'] == 404
            assert 'Not a member' in result['error']
        finally:
            db.session.delete(wg)
            db.session.delete(user)
            db.session.commit()


def test_leave_cancels_pending_member_request():
    with app.app_context():
        user = _make_user('wgleave-pending')
        wg = _make_workgroup('wg-leave-pend')
        req = WorkgroupMemberRequest(
            group_acronym=wg.acronym,
            user_id=user.id,
            user_name=user.username,
            status='pending',
        )
        db.session.add(req)
        db.session.commit()
        try:
            result = leave_workgroup_membership(workgroup=wg, user=user)
            assert result['ok'] is True
            assert result['left'] is False
            assert result['cancelled_request'] is True
            db.session.commit()
            assert req.status == 'cancelled'
            assert EventLog.query.filter_by(
                event_type='workgroup_member_left',
                subject_id=wg.id,
            ).count() == 0
        finally:
            WorkgroupMemberRequest.query.filter_by(group_acronym=wg.acronym).delete()
            db.session.delete(wg)
            db.session.delete(user)
            db.session.commit()


def test_ensure_workgroup_membership_emits_join_event():
    from services.workgroup_membership import ensure_workgroup_membership

    with app.app_context():
        user = _make_user('wgensure')
        wg = _make_workgroup('wg-ensure-emit')
        try:
            member, created = ensure_workgroup_membership(
                acronym=wg.acronym,
                user_id=user.id,
                display_name=user.username,
            )
            assert created is True
            assert member is not None
            db.session.commit()

            events = EventLog.query.filter_by(
                event_type='workgroup_member_joined',
                subject_id=wg.id,
            ).all()
            assert len(events) == 1
            payload = json.loads(events[0].payload_json or '{}')
            assert payload['workgroup_id'] == wg.id
            assert payload['slug'] == wg.slug
        finally:
            EventLog.query.filter_by(subject_id=wg.id).delete()
            WorkingGroupMember.query.filter_by(group_acronym=wg.acronym).delete()
            db.session.delete(wg)
            db.session.delete(user)
            db.session.commit()


def test_api_workgroup_leave_requires_auth_and_succeeds_for_member():
    with app.app_context():
        user = _make_user('wgleave-api')
        wg = _make_workgroup('wg-leave-api')
        member = WorkingGroupMember(
            id=str(uuid4()),
            group_acronym=wg.acronym,
            user_id=user.id,
            user_name=user.username,
        )
        db.session.add(member)
        db.session.commit()
        username = user.username
        workgroup_id = wg.id
        acronym = wg.acronym

    with app.test_client() as anon:
        r = anon.post(f'/api/workgroups/{workgroup_id}/leave/')
        assert r.status_code in (302, 401)

    client = _auth_client(username)
    try:
        r = client.post(f'/api/workgroups/{workgroup_id}/leave/')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['success'] is True
        assert data['left'] is True

        again = client.post(f'/api/workgroups/{workgroup_id}/leave/')
        assert again.status_code == 404
    finally:
        with app.app_context():
            EventLog.query.filter_by(subject_id=workgroup_id).delete()
            WorkingGroupMember.query.filter_by(group_acronym=acronym).delete()
            Workgroup.query.filter_by(id=workgroup_id).delete()
            User.query.filter_by(username=username).delete()
            db.session.commit()
