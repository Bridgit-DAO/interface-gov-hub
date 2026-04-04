"""Pytest: ensure SQLite migrations for models added after first DB clone."""
import pytest


@pytest.fixture(scope='session', autouse=True)
def ensure_schema_migrations():
    from app import app

    with app.app_context():
        from migrations import migrate_guild_unified_phase1
        from extensions import db

        migrate_guild_unified_phase1(app)
        db.create_all()
