"""Read-page helpers for sentence-level proposals on /doc/draft/<ref>/read/."""
from __future__ import annotations

import html as html_mod
import json
import os
from typing import Any, Dict, Optional

from config import PROJECT_ROOT

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


READER_GUIDE_DIR = os.path.join(PROJECT_ROOT, 'static', 'images', 'reader-guide')
READER_GUIDE_MANIFEST = os.path.join(READER_GUIDE_DIR, 'manifest.json')


def _is_gif_file(path: str) -> bool:
    try:
        with open(path, 'rb') as handle:
            return handle.read(3) == b'GIF'
    except OSError:
        return False


def reader_guide_gif_urls() -> Dict[str, str]:
    """Resolve guide modal GIF URLs from manifest; only real GIF binaries are used."""
    from config import BUILD_NUMBER

    bust = f'?b={BUILD_NUMBER}'
    names: Dict[str, str] = {}
    try:
        with open(READER_GUIDE_MANIFEST, encoding='utf-8') as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            for key in ('comment', 'propose', 'invite'):
                value = (raw.get(key) or '').strip()
                if value:
                    names[key] = value
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    urls: Dict[str, str] = {}
    for key, filename in names.items():
        if '..' in filename or '/' in filename or '\\' in filename:
            continue
        path = os.path.join(READER_GUIDE_DIR, filename)
        if not _is_gif_file(path):
            continue
        urls[key] = f'/static/images/reader-guide/{filename}{bust}'
    return urls


