#!/usr/bin/env python3
"""Tests for the per-layer two-letter draft prefix system.

Covers:
- format validation (server-side: ^[A-Z]{2}$)
- global uniqueness (409 on conflict)
- default uniqueness constraint within a layer
- deletion blocked while prefix is the layer default
- deletion blocked on the last remaining prefix
- set_default transitions is_default across other prefixes
- API: list / add / patch / delete / default + auth gates
"""
import os
import sys
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Pure unit tests (no DB)
# ---------------------------------------------------------------------------

def test_format_validator():
    from services.layer_prefixes import is_valid_prefix_format

    assert is_valid_prefix_format('ML') is True
    assert is_valid_prefix_format('ml') is True
    assert is_valid_prefix_format('  ML  ') is True
    assert is_valid_prefix_format('CL') is True

    # Invalid cases
    for bad in ['M', 'ML1', 'M1', '12', 'm-', '-', '', None]:
        assert is_valid_prefix_format(bad) is False, (
            f'expected {bad!r} to be invalid'
        )


# ---------------------------------------------------------------------------
# Service-level integration tests (in-memory DB via app fixture)
# ---------------------------------------------------------------------------

def _pick_fresh_two_letter() -> str:
    """Pick a 2-letter code that no layer_prefix row currently uses.

    Random tags generated inline can collide with prefixes from prior runs
    against the same dev DB; retry against the existing data until free.
    """
    import random
    from models import LayerPrefix
    for _ in range(400):
        tag = ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(2))
        if not LayerPrefix.query.filter_by(prefix=tag).first():
            return tag
    raise RuntimeError('Could not find a free 2-letter prefix after 400 tries')


def _bootstrap_layer_with_admin(app, suffix):
    from extensions import db
    from models import Layer, User, LayerAdmin
    from werkzeug.security import generate_password_hash

    with app.app_context():
        # Ensure the layer_prefix table exists for this dev DB and that we
        # have a default prefix so list/get_default_prefix() always works.
        from migrations import migrate_layer_prefix_v1
        migrate_layer_prefix_v1(app)
        layer_id = str(uuid4())
        # Use a deterministic owner_id + a deterministic username, so
        # repeated runs against the same dev DB don't accumulate stale
        # duplicate users (which would make `get_current_user()` resolve
        # to a user that no longer owns the fresh layer).
        uname = f'prefix_admin_{suffix}'
        existing_user = User.query.filter_by(username=uname).first()
        if existing_user is not None:
            owner_id = existing_user.id
        else:
            owner_id = str(uuid4())
            owner = User(
                id=owner_id,
                public_id=str(uuid4()),
                username=uname,
                handle=uname,
                email=f'{uname}@example.test',
                web3authVerifierId=f'web3auth-prefix-{suffix}',
                password_hash=generate_password_hash('NotARealPassword!'),
                role='user',
            )
            db.session.add(owner)
            db.session.flush()
        layer = Layer(
            id=layer_id,
            public_id=str(uuid4()),
            slug=f'prefix-test-layer-{suffix}-{layer_id[:8]}',
            name=f'Prefix Test Layer {suffix}',
            initiator_id=owner_id,
            approval_status='approved',
        )
        db.session.add(layer)
        db.session.flush()
        admin_link = LayerAdmin(layer_id=layer.id, user_id=owner_id)
        db.session.add(admin_link)
        db.session.flush()
        # Seed the layer with a unique default prefix so the "delete last"
        # path works without state from previous test runs colliding on the
        # global UNIQUE(prefix) constraint.
        from uuid import uuid4 as _uuid
        from models import LayerPrefix
        existing = LayerPrefix.query.filter_by(layer_id=layer.id).first()
        if not existing:
            # Derive a deterministic 2-letter placeholder from layer.id so
            # each new layer gets a unique prefix that survives re-runs.
            digits = ''.join(c for c in layer.id if c.isalnum())
            h1 = sum(ord(c) for c in digits)
            h2 = sum(ord(c) for c in reversed(digits))
            placeholder = '{}{}'.format(
                chr(ord('A') + (h1 % 26)),
                chr(ord('A') + (h2 % 26)),
            )
            # Disambiguate in the (rare) case the hash matches another layer.
            while LayerPrefix.query.filter_by(prefix=placeholder).first():
                h2 = (h2 + 1) % 26
                placeholder = '{}{}'.format(
                    chr(ord('A') + (h1 % 26)),
                    chr(ord('A') + (h2 % 26)),
                )
            db.session.add(LayerPrefix(
                id=str(_uuid()),
                layer_id=layer.id,
                prefix=placeholder,
                is_default=True,
            ))
            db.session.commit()
        return {'layer_id': layer.id, 'user_id': owner_id,
                'username': uname}


