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


class BodyTextToHtmlParagraphTests(unittest.TestCase):
    def test_autolinks_https_urls(self):
        from services.platform_invitation_mail import body_text_to_html_paragraph

        html_out = body_text_to_html_paragraph(
            'Please visit https://desirableproperties.org to participate.'
        )
        self.assertIn(
            '<a href="https://desirableproperties.org">https://desirableproperties.org</a>',
            html_out,
        )
        self.assertNotIn('desirableproperties.org to participate', html_out)


class LongGapOutreachEmailTests(unittest.TestCase):
    def test_long_gap_subject_constant(self):
        from services.platform_invitation_mail import LONG_GAP_EMAIL_SUBJECT

        self.assertEqual(
            LONG_GAP_EMAIL_SUBJECT,
            'From the Metaweb to a Layered Web: Your Input is Requested',
        )

    def test_build_long_gap_outreach_html_includes_progression_image(self):
        from services.platform_invitation_mail import (
            LONG_GAP_PROGRESSION_IMAGE_URL,
            build_long_gap_outreach_html,
        )

        html_out = build_long_gap_outreach_html(
            'Hi Alex,\n\nOpening paragraph.\n\nWarmly,\nDaveed Benjamin',
            'Alex Smith',
        )
        self.assertIn(LONG_GAP_PROGRESSION_IMAGE_URL, html_out)
        self.assertIn('Hi Alex', html_out)
        self.assertIn('Opening paragraph', html_out)

    def test_build_long_gap_outreach_html_includes_dp_card_image(self):
        from services.platform_invitation_mail import build_long_gap_outreach_html

        dp_url = 'https://desirableproperties.org/images/dps/card/DP22.webp'
        body = (
            'Hi Agustin,\n\n'
            'Middle paragraph.\n\n'
            'I would love your input on DP22.\n\n'
            'Take a look here: https://desirableproperties.org/workgroups/dp22\n\n'
            'Warmly,\nDaveed Benjamin'
        )
        html_out = build_long_gap_outreach_html(
            body,
            '"Agustín Borrazás"',
            dp_card_image_url=dp_url,
        )
        self.assertIn(dp_url, html_out)
        self.assertIn('Hi Agustín', html_out)
        self.assertNotIn('Hi "Agustín', html_out)

    def test_send_long_gap_outreach_email_uses_long_gap_subject(self):
        from services import platform_invitation_mail as mail

        captured = {}

        def fake_send(**kwargs):
            captured.update(kwargs)
            return True

        with patch.object(mail, 'send_resend_email', side_effect=fake_send):
            ok = mail.send_long_gap_outreach_email(
                inviter=_inviter(),
                to_email='invitee@example.com',
                to_name='"Agustín Borrazás"',
                body_text='Hi Agustin,\n\nBody text.\n\nWarmly,\nDaveed',
            )
        self.assertTrue(ok)
        self.assertEqual(
            captured['subject'],
            'From the Metaweb to a Layered Web: Your Input is Requested',
        )
        self.assertIn(mail.LONG_GAP_PROGRESSION_IMAGE_URL, captured['html'])


if __name__ == '__main__':
    unittest.main()
