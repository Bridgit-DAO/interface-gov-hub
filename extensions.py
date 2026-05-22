"""
Shared Flask-SQLAlchemy extension. Models import db from here.
Initialized with app in app.py via db.init_app(app).
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, String


class StorageBoolean(TypeDecorator):
    """SQLite stores booleans as TEXT '0'/'1'; stock Boolean treats '0' as truthy."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        from services.utils import coerce_storage_bool
        return '1' if coerce_storage_bool(value) else '0'

    def process_result_value(self, value, dialect):
        from services.utils import coerce_storage_bool
        return coerce_storage_bool(value, default=False)


db = SQLAlchemy()