def render_reader_onboarding_assets() -> str:
    """Onboarding modal + script for approved read pages (not tied to proposal tooling)."""
    guide_gifs = reader_guide_gif_urls()
    return f'''
    <link rel="stylesheet" href="/static/css/dp-proposals-reader.css?v=20260603guiderealgif">
    <div class="modal fade" id="ghReaderGuideModal" tabindex="-1" aria-labelledby="ghReaderGuideTitle" aria-hidden="true">
      <div class="modal-dialog modal-dialog-scrollable gh-reader-guide-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="ghReaderGuideTitle">How to participate on this document</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
            <div class="modal-body">
            <ul class="nav nav-tabs mb-3" role="tablist">
              <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#ghGuideComment" type="button">Comment</button></li>
              <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#ghGuidePropose" type="button">Propose / Edit</button></li>
              <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#ghGuideInvite" type="button">Invite</button></li>
            </ul>
            <div class="tab-content">
              <div class="tab-pane fade show active" id="ghGuideComment">
                <ul class="gh-guide-steps mb-3">
                  <li><strong>Whole document:</strong> click <strong>Add comment</strong> in the toolbar (no text selection needed).</li>
                  <li><strong>On a new passage:</strong> select text to open the compose modal, choose <strong>Comment</strong> and enter comment.</li>
                  <li><strong>On an existing passage:</strong> hover badge to open the context menu, and choose <strong>Add Comment</strong> to open the compose modal, select <strong>Comment</strong> and enter comment.</li>
                  <li><strong>View all comments</strong> anytime via <strong>Comments (N)</strong> in the toolbar.</li>
                </ul>
                <div class="gh-guide-gif">
                  <img src="{guide_gifs['comment']}" data-gh-guide-src="{guide_gifs['comment']}" alt="Demonstration: commenting on a passage and opening the comments panel" width="800" height="500" loading="eager" decoding="async">
                </div>
              </div>
              <div class="tab-pane fade" id="ghGuidePropose">
                <ul class="gh-guide-steps mb-3">
                  <li><strong>On a new passage:</strong> select text to open the compose modal, choose <strong>Propose / Edit</strong> and enter suggested text.</li>
                  <li><strong>On an existing passage:</strong> hover badge to open the context menu, and choose <strong>Suggest a DP Proposal</strong> / <strong>Edit</strong> to open the compose modal, choose <strong>Propose / Edit</strong> and enter suggested text.</li>
                </ul>
                <div class="gh-guide-gif">
                  <img src="{guide_gifs['propose']}" data-gh-guide-src="{guide_gifs['propose']}" alt="Demonstration: selecting text and submitting a proposed edit" width="800" height="500" loading="eager" decoding="async">
                </div>
              </div>
              <div class="tab-pane fade" id="ghGuideInvite">
                <ul class="gh-guide-steps mb-3">
                  <li><strong>Whole document:</strong> Select <strong>Invite</strong> at the top of the page. Copy the shareable link at the top OR enter an email or <strong>@</strong> tag an existing participant.</li>
                  <li><strong>On a new passage:</strong> select text to open the compose modal, choose <strong>Invite</strong> to open the invite modal. Copy the shareable link at the top OR enter an email or <strong>@</strong> tag an existing participant.</li>
                  <li><strong>On an existing passage:</strong> hover badge to open the context menu, and choose <strong>Invite</strong> to open the invite modal. Copy the shareable link at the top OR enter an email or <strong>@</strong> tag an existing participant.</li>
                </ul>
                <div class="gh-guide-gif">
                  <img src="{guide_gifs['invite']}" data-gh-guide-src="{guide_gifs['invite']}" alt="Demonstration: inviting someone to edit the document" width="800" height="500" loading="eager" decoding="async">
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer flex-wrap justify-content-between">
            <div class="form-check mb-0">
              <input class="form-check-input" type="checkbox" id="ghReaderGuideDismiss">
              <label class="form-check-label" for="ghReaderGuideDismiss">Don&apos;t show this again</label>
            </div>
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Got it</button>
          </div>
        </div>
      </div>
    </div>
    <script defer src="/static/js/dp-proposals/reader-onboarding.js?v=20260603guiderealgif"></script>
    '''


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
    <link rel="stylesheet" href="/static/css/dp-proposals-reader.css?v=20260603guidewidth2">
    <div id="dp-proposal-reader-root" data-draft-ref="{draft_ref_esc}" data-meta="{meta_json}"></div>

    <div class="modal fade" id="dpProposalComposeModal" tabindex="-1" aria-labelledby="dpProposalComposeLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header align-items-center flex-wrap gap-2">
            <h5 class="modal-title me-auto" id="dpProposalComposeLabel">{html_mod.escape(labels.get("compose_title", "Suggest a change"))}</h5>
            <div class="btn-group btn-group-sm" role="group" aria-label="Compose mode">
              <button type="button" class="btn btn-primary active" id="dpComposeTabPropose" data-compose-mode="propose">Propose / Edit</button>
              <button type="button" class="btn btn-outline-primary" id="dpComposeTabComment" data-compose-mode="comment">Comment</button>
            </div>
            <button type="button" class="btn btn-sm btn-outline-secondary" id="dpProposalComposeInviteBtn">
              <i class="fas fa-user-plus me-1"></i>Invite
            </button>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <div id="dpComposePanePropose">
              <p class="text-muted small">Original sentence(s) — expanded from your selection.</p>
              <textarea id="dpProposalOriginal" class="form-control font-monospace dp-proposal-pre mb-3" rows="5" readonly></textarea>
              <label class="form-label" for="dpProposalProposed">Proposed text</label>
              <textarea id="dpProposalProposed" class="form-control font-monospace dp-proposal-pre mb-3" rows="5"></textarea>
              <label class="form-label" for="dpProposalRationale">Rationale <span class="text-muted fw-normal">(optional, public)</span></label>
              <textarea id="dpProposalRationale" class="form-control mb-3" rows="2" maxlength="4000"
                placeholder="Why this change improves the standard…"></textarea>
              <label class="form-label" for="dpProposalReferenceUrl">Reference URL <span class="text-muted fw-normal">(optional)</span></label>
              <input type="url" id="dpProposalReferenceUrl" class="form-control" placeholder="https://…" inputmode="url" autocomplete="url">
            </div>
            <div id="dpComposePaneComment" class="d-none">
              <div class="btn-group btn-group-sm w-100 mb-3" role="group" aria-label="Comment scope" id="dpCommentScopeToggle">
                <button type="button" class="btn btn-primary active" id="dpCommentScopeDocument" data-comment-scope="document">Whole document</button>
                <button type="button" class="btn btn-outline-primary" id="dpCommentScopePassage" data-comment-scope="passage">Selected passage</button>
              </div>
              <p class="text-muted small mb-2" id="dpCommentScopeHint">Your comment applies to the full document. It appears on the Comments page and does not highlight text.</p>
              <div id="dpCommentPassageBlock" class="d-none">
                <p class="text-muted small" id="dpCommentPassageHint">Comment is anchored to this passage:</p>
                <textarea id="dpCommentPassage" class="form-control font-monospace dp-proposal-pre mb-3" rows="3" readonly></textarea>
              </div>
              <label class="form-label" for="dpCommentText">Your comment</label>
              <textarea id="dpCommentText" class="form-control mb-2" rows="5" maxlength="8000"
                placeholder="Share your feedback…"></textarea>
              <p class="form-text mb-0">Passage comments are linked to highlighted text. Whole-document comments are general feedback without a highlight.</p>
            </div>
            <div id="dpProposalComposeError" class="alert alert-danger mt-3 d-none" role="alert"></div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
            <button type="button" class="btn btn-primary d-none" id="dpProposalSubmitBtn" disabled>{html_mod.escape(labels.get("post_button", "Post proposal"))}</button>
            <button type="button" class="btn btn-primary" id="dpCommentSubmitBtn" disabled>Post comment</button>
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
    <script defer src="/static/js/dp-proposals/reader.js?v=20260603n"></script>
    '''
