"""SQLAlchemy types that tolerate legacy SQLite TEXT booleans ('0'/'1')."""
from sqlalchemy import Integer
from sqlalchemy.types import TypeDecorator


class SafeBoolean(TypeDecorator):
    """Store 0/1; read bool without treating string '0' as true."""

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return 0
        return 1 if self._coerce_to_bool(value) else 0

    def process_result_value(self, value, dialect):
        return self._coerce_to_bool(value)

    @staticmethod
    def _coerce_to_bool(value) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ('', '0', 'false', 'no', 'off'):
                return False
            if s in ('1', 'true', 'yes', 'on'):
                return True
            return False
        return bool(value)


def comment_is_deleted(value) -> bool:
    """Normalize is_deleted from ORM row, dict, or raw SQLite value."""
    return SafeBoolean._coerce_to_bool(value)
