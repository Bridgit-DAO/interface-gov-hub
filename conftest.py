"""Pytest: ensure SQLite migrations for models added after first DB clone."""
import pytest


@pytest.fixture(scope='session', autouse=True)
def ensure_schema_migrations():
    from app import app

    with app.app_context():
        from migrations import (
            migrate_guild_unified_phase1,
            migrate_access_control_v1,
            migrate_notifications_stack_v1,
        )
        from extensions import db

        db.create_all()
        migrate_guild_unified_phase1(app)
        migrate_access_control_v1(app)
        migrate_notifications_stack_v1(app)
