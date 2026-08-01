"""Disposable Flask app + SQLite database for tests.

Tests that need real rows (users, layers, workgroups, nominations) must never
run against the deployed database. This harness builds a throwaway SQLite file
in a temp directory, points a dedicated ``create_app()`` instance at it, and
seeds only the rows the test asks for.

Fail-closed by design: :func:`isolated_app` raises ``RuntimeError`` if the
temp database cannot be created or if the resulting app is still bound to the
configured (deployed) database, so a misconfigured test errors instead of
silently mutating real data.

Typical use::

    from fixtures.isolated_app import isolated_app, seed_dp_workgroup

    with isolated_app() as ctx:
        with ctx.app.app_context():
            world = seed_dp_workgroup(ctx)
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator, Optional
from uuid import uuid4

DP_WORKGROUP_ACRONYM = 'dp99-isolated-test-property'
DP_WORKGROUP_SLUG = 'dp99-isolated-test-property'
DP_WORKGROUP_NAME = 'DP99 – Isolated Test Property'


@dataclass
class IsolatedContext:
    """Handle for a disposable app/database pair."""

    app: object
    db_path: str
    tmpdir: str

    def client(self):
        return self.app.test_client()

    @contextlib.contextmanager
    def signed_in(self, username: Optional[str]):
        """Test client with ``session['user']`` set (or anonymous when None)."""
        client = self.app.test_client()
        if username:
            with client.session_transaction() as sess:
                sess['user'] = username
        yield client


@dataclass
class SeededWorld:
    """Ids/handles for seeded rows. Only ids are kept so callers re-query."""

    layer_id: str = ''
    layer_slug: str = ''
    workgroup_id: str = ''
    workgroup_acronym: str = ''
    workgroup_slug: str = ''
    users: dict = field(default_factory=dict)


def _production_database_uri() -> str:
    from config import DB_PATH

    return f'sqlite:///{DB_PATH}'


@contextlib.contextmanager
def isolated_app() -> Iterator[IsolatedContext]:
    """Yield a disposable app bound to a fresh SQLite file; delete it after."""
    # A missing secret key would make create_app() raise in production mode;
    # tests always run with an explicit throwaway key.
    os.environ.setdefault('SECRET_KEY', 'isolated-test-secret-key')
    os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'isolated-test-referral-secret')

    tmpdir = tempfile.mkdtemp(prefix='govhub-isolated-db-')
    db_path = os.path.join(tmpdir, 'isolated.db')
    database_uri = f'sqlite:///{db_path}'
    if database_uri == _production_database_uri():
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError('Refusing to run tests against the deployed database.')

    app = None
    try:
        from app import create_app
        from extensions import db

        app = create_app(database_uri=database_uri, testing=True)
        resolved = app.config['SQLALCHEMY_DATABASE_URI']
        if resolved != database_uri:
            raise RuntimeError(
                f'Isolated app is bound to {resolved!r}, expected {database_uri!r}.'
            )

        with app.app_context():
            db.create_all()
            _run_schema_migrations(app)
        if not os.path.exists(db_path):
            raise RuntimeError(f'Isolated database was not created at {db_path}.')

        yield IsolatedContext(app=app, db_path=db_path, tmpdir=tmpdir)
    finally:
        if app is not None:
            with contextlib.suppress(Exception):
                from extensions import db as _db

                with app.app_context():
                    _db.session.remove()
                    _db.engine.dispose()
        shutil.rmtree(tmpdir, ignore_errors=True)


def _run_schema_migrations(app) -> None:
    """Apply migrations whose DDL is not expressible via ``db.create_all()``."""
    from migrations import (
        migrate_user_notification_archived_at_v1,
        migrate_workgroup_member_unique_v1,
    )

    migrate_workgroup_member_unique_v1(app)
    migrate_user_notification_archived_at_v1(app)


def make_user(
    *,
    username: str,
    email: Optional[str],
    role: str = 'user',
    display_name: Optional[str] = None,
):
    """Insert a User row. Returns the model instance (uncommitted)."""
    from extensions import db
    from models import User

    user = User(
        id=str(uuid4()),
        username=username,
        email=email,
        role=role,
        displayName=display_name or username.replace('-', ' ').title(),
        password_hash='!isolated-test-no-login',
    )
    db.session.add(user)
    db.session.flush()
    return user


def seed_dp_workgroup(
    _ctx: Optional[IsolatedContext] = None,
    *,
    acronym: str = DP_WORKGROUP_ACRONYM,
    slug: str = DP_WORKGROUP_SLUG,
    name: str = DP_WORKGROUP_NAME,
) -> SeededWorld:
    """Seed a layer, an approved DP workgroup, and the cast of test users.

    Users seeded: ``site_admin`` (global admin), ``layer_owner`` (layer
    initiator), ``layer_admin`` (assigned LayerAdmin), ``outsider``,
    ``nominee``, ``nominator``, ``attacker``.
    """
    from extensions import db
    from models import Layer, LayerAdmin, Workgroup

    site_admin = make_user(username='iso-site-admin', email='iso-site-admin@example.com', role='admin')
    layer_owner = make_user(username='iso-layer-owner', email='iso-layer-owner@example.com')
    layer_admin = make_user(username='iso-layer-admin', email='iso-layer-admin@example.com')
    outsider = make_user(username='iso-outsider', email='iso-outsider@example.com')
    nominee = make_user(username='iso-nominee', email='iso-nominee@example.com')
    nominator = make_user(username='iso-nominator', email='iso-nominator@example.com')
    attacker = make_user(username='iso-attacker', email='iso-attacker@example.com')

    layer = Layer(
        id=str(uuid4()),
        name='Isolated Test Layer',
        slug='isolated-test-layer',
        description='Disposable layer for DP welcome tests.',
        initiator_id=layer_owner.id,
        approval_status='approved',
    )
    db.session.add(layer)
    db.session.flush()
    db.session.add(LayerAdmin(layer_id=layer.id, user_id=layer_admin.id))

    workgroup = Workgroup(
        id=str(uuid4()),
        acronym=acronym,
        name=name,
        slug=slug,
        layer_id=layer.id,
        coordinator_id=layer_owner.id,
        description='Disposable DP workgroup.',
        status='active',
        approval_status='approved',
        created_at=datetime.utcnow(),
    )
    db.session.add(workgroup)
    db.session.commit()

    return SeededWorld(
        layer_id=layer.id,
        layer_slug=layer.slug,
        workgroup_id=workgroup.id,
        workgroup_acronym=workgroup.acronym,
        workgroup_slug=workgroup.slug,
        users={
            'site_admin': site_admin.id,
            'layer_owner': layer_owner.id,
            'layer_admin': layer_admin.id,
            'outsider': outsider.id,
            'nominee': nominee.id,
            'nominator': nominator.id,
            'attacker': attacker.id,
        },
    )


def make_nomination(
    *,
    group_acronym: str,
    chair_name: str,
    nominee_email: Optional[str],
    status: str,
    position_key: str = 'chair',
    user_id: Optional[str] = None,
    nominated_by_user_id: Optional[str] = None,
    token: Optional[str] = None,
):
    """Insert a WorkingGroupChair nomination row and commit it."""
    from extensions import db
    from models import WorkingGroupChair

    nomination = WorkingGroupChair(
        id=str(uuid4()),
        group_acronym=group_acronym,
        position_key=position_key,
        chair_name=chair_name,
        user_id=user_id,
        nominee_email=nominee_email,
        nominee_profile_url='https://example.com/cv',
        statement='Isolated test statement.',
        nominated_by_user_id=nominated_by_user_id,
        status=status,
        approved=False,
        set_at=datetime.utcnow(),
        nominee_response_token=token,
    )
    db.session.add(nomination)
    db.session.commit()
    return nomination
