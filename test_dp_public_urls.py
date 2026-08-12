"""Tests for DP workgroup invite landing URLs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _FakeInv:
    def __init__(self, token: str, invite_type: str, target_json: str):
        self.token = token
        self.invite_type = invite_type
        self.target_json = target_json


def test_workgroup_invite_landing_url_uses_dp_base():
    from services.dp_public_urls import workgroup_invite_landing_path, workgroup_invite_landing_url

    inv = _FakeInv(
        'tok123',
        'join_workgroup',
        '{"workgroup_slug": "dp8-collaborative-environment"}',
    )
    assert workgroup_invite_landing_path(inv) == (
        '/workgroups/dp8-collaborative-environment?invite=tok123'
    )
    assert workgroup_invite_landing_url(inv).startswith('https://')
    assert 'desirableproperties.org/workgroups/dp8-collaborative-environment?invite=tok123' in (
        workgroup_invite_landing_url(inv)
    )


def test_invitation_landing_url_routes_workgroup_to_dp():
    from services.platform_invitations import invitation_landing_path, invitation_landing_url

    inv = _FakeInv(
        'abc',
        'join_workgroup',
        '{"workgroup_slug": "dp1-trust"}',
    )
    assert invitation_landing_path(inv) == '/workgroups/dp1-trust?invite=abc'
    assert 'desirableproperties.org' in invitation_landing_url(inv)


def test_invitation_landing_url_keeps_gov_hub_for_documents():
    from services.platform_invitations import invitation_landing_path

    inv = _FakeInv(
        'doc1',
        'edit_document',
        '{"draft_ref": "draft-xyz"}',
    )
    assert invitation_landing_path(inv).startswith('/doc/draft/')
    assert 'invite=doc1' in invitation_landing_path(inv)
