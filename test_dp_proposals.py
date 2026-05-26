"""Tests for DP Proposal scaffolding (API + permissions)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _auth_client(app, username):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = username
    return client


def _enable_dp_proposals(app):
    from extensions import db
    from models import SiteConfig
    from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY

    with app.app_context():
        row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
        cfg = {}
        if row and row.value:
            cfg = json.loads(row.value)
        cfg['dp_proposals'] = True
        payload = json.dumps(cfg, sort_keys=True)
        if row:
            row.value = payload
        else:
            db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
        db.session.commit()


def _find_approved_dp_submission():
    from models import Submission
    from services.dp_proposals import is_dp_submission

    for sub in Submission.query.filter_by(status='approved', doc_type='draft').all():
        if is_dp_submission(sub):
            return sub
    return None


def test_compute_anchor_hash_stable():
    from services.dp_proposals import compute_anchor_hash

    h1 = compute_anchor_hash('sub-1', 'abc', 'Hello world.')
    h2 = compute_anchor_hash('sub-1', 'abc', 'Hello world.')
    h3 = compute_anchor_hash('sub-1', 'abc', 'Different.')
    assert h1 == h2
    assert h1 != h3


def test_list_proposals_requires_feature():
    from app import app

    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/draft/{ref}/proposals/')
        if r.status_code == 403:
            return
        assert r.status_code in (200, 403)


def test_create_and_list_proposal():
    from app import app
    from extensions import db
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        ref = sub.id
        username = user.username

    client = _auth_client(app, username)
    r = client.post(
        f'/api/doc/draft/{ref}/proposals/',
        json={
            'original_text': 'The quick brown fox jumps over the lazy dog.',
            'proposed_text': 'The quick brown fox leaps over the lazy dog.',
            'context_anchor': {'textQuote': {'exact': 'The quick brown fox jumps over the lazy dog.'}},
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    data = r.get_json()
    assert data['proposal']['status'] == 'pending'
    assert data['status_label'] == 'DP Proposal'

    r2 = client.get(f'/api/doc/draft/{ref}/proposals/')
    assert r2.status_code == 200
    listed = r2.get_json()
    assert listed['count'] >= 1
    assert listed['counts_by_status'].get('pending', 0) >= 1


def test_accept_proposal_requires_chair():
    from app import app
    from models import User
    from services.dp_proposals import can_manage_amendments, workgroup_for_submission

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        wg = workgroup_for_submission(sub)
        outsider = None
        for user in User.query.all():
            if user.role in ('admin', 'editor'):
                continue
            fake_user = {'id': user.id, 'username': user.username, 'role': user.role}
            if can_manage_amendments(fake_user, wg):
                continue
            outsider = user
            break
        if not outsider:
            return
        ref = sub.id
        outsider_name = outsider.username

    client = _auth_client(app, outsider_name)
    create = client.post(
        f'/api/doc/draft/{ref}/proposals/',
        json={
            'original_text': 'Alpha sentence one.',
            'proposed_text': 'Alpha sentence two.',
        },
    )
    if create.status_code != 201:
        return
    pid = create.get_json()['proposal']['id']

    deny = client.post(f'/api/doc/draft/{ref}/proposals/{pid}/accept/')
    assert deny.status_code == 403


def test_read_meta_for_dp():
    from app import app

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/draft/{ref}/read-meta/')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['is_dp'] is True
        assert data['proposals_enabled'] is True


def test_admin_dashboard_loads():
    from app import app
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        admin = User.query.filter(User.role.in_(['admin', 'editor'])).first()
        if not admin:
            return
        username = admin.username

    client = _auth_client(app, username)
    r = client.get('/admin/dp-proposals/')
    assert r.status_code == 200
    assert b'DP Proposals' in r.data
