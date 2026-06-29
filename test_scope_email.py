"""Tests for scoped email campaigns."""
import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')


class ScopeEmailTests(unittest.TestCase):
    def test_can_manage_layer_requires_admin(self):
        from app import app
        from models import Layer, User
        from services.scope_email import can_manage_scope_email

        with app.app_context():
            layer = Layer.query.first()
            user = User.query.first()
            if not layer or not user:
                self.skipTest('need layer and user')
            self.assertFalse(can_manage_scope_email({'id': 'nonexistent'}, 'layer', layer.id))

    def test_guild_recipient_groups(self):
        from app import app
        from models import Guild
        from services.scope_email import guild_recipient_groups

        with app.app_context():
            guild = Guild.query.first()
            if not guild:
                self.skipTest('need guild')
            groups = guild_recipient_groups(guild.id)
            self.assertIn('members', groups)
            self.assertIn('officers', groups)

    def test_create_campaign_requires_admin(self):
        from app import app
        from models import Layer
        from services.scope_email import create_campaign

        with app.app_context():
            layer = Layer.query.first()
            if not layer:
                self.skipTest('need layer')
            campaign, err, code = create_campaign(
                scope_type='layer',
                scope_id=layer.id,
                user={'id': 'not-a-real-user'},
                subject='Hi',
                body='Test',
                schedule_mode='immediate',
                groups=['members'],
            )
            self.assertIsNone(campaign)
            self.assertEqual(code, 403)

    def test_schedule_at_requires_future(self):
        from app import app
        from extensions import db
        from models import Layer, LayerAdmin, User
        from services.scope_email import create_campaign

        with app.app_context():
            layer = Layer.query.first()
            admin = User.query.filter(User.email.isnot(None)).first()
            if not layer or not admin:
                self.skipTest('need layer and admin user')
            if layer.initiator_id != admin.id:
                if not LayerAdmin.query.filter_by(layer_id=layer.id, user_id=admin.id).first():
                    db.session.add(LayerAdmin(layer_id=layer.id, user_id=admin.id))
                    db.session.commit()
            campaign, err, code = create_campaign(
                scope_type='layer',
                scope_id=layer.id,
                user={'id': admin.id, 'role': admin.role},
                subject='Future',
                body='Scheduled body',
                schedule_mode='at',
                groups=['members'],
                scheduled_at=datetime.utcnow() - timedelta(hours=1),
            )
            self.assertIsNone(campaign)
            self.assertIn('future', (err or '').lower())
            self.assertEqual(code, 400)


if __name__ == '__main__':
    unittest.main()
