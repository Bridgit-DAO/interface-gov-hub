"""DP workgroup welcome delivery, membership, and nomination email rules.

Every test that needs rows runs against a disposable SQLite database built by
``fixtures.isolated_app``. Nothing here reads or writes the deployed database,
and the harness raises rather than falling back if isolation cannot be set up.
"""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')
os.environ.setdefault('SECRET_KEY', 'isolated-test-secret-key')

from fixtures.isolated_app import (  # noqa: E402 - env must be set before import
    isolated_app,
    make_nomination,
    make_user,
    seed_dp_workgroup,
)


class DpWelcomePureTests(unittest.TestCase):
    """Rules that need no database at all."""

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

        self.assertIn(
            '/welcome/member?wg=dp1-federated-auth',
            dp_welcome_page_url('dp1-federated-auth', 'member'),
        )
        self.assertIn(
            '/welcome/lead?wg=dp1-federated-auth',
            dp_welcome_page_url('dp1-federated-auth', 'lead'),
        )

    def test_welcome_slug_is_url_encoded(self):
        from services.dp_welcome import dp_welcome_page_url, welcome_slug_from_link

        url = dp_welcome_page_url('dp7 signals & noise/edge', 'member')
        self.assertNotIn(' ', url)
        self.assertNotIn('&noise', url)
        self.assertIn('%2F', url)
        self.assertEqual(welcome_slug_from_link(url), 'dp7 signals & noise/edge')

    def test_welcome_variant_mapping(self):
        from services.dp_welcome import nomination_welcome_variant

        self.assertEqual(nomination_welcome_variant('chair'), 'lead')
        self.assertEqual(nomination_welcome_variant('co_lead'), 'lead')
        self.assertEqual(nomination_welcome_variant('editor'), 'member')
        self.assertEqual(nomination_welcome_variant(None), 'lead')


