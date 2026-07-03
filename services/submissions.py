"""Submission lookup helpers: get_submission_by_ref, get_next_ml_number, add_to_document_history, generate_draft_name."""
import re
from datetime import datetime

from extensions import db
from models import Submission

# In-memory document history (used by add_to_document_history)
DOCUMENT_HISTORY = {}


def generate_draft_name(title, authors):
    """Generate a draft name from title and authors"""
    first_author = authors[0] if authors else "unknown"
    author_last = first_author.split()[-1].lower() if first_author else "unknown"

    title_slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    title_slug = re.sub(r'\s+', '-', title_slug.strip())
    title_slug = title_slug[:30]  # Limit length

    return f"draft-{author_last}-{title_slug}"


def can_edit_submission_metadata(user, submission) -> bool:
    """Submitter, layer admin, or site staff may update draft metadata."""
    if not user or not submission:
        return False
    if user.get('role') in ('admin', 'editor'):
        return True
    uname = (user.get('name') or '').strip()
    if uname and uname == (submission.submitted_by or '').strip():
        return True
    if submission.layer_id:
        from models import Layer
        from services.coordination import is_layer_admin
        layer = Layer.query.get(submission.layer_id)
        if layer and is_layer_admin(layer, user):
            return True
    return False


def get_submission_by_ref(ref):
    """Look up submission by id (UUID), draft_name, ml_number, or public_id."""
    if not ref:
        return None
    s = Submission.query.filter_by(id=ref).first()
    if s:
        return s
    s = Submission.query.filter_by(draft_name=ref).first()
    if s:
        return s
    s = Submission.query.filter_by(ml_number=ref).first()
    if s:
        return s
    s = Submission.query.filter_by(public_id=ref).first()
    return s


def add_to_document_history(draft_name, action, user, details=""):
    """Add an entry to document history."""
    if draft_name not in DOCUMENT_HISTORY:
        DOCUMENT_HISTORY[draft_name] = []
    entry = {
        'action': action,
        'user': user,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'details': details
    }
    DOCUMENT_HISTORY[draft_name].insert(0, entry)


def get_next_ml_number(doc_type='draft', layer_prefix='ML'):
    """Get the next ML number (ML-Draft-001, ML-RFC-001, or CL-Draft-001 if a layer prefix is supplied)."""
    # Fall back to the legacy 'ML' prefix when no per-layer prefix is provided
    # or when the supplied value is empty/None. The 2-letter prefix token
    # replaces the literal 'ML' in the generated identifier.
    prefix_token = (layer_prefix or 'ML').strip().upper() or 'ML'
    # Normalize the doc-type segment to the canonical mixed-case label so
    # 'rfc' -> 'RFC' (not 'Rfc') while 'draft' stays 'Draft'. Existing data
    # uses 'ML-Draft-NNN' (capital D), so we keep 'Draft' title-cased.
    raw_kind = (doc_type or 'draft').strip().lower()
    kind = 'Draft' if raw_kind == 'draft' else raw_kind.upper()
    prefix = f"{prefix_token}-{kind}-"
    max_ml = db.session.query(db.func.max(Submission.ml_number)).filter(
        Submission.ml_number.like(f"{prefix}%"),
        Submission.status.in_(['submitted', 'approved', 'published']),
    ).scalar()
    if max_ml:
        try:
            current_num = int(max_ml.split('-')[-1])
            next_num = current_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    if next_num < 1000:
        return f"{prefix}{next_num:03d}"
    return f"{prefix}{next_num:04d}"
