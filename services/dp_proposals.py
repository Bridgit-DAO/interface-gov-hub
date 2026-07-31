"""DP Proposal business logic: permissions, anchors, validation, dashboard aggregates."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from extensions import db
from models import DpProposal, Submission, User, Workgroup, WorkingGroupChair
from services.coordination import is_layer_admin, is_site_moderation_staff
from services.submissions import get_submission_by_ref


def resolve_canonical_submission(submission: Optional[Submission]) -> Optional[Submission]:
    """Prefer the current approved row for an ML number (after renumber / duplicate rows)."""
    if not submission:
        return None
    ml = (submission.ml_number or '').strip()
    if ml:
        canonical = get_submission_by_ref(ml)
        if canonical:
            return canonical
    return submission


def canonical_doc_group_key(submission: Optional[Submission]) -> str:
    if not submission:
        return ''
    ml = (submission.ml_number or '').strip()
    if ml:
        return f'ml:{ml}'
    draft = (submission.draft_name or '').strip()
    if draft:
        return f'draft:{draft}'
    return f'id:{submission.id}'


def reassign_proposals_to_canonical_submissions() -> int:
    """
    Move proposals off stale submission rows onto the current row for the same ML number.
    Returns number of proposals updated.
    """
    moved = 0
    for proposal in DpProposal.query.all():
        submission = Submission.query.get(proposal.submission_id)
        if not submission:
            continue
        canonical = resolve_canonical_submission(submission)
        if not canonical or canonical.id == proposal.submission_id:
            continue
        proposal.submission_id = canonical.id
        proposal.anchor_hash = compute_anchor_hash(
            canonical.id,
            canonical.content_hash,
            proposal.original_text,
        )
        moved += 1
    if moved:
        db.session.commit()
    return moved
from services.workgroup_links import extract_dp_number_from_title, is_dp_workgroup
from services.workgroup_positions import NOMINATION_STATUS_APPROVED

_NBSP_RE = re.compile('\u00a0')
_SENTENCE_RE = re.compile(r'[^.!?\u3002\n]+[.!?\u3002\n]+|[^.!?\u3002\n]+$')


def normalize_proposal_text(text: str) -> str:
    """Match Canopi normalizeForMatch baseline for anchor hashing."""
    if not text:
        return ''
    return _NBSP_RE.sub(' ', str(text)).replace('\r\n', '\n').strip()


RATIONALE_MAX_LEN = 4000
REFERENCE_URL_MAX_LEN = 2048


def normalize_rationale(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = normalize_proposal_text(str(text))
    if not cleaned:
        return None
    if len(cleaned) > RATIONALE_MAX_LEN:
        cleaned = cleaned[:RATIONALE_MAX_LEN]
    return cleaned


def validate_reference_url(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (normalized_url, error). Empty input is allowed."""
    if raw is None:
        return None, None
    url = str(raw).strip()
    if not url:
        return None, None
    if len(url) > REFERENCE_URL_MAX_LEN:
        return None, f'reference_url must be at most {REFERENCE_URL_MAX_LEN} characters'
    try:
        parsed = urlparse(url)
    except ValueError:
        return None, 'reference_url is invalid'
    if parsed.scheme not in ('http', 'https'):
        return None, 'reference_url must use http or https'
    if not parsed.netloc:
        return None, 'reference_url must include a host'
    if parsed.username or parsed.password:
        return None, 'reference_url must not include credentials'
    return url, None


def _collapse_sentence(text: str) -> str:
    return ' '.join((text or '').split())


def segment_sentences(text: str) -> List[Dict[str, Any]]:
    """Heuristic sentence boundaries (aligned with proposal-display.js)."""
    raw = text or ''
    parts: List[Dict[str, Any]] = []
    for match in _SENTENCE_RE.finditer(raw):
        parts.append({'start': match.start(), 'end': match.end(), 'text': match.group(0)})
    if not parts and raw:
        parts.append({'start': 0, 'end': len(raw), 'text': raw})
    return parts


