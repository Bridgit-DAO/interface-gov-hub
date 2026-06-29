"""Tests for Resend mail helpers."""
import os
import unittest


class ResendMailTests(unittest.TestCase):
    def test_parse_resend_from_named(self):
        from services.resend_mail import parse_resend_from

        parsed = parse_resend_from('Gov Hub <no-reply@govhub.live>')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['email'], 'no-reply@govhub.live')
        self.assertEqual(parsed['name'], 'Gov Hub')

    def test_parse_resend_from_bare_email(self):
        from services.resend_mail import parse_resend_from

        parsed = parse_resend_from('noreply@example.com')
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['email'], 'noreply@example.com')
        self.assertEqual(parsed['name'], 'Gov Hub')

    def test_strip_outer_env_quotes(self):
        from services.resend_mail import strip_outer_env_quotes

        self.assertEqual(strip_outer_env_quotes('"Gov Hub <a@b.com>"'), 'Gov Hub <a@b.com>')

    def test_format_resend_from(self):
        from services.resend_mail import format_resend_from

        self.assertEqual(
            format_resend_from(name='Gov Hub', email='no-reply@govhub.live'),
            'Gov Hub <no-reply@govhub.live>',
        )

    def test_get_resend_from_env_overrides(self):
        from services import resend_mail

        old_name = os.environ.get('RESEND_FROM_NAME')
        old_email = os.environ.get('RESEND_FROM_EMAIL')
        try:
            os.environ['RESEND_FROM_NAME'] = 'Test Sender'
            os.environ['RESEND_FROM_EMAIL'] = 'test@example.com'
            cfg = resend_mail.get_resend_from()
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg['email'], 'test@example.com')
            self.assertEqual(cfg['displayName'], 'Test Sender')
            self.assertEqual(cfg['formatted'], 'Test Sender <test@example.com>')
        finally:
            if old_name is None:
                os.environ.pop('RESEND_FROM_NAME', None)
            else:
                os.environ['RESEND_FROM_NAME'] = old_name
            if old_email is None:
                os.environ.pop('RESEND_FROM_EMAIL', None)
            else:
                os.environ['RESEND_FROM_EMAIL'] = old_email

    def test_send_resend_email_result_without_api_key(self):
        from services import resend_mail

        old_key = os.environ.get('RESEND_API_KEY')
        try:
            os.environ.pop('RESEND_API_KEY', None)
            result = resend_mail.send_resend_email_result(
                to=['someone@example.com'],
                subject='Test',
                html='<p>Hi</p>',
            )
            self.assertFalse(result.get('ok'))
            self.assertIn('RESEND_API_KEY', result.get('error', ''))
        finally:
            if old_key is not None:
                os.environ['RESEND_API_KEY'] = old_key


if __name__ == '__main__':
    unittest.main()
