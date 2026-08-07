"""Tests for platform invitation email delivery options."""
from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def _inviter(**kwargs):
    defaults = {
        'displayName': 'Jane Doe',
        'name': None,
        'username': None,
        'email': 'jane@example.com',
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class InviterDeliveryOptionsTests(unittest.TestCase):
    def test_defaults_include_reply_to_and_bcc(self):
        from services.platform_invitation_mail import inviter_delivery_options

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            opts = inviter_delivery_options(_inviter())
            self.assertEqual(opts['from_display_name'], 'Jane Doe')
            self.assertEqual(opts['reply_to'], 'Jane Doe <jane@example.com>')
            self.assertEqual(opts['bcc'], ['jane@example.com'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old

    def test_bcc_disabled_via_env(self):
        from services.platform_invitation_mail import inviter_delivery_options

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ['WORKGROUP_INVITE_BCC_INVITER'] = '0'
            opts = inviter_delivery_options(_inviter())
            self.assertEqual(opts['reply_to'], 'Jane Doe <jane@example.com>')
            self.assertIsNone(opts['bcc'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old

    def test_bcc_disabled_via_false_string(self):
        from services.platform_invitation_mail import inviter_delivery_options

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ['WORKGROUP_INVITE_BCC_INVITER'] = 'false'
            opts = inviter_delivery_options(_inviter())
            self.assertIsNone(opts['bcc'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old

    def test_explicit_bcc_override_wins(self):
        from services.platform_invitation_mail import inviter_delivery_options

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ['WORKGROUP_INVITE_BCC_INVITER'] = '0'
            opts = inviter_delivery_options(_inviter(), bcc_inviter=True)
            self.assertEqual(opts['bcc'], ['jane@example.com'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old

    def test_missing_inviter_email_skips_reply_to_and_bcc(self):
        from services.platform_invitation_mail import inviter_delivery_options

        opts = inviter_delivery_options(_inviter(email=''))
        self.assertEqual(opts['from_display_name'], 'Jane Doe')
        self.assertIsNone(opts['reply_to'])
        self.assertIsNone(opts['bcc'])


class MultiWorkgroupInvitationEmailTests(unittest.TestCase):
    def test_passes_delivery_options_to_resend(self):
        from services import platform_invitation_mail as mail

        captured = {}

        def fake_send(**kwargs):
            captured.update(kwargs)
            return True

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            with patch.object(mail, 'send_resend_email', side_effect=fake_send):
                ok = mail.send_multi_workgroup_invitation_email(
                    inviter=_inviter(),
                    invitee_email='invitee@example.com',
                    invitee_name='Bob',
                    body_text='Please join',
                    links=[{'workgroup_name': 'WG', 'landing_url': 'https://example.com/join'}],
                )
            self.assertTrue(ok)
            self.assertEqual(captured['from_display_name'], 'Jane Doe')
            self.assertEqual(captured['reply_to'], 'Jane Doe <jane@example.com>')
            self.assertEqual(captured['bcc'], ['jane@example.com'])
            self.assertEqual(captured['to'], ['invitee@example.com'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old


class PlatformInvitationEmailTests(unittest.TestCase):
    def test_single_invite_uses_same_delivery_options(self):
        from services import platform_invitation_mail as mail

        invitation = SimpleNamespace(
            invite_type='join_workgroup',
            message='Welcome',
            target_json='{}',
        )
        captured = {}

        def fake_send(**kwargs):
            captured.update(kwargs)
            return True

        old = os.environ.get('WORKGROUP_INVITE_BCC_INVITER')
        try:
            os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            with patch.object(mail, 'send_resend_email', side_effect=fake_send):
                ok = mail.send_platform_invitation_email(
                    invitation=invitation,
                    inviter=_inviter(),
                    invitee_email='invitee@example.com',
                    landing_url='https://example.com/invite',
                    target_title='Example WG',
                )
            self.assertTrue(ok)
            self.assertEqual(captured['from_display_name'], 'Jane Doe')
            self.assertEqual(captured['reply_to'], 'Jane Doe <jane@example.com>')
            self.assertEqual(captured['bcc'], ['jane@example.com'])
        finally:
            if old is None:
                os.environ.pop('WORKGROUP_INVITE_BCC_INVITER', None)
            else:
                os.environ['WORKGROUP_INVITE_BCC_INVITER'] = old


if __name__ == '__main__':
    unittest.main()
