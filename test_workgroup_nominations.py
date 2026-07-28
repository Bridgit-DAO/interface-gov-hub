"""Tests for workgroup nomination self-detection."""
from services.workgroup_positions import detect_self_nomination, initial_nomination_status


def test_detect_self_nomination_by_user_id_string_match():
    uid = '57e7c23e-29ec-423a-baee-51ddf34a8174'
    assert detect_self_nomination(
        nominee_user_id=uid,
        nominee_email='other@example.com',
        current_user_id=uid,
        current_user_email='self@example.com',
    ) is True


def test_detect_self_nomination_int_str_user_id():
    assert detect_self_nomination(
        nominee_user_id='6',
        nominee_email=None,
        current_user_id=6,
        current_user_email=None,
    ) is True


def test_detect_self_nomination_other_person():
    assert detect_self_nomination(
        nominee_user_id='3ed85cf6-619c-4964-b9a4-24a4bb0656e4',
        nominee_email='deefrewert@gmail.com',
        current_user_id='57e7c23e-29ec-423a-baee-51ddf34a8174',
        current_user_email='daveed@bridgit.io',
    ) is False


def test_detect_self_nomination_by_email_when_no_user_id():
    assert detect_self_nomination(
        nominee_user_id=None,
        nominee_email='Self@Example.com',
        current_user_id=None,
        current_user_email='self@example.com',
    ) is True


def test_initial_nomination_status():
    assert initial_nomination_status(True) == 'nominee_accepted'
    assert initial_nomination_status(False) == 'pending_nominee'
