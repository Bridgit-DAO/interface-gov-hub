"""Tests for Metaweb Book action-status observer API (Phase 6a)."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_action_status_requires_secret():
    from app import app

    with app.test_client() as client:
        res = client.post('/api/metaweb/action-status', json={'checks': []})
        assert res.status_code == 401


def test_action_status_layer_join_complete():
    from app import app
    from extensions import db
    from models import Layer, LayerMember, User
    from services.metaweb_action_status import evaluate_action_checks

    secret = 'test-metaweb-secret-phase6a'
    os.environ['METAWEB_GOVHUB_INTERNAL_SECRET'] = secret

    with app.app_context():
        user = User.query.first()
        layer = Layer.query.first()
        if not user or not layer:
            pytest.skip('Need seeded user and layer')

        LayerMember.query.filter_by(layer_id=layer.id, user_id=user.id).delete()
        db.session.add(
            LayerMember(
                id=str(uuid4()),
                layer_id=layer.id,
                user_id=user.id,
                status='active',
                role='member',
                joined_at=datetime.utcnow(),
            )
        )
        db.session.commit()

        results = evaluate_action_checks(
            user,
            [
                {
                    'key': 'bb_layer',
                    'actionKind': 'layer_join',
                    'layerSlug': layer.slug,
                }
            ],
        )
        assert results['bb_layer']['complete'] is True
        assert results['bb_layer']['evidence']['actionKind'] == 'layer_join'

        with app.test_client() as client:
            res = client.post(
                '/api/metaweb/action-status',
                headers={'X-Metaweb-Govhub-Secret': secret},
                json={
                    'govhubUserId': str(user.id),
                    'checks': [
                        {
                            'key': 'bb_layer',
                            'actionKind': 'layer_join',
                            'layerSlug': layer.slug,
                        }
                    ],
                },
            )
            assert res.status_code == 200
            payload = res.get_json()
            assert payload['ok'] is True
            assert payload['results']['bb_layer']['complete'] is True


def test_action_status_draft_submit_submitted_mode():
    from app import app
    from extensions import db
    from models import Layer, Submission, User
    from services.metaweb_action_status import evaluate_action_checks

    with app.app_context():
        user = User.query.first()
        layer = Layer.query.first()
        if not user or not layer:
            pytest.skip('Need seeded user and layer')

        draft_name = f'test-{uuid4().hex[:8]}'
        sub = Submission(
            id=str(uuid4()),
            public_id=str(uuid4()),
            draft_name=draft_name,
            title='Phase 6a draft test',
            authors=['Tester'],
            group='',
            layer_id=layer.id,
            status='submitted',
            submitted_by=user.displayName or user.username,
            submitter_user_id=user.id,
        )
        db.session.add(sub)
        db.session.commit()

        results = evaluate_action_checks(
            user,
            [
                {
                    'key': 'bb_draft',
                    'actionKind': 'draft_submit',
                    'layerSlug': layer.slug,
                    'draftCompletion': 'submitted',
                }
            ],
        )
        assert results['bb_draft']['complete'] is True
        assert results['bb_draft']['evidence']['draftName'] == draft_name

        sub.status = 'approved'
        db.session.commit()
        results_approved = evaluate_action_checks(
            user,
            [
                {
                    'key': 'bb_draft',
                    'actionKind': 'draft_submit',
                    'layerSlug': layer.slug,
                    'draftCompletion': 'submitted',
                }
            ],
        )
        assert results_approved['bb_draft']['complete'] is False

        results_mode_approved = evaluate_action_checks(
            user,
            [
                {
                    'key': 'bb_draft',
                    'actionKind': 'draft_submit',
                    'layerSlug': layer.slug,
                    'draftCompletion': 'approved',
                }
            ],
        )
        assert results_mode_approved['bb_draft']['complete'] is True

        db.session.delete(sub)
        db.session.commit()


def test_metaweb_catalog_requires_secret():
    from app import app

    with app.test_client() as client:
        res = client.get('/api/metaweb/catalog?kind=layers')
        assert res.status_code == 401


def test_metaweb_catalog_search_layers():
    from app import app
    from models import Layer

    secret = 'test-metaweb-secret-catalog'
    os.environ['METAWEB_GOVHUB_INTERNAL_SECRET'] = secret

    with app.app_context():
        layer = Layer.query.filter(
            Layer.approval_status == 'approved',
            Layer.display_status == 'active',
        ).first()
        if not layer:
            pytest.skip('Need active approved layer')

        with app.test_client() as client:
            res = client.get(
                f'/api/metaweb/catalog?kind=layers&q={layer.slug[:4]}&limit=5',
                headers={'X-Metaweb-Govhub-Secret': secret},
            )
            assert res.status_code == 200
            payload = res.get_json()
            assert payload['ok'] is True
            ids = {item['id'] for item in payload['items']}
            assert layer.id in ids


def test_action_status_workgroup_join_any_of_acronyms():
    from app import app
    from extensions import db
    from models import User, WorkingGroupMember, Workgroup
    from services.metaweb_action_status import evaluate_action_checks

    with app.app_context():
        user = User.query.first()
        wg = Workgroup.query.filter(
            Workgroup.approval_status == 'approved',
            Workgroup.status == 'active',
            Workgroup.acronym.isnot(None),
        ).first()
        if not user or not wg or not wg.acronym:
            pytest.skip('Need seeded user and approved workgroup')

        WorkingGroupMember.query.filter_by(
            group_acronym=wg.acronym,
            user_id=user.id,
        ).delete()
        db.session.add(
            WorkingGroupMember(
                id=str(uuid4()),
                group_acronym=wg.acronym,
                user_id=user.id,
                joined_at=datetime.utcnow(),
            )
        )
        db.session.commit()

        results = evaluate_action_checks(
            user,
            [
                {
                    'key': 'bb_wg_multi',
                    'actionKind': 'workgroup_join',
                    'groupAcronyms': ['missing-acronym', wg.acronym],
                    'workgroups': [
                        {'workgroupId': '00000000-0000-0000-0000-000000000099', 'groupAcronym': 'also-missing'},
                        {'workgroupId': wg.id, 'label': wg.name},
                    ],
                }
            ],
        )
        assert results['bb_wg_multi']['complete'] is True
        assert results['bb_wg_multi']['evidence']['groupAcronym'] == wg.acronym

        WorkingGroupMember.query.filter_by(
            group_acronym=wg.acronym,
            user_id=user.id,
        ).delete()
        db.session.commit()
