"""Pytest: ensure SQLite migrations for models added after first DB clone.

Most legacy test modules read the configured (deployed) database, so this
fixture keeps its schema in sync. Tests that build their own disposable
database (``fixtures/isolated_app.py``) do not need it; set
``GOVHUB_SKIP_SHARED_DB_MIGRATIONS=1`` when running only those so the session
never opens the deployed database at all.
"""
import os

import pytest


def _skip_shared_db() -> bool:
    return os.environ.get('GOVHUB_SKIP_SHARED_DB_MIGRATIONS', '').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )


@pytest.fixture(scope='session', autouse=True)
def ensure_schema_migrations():
    if _skip_shared_db():
        return

    from app import app

    with app.app_context():
        from migrations import (
            migrate_guild_unified_phase1,
            migrate_access_control_v1,
            migrate_notifications_stack_v1,
            migrate_layer_invitations,
            migrate_dp_proposals,
            migrate_user_mfa_v1,
            migrate_layer_prefix_v1,
            migrate_submission_submitter_user_id_v1,
            migrate_user_notification_archived_at_v1,
            migrate_workgroup_member_unique_v1,
        )
        from extensions import db

        db.create_all()
        migrate_guild_unified_phase1(app)
        migrate_access_control_v1(app)
        migrate_notifications_stack_v1(app)
        migrate_layer_invitations(app)
        migrate_dp_proposals(app)
        migrate_user_mfa_v1(app)
        migrate_layer_prefix_v1(app)
        migrate_submission_submitter_user_id_v1(app)
        migrate_workgroup_member_unique_v1(app)
        migrate_user_notification_archived_at_v1(app)
