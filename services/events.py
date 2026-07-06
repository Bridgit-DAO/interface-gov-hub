"""Event emission service. Append-only EventLog."""
import json
from datetime import datetime, timedelta

from extensions import db
from models import EventLog


def emit_event(event_type, actor_type='user', actor_id=None, subject_type=None, subject_id=None,
               layer_id=None, payload=None):
    """Append an event to the EventLog. Flushes so evt.id is available. Call before db.session.commit().

    Skips emission if a row with the same (event_type, subject_type, subject_id, payload_json)
    already exists in this layer within the last 60s. Returns the existing EventLog row in that case.

    Returns the EventLog row or None on failure.
    """
    try:
        try:
            from services.event_registry import is_registered_event_type
            if not is_registered_event_type(event_type):
                try:
                    from flask import current_app
                    current_app.logger.debug(
                        "[EventLog] Unregistered event_type %r – add to services/event_registry.py", event_type
                    )
                except RuntimeError:
                    pass
        except Exception:
            pass
        payload_json = json.dumps(payload) if payload is not None else None
        # Idempotency: skip emit if an identical row was already logged in this layer
        # within the last 60s. Only applies when subject_id and payload are both set —
        # events that intentionally have NULL subject_id (e.g., some member_joined rows)
        # are left untouched.
        if subject_id is not None and payload_json is not None and layer_id is not None:
            window_start = datetime.utcnow() - timedelta(seconds=60)
            existing = (
                EventLog.query.filter_by(
                    event_type=event_type,
                    subject_type=subject_type,
                    subject_id=str(subject_id),
                    layer_id=layer_id,
                    payload_json=payload_json,
                )
                .filter(EventLog.created_at >= window_start)
                .first()
            )
            if existing is not None:
                return existing
        evt = EventLog(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=str(actor_id) if actor_id is not None else None,
            subject_type=subject_type,
            subject_id=str(subject_id) if subject_id is not None else None,
            layer_id=layer_id,
            payload_json=payload_json
        )
        db.session.add(evt)
        db.session.flush()
        return evt
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(f"[EventLog] Failed to emit {event_type}: {e}")
        except RuntimeError:
            pass
        return None
