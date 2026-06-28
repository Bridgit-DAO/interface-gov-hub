"""Tests for referral attribution resolution (token-only)."""
import os
import unittest

os.environ['REFERRAL_TOKEN_SECRET'] = 'test-secret-for-share-ref-token'

from services.referral_attribution import resolve_referrer_from_token  # noqa: E402
from services.referral_tokens import create_scoped_share_ref_token  # noqa: E402

REFERRER = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'


class ReferralAttributionTests(unittest.TestCase):
    def test_legacy_code_not_resolved(self):
        referrer_id, attr = resolve_referrer_from_token(None, current_user_id=OTHER)
        self.assertIsNone(referrer_id)
        self.assertIsNone(attr)

    def test_invalid_token_not_resolved(self):
        referrer_id, attr = resolve_referrer_from_token('not-a-token', current_user_id=OTHER)
        self.assertIsNone(referrer_id)
        self.assertIsNotNone(attr)
        self.assertFalse(attr.get('valid'))


if __name__ == '__main__':
    unittest.main()