def focused_passage_core(original: str, proposed: str) -> Tuple[str, str]:
    """
    Return only the contiguous changed sentence(s) at the start/end of a passage.
    Unchanged leading/trailing sentences are removed (no ellipsis).
    """
    o_s = segment_sentences(original)
    p_s = segment_sentences(proposed)
    start = 0
    while (
        start < len(o_s)
        and start < len(p_s)
        and _collapse_sentence(o_s[start]['text']) == _collapse_sentence(p_s[start]['text'])
    ):
        start += 1
    o_end = len(o_s) - 1
    p_end = len(p_s) - 1
    while (
        o_end >= start
        and p_end >= start
        and _collapse_sentence(o_s[o_end]['text']) == _collapse_sentence(p_s[p_end]['text'])
    ):
        o_end -= 1
        p_end -= 1
    if start > o_end:
        return original.strip(), proposed.strip()
    return (
        original[o_s[start]['start']: o_s[o_end]['end']].strip(),
        proposed[p_s[start]['start']: p_s[p_end]['end']].strip(),
    )


def align_context_anchor_to_original(context_anchor: Any, original_text: str) -> Any:
    """Keep stored textQuote.exact in sync with truncated original_text."""
    if not original_text:
        return context_anchor
    anchor: Dict[str, Any]
    if context_anchor is None:
        anchor = {}
    elif isinstance(context_anchor, str):
        try:
            anchor = json.loads(context_anchor.strip())
        except json.JSONDecodeError:
            return context_anchor
        if not isinstance(anchor, dict):
            return context_anchor
    elif isinstance(context_anchor, dict):
        anchor = dict(context_anchor)
    else:
        return context_anchor

    text_quote = anchor.get('textQuote')
    if not isinstance(text_quote, dict):
        text_quote = {'type': 'TextQuoteSelector'}
    else:
        text_quote = dict(text_quote)
    text_quote['type'] = text_quote.get('type') or 'TextQuoteSelector'
    text_quote['exact'] = original_text
    anchor['textQuote'] = text_quote
    return anchor


def compute_anchor_hash(
    submission_id: str,
    content_hash: Optional[str],
    exact_text: str,
) -> str:
    norm = normalize_proposal_text(exact_text)
    payload = f'{submission_id}\0{content_hash or ""}\0{norm}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def is_dp_submission(submission: Optional[Submission]) -> bool:
    if not submission:
        return False
    group = (submission.group or '').strip()
    if group:
        wg = Workgroup.query.filter_by(acronym=group).first()
        if wg and is_dp_workgroup(wg):
            return True
    return extract_dp_number_from_title(submission.title or '') is not None


def workgroup_for_submission(submission: Submission) -> Optional[Workgroup]:
    group = (submission.group or '').strip()
    if group:
        wg = Workgroup.query.filter_by(acronym=group).first()
        if wg:
            return wg
    dp_num = extract_dp_number_from_title(submission.title or '')
    if dp_num is None:
        return None
    from services.groups import extract_dp_number

    for wg in Workgroup.query.all():
        if extract_dp_number(wg.acronym or '') == dp_num:
            return wg
    return None


def can_accept_amendments(user: Optional[dict], workgroup: Optional[Workgroup] = None) -> bool:
    """Workgroup chairs, coordinators, layer admins, and site staff may accept amendments."""
    return can_manage_amendments(user, workgroup)


def can_manage_amendments(user: Optional[dict], workgroup: Optional[Workgroup]) -> bool:
    """Chair/coordinator, layer admin, and site staff may manage DP proposals (accept/decline/consider)."""
    if not user:
        return False
    if is_site_moderation_staff(user):
        return True
    if not workgroup:
        return False
    if workgroup.layer_id and workgroup.layer:
        if is_layer_admin(workgroup.layer, user):
            return True
    uid = user.get('id')
    if uid and workgroup.coordinator_id == uid:
        return True
    if not workgroup.acronym or not uid:
        return False
    approved_chair = WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == workgroup.acronym,
        WorkingGroupChair.position_key == 'chair',
        WorkingGroupChair.user_id == uid,
        db.or_(
            WorkingGroupChair.status == NOMINATION_STATUS_APPROVED,
            WorkingGroupChair.approved.is_(True),
        ),
    ).first()
    return approved_chair is not None


def require_dp_proposals_enabled() -> Optional[Tuple[dict, int]]:
    from flask import jsonify

    from services.product_rollout import is_feature_enabled

    if not is_feature_enabled('patches'):
        return jsonify({
            'error': 'Patches are not enabled.',
            'error_code': 'FEATURE_DISABLED',
            'feature': 'patches',
        }), 403
    return None


def resolve_submission_for_proposals(draft_ref: str) -> Tuple[Optional[Submission], Optional[str]]:
    submission = get_submission_by_ref(draft_ref)
    if not submission:
        return None, 'Document not found'
    if (submission.status or '').lower() != 'approved':
        return None, 'Proposals are only allowed on approved documents'
    return submission, None


