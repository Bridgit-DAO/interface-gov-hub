"""Tests for unified platform invitations."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_validate_invitee_email():
    from services.platform_invitations import validate_invitee_email, normalize_invitee_email

    assert validate_invitee_email('a@b.co')
    assert not validate_invitee_email('not-an-email')
    assert normalize_invitee_email('  A@B.Co ') == 'a@b.co'


def test_rate_limit_participation_excluded():
    from app import app
    from models import User
    from services.platform_invitations import check_rate_limit

    with app.app_context():
        user = User.query.first()
        if not user:
            return
        assert check_rate_limit(user.id, 'participation') is None


def test_create_participate_invitation():
    from app import app
    from models import User, PlatformInvitation

    with app.app_context():
        user = User.query.first()
        if not user or not user.email:
            return
        from services.platform_invitations import create_invitation

        body, status = create_invitation(
            invite_type='participate_dp',
            inviter_id=user.id,
            invitee_email='invite-test@example.com',
            message='Join us',
            target={},
        )
        assert status in (201, 200), body
        assert body.get('invite_path', '').startswith('/dp-challenge/')
        inv_id = (body.get('invitation') or {}).get('id')
        if inv_id:
            PlatformInvitation.query.filter_by(id=inv_id).delete()
            from extensions import db
            db.session.commit()


def test_reference_url_validation():
    from services.dp_proposals import validate_reference_url

    url, err = validate_reference_url('https://example.com/doc')
    assert url == 'https://example.com/doc'
    assert err is None
    url2, err2 = validate_reference_url('javascript:alert(1)')
    assert url2 is None
    assert err2