class IsolatedDatabaseSafetyTests(unittest.TestCase):
    def test_harness_uses_a_disposable_database(self):
        from config import DB_PATH

        with isolated_app() as ctx:
            self.assertTrue(os.path.exists(ctx.db_path))
            self.assertNotEqual(os.path.realpath(ctx.db_path), os.path.realpath(DB_PATH))
            self.assertEqual(
                ctx.app.config['SQLALCHEMY_DATABASE_URI'],
                f'sqlite:///{ctx.db_path}',
            )
            with ctx.app.app_context():
                from models import User

                self.assertEqual(User.query.count(), 0)
        self.assertFalse(os.path.exists(ctx.db_path))

    def test_seeded_world_is_self_contained(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import User

                world = seed_dp_workgroup(ctx)
                self.assertEqual(User.query.count(), len(world.users))


class MembershipUniquenessTests(unittest.TestCase):
    def test_unique_index_blocks_duplicate_membership(self):
        from sqlalchemy.exc import IntegrityError

        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import WorkingGroupMember

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                db.session.add(WorkingGroupMember(
                    group_acronym=world.workgroup_acronym, user_id=uid, user_name='A',
                ))
                db.session.commit()
                db.session.add(WorkingGroupMember(
                    group_acronym=world.workgroup_acronym, user_id=uid, user_name='B',
                ))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym, user_id=uid,
                    ).count(),
                    1,
                )

    def test_ensure_membership_is_idempotent_and_race_safe(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import WorkingGroupMember
                from services.workgroup_membership import ensure_workgroup_membership

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']

                first, created_first = ensure_workgroup_membership(
                    acronym=world.workgroup_acronym, user_id=uid, display_name='First',
                )
                db.session.commit()
                self.assertTrue(created_first)
                self.assertIsNotNone(first)

                second, created_second = ensure_workgroup_membership(
                    acronym=world.workgroup_acronym, user_id=uid, display_name='Second',
                )
                db.session.commit()
                self.assertFalse(created_second)
                self.assertEqual(second.id, first.id)
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym, user_id=uid,
                    ).count(),
                    1,
                )

    def test_ensure_membership_survives_concurrent_insert(self):
        """A row appearing mid-transaction must not break the caller's session."""
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import WorkingGroupMember
                from services.workgroup_membership import ensure_workgroup_membership

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                acronym = world.workgroup_acronym

                real_lookup = WorkingGroupMember.query.filter_by

                db.session.execute(
                    db.text(
                        'INSERT INTO working_group_member '
                        '(id, group_acronym, user_id, user_name) '
                        'VALUES (:id, :acronym, :uid, :name)'
                    ),
                    {'id': 'competing-row', 'acronym': acronym, 'uid': uid, 'name': 'Racer'},
                )

                calls = {'n': 0}

                def lookup(acr, user_id):
                    # First call is the pre-insert check, which in a lost race
                    # still sees nothing; later calls are the recovery lookup.
                    calls['n'] += 1
                    if calls['n'] == 1:
                        return None
                    return real_lookup(group_acronym=acr, user_id=user_id).first()

                with patch(
                    'services.workgroup_membership.find_workgroup_membership',
                    side_effect=lookup,
                ):
                    member, created = ensure_workgroup_membership(
                        acronym=acronym, user_id=uid, display_name='Loser',
                    )
                self.assertFalse(created)
                db.session.commit()
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=acronym, user_id=uid,
                    ).count(),
                    1,
                )
                self.assertIsNotNone(member)

    def test_migration_dedupes_existing_rows_and_is_idempotent(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from migrations import migrate_workgroup_member_unique_v1
                from services.workgroup_membership import ensure_workgroup_membership

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                acronym = world.workgroup_acronym

                # Reproduce the deployed pre-migration schema: the table exists
                # without any uniqueness on (group_acronym, user_id).
                db.session.execute(db.text('DROP TABLE working_group_member'))
                db.session.execute(db.text(
                    'CREATE TABLE working_group_member ('
                    '  id VARCHAR(36) NOT NULL PRIMARY KEY,'
                    '  group_acronym VARCHAR(50),'
                    '  user_id VARCHAR(36) REFERENCES user(id),'
                    '  user_name VARCHAR(100),'
                    '  joined_at DATETIME)'
                ))
                for idx in range(3):
                    db.session.execute(
                        db.text(
                            'INSERT INTO working_group_member '
                            '(id, group_acronym, user_id, user_name) '
                            'VALUES (:id, :acronym, :uid, :name)'
                        ),
                        {'id': f'dup-{idx}', 'acronym': acronym, 'uid': uid, 'name': f'Dup {idx}'},
                    )
                # NULL user_id rows are legacy display-only rows: preserved.
                db.session.execute(
                    db.text(
                        'INSERT INTO working_group_member '
                        '(id, group_acronym, user_id, user_name) '
                        'VALUES (:id, :acronym, NULL, :name)'
                    ),
                    {'id': 'legacy-1', 'acronym': acronym, 'name': 'Legacy One'},
                )
                db.session.execute(
                    db.text(
                        'INSERT INTO working_group_member '
                        '(id, group_acronym, user_id, user_name) '
                        'VALUES (:id, :acronym, NULL, :name)'
                    ),
                    {'id': 'legacy-2', 'acronym': acronym, 'name': 'Legacy Two'},
                )
                db.session.commit()

                # Joining must keep working on a database that has not applied
                # the migration yet (deploy order is not guaranteed).
                pre_member, pre_created = ensure_workgroup_membership(
                    acronym=acronym,
                    user_id=world.users['outsider'],
                    display_name='Pre Migration',
                )
                self.assertTrue(pre_created)
                self.assertIsNotNone(pre_member)
                db.session.commit()

            migrate_workgroup_member_unique_v1(ctx.app)
            migrate_workgroup_member_unique_v1(ctx.app)  # idempotent

            with ctx.app.app_context():
                from extensions import db
                from models import WorkingGroupMember

                db.session.remove()
                survivors = WorkingGroupMember.query.filter_by(
                    group_acronym=acronym, user_id=uid,
                ).all()
                self.assertEqual(len(survivors), 1)
                self.assertEqual(survivors[0].id, 'dup-0')  # oldest row kept
                self.assertEqual(
                    WorkingGroupMember.query.filter(
                        WorkingGroupMember.group_acronym == acronym,
                        WorkingGroupMember.user_id.is_(None),
                    ).count(),
                    2,
                )
                indexes = db.session.execute(db.text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='working_group_member'"
                )).fetchall()
                self.assertIn('uq_wgm_group_user', {row[0] for row in indexes})

    def test_notification_archive_migration_adds_column_and_is_idempotent(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db

                # Deployed shape before the migration: no archived_at column.
                db.session.execute(db.text('DROP TABLE user_notification'))
                db.session.execute(db.text(
                    'CREATE TABLE user_notification ('
                    '  id VARCHAR(36) NOT NULL PRIMARY KEY,'
                    '  user_id VARCHAR(36) NOT NULL,'
                    '  event_log_id VARCHAR(36),'
                    '  title VARCHAR(255) NOT NULL,'
                    '  body TEXT,'
                    '  link_url VARCHAR(500),'
                    '  read_at DATETIME,'
                    '  email_sent_at DATETIME,'
                    '  created_at DATETIME NOT NULL)'
                ))
                db.session.commit()

            from migrations import migrate_user_notification_archived_at_v1

            migrate_user_notification_archived_at_v1(ctx.app)
            migrate_user_notification_archived_at_v1(ctx.app)  # idempotent

            with ctx.app.app_context():
                from extensions import db

                db.session.remove()
                cols = {
                    row[1]
                    for row in db.session.execute(
                        db.text('PRAGMA table_info(user_notification)')
                    ).fetchall()
                }
                self.assertIn('archived_at', cols)


class WelcomeDeliveryTests(unittest.TestCase):
    def test_delivery_is_idempotent_per_variant(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import UserNotification, Workgroup
                from services.dp_welcome import deliver_dp_welcome

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                workgroup = Workgroup.query.get(world.workgroup_id)

                first = deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                db.session.commit()
                second = deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                db.session.commit()
                self.assertEqual(first, second)
                self.assertEqual(
                    UserNotification.query.filter_by(user_id=uid, link_url=first).count(), 1,
                )

                lead = deliver_dp_welcome(
                    user_id=uid, workgroup=workgroup, variant='lead', position_key='chair',
                )
                db.session.commit()
                self.assertNotEqual(lead, first)
                self.assertEqual(UserNotification.query.filter_by(user_id=uid).count(), 2)

    def test_listing_only_returns_welcomes_with_a_live_grant(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import Workgroup, WorkingGroupMember
                from services.dp_welcome import (
                    deliver_dp_welcome,
                    list_dp_welcome_notifications,
                )

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                workgroup = Workgroup.query.get(world.workgroup_id)

                deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                db.session.commit()
                # No membership yet: the welcome is not a valid grant.
                self.assertEqual(list_dp_welcome_notifications(uid), [])

                db.session.add(WorkingGroupMember(
                    group_acronym=world.workgroup_acronym, user_id=uid, user_name='Nominee',
                ))
                db.session.commit()
                welcomes = list_dp_welcome_notifications(uid)
                self.assertEqual(len(welcomes), 1)
                self.assertEqual(welcomes[0]['variant'], 'member')

    def test_lead_welcome_requires_approved_position(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import Workgroup
                from services.dp_welcome import (
                    deliver_dp_welcome,
                    list_dp_welcome_notifications,
                )
                from services.workgroup_positions import NOMINATION_STATUS_APPROVED

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                workgroup = Workgroup.query.get(world.workgroup_id)

                deliver_dp_welcome(
                    user_id=uid, workgroup=workgroup, variant='lead', position_key='chair',
                )
                db.session.commit()
                self.assertEqual(list_dp_welcome_notifications(uid), [])

                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_APPROVED,
                    user_id=uid,
                )
                nomination.approved = True
                db.session.commit()
                welcomes = list_dp_welcome_notifications(uid)
                self.assertEqual([w['variant'] for w in welcomes], ['lead'])

    def test_leaving_a_workgroup_archives_the_member_welcome(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import User, Workgroup, WorkingGroupMember
                from services.dp_welcome import (
                    deliver_dp_welcome,
                    list_dp_welcome_notifications,
                )

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                username = User.query.get(uid).username
                workgroup = Workgroup.query.get(world.workgroup_id)
                acronym = world.workgroup_acronym
                db.session.add(WorkingGroupMember(
                    group_acronym=acronym, user_id=uid, user_name='Nominee',
                ))
                deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                db.session.commit()
                self.assertEqual(len(list_dp_welcome_notifications(uid)), 1)

            with ctx.signed_in(username) as client:
                response = client.post(f'/group/{acronym}/leave')
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

            with ctx.app.app_context():
                from models import UserNotification
                from services.dp_welcome import list_dp_welcome_notifications

                self.assertEqual(list_dp_welcome_notifications(uid), [])
                # Archived, not deleted, and the title the person saw is intact.
                row = UserNotification.query.filter_by(user_id=uid).one()
                self.assertIsNotNone(row.archived_at)
                self.assertTrue(row.title.startswith('Welcome to '))

    def test_rejoining_revives_the_archived_welcome_without_duplicating(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import UserNotification, Workgroup, WorkingGroupMember
                from services.dp_welcome import (
                    deliver_dp_welcome,
                    invalidate_dp_welcomes_for_workgroup,
                    list_dp_welcome_notifications,
                )

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                workgroup = Workgroup.query.get(world.workgroup_id)

                deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                invalidate_dp_welcomes_for_workgroup(
                    user_id=uid, workgroup=workgroup, variants=('member',),
                )
                db.session.commit()

                db.session.add(WorkingGroupMember(
                    group_acronym=world.workgroup_acronym, user_id=uid, user_name='Nominee',
                ))
                deliver_dp_welcome(user_id=uid, workgroup=workgroup, variant='member')
                db.session.commit()

                self.assertEqual(UserNotification.query.filter_by(user_id=uid).count(), 1)
                self.assertEqual(len(list_dp_welcome_notifications(uid)), 1)
                self.assertIsNone(
                    UserNotification.query.filter_by(user_id=uid).one().archived_at
                )


class NomineeIdentityResolutionTests(unittest.TestCase):
    def test_account_email_wins_and_mismatch_is_rejected(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import (
                    NOMINEE_EMAIL_MISMATCH_ERROR,
                    resolve_nominee_identity,
                )

                world = seed_dp_workgroup(ctx)
                victim_id = world.users['nominee']

                derived = resolve_nominee_identity(nominee_user_id=victim_id, nominee_email='')
                self.assertIsNone(derived.error)
                self.assertEqual(derived.email, 'iso-nominee@example.com')

                matching = resolve_nominee_identity(
                    nominee_user_id=victim_id, nominee_email='ISO-Nominee@Example.com',
                )
                self.assertIsNone(matching.error)
                self.assertEqual(matching.email, 'iso-nominee@example.com')

                attack = resolve_nominee_identity(
                    nominee_user_id=victim_id, nominee_email='attacker@evil.example',
                )
                self.assertEqual(attack.error, NOMINEE_EMAIL_MISMATCH_ERROR)

    def test_account_without_email_cannot_be_nominated(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from services.workgroup_nomination_flow import (
                    NOMINEE_ACCOUNT_MISSING_EMAIL_ERROR,
                    resolve_nominee_identity,
                )

                seed_dp_workgroup(ctx)
                mailless = make_user(username='iso-no-email', email=None)
                db.session.commit()

                result = resolve_nominee_identity(
                    nominee_user_id=mailless.id, nominee_email='attacker@evil.example',
                )
                self.assertEqual(result.error, NOMINEE_ACCOUNT_MISSING_EMAIL_ERROR)

    def test_email_only_nomination_keeps_submitted_email(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import resolve_nominee_identity

                seed_dp_workgroup(ctx)
                result = resolve_nominee_identity(
                    nominee_user_id=None, nominee_email='Someone@Example.COM',
                )
                self.assertIsNone(result.error)
                self.assertIsNone(result.user_id)
                self.assertEqual(result.email, 'someone@example.com')


class ApprovalFlowTests(unittest.TestCase):
    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_approval_grants_role_membership_and_one_lead_welcome(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import UserNotification, WorkingGroupMember
                from services.workgroup_nomination_flow import approve_nomination
                from services.workgroup_positions import (
                    NOMINATION_STATUS_APPROVED,
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                    user_id=uid,
                )

                result = approve_nomination(nomination)
                self.assertTrue(result.ok, result.error)
                self.assertTrue(result.membership_created)
                self.assertIn('/welcome/lead', result.welcome_url)
                self.assertEqual(nomination.status, NOMINATION_STATUS_APPROVED)
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym, user_id=uid,
                    ).count(),
                    1,
                )
                self.assertEqual(UserNotification.query.filter_by(user_id=uid).count(), 1)

    def test_approval_requires_nominee_acceptance(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import approve_nomination
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                world = seed_dp_workgroup(ctx)
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_PENDING_NOMINEE,
                    user_id=world.users['nominee'],
                )
                result = approve_nomination(nomination)
                self.assertFalse(result.ok)
                self.assertEqual(result.status_code, 400)

    def test_email_only_nominee_without_account_is_blocked(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import WorkingGroupMember
                from services.workgroup_nomination_flow import approve_nomination
                from services.workgroup_positions import (
                    NOMINATION_STATUS_APPROVED,
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

                world = seed_dp_workgroup(ctx)
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Unknown Person',
                    nominee_email='nobody@example.org',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

                result = approve_nomination(nomination)
                self.assertFalse(result.ok)
                self.assertEqual(result.status_code, 409)
                self.assertIn('nobody@example.org', result.error)
                self.assertIn('sign in to Gov Hub', result.error)
                self.assertNotEqual(nomination.status, NOMINATION_STATUS_APPROVED)
                self.assertIsNone(nomination.user_id)
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                    ).count(),
                    0,
                )

    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_email_only_nominee_is_linked_when_account_exists(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import WorkingGroupMember
                from services.workgroup_nomination_flow import approve_nomination
                from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

                world = seed_dp_workgroup(ctx)
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    # Same address as the seeded account, different casing.
                    nominee_email='ISO-Nominee@Example.com',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

                result = approve_nomination(nomination)
                self.assertTrue(result.ok, result.error)
                self.assertEqual(result.linked_user_id, world.users['nominee'])
                self.assertEqual(nomination.user_id, world.users['nominee'])
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_replayed_approval_repairs_instead_of_duplicating(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import UserNotification, WorkingGroupMember
                from services.workgroup_nomination_flow import approve_nomination
                from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

                world = seed_dp_workgroup(ctx)
                uid = world.users['nominee']
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                    user_id=uid,
                )
                self.assertTrue(approve_nomination(nomination).ok)

                # Simulate a half-delivered approval: membership vanished.
                WorkingGroupMember.query.filter_by(
                    group_acronym=world.workgroup_acronym, user_id=uid,
                ).delete()
                db.session.commit()

                replay = approve_nomination(nomination)
                self.assertTrue(replay.ok, replay.error)
                self.assertTrue(replay.already_approved)
                self.assertTrue(replay.membership_created)
                self.assertEqual(UserNotification.query.filter_by(user_id=uid).count(), 1)

    @patch('services.workgroup_nomination_mail.send_resend_email')
    def test_approved_role_cannot_be_rejected(self, _mock_send):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import WorkingGroupMember
                from services.workgroup_nomination_flow import (
                    APPROVED_CANNOT_BE_REJECTED_ERROR,
                    approve_nomination,
                    reject_nomination,
                )
                from services.workgroup_positions import (
                    NOMINATION_STATUS_APPROVED,
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                )

                world = seed_dp_workgroup(ctx)
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                    user_id=world.users['nominee'],
                )
                self.assertTrue(approve_nomination(nomination).ok)

                result = reject_nomination(nomination)
                self.assertFalse(result.ok)
                self.assertEqual(result.error, APPROVED_CANNOT_BE_REJECTED_ERROR)
                self.assertEqual(nomination.status, NOMINATION_STATUS_APPROVED)
                # Membership must survive the refused transition.
                self.assertEqual(
                    WorkingGroupMember.query.filter_by(
                        group_acronym=world.workgroup_acronym,
                        user_id=world.users['nominee'],
                    ).count(),
                    1,
                )

    def test_unapproved_nomination_can_be_rejected(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import reject_nomination
                from services.workgroup_positions import (
                    NOMINATION_STATUS_NOMINEE_ACCEPTED,
                    NOMINATION_STATUS_REJECTED,
                )

                world = seed_dp_workgroup(ctx)
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='iso-nominee@example.com',
                    status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
                    user_id=world.users['nominee'],
                )
                self.assertTrue(reject_nomination(nomination).ok)
                self.assertEqual(nomination.status, NOMINATION_STATUS_REJECTED)


class ReviewAuthorizationTests(unittest.TestCase):
    def _nomination_and_users(self, ctx):
        from models import User
        from services.workgroup_positions import NOMINATION_STATUS_NOMINEE_ACCEPTED

        world = seed_dp_workgroup(ctx)
        nomination = make_nomination(
            group_acronym=world.workgroup_acronym,
            chair_name='Nominee Person',
            nominee_email='iso-nominee@example.com',
            status=NOMINATION_STATUS_NOMINEE_ACCEPTED,
            user_id=world.users['nominee'],
        )
        users = {
            key: User.query.get(uid) for key, uid in world.users.items()
        }
        return world, nomination, users

    def _as_dict(self, user):
        return {'id': user.id, 'email': user.email, 'role': user.role}

    def test_layer_owner_and_layer_admin_may_review(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import can_review_nomination

                _world, nomination, users = self._nomination_and_users(ctx)
                for key in ('site_admin', 'layer_owner', 'layer_admin'):
                    self.assertTrue(
                        can_review_nomination(nomination, self._as_dict(users[key])),
                        f'{key} should be able to review',
                    )

    def test_unrelated_user_may_not_review(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from services.workgroup_nomination_flow import (
                    can_review_any_nomination,
                    can_review_nomination,
                )

                _world, nomination, users = self._nomination_and_users(ctx)
                outsider = self._as_dict(users['outsider'])
                self.assertFalse(can_review_nomination(nomination, outsider))
                self.assertFalse(can_review_any_nomination(outsider))
                self.assertFalse(can_review_nomination(nomination, None))

    def test_layer_admin_of_another_layer_may_not_review(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from extensions import db
                from models import Layer, LayerAdmin
                from services.workgroup_nomination_flow import (
                    can_review_any_nomination,
                    can_review_nomination,
                )

                _world, nomination, users = self._nomination_and_users(ctx)
                other_admin = users['outsider']
                other_layer = Layer(
                    name='Other Isolated Layer',
                    slug='other-isolated-layer',
                    initiator_id=users['attacker'].id,
                    approval_status='approved',
                )
                db.session.add(other_layer)
                db.session.flush()
                db.session.add(LayerAdmin(layer_id=other_layer.id, user_id=other_admin.id))
                db.session.commit()

                payload = self._as_dict(other_admin)
                # Reachable queue (they do administer something) but not this row.
                self.assertTrue(can_review_any_nomination(payload))
                self.assertFalse(can_review_nomination(nomination, payload))


class NomineeResponseBindingTests(unittest.TestCase):
    def test_only_linked_account_matches(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import User
                from services.workgroup_nomination_flow import caller_matches_nomination
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                world = seed_dp_workgroup(ctx)
                nominee = User.query.get(world.users['nominee'])
                attacker = User.query.get(world.users['attacker'])
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email=nominee.email,
                    status=NOMINATION_STATUS_PENDING_NOMINEE,
                    user_id=nominee.id,
                )

                self.assertTrue(caller_matches_nomination(
                    nomination, {'id': nominee.id, 'email': nominee.email},
                ))
                self.assertFalse(caller_matches_nomination(
                    nomination, {'id': attacker.id, 'email': attacker.email},
                ))
                # An attacker who somehow shares the email still cannot act on a
                # nomination bound to another account.
                self.assertFalse(caller_matches_nomination(
                    nomination, {'id': attacker.id, 'email': nominee.email},
                ))

    def test_email_only_nomination_matches_verified_account_email(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import User
                from services.workgroup_nomination_flow import caller_matches_nomination
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                world = seed_dp_workgroup(ctx)
                nominee = User.query.get(world.users['nominee'])
                attacker = User.query.get(world.users['attacker'])
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email='ISO-Nominee@Example.com',
                    status=NOMINATION_STATUS_PENDING_NOMINEE,
                )

                self.assertTrue(caller_matches_nomination(
                    nomination, {'id': nominee.id, 'email': nominee.email},
                ))
                self.assertFalse(caller_matches_nomination(
                    nomination, {'id': attacker.id, 'email': attacker.email},
                ))

    def test_nomination_without_email_or_account_matches_nobody(self):
        with isolated_app() as ctx:
            with ctx.app.app_context():
                from models import User
                from services.workgroup_nomination_flow import caller_matches_nomination
                from services.workgroup_positions import NOMINATION_STATUS_PENDING_NOMINEE

                world = seed_dp_workgroup(ctx)
                nominee = User.query.get(world.users['nominee'])
                nomination = make_nomination(
                    group_acronym=world.workgroup_acronym,
                    chair_name='Nominee Person',
                    nominee_email=None,
                    status=NOMINATION_STATUS_PENDING_NOMINEE,
                )
                self.assertFalse(caller_matches_nomination(
                    nomination, {'id': nominee.id, 'email': nominee.email},
                ))


if __name__ == '__main__':
    unittest.main()
