"""Public patches list page – passage-anchored only (no document-wide patches)."""
from __future__ import annotations

import html as html_mod
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode

from models import DpProposal, Submission
from services.dp_proposals import (
    can_accept_amendments,
    can_manage_amendments,
    list_proposals_for_submission,
    resolve_submission_for_proposals,
    workgroup_for_submission,
)
from services.proposal_modes import is_mode_enabled, mode_labels, proposal_mode_for_submission
from services.read_navigation import read_page_url
from services.submissions import get_submission_by_ref
from services.text_diff import build_diff_html, change_counts


def _draft_dict_from_submission(submission: Submission, draft_name: str) -> dict:
    return {
        'name': draft_name,
        'title': submission.title,
        'authors': submission.authors or [],
        'status': submission.status,
        'group': submission.group,
        'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
        'ml_number': submission.ml_number,
    }


def resolve_draft_for_patches_page(draft_name: str) -> Tuple[Optional[dict], Optional[Submission]]:
    """Resolve draft display dict and submission for the patches page."""
    submission = get_submission_by_ref(draft_name)
    if submission:
        return _draft_dict_from_submission(submission, draft_name), submission
    return None, None


def patches_enabled_for_submission(submission: Submission) -> bool:
    mode = proposal_mode_for_submission(submission)
    return is_mode_enabled(mode)


def count_patches_for_draft_ref(draft_ref: str) -> int:
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err or not submission:
        return 0
    if not patches_enabled_for_submission(submission):
        return 0
    return DpProposal.query.filter_by(submission_id=submission.id).count()


