"""Read-page helpers for sentence-level proposals on /doc/draft/<ref>/read/."""
from __future__ import annotations

import html as html_mod
import json
from typing import Any, Dict, Optional

from models import Submission
from services.dp_proposals import (
    can_accept_amendments,
    can_manage_amendments,
    is_dp_submission,
    workgroup_for_submission,
)
from services.identity import get_current_user
from services.proposal_modes import is_mode_enabled, mode_labels, proposal_mode_for_submission


def is_reader_body_selectable(*, render_html: bool, document_content: str) -> bool:
    """Text selection works on HTML/plain pre bodies, not PDF iframes."""
    if not render_html:
        return True
    low = (document_content or '').lower()
    if 'pdf-viewer-container' in low or '<iframe' in low:
        return False
    return True


def build_read_meta(
    submission: Submission,
    draft_ref: str,
    *,
    render_html: bool,
    document_content: str,
) -> Dict[str, Any]:
    current_user = get_current_user()
    wg = workgroup_for_submission(submission)
    can_manage = bool(current_user and can_manage_amendments(current_user, wg))
    can_accept = bool(current_user and can_accept_amendments(current_user))
    mode = proposal_mode_for_submission(submission)
    labels = mode_labels(mode)
    enabled = is_mode_enabled(mode)
    is_dp = is_dp_submission(submission)
    return {
        'draft_ref': draft_ref,
        'submission_id': submission.id,
        'mode': mode,
        'scope': mode,
        'is_dp': is_dp,
        'proposals_enabled': enabled,
        'selectable': is_reader_body_selectable(
            render_html=render_html,
            document_content=document_content,
        ),
        'content_hash': submission.content_hash,
        'can_manage_amendments': can_manage,
        'can_accept_amendments': can_accept,
        'authenticated': bool(current_user),
        'labels': labels,
    }


def render_dp_proposal_reader_assets(
    submission: Optional[Submission],
    draft_ref: str,
    *,
    render_html: bool,
    document_content: str,
) -> str:
    """Return HTML/CSS/JS to inject on read page, or empty when not applicable."""
    if not submission or submission.status != 'approved':
        return ''
    meta = build_read_meta(
        submission,
        draft_ref,
        render_html=render_html,
        document_content=document_content,
    )
    if not meta.get('proposals_enabled') or not meta.get('selectable'):
        return ''

    labels = meta.get('labels') or {}
    meta_json = html_mod.escape(json.dumps(meta), quote=True)
    draft_ref_esc = html_mod.escape(draft_ref, quote=True)

    return f'''
    <link rel="stylesheet" href="/static/css/dp-proposals-reader.css?v=20260528c">
    <div id="dp-proposal-reader-root" data-draft-ref="{draft_ref_esc}" data-meta="{meta_json}"></div>

    <div class="modal fade" id="dpProposalComposeModal" tabindex="-1" aria-labelledby="dpProposalComposeLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header align-items-center">
            <h5 class="modal-title me-auto" id="dpProposalComposeLabel">{html_mod.escape(labels.get("compose_title", "Suggest a change"))}</h5>
            <button type="button" class="btn btn-sm btn-outline-secondary me-2" id="dpProposalComposeInviteBtn">
              <i class="fas fa-user-plus me-1"></i>Invite to edit
            </button>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p class="text-muted small">Original sentence(s) — expanded from your selection.</p>
            <textarea id="dpProposalOriginal" class="form-control font-monospace dp-proposal-pre mb-3" rows="6" readonly></textarea>
            <label class="form-label" for="dpProposalProposed">Proposed text</label>
            <textarea id="dpProposalProposed" class="form-control font-monospace dp-proposal-pre mb-3" rows="6"></textarea>
            <label class="form-label" for="dpProposalRationale">Rationale <span class="text-muted fw-normal">(optional, public)</span></label>
            <textarea id="dpProposalRationale" class="form-control mb-3" rows="3" maxlength="4000"
              placeholder="Why this change improves the standard…"></textarea>
            <label class="form-label" for="dpProposalReferenceUrl">Reference URL <span class="text-muted fw-normal">(optional)</span></label>
            <input type="url" id="dpProposalReferenceUrl" class="form-control" placeholder="https://…" inputmode="url" autocomplete="url">
            <div id="dpProposalComposeError" class="alert alert-danger mt-3 d-none" role="alert"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-primary" id="dpProposalSubmitBtn" disabled>{html_mod.escape(labels.get("post_button", "Post proposal"))}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" id="dpProposalListModal" tabindex="-1" aria-labelledby="dpProposalListLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="dpProposalListLabel">{html_mod.escape(labels.get("list_title", "Proposals on this passage"))}</h5>
            <div class="form-check form-switch ms-auto me-3 mb-0">
              <input class="form-check-input" type="checkbox" id="dpProposalShowDiffToggle">
              <label class="form-check-label small" for="dpProposalShowDiffToggle">Show changes</label>
            </div>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body" id="dpProposalListBody"></div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-primary" id="dpProposalListAddBtn">{html_mod.escape(labels.get("list_add", "Suggest a change"))}</button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
          </div>
        </div>
      </div>
    </div>

    <script src="/static/js/dp-proposals/sentence-tools.js?v=20260527h"></script>
    <script src="/static/js/dp-proposals/proposal-display.js?v=20260526h"></script>
    <script defer src="/static/js/dp-proposals/reader.js?v=20260528c"></script>
    '''
