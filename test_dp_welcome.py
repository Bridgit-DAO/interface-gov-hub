"""Tests for DP workgroup welcome delivery and nomination email enforcement."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')


class DpWelcomeTests(unittest.TestCase):
    def test_require_nominee_email_missing(self):
        from models import WorkingGroupChair
        from services.dp_welcome import require_nominee_email

        nomination = WorkingGroupChair(chair_name='Test', nominee_email=None)
        self.assertIsNotNone(require_nominee_email(nomination))

    def test_require_nominee_email_valid(self):
        from models import WorkingGroupChair
        from services.dp_welcome import require_nominee_email

        nomination = WorkingGroupChair(chair_name='Test', nominee_email='nominee@example.com')
        self.assertIsNone(require_nominee_email(nomination))

    def test_dp_welcome_page_urls(self):
        from services.dp_welcome import dp_welcome_page_url

        self.assertIn('/welcome/member?wg=dp1-federated-auth', dp_welcome_page_url('dp1-federated-auth', 'member'))
        self.assertIn('/welcome/lead?wg=dp1-federated-auth', dp_welcome_page_url('dp1-federated-auth', 'lead'))

    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_admin_approve_creates_member_and_welcome(self, mock_send):
        from app import app
        from extensions import db
        from models import User, Workgroup, WorkingGroupChair, WorkingGroupMember
        from services.workgroup_links import is_dp_workgroup
        from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED
        from services.dp_welcome import ensure_nomination_membership, deliver_dp_welcome
        from services.workgroup_nomination_mail import send_admin_decision

        with app.app_context():
            wg = Workgroup.query.filter(Workgroup.slug.like('dp%')).first()
            if not wg or not is_dp_workgroup(wg):
                self.skipTest('need DP workgroup')
            user = User.query.first()
            if not user:
                self.skipTest('need user')

            existing = WorkingGroupMember.query.filter_by(
                group_acronym=wg.acronym,
                user_id=user.id,
            ).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

            nomination = WorkingGroupChair(
                group_acronym=wg.acronym,
                chair_name=user.displayName or user.username,
                user_id=user.id,
                nominee_email=user.email or 'nominee@example.com',
                position_key='chair',
                status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            )
            db.session.add(nomination)
            db.session.commit()

            nomination.approved = True
            nomination.status = 'approved'
            self.assertTrue(ensure_nomination_membership(nomination))
            welcome_url = deliver_dp_welcome(
                user_id=user.id,
                workgroup=wg,
                variant='lead',
                position_key='chair',
            )
            send_admin_decision(nomination, approved=True)
            db.session.commit()

            member = WorkingGroupMember.query.filter_by(
                group_acronym=wg.acronym,
                user_id=user.id,
            ).first()
            self.assertIsNotNone(member)
            self.assertIsNotNone(welcome_url)
            self.assertIn('/welcome/lead', welcome_url)

            db.session.delete(member)
            db.session.delete(nomination)
            db.session.commit()

    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_admin_approve_route_resolves_welcome_variant(self, mock_send):
        """Regression: admin approve route must import nomination_welcome_variant."""
        from app import app
        from extensions import db
        from models import User, Workgroup, WorkingGroupChair, WorkingGroupMember
        from services.workgroup_links import is_dp_workgroup
        from services.workgroup_positions import (
            NOMINATION_STATUS_APPROVED,
            NOMINATION_STATUS_NOMINEE_ACCEPTED,
        )

        with app.app_context():
            admin = User.query.filter(User.role.in_(['admin', 'editor'])).first()
            wg = Workgroup.query.filter(Workgroup.slug.like('dp%')).first()
            if not admin or not wg or not is_dp_workgroup(wg):
                self.skipTest('need admin and DP workgroup')
            user = User.query.first()
            if not user:
                self.skipTest('need user')
            admin_username = admin.username

            existing = WorkingGroupMember.query.filter_by(
                group_acronym=wg.acronym,
                user_id=user.id,
            ).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

            nomination = WorkingGroupChair(
                group_acronym=wg.acronym,
                chair_name=user.displayName or user.username,
                user_id=user.id,
                nominee_email=user.email or 'nominee@example.com',
                position_key='chair',
                status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            )
            db.session.add(nomination)
            db.session.commit()
            nomination_id = nomination.id

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user'] = admin_username

        response = client.post(f'/api/admin/chair-nominations/{nomination_id}/approve/')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('welcome_url', data)
        self.assertIn('/welcome/lead', data['welcome_url'])

        with app.app_context():
            nomination = WorkingGroupChair.query.get(nomination_id)
            self.assertEqual(nomination.status, NOMINATION_STATUS_APPROVED)
            member = WorkingGroupMember.query.filter_by(
                group_acronym=nomination.group_acronym,
                user_id=nomination.user_id,
            ).first()
            if member:
                db.session.delete(member)
            db.session.delete(nomination)
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
