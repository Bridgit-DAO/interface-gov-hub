"""Tests for workgroup nomination email notifications."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')


class WorkgroupNominationMailTests(unittest.TestCase):
    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_send_admin_nomination_accepted_emails_layer_admins(self, mock_send):
        from app import app
        from extensions import db
        from models import Layer, LayerAdmin, User, Workgroup, WorkingGroupChair
        from services.workgroup_nomination_mail import send_admin_nomination_accepted

        with app.app_context():
            layer = Layer.query.first()
            if not layer:
                self.skipTest('need layer')
            wg = Workgroup.query.filter_by(layer_id=layer.id).first()
            if not wg:
                self.skipTest('need workgroup on layer')

            admin = User.query.filter(User.email.isnot(None)).first()
            if not admin:
                self.skipTest('need user with email')
            if layer.initiator_id != admin.id:
                if not LayerAdmin.query.filter_by(layer_id=layer.id, user_id=admin.id).first():
                    db.session.add(LayerAdmin(layer_id=layer.id, user_id=admin.id))
                    db.session.commit()

            nomination = WorkingGroupChair(
                group_acronym=wg.acronym,
                chair_name='Test Nominee',
                position_key='chair',
                status='nominee_accepted',
            )
            db.session.add(nomination)
            db.session.commit()

            send_admin_nomination_accepted(nomination)

            self.assertTrue(mock_send.called)
            recipients = {call.kwargs['to'][0] for call in mock_send.call_args_list}
            self.assertIn(admin.email.strip(), recipients)
            html = mock_send.call_args.kwargs['html']
            self.assertIn('Test Nominee', html)
            self.assertIn('/admin/chair-nominations/', html)

            db.session.delete(nomination)
            db.session.commit()

    @patch('services.workgroup_nomination_mail.send_admin_nomination_accepted')
    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_send_nominee_accepted_notifies_nominator_and_admins(self, mock_send, mock_admin):
        from app import app
        from extensions import db
        from models import User, Workgroup, WorkingGroupChair
        from services.workgroup_nomination_mail import send_nominee_accepted

        with app.app_context():
            wg = Workgroup.query.first()
            nominator = User.query.filter(User.email.isnot(None)).first()
            if not wg or not nominator:
                self.skipTest('need workgroup and nominator')

            nomination = WorkingGroupChair(
                group_acronym=wg.acronym,
                chair_name='Accepted Person',
                position_key='chair',
                status='nominee_accepted',
                nominated_by_user_id=nominator.id,
            )
            db.session.add(nomination)
            db.session.commit()

            send_nominee_accepted(nomination)

            mock_send.assert_called_once()
            mock_admin.assert_called_once_with(nomination)

            db.session.delete(nomination)
            db.session.commit()


if __name__ == '__main__':
    unittest.main()
