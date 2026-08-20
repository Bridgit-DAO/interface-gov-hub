"""ML document and artifact type constants for Gov Hub.

ML-REQ and ML-ADR extend the submission doc_type line (ML-Draft, ML-RFC) and the
GOV-HUB-3 artifact model. See docs/ML-REQ-ML-ADR-SPEC.md.
"""
from __future__ import annotations

# Submission.doc_type values (drive ML-* numbering via get_next_ml_number)
ML_DOC_TYPES = frozenset({'draft', 'rfc', 'req', 'adr'})

ML_DOC_TYPE_LABELS = {
    'draft': 'ML-Draft',
    'rfc': 'ML-RFC',
    'req': 'ML-REQ',
    'adr': 'ML-ADR',
}

# Artifact.artifact_type values (GOV-HUB-3); requirement/adr mirror doc types for linking
ML_ARTIFACT_TYPES = frozenset({'requirement', 'adr'})

CORE_ARTIFACT_TYPES = (
    'proposal',
    'evidence',
    'insight',
    'reflection',
    'translation',
    'implementation',
    'decision',
    'monument',
    'bridge',
    'submission',
    'requirement',
    'adr',
)


def normalize_ml_doc_type(value: str | None, *, default: str = 'draft') -> str:
    """Return a supported doc_type or default."""
    v = (value or '').strip().lower()
    if v in ML_DOC_TYPES:
        return v
    return default


def ml_doc_type_label(doc_type: str) -> str:
    return ML_DOC_TYPE_LABELS.get(doc_type, 'ML-Draft')