def expected_proposal_scope(submission: Submission) -> str:
    from services.proposal_modes import proposal_mode_for_submission

    return get_proposal_mode(proposal_mode_for_submission(submission))['scope']


def validate_proposal_scope_for_submission(
    submission: Submission,
    scope: str,
) -> Optional[str]:
    expected = expected_proposal_scope(submission)
    if scope != expected:
        if expected == 'dp':
            return 'This document requires scope=dp (patch on DP draft)'
        return 'This document requires scope=document (patch on document)'
    return None


def get_proposal_mode(mode: str):
    from services.proposal_modes import get_proposal_mode as _get

    return _get(mode)


def validate_create_payload(data: Any) -> Tuple[Optional[dict], Optional[str]]:
    if not isinstance(data, dict):
        return None, 'JSON body required'
    original = normalize_proposal_text(data.get('original_text') or '')
    proposed = normalize_proposal_text(data.get('proposed_text') or '')
    if not original:
        return None, 'original_text is required'
    if not proposed:
        return None, 'proposed_text is required'
    original, proposed = focused_passage_core(original, proposed)
    if not original:
        return None, 'original_text is required'
    if not proposed:
        return None, 'proposed_text is required'
    if original == proposed:
        return None, 'proposed_text must differ from original_text'
    context_anchor = align_context_anchor_to_original(
        data.get('context_anchor'),
        original,
    )
    if context_anchor is not None and not isinstance(context_anchor, (dict, str)):
        return None, 'context_anchor must be a JSON object or string'
    scope = (data.get('scope') or 'dp').strip().lower()
    if scope not in ('dp', 'document'):
        return None, 'scope must be dp or document'
    reference_url, ref_err = validate_reference_url(data.get('reference_url'))
    if ref_err:
        return None, ref_err
    return {
        'original_text': original,
        'proposed_text': proposed,
        'context_anchor': context_anchor,
        'scope': scope,
        'rationale': normalize_rationale(data.get('rationale')),
        'reference_url': reference_url,
    }, None