def _truncate(text: str, max_len: int = 160) -> str:
    s = ' '.join((text or '').split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'


def _status_badge_class(status: str) -> str:
    if status == 'accepted':
        return 'bg-success'
    if status == 'declined':
        return 'bg-secondary'
    if status == 'pending':
        return 'bg-primary'
    return 'bg-secondary'


def _group_patches_by_passage(rows: List[DpProposal]) -> List[dict]:
    by_anchor: Dict[str, List[DpProposal]] = defaultdict(list)
    for row in rows:
        key = row.anchor_hash or row.id
        by_anchor[key].append(row)
    groups = []
    for anchor_hash, items in by_anchor.items():
        items.sort(key=lambda p: p.created_at or '', reverse=True)
        groups.append({
            'anchor_hash': anchor_hash,
            'passage': items[0].original_text or '',
            'patches': items,
        })
    groups.sort(key=lambda g: g['patches'][0].created_at or '', reverse=True)
    return groups


def _patch_reader_href(draft_ref: str, patch_id: str, *, return_to: str) -> str:
    base = read_page_url(draft_ref, return_to)
    sep = '&' if '?' in base else '?'
    return base + sep + urlencode({'patch': patch_id})


def _render_diff_block(patch: DpProposal, labels: Dict[str, str]) -> str:
    """Inline red/green diff, matching the reader's patch modal."""
    original = patch.original_text or ''
    proposed = patch.proposed_text or ''
    label = html_mod.escape(labels.get('proposed_label', 'Patched text'))

    if not original:
        body = html_mod.escape(proposed)
        legend = ''
    else:
        body = build_diff_html(original, proposed)
        added, removed = change_counts(original, proposed)
        legend = (
            '<div class="gh-patch-diff-legend small text-muted mt-1">'
            f'<span class="gh-patch-diff-added">+{added}</span>'
            f'<span class="gh-patch-diff-removed ms-2">&minus;{removed}</span>'
            '</div>'
        )

    return (
        '<div class="gh-patch-diff">'
        f'<div class="small text-muted mb-1">{label}</div>'
        f'<pre class="dp-proposal-pre gh-patch-pre mb-0">{body}</pre>'
        f'{legend}'
        '</div>'
    )


def render_patch_card(
    patch: DpProposal,
    *,
    draft_ref: str,
    return_to: str,
    can_merge: bool,
    can_decline: bool,
    labels: Dict[str, str],
) -> str:
    author = html_mod.escape(patch.author.displayName or patch.author.username if patch.author else 'Anonymous')
    status = patch.status or 'pending'
    status_label = html_mod.escape(patch.status_label())
    badge_cls = _status_badge_class(status)
    created = patch.created_at.strftime('%b %d, %Y') if patch.created_at else ''
    reader_href = html_mod.escape(_patch_reader_href(draft_ref, patch.id, return_to=return_to))
    diff_block = _render_diff_block(patch, labels)

    rationale_block = ''
    if patch.rationale:
        rationale_block = (
            '<div class="gh-patch-rationale mt-2">'
            f'<div class="small text-muted mb-1">Rationale</div>'
            f'<p class="mb-0 small">{html_mod.escape(patch.rationale)}</p>'
            '</div>'
        )
    reference_block = ''
    if patch.reference_url:
        ref_esc = html_mod.escape(patch.reference_url)
        reference_block = (
            '<div class="mt-2 small">'
            f'<a href="{ref_esc}" target="_blank" rel="noopener noreferrer">Reference</a>'
            '</div>'
        )

    actions = ''
    if status == 'pending' and (can_merge or can_decline):
        btns = []
        if can_merge:
            merge_label = html_mod.escape(labels.get('accept_button', 'Merge patch'))
            btns.append(
                f'<button type="button" class="btn btn-success btn-sm" '
                f'data-gh-patch-action="accept" data-patch-id="{html_mod.escape(patch.id)}">'
                f'{merge_label}</button>'
            )
        if can_decline:
            btns.append(
                f'<button type="button" class="btn btn-outline-secondary btn-sm" '
                f'data-gh-patch-action="decline" data-patch-id="{html_mod.escape(patch.id)}">'
                'Decline</button>'
            )
        actions = '<div class="btn-group btn-group-sm mt-3">' + ''.join(btns) + '</div>'

    return f'''
    <div class="gh-patch-item card mb-2" id="patch-{html_mod.escape(patch.id)}">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
          <span class="badge {badge_cls}">{status_label}</span>
          <small class="text-muted text-nowrap">{html_mod.escape(created)}</small>
        </div>
        <p class="small mb-2"><strong>{author}</strong></p>
        {diff_block}
        {rationale_block}
        {reference_block}
        <div class="mt-3">
          <a href="{reader_href}" class="btn btn-sm btn-outline-primary">View passage in reader</a>
        </div>
        {actions}
      </div>
    </div>'''


def render_passage_group(
    group: dict,
    *,
    draft_ref: str,
    return_to: str,
    can_merge: bool,
    can_decline: bool,
    labels: Dict[str, str],
) -> str:
    passage = html_mod.escape(_truncate(group.get('passage') or '', 220))
    patch_count = len(group.get('patches') or [])
    count_word = labels.get('count_word', 'patch')
    count_label = f'{patch_count} {count_word}' + ('' if patch_count == 1 else 'es')

    cards = ''.join(
        render_patch_card(
            p,
            draft_ref=draft_ref,
            return_to=return_to,
            can_merge=can_merge,
            can_decline=can_decline,
            labels=labels,
        )
        for p in group.get('patches') or []
    )

    first_patch = (group.get('patches') or [None])[0]
    passage_link = ''
    if first_patch:
        href = html_mod.escape(_patch_reader_href(draft_ref, first_patch.id, return_to=return_to))
        passage_link = f'<a href="{href}" class="btn btn-sm btn-link px-0">Open passage in reader</a>'

    return f'''
    <section class="gh-patch-passage-group mb-4">
      <div class="gh-patch-passage-header mb-3">
        <h6 class="text-muted text-uppercase small mb-2">Passage</h6>
        <blockquote class="gh-patch-passage-quote mb-2">{passage}</blockquote>
        <div class="d-flex flex-wrap align-items-center gap-2">
          <span class="badge bg-light text-dark border">{html_mod.escape(count_label)}</span>
          {passage_link}
        </div>
      </div>
      {cards}
    </section>'''


def render_patches_list_html(
    submission: Submission,
    draft_ref: str,
    *,
    current_user: Optional[dict],
) -> str:
    labels = mode_labels(proposal_mode_for_submission(submission))
    rows = list_proposals_for_submission(submission.id)
    if not rows:
        return '''
        <div class="alert alert-info mb-0">
          <i class="fas fa-info-circle me-2"></i>
          No patches yet. Open the reader, <strong>select a passage</strong>, and propose a patch.
          Patches are always anchored to specific text – there are no document-wide patches.
        </div>'''

    wg = workgroup_for_submission(submission)
    can_merge = bool(current_user and can_accept_amendments(current_user, wg))
    can_decline = bool(current_user and can_manage_amendments(current_user, wg))
    return_to = f'/doc/draft/{quote(draft_ref, safe="")}/patches/'
    groups = _group_patches_by_passage(rows)
    return ''.join(
        render_passage_group(
            g,
            draft_ref=draft_ref,
            return_to=return_to,
            can_merge=can_merge,
            can_decline=can_decline,
            labels=labels,
        )
        for g in groups
    )
