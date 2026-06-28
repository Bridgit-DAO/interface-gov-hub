"""Tests for scoped referral tokens (interop with canopi/utils/shareRefToken.js)."""
import os
import unittest

os.environ['REFERRAL_TOKEN_SECRET'] = 'test-secret-for-share-ref-token'

from services.referral_tokens import (  # noqa: E402
    attribution_from_token,
    create_scoped_share_ref_token,
    verify_share_ref_token,
)


REFERRER = '00000000-0000-4000-8000-000000000001'
LAYER_ID = '11111111-1111-4111-8111-111111111111'


class ReferralTokenTests(unittest.TestCase):
    def test_create_and_verify_scoped_token(self):
        token = create_scoped_share_ref_token(
            referrer_user_id=REFERRER,
            entity_type='layer',
            entity_id=LAYER_ID,
            scope_type='layer',
            scope_id=LAYER_ID,
            product='gov_hub',
            channel='layer_join',
        )
        ok, payload, reason = verify_share_ref_token(token)
        self.assertTrue(ok, reason)
        self.assertEqual(payload['referrerUserId'], REFERRER)
        self.assertEqual(payload['scopeType'], 'layer')
        self.assertEqual(payload['product'], 'gov_hub')

    def test_attribution_from_token(self):
        token = create_scoped_share_ref_token(
            referrer_user_id=REFERRER,
            entity_type='waitlist',
            entity_id='wl-1',
            scope_type='waitlist',
            scope_id='wl-1',
        )
        attr = attribution_from_token(token)
        self.assertTrue(attr['valid'])
        self.assertEqual(attr['referrer_user_id'], REFERRER)
        self.assertEqual(attr['scope_type'], 'waitlist')

    def test_rejects_tampered_token(self):
        token = create_scoped_share_ref_token(
            referrer_user_id=REFERRER,
            entity_type='layer',
            entity_id=LAYER_ID,
            scope_type='layer',
            scope_id=LAYER_ID,
        )
        ok, _, reason = verify_share_ref_token(token + 'x')
        self.assertFalse(ok)
        self.assertEqual(reason, 'bad_signature')


if __name__ == '__main__':
    unittest.main()