def serialize_context_anchor(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return None
        try:
            json.loads(trimmed)
        except json.JSONDecodeError:
            return None
        return trimmed
    if isinstance(raw, dict):
        return json.dumps(raw, sort_keys=True)
    return None


def _html_to_plain_text(content: str) -> str:
    import html as html_mod

    text = re.sub(r'<[^>]+>', ' ', content or '')
    return normalize_proposal_text(html_mod.unescape(text))


def _collapse_match_text(text: str) -> str:
    return ' '.join((text or '').split())


def passage_text_in_haystack(haystack: str, exact: str) -> bool:
    """True when normalized passage text appears in document plain text."""
    hay = normalize_proposal_text(haystack)
    needle = normalize_proposal_text(exact)
    if not needle:
        return False
    if needle in hay:
        return True
    return _collapse_match_text(needle) in _collapse_match_text(hay)


def proposal_passage_text(proposal: DpProposal) -> str:
    anchor = parse_stored_context_anchor(proposal.context_anchor)
    if anchor:
        text_quote = anchor.get('textQuote') if isinstance(anchor.get('textQuote'), dict) else None
        if text_quote and text_quote.get('exact'):
            return normalize_proposal_text(str(text_quote['exact']))
    return normalize_proposal_text(proposal.original_text or '')


def submission_family_refs(submission: Submission) -> set:
    refs = {submission.id}
    draft = (submission.draft_name or '').strip()
    if draft:
        refs.add(draft)
    parent = (submission.parent_draft_name or '').strip()
    if parent:
        refs.add(parent)
    ml = (submission.ml_number or '').strip()
    if ml:
        refs.add(ml)
    return refs


def submission_family_submissions(canonical: Submission) -> List[Submission]:
    refs = list(submission_family_refs(canonical))
    return (
        Submission.query.filter(
            db.or_(
                Submission.id.in_(refs),
                Submission.draft_name.in_(refs),
                Submission.parent_draft_name.in_(refs),
                Submission.ml_number.in_(refs),
            )
        )
        .all()
    )


def load_submission_plain_document_text(submission: Submission) -> str:
    from services.draft_reader import build_draft_context, load_draft_document_body

    ref = (submission.draft_name or submission.ml_number or submission.id or '').strip()
    if not ref:
        return ''
    draft, sub = build_draft_context(ref)
    if not draft or not sub:
        return ''
    content, render_html, _, _ = load_draft_document_body(draft, sub, ref)
    if render_html:
        return _html_to_plain_text(content)
    return normalize_proposal_text(content)


def classify_proposal_location(
    proposal: DpProposal,
    canonical: Optional[Submission] = None,
) -> str:
    """
    Return how a patch relates to the current approved document body:
    - current: passage text is in the canonical document
    - superseded: passage is only in an older revision (content hash / revision row)
    - bogus: not found in current or any revision in the document family
    """
    if not canonical:
        canonical = resolve_canonical_submission(
            Submission.query.get(proposal.submission_id)
        )
    if not canonical:
        return 'bogus'

    passage = proposal_passage_text(proposal)
    if not passage:
        return 'bogus'

    current_body = load_submission_plain_document_text(canonical)
    if passage_text_in_haystack(current_body, passage):
        return 'current'

    create_hash = (proposal.content_hash_at_create or '').strip().lower()
    current_hash = (canonical.content_hash or '').strip().lower()

    for row in submission_family_submissions(canonical):
        if row.id == canonical.id:
            continue
        row_hash = (row.content_hash or '').strip().lower()
        if create_hash and row_hash and row_hash != create_hash:
            continue
        body = load_submission_plain_document_text(row)
        if passage_text_in_haystack(body, passage):
            return 'superseded'

    if create_hash and current_hash and create_hash != current_hash:
        for row in submission_family_submissions(canonical):
            row_hash = (row.content_hash or '').strip().lower()
            if row_hash != create_hash:
                continue
            body = load_submission_plain_document_text(row)
            if passage_text_in_haystack(body, passage):
                return 'superseded'

    return 'bogus'


def passage_exists_in_current_document(submission: Submission, original_text: str) -> bool:
    canonical = resolve_canonical_submission(submission) or submission
    body = load_submission_plain_document_text(canonical)
    return passage_text_in_haystack(body, original_text)


def reconcile_dp_proposal_locations(*, dry_run: bool = False) -> Dict[str, Any]:
    """
    Delete bogus patches; mark superseded-revision patches as orphaned.
    """
    stats: Dict[str, Any] = {
        'total': 0,
        'current': 0,
        'superseded_marked': 0,
        'bogus_deleted': 0,
        'deleted_ids': [],
        'orphaned_ids': [],
    }
    for proposal in DpProposal.query.order_by(DpProposal.created_at.asc()).all():
        stats['total'] += 1
        kind = classify_proposal_location(proposal)
        if kind == 'current':
            stats['current'] += 1
            if proposal.status == 'orphaned':
                proposal.status = 'pending'
            continue
        if kind == 'superseded':
            stats['superseded_marked'] += 1
            stats['orphaned_ids'].append(proposal.id)
            if proposal.status not in ('accepted', 'declined', 'incorporated'):
                proposal.status = 'orphaned'
            continue
        stats['bogus_deleted'] += 1
        stats['deleted_ids'].append(proposal.id)
        db.session.delete(proposal)
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return stats


def list_proposals_for_submission(submission_id: str) -> List[DpProposal]:
    canonical = resolve_canonical_submission(Submission.query.get(submission_id))
    sid = canonical.id if canonical else submission_id
    rows = (
        DpProposal.query.filter_by(submission_id=sid)
        .order_by(DpProposal.created_at.desc())
        .all()
    )
    if not canonical:
        return rows
    return [row for row in rows if classify_proposal_location(row, canonical) != 'bogus']


def proposal_counts(proposals: List[DpProposal]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_anchor: Dict[str, int] = {}
    for row in proposals:
        st = row.status or 'pending'
        by_status[st] = by_status.get(st, 0) + 1
        ah = row.anchor_hash or ''
        if ah:
            by_anchor[ah] = by_anchor.get(ah, 0) + 1
    return {
        'by_status': by_status,
        'by_anchor': by_anchor,
        'total': len(proposals),
    }


def parse_stored_context_anchor(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def retrim_stored_proposal(proposal: DpProposal) -> Tuple[bool, Optional[str]]:
    """
    Trim stored original/proposed text and refresh anchor_hash and context_anchor.
    Returns (changed, error_message). error_message is set when the row is left unchanged.
    """
    orig = normalize_proposal_text(proposal.original_text or '')
    prop = normalize_proposal_text(proposal.proposed_text or '')
    new_orig, new_prop = focused_passage_core(orig, prop)
    if not new_orig or not new_prop:
        return False, 'empty text after trim'
    if new_orig == new_prop:
        return False, 'no differing sentences after trim'

    new_anchor = align_context_anchor_to_original(
        parse_stored_context_anchor(proposal.context_anchor),
        new_orig,
    )
    new_hash = compute_anchor_hash(
        proposal.submission_id,
        proposal.content_hash_at_create,
        new_orig,
    )
    serialized_anchor = serialize_context_anchor(new_anchor)

    changed = (
        new_orig != orig
        or new_prop != prop
        or new_hash != (proposal.anchor_hash or '')
        or serialized_anchor != proposal.context_anchor
    )
    proposal.original_text = new_orig
    proposal.proposed_text = new_prop
    proposal.context_anchor = serialized_anchor
    proposal.anchor_hash = new_hash
    return changed, None


def retrim_all_dp_proposals(*, dry_run: bool = False) -> Dict[str, Any]:
    """One-off / maintenance: trim all stored DP proposals to changed sentences only."""
    rows = DpProposal.query.order_by(DpProposal.created_at.asc()).all()
    stats: Dict[str, Any] = {
        'total': len(rows),
        'updated': 0,
        'unchanged': 0,
        'skipped': 0,
        'errors': [],
    }
    for row in rows:
        changed, err = retrim_stored_proposal(row)
        if err:
            stats['skipped'] += 1
            stats['errors'].append({'id': row.id, 'error': err})
            continue
        if changed:
            stats['updated'] += 1
        else:
            stats['unchanged'] += 1
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return stats


def create_dp_proposal(
    submission: Submission,
    *,
    author_user_id: str,
    original_text: str,
    proposed_text: str,
    context_anchor: Any = None,
    scope: str = 'dp',
    rationale: Optional[str] = None,
    reference_url: Optional[str] = None,
) -> DpProposal:
    anchor_hash = compute_anchor_hash(
        submission.id,
        submission.content_hash,
        original_text,
    )
    row = DpProposal(
        submission_id=submission.id,
        scope=scope,
        status='pending',
        anchor_hash=anchor_hash,
        context_anchor=serialize_context_anchor(context_anchor),
        original_text=original_text,
        proposed_text=proposed_text,
        rationale=rationale,
        reference_url=reference_url,
        content_hash_at_create=submission.content_hash,
        author_user_id=author_user_id,
        source_channel='gov-hub',
    )
    db.session.add(row)
    from services.contribution_pipeline import contribution_registry_id

    row.contribution_registry_id = contribution_registry_id(row.source_channel, row.id)
    return row


def _emit_dp_proposal_review_event(
    proposal: DpProposal,
    *,
    reviewer_user_id: str,
    event_type: str,
) -> None:
    """Emit EventLog when a patch is merged or declined."""
    from services.events import emit_event

    sub = proposal.submission
    layer_id = sub.layer_id if sub else None
    emit_event(
        event_type,
        actor_type='user',
        actor_id=reviewer_user_id,
        subject_type='dp_proposal',
        subject_id=proposal.id,
        layer_id=layer_id,
        payload={
            'draft_name': submission_draft_ref(sub),
            'ml_number': sub.ml_number if sub else None,
            'submission_id': proposal.submission_id,
            'proposal_id': proposal.id,
            'scope': proposal.scope or 'dp',
            'author_user_id': proposal.author_user_id,
        },
    )


def _enqueue_proposal_pipeline(proposal: DpProposal, event_type: str) -> None:
    from services.contribution_pipeline import (
        enqueue_contribution_pipeline_event,
        pipeline_payload_for_proposal,
    )

    sub = proposal.submission
    enqueue_contribution_pipeline_event(
        subject_type='dp_proposal',
        subject_id=proposal.id,
        event_type=event_type,
        source_channel=getattr(proposal, 'source_channel', None) or 'gov-hub',
        payload=pipeline_payload_for_proposal(proposal, sub),
    )


def accept_proposal(proposal: DpProposal, reviewer_user_id: str) -> DpProposal:
    proposal.status = 'accepted'
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.utcnow()
    _emit_dp_proposal_review_event(
        proposal,
        reviewer_user_id=reviewer_user_id,
        event_type='dp_proposal_accepted',
    )
    from services.dp_contribution_badges import on_dp_contribution_outcome

    on_dp_contribution_outcome(proposal, 'accepted')
    _enqueue_proposal_pipeline(proposal, 'accepted')
    return proposal


def consider_proposal(proposal: DpProposal, reviewer_user_id: str) -> DpProposal:
    proposal.status = 'considered'
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.utcnow()
    _emit_dp_proposal_review_event(
        proposal,
        reviewer_user_id=reviewer_user_id,
        event_type='dp_proposal_considered',
    )
    from services.dp_contribution_badges import on_dp_contribution_outcome

    on_dp_contribution_outcome(proposal, 'considered')
    _enqueue_proposal_pipeline(proposal, 'considered')
    return proposal


def decline_proposal(proposal: DpProposal, reviewer_user_id: str) -> DpProposal:
    proposal.status = 'declined'
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.utcnow()
    _emit_dp_proposal_review_event(
        proposal,
        reviewer_user_id=reviewer_user_id,
        event_type='dp_proposal_declined',
    )
    _enqueue_proposal_pipeline(proposal, 'declined')
    return proposal


def submission_draft_ref(submission: Optional[Submission]) -> str:
    """URL ref for /doc/draft/<ref>/read/ (ml_number preferred)."""
    if not submission:
        return ''
    return (submission.ml_number or submission.draft_name or submission.id or '').strip()


def submission_display_label(submission: Optional[Submission]) -> str:
    """Human-readable label for profile and activity lists."""
    if not submission:
        return 'Document'
    title = (submission.title or '').strip()
    ml = (submission.ml_number or '').strip()
    if title and ml:
        return f'{ml}: {title}'
    if title:
        return title
    if ml:
        return ml
    draft = (submission.draft_name or '').strip()
    if draft:
        return draft
    sid = str(submission.id or '').strip()
    return f'Document {sid[:8]}' if sid else 'Document'


def submission_profile_href(submission: Optional[Submission]) -> str:
    """Profile list link: approved drafts open the reader; others go to status."""
    if not submission:
        return '#'
    if (submission.status or '').lower() == 'approved':
        ref = submission_draft_ref(submission)
        if ref:
            from urllib.parse import quote

            return f'/doc/draft/{quote(ref, safe="")}/read/'
    sid = str(submission.id or '').strip()
    return f'/submit/status/{sid}/' if sid else '#'


def submission_for_reader_ref(draft_ref: str) -> Optional[Submission]:
    """Resolve a draft ref (ml_number, draft_name, or id) to a submission row."""
    ref = (draft_ref or '').strip()
    if not ref:
        return None
    return (
        Submission.query.filter(
            db.or_(
                Submission.ml_number == ref,
                Submission.draft_name == ref,
                Submission.id == ref,
            )
        )
        .order_by(Submission.submitted_at.desc())
        .first()
    )


def user_profile_path(user: Optional[User]) -> Optional[str]:
    if not user or not user.username:
        return None
    return f'/profile/{user.username}/'


def user_display_label(user: Optional[User]) -> str:
    if not user:
        return 'Anonymous'
    return (user.displayName or user.username or 'Participant').strip()


def list_approved_submissions_for_mode(mode: str = 'dp', program=None) -> List[Submission]:
    """Approved drafts for a proposal hub mode, one row per ML number when present."""
    from services.layer_programs import filter_submissions_for_program

    want_dp = mode == 'dp'
    subs = Submission.query.filter_by(status='approved', doc_type='draft').all()
    seen_ml: set = set()
    out: List[Submission] = []
    filtered = [
        s for s in subs
        if (is_dp_submission(s) if want_dp else not is_dp_submission(s))
    ]
    for sub in sorted(
        filtered,
        key=lambda s: ((s.ml_number or ''), (s.title or '')),
    ):
        ml = (sub.ml_number or '').strip()
        if ml:
            if ml in seen_ml:
                continue
            seen_ml.add(ml)
            canonical = get_submission_by_ref(ml) or sub
            out.append(canonical)
        else:
            out.append(sub)
    return filter_submissions_for_program(out, program)


def list_approved_dp_submissions() -> List[Submission]:
    """Approved DP drafts, one row per ML number (canonical read target)."""
    return list_approved_submissions_for_mode('dp')


def _proposal_scope_for_mode(mode: str) -> str:
    return get_proposal_mode(mode)['scope']


def dashboard_dp_challenge_stats(mode: str = 'dp', program=None) -> Dict[str, Any]:
    from sqlalchemy import func

    from services.layer_programs import filter_submission_id_set

    scope = _proposal_scope_for_mode(mode)
    allowed = filter_submission_id_set(program)
    q = db.session.query(func.count(DpProposal.id)).filter(DpProposal.scope == scope)
    cq = db.session.query(func.count(func.distinct(DpProposal.author_user_id))).filter(
        DpProposal.author_user_id.isnot(None),
        DpProposal.scope == scope,
    )
    if allowed is not None:
        if not allowed:
            return {'total_proposals': 0, 'contributors': 0, 'documents': 0}
        q = q.filter(DpProposal.submission_id.in_(list(allowed)))
        cq = cq.filter(DpProposal.submission_id.in_(list(allowed)))
    total = q.scalar() or 0
    contributors = cq.scalar() or 0
    docs = len(dashboard_dp_activity(limit=500, mode=mode, program=program))
    return {
        'total_proposals': int(total),
        'contributors': int(contributors),
        'documents': int(docs),
    }


def dashboard_dp_activity(limit: int = 100, mode: str = 'dp', program=None) -> List[dict]:
    """Rows for dashboards by document (ML number), not duplicate submission rows."""
    from sqlalchemy import case, func

    from services.layer_programs import filter_submission_id_set

    scope = _proposal_scope_for_mode(mode)
    want_dp = mode == 'dp'
    allowed = filter_submission_id_set(program)
    activity_expr = func.max(DpProposal.created_at)
    q = (
        db.session.query(
            DpProposal.submission_id,
            func.count(DpProposal.id).label('total'),
            func.sum(case((DpProposal.status == 'pending', 1), else_=0)).label('pending'),
            func.sum(case((DpProposal.status == 'accepted', 1), else_=0)).label('accepted'),
            func.sum(case((DpProposal.status == 'declined', 1), else_=0)).label('declined'),
            func.sum(case((DpProposal.status == 'incorporated', 1), else_=0)).label('incorporated'),
            func.sum(case((DpProposal.status == 'orphaned', 1), else_=0)).label('orphaned'),
            activity_expr.label('last_activity'),
        )
        .filter(DpProposal.scope == scope)
    )
    if allowed is not None:
        if not allowed:
            return []
        q = q.filter(DpProposal.submission_id.in_(list(allowed)))
    rows = q.group_by(DpProposal.submission_id).order_by(activity_expr.desc()).all()
    merged: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        submission = Submission.query.get(row.submission_id)
        if not submission:
            continue
        if is_dp_submission(submission) != want_dp:
            continue
        canonical = resolve_canonical_submission(submission)
        if not canonical:
            continue
        key = canonical_doc_group_key(canonical)
        if key not in merged:
            wg = workgroup_for_submission(canonical)
            title = canonical.title or ''
            merged[key] = {
                'submission_ids': {row.submission_id},
                'draft_ref': submission_draft_ref(canonical),
                'title': title,
                'title_short': _short_dp_title(title),
                'ml_number': canonical.ml_number,
                'dp_number': extract_dp_number_from_title(title),
                'workgroup_acronym': wg.acronym if wg else (canonical.group or None),
                'workgroup_name': wg.name if wg else None,
                'counts': {
                    'total': 0,
                    'pending': 0,
                    'accepted': 0,
                    'declined': 0,
                    'incorporated': 0,
                    'orphaned': 0,
                },
                'last_activity': None,
            }
        entry = merged[key]
        entry['submission_ids'].add(row.submission_id)
        for field in ('total', 'pending', 'accepted', 'declined', 'incorporated', 'orphaned'):
            entry['counts'][field] += int(getattr(row, field) or 0)
        last = row.last_activity.isoformat() if row.last_activity else None
        if last and (not entry['last_activity'] or last > entry['last_activity']):
            entry['last_activity'] = last

    out: List[dict] = []
    for entry in merged.values():
        sub_ids = list(entry.pop('submission_ids'))
        contributors = (
            db.session.query(func.count(func.distinct(DpProposal.author_user_id)))
            .filter(
                DpProposal.submission_id.in_(sub_ids),
                DpProposal.author_user_id.isnot(None),
            )
            .scalar()
        ) or 0
        entry['contributors'] = int(contributors)
        out.append(entry)

    out.sort(key=lambda r: r.get('last_activity') or '', reverse=True)
    return out[:limit]


def _short_dp_title(title: str) -> str:
    """Strip leading 'DP11 - ' style prefix for a compact title column."""
    t = (title or '').strip()
    m = re.match(r'^DP\s*\d+\s*[-––:]\s*(.+)$', t, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def dashboard_dp_by_participant(limit: int = 100, mode: str = 'dp', program=None) -> List[dict]:
    """Contributor activity for proposal hubs (most proposals first)."""
    from sqlalchemy import case, func

    from services.layer_programs import filter_submission_id_set

    scope = _proposal_scope_for_mode(mode)
    allowed = filter_submission_id_set(program)
    activity_expr = func.max(DpProposal.created_at)
    q = (
        db.session.query(
            DpProposal.author_user_id,
            func.count(DpProposal.id).label('total'),
            func.count(func.distinct(DpProposal.submission_id)).label('docs'),
            func.sum(case((DpProposal.status == 'accepted', 1), else_=0)).label('accepted'),
            func.sum(case((DpProposal.status == 'pending', 1), else_=0)).label('pending'),
            activity_expr.label('last_activity'),
        )
        .filter(
            DpProposal.author_user_id.isnot(None),
            DpProposal.scope == scope,
        )
    )
    if allowed is not None:
        if not allowed:
            return []
        q = q.filter(DpProposal.submission_id.in_(list(allowed)))
    rows = q.group_by(DpProposal.author_user_id).order_by(activity_expr.desc()).limit(limit).all()
    out: List[dict] = []
    for row in rows:
        user = User.query.get(row.author_user_id)
        out.append({
            'author_user_id': row.author_user_id,
            'display_name': user_display_label(user),
            'username': user.username if user else None,
            'profile_href': user_profile_path(user),
            'counts': {
                'total': int(row.total or 0),
                'docs': int(row.docs or 0),
                'accepted': int(row.accepted or 0),
                'pending': int(row.pending or 0),
            },
            'last_activity': row.last_activity.isoformat() if row.last_activity else None,
        })
    return out


def parse_challenge_since_param(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    text = str(raw).strip().replace('Z', '')
    if '+' in text:
        text = text.split('+', 1)[0]
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def challenge_recent_events(
    since: Optional[datetime] = None,
    *,
    limit: int = 20,
    mode: str = 'dp',
    program=None,
) -> List[dict]:
    """Recent proposal created + accepted events for live toasts."""
    from services.layer_programs import filter_submission_id_set

    if since is None:
        since = datetime.utcnow() - timedelta(hours=24)

    scope = _proposal_scope_for_mode(mode)
    allowed = filter_submission_id_set(program)
    created_q = DpProposal.query.filter(
        DpProposal.created_at > since,
        DpProposal.scope == scope,
    )
    accepted_q = DpProposal.query.filter(
        DpProposal.status == 'accepted',
        DpProposal.reviewed_at.isnot(None),
        DpProposal.reviewed_at > since,
        DpProposal.scope == scope,
    )
    if allowed is not None:
        if not allowed:
            return []
        created_q = created_q.filter(DpProposal.submission_id.in_(list(allowed)))
        accepted_q = accepted_q.filter(DpProposal.submission_id.in_(list(allowed)))
    created_rows = created_q.order_by(DpProposal.created_at.desc()).limit(limit).all()
    accepted_rows = accepted_q.order_by(DpProposal.reviewed_at.desc()).limit(limit).all()

    events: List[dict] = []
    for p in created_rows:
        sub = Submission.query.get(p.submission_id)
        author = User.query.get(p.author_user_id) if p.author_user_id else None
        draft_ref = submission_draft_ref(sub)
        events.append({
            'type': 'created',
            'at': p.created_at.isoformat() if p.created_at else None,
            'proposal_id': p.id,
            'author_user_id': p.author_user_id,
            'author_name': user_display_label(author),
            'author_profile_href': user_profile_path(author),
            'doc_title': sub.title if sub else 'DP draft',
            'doc_href': f'/doc/draft/{draft_ref}/read/' if draft_ref else None,
            'ml_number': sub.ml_number if sub else None,
        })
    for p in accepted_rows:
        sub = Submission.query.get(p.submission_id)
        author = User.query.get(p.author_user_id) if p.author_user_id else None
        draft_ref = submission_draft_ref(sub)
        events.append({
            'type': 'accepted',
            'at': p.reviewed_at.isoformat() if p.reviewed_at else None,
            'proposal_id': p.id,
            'author_user_id': p.author_user_id,
            'author_name': user_display_label(author),
            'author_profile_href': user_profile_path(author),
            'doc_title': sub.title if sub else 'DP draft',
            'doc_href': f'/doc/draft/{draft_ref}/read/' if draft_ref else None,
            'ml_number': sub.ml_number if sub else None,
        })

    events.sort(key=lambda e: e.get('at') or '', reverse=True)
    return events[:limit]


def user_from_session(current_user: dict) -> Optional[User]:
    uid = current_user.get('id')
    if uid:
        return User.query.get(uid)
    username = current_user.get('username')
    if username:
        return User.query.filter_by(username=username).first()
    return None