def test_add_prefix_happy_path(app):
    from services.layer_prefixes import add_prefix, list_prefixes, get_default_prefix
    import random

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'happy')
        # Pick a fresh 2-letter code so this test doesn't collide with prior
        # test runs against the same DB.
        tag = _pick_fresh_two_letter()
        body, status = add_prefix(ids['layer_id'], tag, ids['user_id'])
        assert status == 201, body
        assert body['prefix']['prefix'] == tag
        rows = list_prefixes(ids['layer_id'])
        assert any(r.prefix == tag for r in rows)


def test_add_prefix_normalizes_lowercase(app):
    from services.layer_prefixes import add_prefix

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'lower')
        # Pick the lowercase spelling of a fresh uppercase tag.
        fresh_upper = _pick_fresh_two_letter()
        raw = fresh_upper.lower()
        body, status = add_prefix(ids['layer_id'], raw, ids['user_id'])
        assert status == 201, body
        assert body['prefix']['prefix'] == fresh_upper


def test_add_prefix_rejects_bad_format(app):
    from services.layer_prefixes import add_prefix

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'badtwo')
        for bad in ['M', 'ML1', 'm1', '12', '', '  ']:
            body, status = add_prefix(ids['layer_id'], bad, ids['user_id'])
            assert status == 400, (bad, body, status)
            assert body['code'] == 'invalid_format'


def test_global_uniqueness(app):
    """Adding the same prefix from a second layer returns 409."""
    from services.layer_prefixes import add_prefix
    import random

    with app.app_context():
        a = _bootstrap_layer_with_admin(app, 'unique1')
        b = _bootstrap_layer_with_admin(app, 'unique2')
        tag = _pick_fresh_two_letter()
        body, status = add_prefix(a['layer_id'], tag, a['user_id'])
        assert status == 201, body
        # Second layer tries same prefix
        body2, status2 = add_prefix(b['layer_id'], tag, b['user_id'])
        assert status2 == 409, (body2, status2)
        assert body2['code'] == 'prefix_taken'


def test_update_prefix_rename_recheck_uniqueness(app):
    from services.layer_prefixes import add_prefix, update_prefix
    import random

    with app.app_context():
        a = _bootstrap_layer_with_admin(app, 'rename1')
        b = _bootstrap_layer_with_admin(app, 'rename2')
        tag_a = _pick_fresh_two_letter()
        tag_b = _pick_fresh_two_letter()
        add_prefix(a['layer_id'], tag_a, a['user_id'])
        body, status = add_prefix(b['layer_id'], tag_b, b['user_id'])
        assert status == 201, body
        # Try to rename B's prefix to A's prefix — should fail with 409.
        body2, status2 = update_prefix(
            b['layer_id'], body['prefix']['id'], tag_a,
        )
        assert status2 == 409, (body2, status2)


def test_delete_default_blocked(app):
    from services.layer_prefixes import (
        add_prefix, set_default_prefix, delete_prefix,
    )
    import random

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'deldefault')
        tag = _pick_fresh_two_letter()
        added, _ = add_prefix(ids['layer_id'], tag, ids['user_id'])
        set_default_prefix(ids['layer_id'], added['prefix']['id'])
        body, status = delete_prefix(ids['layer_id'], added['prefix']['id'])
        assert status == 400, body
        assert body['code'] == 'cannot_delete_default'


