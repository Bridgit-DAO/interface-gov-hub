"""Admin CFI proposed-patch viewer – grouped by submission."""
from __future__ import annotations

import html as html_mod
from typing import Any, Dict, List, Optional

from services.patch_modes import normalize_patch_mode, patch_mode_status_label
from services.text_diff import build_diff_html, change_counts


def _truncate(text: str, max_len: int = 180) -> str:
    s = ' '.join((text or '').split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'


def _patch_mode_badge(mode: str | None) -> str:
    normalized = normalize_patch_mode(mode)
    if normalized == 'insert':
        label = 'Insert above'
        cls = 'bg-info text-dark'
    elif normalized == 'insert_after':
        label = 'Insert after'
        cls = 'bg-primary'
    else:
        label = 'Replace'
        cls = 'bg-secondary'
    return (
        f'<span class="badge {cls} me-1">{html_mod.escape(label)}</span>'
    )


def _confidence_badge(confidence: str | None) -> str:
    raw = (confidence or '').strip().lower()
    if not raw:
        return ''
    cls = {
        'high': 'bg-success',
        'medium': 'bg-warning text-dark',
        'low': 'bg-secondary',
    }.get(raw, 'bg-light text-dark border')
    return f'<span class="badge {cls}">{html_mod.escape(raw)}</span>'


def _render_patch_diff(patch: dict) -> str:
    mode = normalize_patch_mode(patch.get('patch_mode'))
    original = patch.get('original_text') or ''
    proposed = patch.get('proposed_text') or ''

    if mode == 'insert':
        return (
            '<div class="gh-patch-diff">'
            '<div class="small text-muted mb-1">Insert above anchor</div>'
            f'<pre class="dp-proposal-pre gh-patch-pre mb-2">{html_mod.escape(proposed)}</pre>'
            '<div class="small text-muted mb-1">Anchor (unchanged)</div>'
            f'<pre class="dp-proposal-pre gh-patch-pre mb-0">{html_mod.escape(original)}</pre>'
            '</div>'
        )
    if mode == 'insert_after':
        return (
            '<div class="gh-patch-diff">'
            '<div class="small text-muted mb-1">Insert after list item</div>'
            '<div class="small text-muted mb-1">List item anchor</div>'
            f'<pre class="dp-proposal-pre gh-patch-pre mb-2">{html_mod.escape(original)}</pre>'
            f'<pre class="dp-proposal-pre gh-patch-pre mb-0">{html_mod.escape(proposed)}</pre>'
            '</div>'
        )

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
        f'<pre class="dp-proposal-pre gh-patch-pre mb-0">{body}</pre>'
        f'{legend}'
        '</div>'
    )


def render_cfi_patch_card(patch: dict) -> str:
    target_dp = html_mod.escape(patch.get('target_dp') or '–')
    patch_id = html_mod.escape(patch.get('id') or '')
    mode_badge = _patch_mode_badge(patch.get('patch_mode'))
    conf_badge = _confidence_badge(patch.get('confidence'))
    anchor_fit = (patch.get('anchor_fit') or '').strip()
    fit_html = (
        f'<span class="badge bg-light text-dark border ms-1">fit: {html_mod.escape(anchor_fit)}</span>'
        if anchor_fit else ''
    )
    section_ref = (patch.get('anchor_section_ref') or '').strip()
    section_html = (
        f'<div class="small text-muted mb-2">§ {html_mod.escape(section_ref)}</div>'
        if section_ref else ''
    )
    rationale = (patch.get('rationale') or '').strip()
    rationale_html = (
        '<div class="gh-patch-rationale mt-2">'
        '<div class="small text-muted mb-1">Rationale</div>'
        f'<p class="mb-0 small">{html_mod.escape(rationale)}</p>'
        '</div>'
        if rationale else ''
    )
    scores = []
    if patch.get('relevance_score') is not None:
        scores.append(f'relevance {patch.get("relevance_score")}')
    if patch.get('novelty_ratio') is not None:
        scores.append(f'novelty {patch.get("novelty_ratio")}')
    score_html = (
        f'<div class="small text-muted mt-2">{html_mod.escape(", ".join(scores))}</div>'
        if scores else ''
    )

    canopi_msg = (patch.get('canopi_message_id') or '').strip()
    canopi_href = (patch.get('canopi_discuss_href') or '').strip()
    is_promoted = bool(canopi_msg or canopi_href)
    promoted_badge = (
        '<span class="badge bg-success ms-1">On Canopi</span>'
        if is_promoted else ''
    )
    canopi_html = ''
    if canopi_href:
        canopi_html = (
            '<div class="mt-3">'
            f'<a href="{html_mod.escape(canopi_href)}" class="btn btn-sm btn-outline-success" '
            'target="_blank" rel="noopener noreferrer">'
            '<i class="fas fa-comments me-1"></i>View on Canopi Discuss</a>'
            '</div>'
        )
    elif canopi_msg:
        canopi_html = (
            '<div class="mt-2"><span class="badge bg-success">On Canopi</span> '
            f'<code class="small">{html_mod.escape(canopi_msg)}</code></div>'
        )
    else:
        raw_patch_id = patch.get('id') or ''
        canopi_html = (
            '<div class="mt-3">'
            f'<button type="button" class="btn btn-sm btn-success gh-cfi-promote-patch" '
            f'data-patch-id="{html_mod.escape(raw_patch_id)}">'
            '<i class="fas fa-upload me-1"></i>Promote to Canopi</button>'
            '</div>'
        )

    card_class = 'card mb-2 gh-cfi-patch-card'
    if is_promoted:
        card_class += ' border-success gh-cfi-patch-card--promoted'

    return f'''
    <div class="{card_class}" id="cfi-patch-{patch_id}">
      <div class="card-body">
        <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
          <strong class="me-1">{target_dp}</strong>
          {mode_badge}
          {conf_badge}
          {fit_html}
          {promoted_badge}
        </div>
        {section_html}
        {_render_patch_diff(patch)}
        {rationale_html}
        {score_html}
        {canopi_html}
      </div>
    </div>'''


