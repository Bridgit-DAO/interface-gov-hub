"""Route-level tests for the DP welcome / nomination flow.

Runs against a disposable database (``fixtures.isolated_app``); the deployed
database is never opened. Covers identity binding on accept/decline, the
email-only approval block and link, object-scoped review authorization,
idempotent approval, transaction behaviour on join, the ``?action=join``
sign-in continuation, and ``/api/me/dp-welcome/`` status semantics.
"""
import os
import unittest
from unittest.mock import patch
from urllib.parse import quote

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')
os.environ.setdefault('SECRET_KEY', 'isolated-test-secret-key')

from fixtures.isolated_app import (  # noqa: E402 - env must be set before import
    isolated_app,
    make_nomination,
    seed_dp_workgroup,
)

MAIL_TARGET = 'services.workgroup_nomination_mail.send_resend_email'


def _username(user_id):
    from models import User

    return User.query.get(user_id).username


class NominationResponseRouteTests(unittest.TestCase):
    """POST /api/workgroup-nominations/<id>/accept|decline/"""

    def _setup(self, ctx, *, user_id=None, nominee_email='iso-nominee@example.com'):
        from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

        world = seed_dp_workgroup(ctx)
        nomination = make_nomination(
            group_acronym=world.workgroup_acronym,
            chair_name='Nominee Person',
            nominee_email=nominee_email,
            status=NOMINATION_STATUS_PENDING_NOMINEE,
            user_id=world.users[user_id] if user_id else None,
            nominated_by_user_id=world.users['nominator'],
        )
        return world, nomination.id

    @patch(MAIL_TARGET)
    def test_nominee_can_accept_own_nomination(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._setup(ctx, user_id='nominee')
                nominee_username = _username(world.users['nominee'])

            with ctx.signed_in(nominee_username) as client:
                response = client.post(f'/api/workgroup-nominations/{nomination_id}/accept/')
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair, WorkingGroupMember
                from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

                nomination = WorkingGroupChair.query.get(nomination_id)
                self.assertEqual(nomination.status, NOMINATION_STATUS_NOMINEE_ACCEPTED)
                # Accepting is willingness only: no role, no membership yet.
                self.assertFalse(bool(nomination.approved))
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                    ).count(),
                    0,
                )

    @patch(MAIL_TARGET)
    def test_other_user_cannot_accept_someone_elses_nomination(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._setup(ctx, user_id='nominee')
                attacker_username = _username(world.users['attacker'])

            with ctx.signed_in(attacker_username) as client:
                response = client.post(f'/api/workgroup-nominations/{nomination_id}/accept/')
            self.assertEqual(response.status_code, 403, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_PENDING_NOMINEE,
                )

    @patch(MAIL_TARGET)
    def test_other_user_cannot_decline_someone_elses_nomination(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._setup(ctx, user_id='nominee')
                attacker_username = _username(world.users['attacker'])

            with ctx.signed_in(attacker_username) as client:
                response = client.post(f'/api/workgroup-nominations/{nomination_id}/decline/')
            self.assertEqual(response.status_code, 403)

            with ctx.app.app_context():
                from models import WorkingGroupChair
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_PENDING_NOMINEE,
                )

    @patch(MAIL_TARGET)
    def test_email_only_nomination_accepted_by_matching_account(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._setup(
                    ctx, user_id=None, nominee_email='ISO-Nominee@Example.com',
                )
                nominee_username = _username(world.users['nominee'])
                attacker_username = _username(world.users['attacker'])

            with ctx.signed_in(attacker_username) as client:
                denied = client.post(f'/api/workgroup-nominations/{nomination_id}/accept/')
            self.assertEqual(denied.status_code, 403)

            with ctx.signed_in(nominee_username) as client:
                allowed = client.post(f'/api/workgroup-nominations/{nomination_id}/accept/')
            self.assertEqual(allowed.status_code, 200, allowed.get_data(as_text=True))

    @patch(MAIL_TARGET)
    def test_acceptance_survives_email_failure_and_still_alerts_reviewers(self, mock_send):
        mock_send.side_effect = RuntimeError('smtp down')
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._setup(ctx, user_id='nominee')
                nominee_username = _username(world.users['nominee'])

            with ctx.signed_in(nominee_username) as client:
                response = client.post(f'/api/workgroup-nominations/{nomination_id}/accept/')
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertFalse(response.get_json()['notifications_sent'])

            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupChair
                from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )
                # Reviewers are still told in-app, so the nomination cannot be
                # stranded by an email outage.
                reviewer_ids = {world.users['layer_owner'], world.users['layer_admin']}
                notified = {
                    row.user_id
                    for row in UserNotification.query.filter(
                        UserNotification.link_url.like('%/admin/chair-nominations/%')
                    ).all()
                }
                self.assertEqual(reviewer_ids, notified & reviewer_ids)

    def test_anonymous_response_is_rejected(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                _world, nomination_id = self._setup(ctx, user_id='nominee')

            with ctx.signed_in(None) as client:
                response = client.post(
                    f'/api/workgroup-nominations/{nomination_id}/accept/',
                    follow_redirects=False,
                )
            self.assertIn(response.status_code, (302, 401))


class NominationCreationRouteTests(unittest.TestCase):
    """POST /api/workgroups/<id>/nominate/"""

    def _payload(self, **overrides):
        payload = {
            'position_key': 'chair',
            'nominee_name': 'Target Person',
            'nominee_email': 'iso-nominee@example.com',
            'nominee_profile_url': 'https://linkedin.com/in/target',
            'statement': 'They would be great.',
        }
        payload.update(overrides)
        return payload

    @patch(MAIL_TARGET)
    def test_cannot_pair_victim_account_with_attacker_email(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                attacker_username = _username(world.users['attacker'])
                victim_id = world.users['nominee']

            with ctx.signed_in(attacker_username) as client:
                response = client.post(
                    f'/api/workgroups/{world.workgroup_id}/nominate/',
                    json=self._payload(
                        nominee_user_id=victim_id,
                        nominee_email='attacker@evil.example',
                    ),
                )
            self.assertEqual(response.status_code, 400, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair

                self.assertEqual(WorkingGroupChair.query.count(), 0)

    @patch(MAIL_TARGET)
    def test_account_email_is_derived_server_side(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                nominator_username = _username(world.users['nominator'])
                nominee_id = world.users['nominee']

            with ctx.signed_in(nominator_username) as client:
                response = client.post(
                    f'/api/workgroups/{world.workgroup_id}/nominate/',
                    json=self._payload(nominee_user_id=nominee_id, nominee_email=''),
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair

                nomination = WorkingGroupChair.query.one()
                self.assertEqual(nomination.user_id, nominee_id)
                self.assertEqual(nomination.nominee_email, 'iso-nominee@example.com')
                self.assertFalse(bool(nomination.is_self_nomination))

    @patch(MAIL_TARGET)
    def test_nomination_survives_email_failure(self, mock_send):
        mock_send.side_effect = RuntimeError('smtp down')
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                nominator_username = _username(world.users['nominator'])

            with ctx.signed_in(nominator_username) as client:
                response = client.post(
                    f'/api/workgroups/{world.workgroup_id}/nominate/',
                    json=self._payload(),
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertFalse(response.get_json()['notifications_sent'])

            with ctx.app.app_context():
                from models import WorkingGroupChair

                nomination = WorkingGroupChair.query.one()
                # The response token must be persisted, or the emailed link the
                # nominee eventually receives would be dead.
                self.assertTrue(nomination.nominee_response_token)

    @patch(MAIL_TARGET)
    def test_email_is_still_required_for_email_only_nomination(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                nominator_username = _username(world.users['nominator'])

            with ctx.signed_in(nominator_username) as client:
                response = client.post(
                    f'/api/workgroups/{world.workgroup_id}/nominate/',
                    json=self._payload(nominee_email='not-an-email'),
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn('valid nominee email', response.get_json()['error'])


class AdminReviewRouteTests(unittest.TestCase):
    """POST /api/admin/chair-nominations/<id>/approve|reject/"""

    def _accepted_nomination(self, ctx, *, linked=True, email='iso-nominee@example.com'):
        from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

        world = seed_dp_workgroup(ctx)
        nomination = make_nomination(
            group_acronym=world.workgroup_acronym,
            chair_name='Nominee Person',
            nominee_email=email,
            status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            user_id=world.users['nominee'] if linked else None,
            nominated_by_user_id=world.users['nominator'],
        )
        return world, nomination.id

    @patch(MAIL_TARGET)
    def test_layer_admin_can_approve_and_gets_membership_plus_welcome(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                layer_admin_username = _username(world.users['layer_admin'])

            with ctx.signed_in(layer_admin_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            data = response.get_json()
            self.assertTrue(data['success'])
            self.assertIn('/welcome/lead', data['welcome_url'])
            self.assertTrue(data['membership_created'])
            self.assertTrue(data['notifications_sent'])

            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupChair, WorkingGroupMember
                from services.workgroup_positions import NOMINATION_STATUS_APPROVED

                nomination = WorkingGroupChair.query.get(nomination_id)
                self.assertEqual(nomination.status, NOMINATION_STATUS_APPROVED)
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )
                # One combined lead welcome, not one per message.
                self.assertEqual(
                    UserNotification.query.filter_by(
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    @patch(MAIL_TARGET)
    def test_layer_owner_can_approve(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                owner_username = _username(world.users['layer_owner'])

            with ctx.signed_in(owner_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    @patch(MAIL_TARGET)
    def test_unrelated_user_cannot_approve(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                outsider_username = _username(world.users['outsider'])

            with ctx.signed_in(outsider_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 403, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair
                from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

    def test_anonymous_approve_gets_json_401(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                _world, nomination_id = self._accepted_nomination(ctx)

            with ctx.signed_in(None) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()['code'], 'authentication_required')

    @patch(MAIL_TARGET)
    def test_email_only_nominee_without_account_is_blocked_with_actionable_error(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(
                    ctx, linked=False, email='stranger@example.org',
                )
                admin_username = _username(world.users['site_admin'])

            with ctx.signed_in(admin_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
            error = response.get_json()['error']
            self.assertIn('stranger@example.org', error)
            self.assertIn('sign in to Gov Hub', error)

            with ctx.app.app_context():
                from models import WorkingGroupChair, WorkingGroupMember
                from services.workgroup_positions import NOMINATION_STATUS_APPROVED

                nomination = WorkingGroupChair.query.get(nomination_id)
                self.assertNotEqual(nomination.status, NOMINATION_STATUS_APPROVED)
                self.assertIsNone(nomination.user_id)
                self.assertEqual(WorkingGroupMember.query.count(), 0)

    @patch(MAIL_TARGET)
    def test_email_only_nominee_with_account_is_linked_on_approval(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(
                    ctx, linked=False, email='ISO-Nominee@Example.com',
                )
                admin_username = _username(world.users['site_admin'])

            with ctx.signed_in(admin_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair, WorkingGroupMember

                nomination = WorkingGroupChair.query.get(nomination_id)
                self.assertEqual(nomination.user_id, world.users['nominee'])
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    @patch(MAIL_TARGET)
    def test_repeated_approve_is_idempotent(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                admin_username = _username(world.users['site_admin'])

            with ctx.signed_in(admin_username) as client:
                first = client.post(f'/api/admin/chair-nominations/{nomination_id}/approve/')
                second = client.post(f'/api/admin/chair-nominations/{nomination_id}/approve/')
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
            self.assertTrue(second.get_json()['already_approved'])

            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupMember

                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )
                self.assertEqual(
                    UserNotification.query.filter_by(
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    @patch(MAIL_TARGET)
    def test_approval_survives_email_failure(self, mock_send):
        mock_send.side_effect = RuntimeError('smtp down')
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                admin_username = _username(world.users['site_admin'])

            with ctx.signed_in(admin_username) as client:
                response = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/approve/'
                )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            data = response.get_json()
            self.assertFalse(data['notifications_sent'])
            self.assertIn('Approve again to retry', data['warning'])

            with ctx.app.app_context():
                from models import WorkingGroupMember
                from services.workgroup_positions import NOMINATION_STATUS_APPROVED
                from models import WorkingGroupChair

                # Consent + role + membership must survive a mail outage.
                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_APPROVED,
                )
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    @patch(MAIL_TARGET)
    def test_approved_nomination_cannot_be_rejected(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world, nomination_id = self._accepted_nomination(ctx)
                admin_username = _username(world.users['site_admin'])

            with ctx.signed_in(admin_username) as client:
                self.assertEqual(
                    client.post(
                        f'/api/admin/chair-nominations/{nomination_id}/approve/'
                    ).status_code,
                    200,
                )
                rejected = client.post(
                    f'/api/admin/chair-nominations/{nomination_id}/reject/'
                )
            self.assertEqual(rejected.status_code, 409, rejected.get_data(as_text=True))

            with ctx.app.app_context():
                from models import WorkingGroupChair, WorkingGroupMember
                from services.workgroup_positions import NOMINATION_STATUS_APPROVED

                self.assertEqual(
                    WorkingGroupChair.query.get(nomination_id).status,
                    NOMINATION_STATUS_APPROVED,
                )
                # A refused rejection must not strip legitimate membership.
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )


class AdminReviewListScopeTests(unittest.TestCase):
    """GET /api/admin/chair-nominations/"""

    def _two_layers(self, ctx):
        from extensions import db
        from models import Layer, LayerAdmin, Workgroup
        from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

        world = seed_dp_workgroup(ctx)
        make_nomination(
            group_acronym=world.workgroup_acronym,
            chair_name='On My Layer',
            nominee_email='iso-nominee@example.com',
            status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            user_id=world.users['nominee'],
        )

        other_layer = Layer(
            name='Other Isolated Layer',
            slug='other-isolated-layer',
            initiator_id=world.users['attacker'],
            approval_status='approved',
        )
        db.session.add(other_layer)
        db.session.flush()
        db.session.add(LayerAdmin(
            layer_id=other_layer.id, user_id=world.users['outsider'],
        ))
        other_wg = Workgroup(
            acronym='dp98-other-layer-property',
            name='DP98 – Other Layer Property',
            slug='dp98-other-layer-property',
            layer_id=other_layer.id,
            status='active',
            approval_status='approved',
        )
        db.session.add(other_wg)
        db.session.commit()
        make_nomination(
            group_acronym=other_wg.acronym,
            chair_name='On Other Layer',
            nominee_email='iso-outsider@example.com',
            status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            user_id=world.users['outsider'],
        )
        return world

    def test_staff_see_all_layer_admins_see_only_their_own(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = self._two_layers(ctx)
                admin_username = _username(world.users['site_admin'])
                layer_admin_username = _username(world.users['layer_admin'])
                other_admin_username = _username(world.users['outsider'])

            with ctx.signed_in(admin_username) as client:
                staff = client.get('/api/admin/chair-nominations/').get_json()
            self.assertEqual(staff['count'], 2)

            with ctx.signed_in(layer_admin_username) as client:
                scoped = client.get('/api/admin/chair-nominations/').get_json()
            self.assertEqual([n['chair_name'] for n in scoped['nominations']], ['On My Layer'])

            with ctx.signed_in(other_admin_username) as client:
                other = client.get('/api/admin/chair-nominations/').get_json()
            self.assertEqual([n['chair_name'] for n in other['nominations']], ['On Other Layer'])

    def test_user_without_any_layer_gets_403(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                nobody_username = _username(world.users['nominee'])

            with ctx.signed_in(nobody_username) as client:
                response = client.get('/api/admin/chair-nominations/')
            self.assertEqual(response.status_code, 403)

            with ctx.signed_in(nobody_username) as client:
                page = client.get('/admin/chair-nominations/')
            self.assertEqual(page.status_code, 403)


class JoinRouteTests(unittest.TestCase):
    """POST /api/workgroups/<id>/join/"""

    def test_join_creates_membership_and_welcome_together(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                joiner_username = _username(world.users['outsider'])

            with ctx.signed_in(joiner_username) as client:
                response = client.post(f'/api/workgroups/{world.workgroup_id}/join/')
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            data = response.get_json()
            self.assertIn('/welcome/member', data['welcome_url'])

            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupMember
                from services.dp_welcome import list_dp_welcome_notifications

                uid = world.users['outsider']
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym, user_id=uid,
                    ).count(),
                    1,
                )
                self.assertEqual(UserNotification.query.filter_by(user_id=uid).count(), 1)
                welcomes = list_dp_welcome_notifications(uid)
                self.assertEqual([w['variant'] for w in welcomes], ['member'])

    def test_welcome_and_membership_roll_back_together_on_failure(self):
        """A welcome-delivery error must not leave a membership behind."""
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                joiner_username = _username(world.users['outsider'])

            with patch(
                'routes.workgroups.deliver_dp_welcome',
                side_effect=RuntimeError('notification store down'),
            ):
                with ctx.signed_in(joiner_username) as client:
                    with self.assertRaises(RuntimeError):
                        client.post(f'/api/workgroups/{world.workgroup_id}/join/')

            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupMember

                self.assertEqual(WorkingGroupMember.query.count(), 0)
                self.assertEqual(UserNotification.query.count(), 0)

    def test_second_join_is_reported_as_duplicate(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                joiner_username = _username(world.users['outsider'])

            with ctx.signed_in(joiner_username) as client:
                self.assertEqual(
                    client.post(f'/api/workgroups/{world.workgroup_id}/join/').status_code, 200,
                )
                again = client.post(f'/api/workgroups/{world.workgroup_id}/join/')
            self.assertEqual(again.status_code, 400)
            self.assertIn('already a member', again.get_json()['error'])

            with ctx.app.app_context():
                from models import WorkingGroupMember

                self.assertEqual(WorkingGroupMember.query.count(), 1)


class JoinContinuationTests(unittest.TestCase):
    """?action=join must survive the sign-in round trip."""

    def test_workgroup_page_keeps_action_for_anonymous_visitors(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                slug = world.workgroup_slug

            with ctx.signed_in(None) as client:
                response = client.get(f'/workgroups/{slug}/?action=join')
            self.assertEqual(response.status_code, 200)
            body = response.get_data(as_text=True)
            # The action is captured before any URL rewrite and reused for ?next=.
            self.assertIn('const initialSearch = window.location.search;', body)
            self.assertIn('if (isAuthenticated) {', body)
            self.assertIn('(initialSearch || window.location.search)', body)

    def test_login_next_preserves_query_string(self):
        from services.auth_redirect import login_url, safe_return_path

        target = '/workgroups/dp99-isolated-test-property/?action=join'
        self.assertEqual(safe_return_path(target), target)
        self.assertIn('action%3Djoin', login_url(target))

    def test_login_returns_signed_in_user_to_the_pending_action(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                username = _username(world.users['outsider'])
                target = f'/workgroups/{world.workgroup_slug}/?action=join'

            with ctx.signed_in(username) as client:
                response = client.get(
                    f'/login/?next={quote(target, safe="")}', follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers['Location'].endswith(target))


class MeDpWelcomeApiTests(unittest.TestCase):
    """GET /api/me/dp-welcome/"""

    def test_anonymous_gets_json_401(self):
        with isolated_app() as ctx:
            with ctx.signed_in(None) as client:
                response = client.get('/api/me/dp-welcome/')
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.content_type.split(';')[0], 'application/json')
            self.assertEqual(response.get_json()['code'], 'authentication_required')

    def test_invalid_bearer_token_gets_json_401(self):
        with isolated_app() as ctx:
            with ctx.signed_in(None) as client:
                response = client.get(
                    '/api/me/dp-welcome/',
                    headers={'Authorization': 'Bearer not-a-real-token'},
                )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.get_json()['code'], 'authentication_required')

    def test_signed_in_user_without_welcome_gets_empty_list(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                username = _username(world.users['outsider'])

            with ctx.signed_in(username) as client:
                response = client.get('/api/me/dp-welcome/')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['count'], 0)
            self.assertEqual(data['welcomes'], [])

    def test_welcome_disappears_after_leaving_the_workgroup(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                world = seed_dp_workgroup(ctx)
                username = _username(world.users['outsider'])
                acronym = world.workgroup_acronym

            with ctx.signed_in(username) as client:
                self.assertEqual(
                    client.post(f'/api/workgroups/{world.workgroup_id}/join/').status_code, 200,
                )
                listed = client.get('/api/me/dp-welcome/').get_json()
                self.assertEqual(listed['count'], 1)

                self.assertEqual(client.post(f'/group/{acronym}/leave').status_code, 200)
                after = client.get('/api/me/dp-welcome/').get_json()
                notifications = client.get('/api/me/notifications/').get_json()
            self.assertEqual(after['count'], 0)
            # The stale welcome also stops appearing in the general feed.
            self.assertEqual(notifications['count'], 0)


if __name__ == '__main__':
    unittest.main()
