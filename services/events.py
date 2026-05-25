"""Event emission service. Append-only EventLog."""
import json

from extensions import db
from models import EventLog


def emit_event(event_type, actor_type='user', actor_id=None, subject_type=None, subject_id=None,
               layer_id=None, payload=None):
    """Append an event to the EventLog. Flushes so evt.id is available. Call before db.session.commit().

    Returns the EventLog row or None on failure.
    """
    try:
        try:
            from services.event_registry import is_registered_event_type
            if not is_registered_event_type(event_type):
                try:
                    from flask import current_app
                    current_app.logger.debug(
                        "[EventLog] Unregistered event_type %r — add to services/event_registry.py", event_type
                    )
                except RuntimeError:
                    pass
        except Exception:
            pass
        payload_json = json.dumps(payload) if payload is not None else None
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