def test_delete_last_prefix_blocked(app):
    from services.layer_prefixes import (
        add_prefix, set_default_prefix, delete_prefix, list_prefixes,
    )
    import random

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'lastone')
        # Layer now ships with exactly one default prefix. Attempting to
        # delete it must be refused (every layer must keep >= 1 prefix).
        rows = list_prefixes(ids['layer_id'])
        assert len(rows) == 1, [(r.prefix, bool(r.is_default)) for r in rows]
        only = rows[0]
        body, status = delete_prefix(ids['layer_id'], only.id)
        assert status == 400, body
        assert body['code'] in {'cannot_delete_default', 'last_prefix'}, body


def test_set_default_clears_others(app):
    from services.layer_prefixes import (
        add_prefix, set_default_prefix, list_prefixes,
    )

    with app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'switchdefault')
        tag_b = _pick_fresh_two_letter()
        while True:
            tag_c = _pick_fresh_two_letter()
            if tag_c != tag_b:
                break
        first, status_b = add_prefix(ids['layer_id'], tag_b, ids['user_id'])
        assert status_b == 201, first
        second, status_c = add_prefix(ids['layer_id'], tag_c, ids['user_id'])
        assert status_c == 201, second
        # Promote second to default
        set_default_prefix(ids['layer_id'], second['prefix']['id'])
        rows = list_prefixes(ids['layer_id'])
        is_default = {r.prefix: bool(r.is_default) for r in rows}
        assert is_default[tag_c] is True
        assert is_default[tag_b] is False
        # Promotion is one-way — re-set first to default
        set_default_prefix(ids['layer_id'], first['prefix']['id'])
        rows = list_prefixes(ids['layer_id'])
        is_default = {r.prefix: bool(r.is_default) for r in rows}
        assert is_default[tag_b] is True
        assert is_default[tag_c] is False


# ---------------------------------------------------------------------------
# API tests using Flask test client + session-authenticated user
# ---------------------------------------------------------------------------

def _sign_in(c, username):
    with c.session_transaction() as sess:
        sess['user'] = username


def test_api_anonymous_list_returns_empty_or_published():
    """Anonymous listing of a layer's prefixes still works for any GET."""
    from app import app
    with app.test_client() as c:
        r = c.get('/api/layers/nonexistent-id/prefixes/')
        # 404 is acceptable since the layer doesn't exist; we only assert we
        # didn't 500/401 (anonymous reads do not require auth).
        assert r.status_code in (200, 404)


def test_api_add_requires_admin(app):
    """Non-admin POST should 403, even authenticated."""
    from models import Layer, LayerAdmin, User
    from werkzeug.security import generate_password_hash
    from extensions import db

    with app.test_client() as c, app.app_context():
        # Create a layer owned by someone else
        suffix = 'notadmin'
        owner_id = str(uuid4())
        layer = Layer(
            id=str(uuid4()),
            public_id=str(uuid4()),
            slug=f'api-guard-layer-{suffix}',
            name=f'API guard layer {suffix}',
            initiator_id=owner_id,
            approval_status='approved',
        )
        owner = User(
            id=owner_id,
            public_id=str(uuid4()),
            username=f'guard_owner_{suffix}',
            handle=f'guard_owner_{suffix}',
            email=f'guard_owner_{suffix}@example.test',
            web3authVerifierId=f'web3auth-guard-{suffix}',
            password_hash=generate_password_hash('not-real'),
            role='user',
        )
        db.session.add(layer)
        db.session.add(owner)
        db.session.commit()
        layer_id = layer.id
        owner_username = owner.username

        # Find a different user that exists in DB and try to add a prefix.
        other = User.query.filter(User.username != owner_username).first()
        if not other:
            return  # nothing to test against
        _sign_in(c, other.username)
        csrf = 'csrf-test-token-' + ('x' * 24)
        with c.session_transaction() as sess:
            sess['_csrf_token'] = csrf
        r = c.post(
            f'/api/layers/{layer_id}/prefixes/',
            json={'prefix': 'XX'},
            headers={'X-CSRFToken': csrf},
        )
        assert r.status_code == 403, r.data


