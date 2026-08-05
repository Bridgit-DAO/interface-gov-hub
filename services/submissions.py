"""Submission lookup helpers: get_submission_by_ref, get_next_ml_number, add_to_document_history, generate_draft_name."""
import re
from datetime import datetime

from sqlalchemy import or_

from extensions import db
from models import Submission

APPROVED_STATUSES = ('approved', 'published')


def submission_is_revision(submission) -> bool:
    """
    True when a row is a revision of another submission.

    The ``is_revision`` column cannot be trusted in Python: deployed SQLite rows
    hold TEXT '0'/'1', and SQLAlchemy's Boolean turns the string '0' into True.
    SQL comparisons still work (numeric affinity), so queries keep using the
    column, but attribute reads go through ``parent_draft_name``, which every
    revision sets.
    """
    if not submission:
        return False
    return bool((getattr(submission, 'parent_draft_name', '') or '').strip())


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


def family_parent_refs(submission) -> list:
    """Refs that revisions of ``submission``'s family point at via parent_draft_name."""
    if not submission:
        return []
    parent_ref = (getattr(submission, 'parent_draft_name', '') or '').strip()
    if submission_is_revision(submission) and parent_ref:
        parent = Submission.query.filter(
            or_(Submission.id == parent_ref, Submission.draft_name == parent_ref)
        ).first()
    else:
        parent = submission
    refs = {parent_ref} if parent_ref else set()
    if parent:
        refs.add(parent.id)
        if parent.draft_name:
            refs.add(parent.draft_name)
    return [r for r in refs if r]


def _revision_sort_key(row):
    raw = (getattr(row, 'revision_number', '') or '').strip()
    try:
        number = int(raw)
    except ValueError:
        number = -1
    return (number, row.submitted_at or datetime.min)


def latest_approved_revision(submission):
    """Newest approved revision in ``submission``'s family, or None when there is none."""
    refs = family_parent_refs(submission)
    if not refs:
        return None
    rows = Submission.query.filter(
        Submission.parent_draft_name.in_(refs),
        Submission.is_revision == True,  # noqa: E712 - SQLAlchemy column comparison
        Submission.status.in_(APPROVED_STATUSES),
    ).all()
    if not rows:
        return None
    return max(rows, key=_revision_sort_key)


def ref_addresses_document_family(ref, submission) -> bool:
    """
    True when ``ref`` names the document family rather than one stored row.

    An ML number is the stable public identifier for a document and is shared by
    every revision, so it means "the document". Ids, draft names and public ids
    each belong to exactly one row and mean "this revision".
    """
    value = (ref or '').strip()
    if not value or not submission:
        return False
    row_refs = {
        (getattr(submission, 'id', '') or '').strip(),
        (getattr(submission, 'draft_name', '') or '').strip(),
        (getattr(submission, 'public_id', '') or '').strip(),
    }
    if value in row_refs:
        return False
    return value == (getattr(submission, 'ml_number', '') or '').strip()


def revision_display_label(submission) -> str:
    """Human label for one revision row, e.g. 'Revision 02' or 'Revision 00 (original)'."""
    if not submission:
        return ''
    if submission_is_revision(submission):
        number = (getattr(submission, 'revision_number', '') or '').strip() or '01'
        return f'Revision {number}'
    return 'Revision 00 (original)'


def rev_number_for_display(submission) -> str:
    """Two-digit revision for record metadata, e.g. '04' or '00' for the original."""
    served = served_submission_for_family(submission)
    if served and submission_is_revision(served):
        return (getattr(served, 'revision_number', '') or '').strip() or '01'
    return '00'


def family_root_submission(submission):
    """Root (Rev 00) row for a document family."""
    if not submission:
        return None
    parent_ref = (getattr(submission, 'parent_draft_name', '') or '').strip()
    if submission_is_revision(submission) and parent_ref:
        return get_submission_by_ref(parent_ref) or submission
    return submission


def count_family_revision_entries(ref_or_submission) -> int:
    """Approved numbered revisions in the family (Rev 01+), excluding the Rev 00 root."""
    submission = (
        ref_or_submission
        if hasattr(ref_or_submission, 'id')
        else get_submission_by_ref(ref_or_submission)
    )
    root = family_root_submission(submission)
    if not root:
        return 0
    refs = family_parent_refs(root)
    if not refs:
        return 0
    return Submission.query.filter(
        Submission.parent_draft_name.in_(refs),
        Submission.is_revision == True,  # noqa: E712
        Submission.status.in_(APPROVED_STATUSES),
    ).count()


def served_submission_for_family(submission):
    """
    The row a reader is served for this document.

    A revision ref means that exact revision; anything else means the document,
    which serves its latest approved revision.
    """
    if not submission:
        return None
    if submission_is_revision(submission):
        return submission
    return latest_approved_revision(submission) or submission


def served_revision_label(submission) -> str:
    """Label for the revision a reader is served when they open this document."""
    return revision_display_label(served_submission_for_family(submission))


def get_readable_submission_by_ref(ref):
    """
    Resolve ``ref`` to the row whose body should be displayed.

    Same as :func:`get_submission_by_ref`, except an ML number resolves to the
    latest approved revision instead of the Rev 00 parent row.
    """
    submission = get_submission_by_ref(ref)
    if not submission:
        return None
    if not ref_addresses_document_family(ref, submission):
        return submission
    return latest_approved_revision(submission) or submission


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
