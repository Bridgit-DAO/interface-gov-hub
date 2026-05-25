"""Waitlist boolean coercion from SQLite TEXT storage."""
import pytest

from app import app
from extensions import db
from models import Layer, Waitlist
from services.utils import coerce_storage_bool


def test_coerce_storage_bool_string_zero():
    assert coerce_storage_bool('0') is False
    assert coerce_storage_bool('1') is True
    assert coerce_storage_bool(0) is False
    assert coerce_storage_bool(1) is True


def test_waitlist_to_dict_archived_not_true_when_db_zero():
    with app.app_context():
        layer = Layer.query.filter_by(slug='canopi').first()
        if not layer:
            pytest.skip('canopi layer missing')
        wl = Waitlist.query.filter_by(layer_id=layer.id).first()
        if not wl:
            pytest.skip('no waitlists on canopi')
        d = wl.to_dict()
        assert d['archived'] is False
        assert d['active'] is True
        assert d['closed'] is False
        assert d['started'] is True
