"""Artifact services: get_artifact_by_ref, _ensure_artifact_for_submission, Submission before_insert listener."""
from sqlalchemy import event, or_, func

from flask import current_app

from extensions import db
from models import Artifact, Submission
from services.events import emit_event


def _register_submission_listener():
    """Register SQLAlchemy event listener for auto-creating Artifact on Submission insert."""

    @event.listens_for(Submission, 'before_insert')
    def _on_submission_before_insert(mapper, connection, target):
        """Auto-create Artifact for new Submissions (GOV-HUB-3)."""
        if target.artifact_id:
            return
        try:
            _ensure_artifact_for_submission(target)
        except Exception as e:
            try:
                current_app.logger.warning(f"[Artifact] Failed to create artifact for submission {target.id}: {e}")
            except RuntimeError:
                print(f"[Artifact] Failed to create artifact for submission {target.id}: {e}")


def _ensure_artifact_for_submission(submission):
    """Create Artifact for a new Submission (GOV-HUB-3). Idempotent if artifact_id already set."""
    if submission.artifact_id:
        return
    art = Artifact(
        layer_id=submission.layer_id,
        creator_user_id=None,
        artifact_type='submission',
        title=submission.title or f"Draft {submission.id}",
        summary=submission.abstract,
        uri=None,
        status=submission.status or 'submitted',
        created_at=submission.submitted_at,
    )
    db.session.add(art)
    db.session.flush()
    submission.artifact_id = art.id
    emit_event('artifact_created', subject_type='artifact', subject_id=art.id,
               layer_id=art.layer_id, payload={'submission_id': submission.id, 'artifact_type': 'submission'})


def get_artifact_by_ref(layer_id, ref):
    """Resolve artifact by id, public_id, or short public_ref (e.g. ed3f6ea9io)."""
    if not ref:
        return None
    a = Artifact.query.filter_by(layer_id=layer_id).filter(
        (Artifact.id == ref) | (Artifact.public_id == ref)
    ).first()
    if a:
        return a
    if ref.endswith('io') and len(ref) == 10:
        prefix = ref[:8].lower()
        a = Artifact.query.filter_by(layer_id=layer_id).filter(
            or_(
                func.lower(func.substr(func.replace(Artifact.public_id, '-', ''), 1, 8)) == prefix,
                func.lower(func.substr(func.replace(Artifact.id, '-', ''), 1, 8)) == prefix
            )
        ).first()
        return a
    return None


_register_submission_listener()