def render_submission_group(group: dict, *, expanded: bool = False) -> str:
    submission_id = html_mod.escape(group.get('submission_id') or '')
    title = html_mod.escape(group.get('title') or submission_id or 'Untitled')
    round_label = group.get('round')
    round_html = (
        f'<span class="badge bg-dark me-2">Round {html_mod.escape(str(round_label))}</span>'
        if round_label is not None else ''
    )
    author = html_mod.escape(
        group.get('attributed_to') or group.get('submitted_by') or 'Unknown',
    )
    patch_count = len(group.get('patches') or [])
    count_label = f'{patch_count} patch{"es" if patch_count != 1 else ""}'
    collapse_id = f'cfi-group-{submission_id.replace(":", "-")}'
    show_class = 'show' if expanded else ''

    cards = ''.join(
        render_cfi_patch_card(patch)
        for patch in (group.get('patches') or [])
    )

    raw_submission_id = group.get('submission_id') or ''
    unpromoted = sum(
        1 for p in (group.get('patches') or [])
        if not (p.get('canopi_message_id') or '').strip()
    )
    promote_group_btn = ''
    if unpromoted > 0 and raw_submission_id:
        promote_group_btn = (
            f'<button type="button" class="btn btn-sm btn-success ms-2 gh-cfi-promote-submission" '
            f'data-submission-id="{html_mod.escape(raw_submission_id)}">'
            f'<i class="fas fa-upload me-1"></i>Promote {unpromoted} to Canopi</button>'
        )

    return f'''
    <div class="accordion-item gh-cfi-submission-group mb-2 border rounded"
         data-submission-id="{submission_id}">
      <h2 class="accordion-header" id="heading-{collapse_id}">
        <button class="accordion-button{' collapsed' if not expanded else ''}" type="button"
                data-bs-toggle="collapse" data-bs-target="#{collapse_id}"
                aria-expanded="{'true' if expanded else 'false'}" aria-controls="{collapse_id}">
          <span class="me-2">{title}</span>
          {round_html}
          <span class="badge bg-primary ms-auto me-2">{html_mod.escape(count_label)}</span>
        </button>
      </h2>
      <div id="{collapse_id}" class="accordion-collapse collapse {show_class}"
           aria-labelledby="heading-{collapse_id}">
        <div class="accordion-body">
          <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
            <div class="small text-muted">
              Submission <code>{submission_id}</code> · {author}
            </div>
            {promote_group_btn}
          </div>
          {cards}
        </div>
      </div>
    </div>'''


def render_cfi_patches_summary(summary: Dict[str, Any]) -> str:
    total = int(summary.get('total_patches') or 0)
    groups = int(summary.get('submission_groups') or 0)
    by_mode = summary.get('by_mode') or {}
    mode_chips = ''.join(
        f'<span class="badge bg-secondary me-1">{html_mod.escape(str(mode))}: {int(count)}</span>'
        for mode, count in sorted(by_mode.items())
        if count
    )
    return f'''
    <div class="alert alert-secondary gh-cfi-patch-summary" role="note">
      <div class="mb-2">
        <strong>{groups}</strong> CFI submission{"s" if groups != 1 else ""} with
        <strong>{total}</strong> proposed patch{"es" if total != 1 else ""}
      </div>
      <div class="d-flex flex-wrap gap-1">{mode_chips}</div>
      <div class="small text-muted mt-2 mb-0">
        Patches are grouped by source CFI submission. Each group may propose changes
        across multiple DPs. Promote to <strong>Canopi Discuss</strong> so readers see
        proposals on the DP book overlay. Status is <em>proposed</em> in the graph until
        promoted.
      </div>
    </div>'''


def render_cfi_patches_page_html(
    export: dict,
    *,
    focus_submission_id: Optional[str] = None,
) -> str:
    if not export.get('ok'):
        err = html_mod.escape(export.get('error') or 'Failed to load CFI patches')
        return f'''
        <div class="alert alert-danger mb-0">
          <i class="fas fa-triangle-exclamation me-2"></i>
          {err}
        </div>'''

    groups: List[dict] = export.get('groups') or []
    if not groups:
        return '''
        <div class="alert alert-info mb-0">
          <i class="fas fa-info-circle me-2"></i>
          No CFI proposed patches in the graph yet. Run Phase 2 propose in dp-memory-graph.
        </div>'''

    summary_html = render_cfi_patches_summary(export.get('summary') or {})
    accordion = '<div class="accordion gh-cfi-patches-accordion" id="cfiPatchesAccordion">'
    for group in groups:
        sid = group.get('submission_id') or ''
        accordion += render_submission_group(
            group,
            expanded=bool(focus_submission_id and sid == focus_submission_id),
        )
    accordion += '</div>'
    return summary_html + accordion