def test_api_full_round_trip(app):
    from models import User
    import random

    with app.test_client() as c, app.app_context():
        ids = _bootstrap_layer_with_admin(app, 'roundtrip')

        # Owner of this layer must exist
        admin_user = User.query.get(ids['user_id'])
        if not admin_user:
            return
        tag = _pick_fresh_two_letter()

        # Sign in AND prime a CSRF token in the same session transaction so
        # the middleware accepts our X-CSRFToken header on subsequent POSTs.
        csrf = 'csrf-test-token-' + ('x' * 24)
        with c.session_transaction() as sess:
            sess['user'] = admin_user.username
            sess['_csrf_token'] = csrf

        post_headers = {'X-CSRFToken': csrf}

        r = c.post(
            f'/api/layers/{ids["layer_id"]}/prefixes/',
            json={'prefix': tag},
            headers=post_headers,
        )
        assert r.status_code == 201, r.data
        prefix_id = r.get_json()['prefix']['id']

        # Promote to default
        r2 = c.post(
            f'/api/layers/{ids["layer_id"]}/prefixes/{prefix_id}/default/',
            json={},
            headers=post_headers,
        )
        assert r2.status_code == 200, r2.data
        assert r2.get_json()['prefix']['is_default'] is True

        # List
        r3 = c.get(f'/api/layers/{ids["layer_id"]}/prefixes/')
        assert r3.status_code == 200
        items = r3.get_json()['prefixes']
        prefixes = {p['prefix'] for p in items}
        assert tag in prefixes

        # Try default delete (should 400)
        r4 = c.delete(
            f'/api/layers/{ids["layer_id"]}/prefixes/{prefix_id}/',
            headers=post_headers,
        )
        assert r4.status_code == 400
        assert r4.get_json()['code'] == 'cannot_delete_default'


if __name__ == '__main__':
    # Wipe test-layer rows left over from prior runs so the global
    # UNIQUE(prefix) constraint does not collide with these new picks.
    from app import app as flask_app
    from extensions import db
    from models import Layer, LayerPrefix, LayerAdmin
    with flask_app.app_context():
        try:
            test_layer_ids = [
                L.id for L in Layer.query.all()
                if (L.slug or '').startswith('prefix-test-layer-')
            ]
            if test_layer_ids:
                LayerPrefix.query.filter(
                    LayerPrefix.layer_id.in_(test_layer_ids)
                ).delete(synchronize_session=False)
                LayerAdmin.query.filter(
                    LayerAdmin.layer_id.in_(test_layer_ids)
                ).delete(synchronize_session=False)
                Layer.query.filter(Layer.id.in_(test_layer_ids)).delete(
                    synchronize_session=False
                )
                db.session.commit()
        except Exception as cleanup_err:  # noqa
            print(f'(cleanup warning: {cleanup_err})')
            db.session.rollback()

    failures = []
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                if name == 'test_format_validator':
                    fn()  # pure unit test, no fixture
                elif name == 'test_api_anonymous_list_returns_empty_or_published':
                    fn()  # uses its own test client
                else:
                    fn(flask_app)
                print(f'  ✓ {name}')
            except Exception as e:  # noqa
                failures.append((name, str(e)))
                print(f'  ✗ {name}: {e}')
    if failures:
        print(f'\n{len(failures)} test(s) failed:')
        for n, msg in failures:
            print(f'  {n}: {msg}')
        sys.exit(1)
    print('\n✅ all layer-prefix tests passed')
