/**
 * Patch read-page UI: selection → compose modal → badges → list modal.
 */
(function (global) {
  'use strict';

  var PENDING_STORAGE_KEY = 'ghDpProposalPending';

  var root = document.getElementById('dp-proposal-reader-root');
  if (!root) return;

  var meta;
  try {
    meta = JSON.parse(root.getAttribute('data-meta') || '{}');
  } catch (_e) {
    return;
  }
  if (!meta.proposals_enabled || !meta.selectable) return;

  var labels = meta.labels || {};
  function label(key, fallback) {
    return labels[key] || fallback;
  }

  function countPhrase(n) {
    var word = label('count_word', 'patch');
    return String(n) + ' ' + word + (n === 1 ? '' : 's');
  }

  var draftRef = root.getAttribute('data-draft-ref') || meta.draft_ref;
  var bodyEl = document.getElementById('dp-reader-selectable-body');
  if (!bodyEl || !window.DpSentenceTools) return;

  var tools = window.DpSentenceTools;
  var proposals = [];
  var readerComments = [];
  var anchorRegistry = [];
  var displayMode = localStorage.getItem('dpProposalDisplay:' + draftRef) || 'showAll';
  var showDiff = localStorage.getItem('dpProposalShowDiff:' + draftRef) === 'true';
  var composeModalEl = document.getElementById('dpProposalComposeModal');
  var listModalEl = document.getElementById('dpProposalListModal');
  var pendingSelection = null;
  var composeMode = 'propose';
  var commentScopeMode = 'document';
  var COMPOSE_MODE_KEY = 'gh_compose_mode';
  var COMMENT_SCOPE_KEY = 'gh_comment_scope';
  var MAX_DISTANCE = 320;
  var PROXIMITY_SHOW_THRESHOLD = 0.04;
  var PROXIMITY_BADGE_MIN_OPACITY = 0.35;
  var DISPLAY_MODE_ICONS = {
    hidden:
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
    attention:
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></svg>',
    showAll:
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
  };
  var lastPointer = { x: -1, y: -1 };
  var hoverHideTimer = null;
  var activeHoverWrap = null;
  /** While set, keep one anchor's highlights visible (deep-link flash after reader guide). */
  var anchorFlashLock = null;
  var ANCHOR_FLASH_MS = 3200;
  var ANCHOR_FLASH_SCROLL_DELAY_MS = 500;

  function apiUrl(path) {
    return '/api/doc/draft/' + encodeURIComponent(draftRef) + path;
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function whenBootstrapReady(fn) {
    if (window.bootstrap) {
      fn();
      return;
    }
    var attempts = 0;
    (function tick() {
      if (window.bootstrap) fn();
      else if (++attempts < 100) setTimeout(tick, 25);
    })();
  }

  function getComposeModal() {
    if (!composeModalEl || !window.bootstrap) return null;
    return bootstrap.Modal.getOrCreateInstance(composeModalEl);
  }

  function getListModal() {
    if (!listModalEl || !window.bootstrap) return null;
    return bootstrap.Modal.getOrCreateInstance(listModalEl);
  }

  function statusBadgeClass(status) {
    if (status === 'accepted') return 'bg-success';
    if (status === 'declined') return 'bg-secondary';
    if (status === 'orphaned') return 'bg-warning text-dark';
    if (status === 'incorporated') return 'bg-info text-dark';
    return 'bg-primary';
  }

  function setDisplayMode(mode) {
    displayMode = mode;
    localStorage.setItem('dpProposalDisplay:' + draftRef, displayMode);
    refreshDisplayModeOptions();
    syncDisplayMode();
  }

  function parseContextAnchor(proposal) {
    var raw = proposal.context_anchor;
    if (!raw) return null;
    if (typeof raw === 'object') return raw;
    try {
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  function focusedTextForProposal(proposal) {
    if (display && display.focusedPassageCore) {
      var core = display.focusedPassageCore(
        proposal.original_text || '',
        proposal.proposed_text || ''
      );
      if (core.original) return core.original;
    }
    return proposal.original_text || '';
  }

  function refineLocatedToFocus(located, focus) {
    if (!located || !focus || !tools.normalizeForMatch) return located;
    var hay = tools.normalizeForMatch(located.map.text);
    var f = tools.normalizeForMatch(focus).trim();
    if (!f) return located;
    var inner = hay.slice(located.start, located.end);
    var rel = inner.indexOf(f);
    if (rel >= 0) {
      return {
        start: located.start + rel,
        end: located.start + rel + f.length,
        map: located.map,
      };
    }
    if (tools.expandToSentences) {
      var expanded = tools.expandToSentences(f, hay);
      var e = tools.normalizeForMatch(expanded).trim();
      var idx = hay.indexOf(e);
      if (idx >= 0) {
        return { start: idx, end: idx + e.length, map: located.map };
      }
    }
    var idxOnly = hay.indexOf(f);
    if (idxOnly >= 0) {
      return { start: idxOnly, end: idxOnly + f.length, map: located.map };
    }
    return located;
  }

  function locateProposalInDocument(proposal) {
    var anchor = parseContextAnchor(proposal);
    var textQuote = anchor && anchor.textQuote;
    var focus = focusedTextForProposal(proposal);
    var located = null;

    if (focus) {
      located = tools.locateTextInRoot(bodyEl, {
        original_text: focus,
        textQuote: null,
      });
      if (located) return refineLocatedToFocus(located, focus);
    }

    if (textQuote && focus) {
      var narrowQuote = Object.assign({}, textQuote, { exact: focus });
      located = tools.locateTextInRoot(bodyEl, {
        original_text: focus,
        textQuote: narrowQuote,
      });
      if (located) return refineLocatedToFocus(located, focus);
    }

    if (textQuote) {
      located = tools.locateTextInRoot(bodyEl, {
        original_text: proposal.original_text,
        textQuote: textQuote,
      });
      if (located && focus) return refineLocatedToFocus(located, focus);
      if (located) return located;
    }

    located = tools.locateTextInRoot(bodyEl, {
      original_text: proposal.original_text,
      textQuote: null,
    });
    if (located && focus) return refineLocatedToFocus(located, focus);
    return located;
  }

  function locateCommentInDocument(comment) {
    if (!comment) return null;
    var anchor = comment.context_anchor;
    var textQuote = anchor && anchor.textQuote;
    var focus = (comment.original_text || '').trim();
    if (!focus) {
      focus = (comment.passage_excerpt || '').replace(/\u2026$/, '').trim();
    }
    if (!focus) return null;
    var located = tools.locateTextInRoot(bodyEl, {
      original_text: focus,
      textQuote: textQuote || null,
    });
    if (located) return refineLocatedToFocus(located, focus);
    if (textQuote) {
      located = tools.locateTextInRoot(bodyEl, {
        original_text: focus,
        textQuote: textQuote,
      });
      if (located) return refineLocatedToFocus(located, focus);
    }
    return null;
  }

  function flattenPassageComments(list, out) {
    out = out || [];
    (list || []).forEach(function (c) {
      if (c && c.comment_scope === 'passage' && c.anchor_hash) {
        out.push(c);
      }
      flattenPassageComments(c.replies, out);
    });
    return out;
  }

  function passageActivityCount(bundle) {
    return (bundle.proposals ? bundle.proposals.length : 0) +
      (bundle.comments ? bundle.comments.length : 0);
  }

  function passageOriginalFromBundle(bundle) {
    if (bundle.proposals && bundle.proposals[0]) {
      return bundle.proposals[0].original_text;
    }
    if (bundle.comments && bundle.comments[0]) {
      var c = bundle.comments[0];
      return c.original_text || (c.passage_excerpt || '').replace(/\u2026$/, '').trim();
    }
    return '';
  }

  function isAnchorFlashActive(hash) {
    return !!(anchorFlashLock && anchorFlashLock.hash === hash &&
      Date.now() < anchorFlashLock.until);
  }

  function revealAnchorForFlash(hash, flashTargets, entry) {
    anchorFlashLock = { hash: hash, until: Date.now() + ANCHOR_FLASH_MS };
    if (entry) {
      repositionEntryOverlays(entry);
      positionPin(entry);
    }
    var layer = bodyEl.querySelector('.dp-proposal-highlight-layer');
    if (layer) {
      layer.classList.remove('dp-proposal-highlight-layer-hidden');
    }
    flashTargets.forEach(function (box) {
      box.classList.remove('dp-proposal-highlight-hidden', 'dp-proposal-highlight-dim');
      box.classList.add('gh-anchor-flash-hold');
      box.style.opacity = '1';
      box.style.visibility = 'visible';
      box.style.pointerEvents = 'auto';
    });
    if (entry && entry.pin) {
      entry.pin.style.display = '';
      var badge = entry.pin.querySelector('.dp-proposal-badge');
      if (badge) {
        badge.style.opacity = '1';
        badge.style.pointerEvents = 'auto';
      }
    }
  }

  function clearAnchorFlash(flashTargets) {
    anchorFlashLock = null;
    (flashTargets || []).forEach(function (box) {
      box.classList.remove('gh-anchor-flash', 'gh-anchor-flash-hold');
      box.style.removeProperty('opacity');
      box.style.removeProperty('visibility');
      box.style.removeProperty('pointer-events');
    });
    syncDisplayMode();
  }

  function scrollToGhAnchor(hash) {
    if (!hash) return false;
    var entry = null;
    anchorRegistry.forEach(function (e) {
      if (e.hash === hash) entry = e;
    });
    var el = document.getElementById('gh-anchor-' + hash);
    var flashTargets = [];
    if (el) flashTargets.push(el);
    if (entry && entry.boxes) {
      entry.boxes.forEach(function (box) {
        if (flashTargets.indexOf(box) < 0) flashTargets.push(box);
      });
    }
    if (!flashTargets.length) return false;
    revealAnchorForFlash(hash, flashTargets, entry);
    (el || flashTargets[0]).scrollIntoView({ behavior: 'smooth', block: 'center' });
    global.setTimeout(function () {
      if (!isAnchorFlashActive(hash)) return;
      flashTargets.forEach(function (box) {
        box.classList.add('gh-anchor-flash');
      });
    }, ANCHOR_FLASH_SCROLL_DELAY_MS);
    global.setTimeout(function () {
      flashTargets.forEach(function (box) {
        box.classList.remove('gh-anchor-flash');
      });
      clearAnchorFlash(flashTargets);
    }, ANCHOR_FLASH_MS);
    return true;
  }

  function whenReaderGuideBypassed(fn) {
    if (global.GhReaderGuide && typeof global.GhReaderGuide.whenBypassed === 'function') {
      global.GhReaderGuide.whenBypassed(fn);
      return;
    }
    global.setTimeout(fn, 400);
  }

  function scrollToGhAnchorFromLocation() {
    var h = (global.location.hash || '').replace(/^#/, '');
    if (!h || h.indexOf('gh-anchor-') !== 0) return;
    var hash = h.slice('gh-anchor-'.length);
    whenReaderGuideBypassed(function () {
      global.setTimeout(function () {
        scrollToGhAnchor(hash);
      }, 150);
    });
  }

  var display = window.DpProposalDisplay || null;

  function truncateTexts(original, proposed) {
    if (display && display.truncateUnchangedSentences) {
      return display.truncateUnchangedSentences(original, proposed);
    }
    return { original: original, proposed: proposed, trimmedStart: false, trimmedEnd: false };
  }

  function renderProposalBody(original, proposed, diffOn) {
    var trimmed = truncateTexts(original, proposed);
    var origHtml;
    if (diffOn && display && display.buildDiffHtml) {
      origHtml = display.buildDiffHtml(trimmed.original, trimmed.proposed);
    } else if (display && display.formatPreHtml) {
      origHtml = display.formatPreHtml(trimmed.original);
    } else {
      origHtml = esc(trimmed.original);
    }
    var propHtml = display && display.formatPreHtml
      ? display.formatPreHtml(trimmed.proposed)
      : esc(trimmed.proposed);
    return (
      '<div class="dp-proposal-card-label">Original</div>' +
      '<div class="dp-proposal-card-original dp-proposal-pre-block' +
      (diffOn ? '' : ' dp-proposal-plain-original') + '">' + origHtml + '</div>' +
      '<div class="dp-proposal-card-label mt-3">' + esc(label('proposed_label', 'Patched text')) + '</div>' +
      '<div class="dp-proposal-card-proposed dp-proposal-pre-block">' + propHtml + '</div>'
    );
  }

  function anchorRectFromWrap(wrap) {
    if (!wrap) {
      return {
        left: window.scrollX + 24,
        top: window.scrollY + 120,
        width: 0,
        height: 0,
      };
    }
    var domRect = wrap.getBoundingClientRect();
    return {
      left: domRect.left + window.scrollX,
      top: domRect.top + window.scrollY,
      width: domRect.width,
      height: domRect.height,
    };
  }

  function proposalLinkTitle(p, index) {
    return label('link_prefix', 'Patch') + ' ' + (index + 1);
  }

  function truncateText(text, maxLen) {
    var s = String(text || '').replace(/\s+/g, ' ').trim();
    if (!s) return '';
    if (s.length <= maxLen) return s;
    return s.slice(0, Math.max(0, maxLen - 1)) + '…';
  }

  function hoverRowLabel(p, index) {
    var parts = [];
    if (p.author_name) parts.push(p.author_name);
    if (p.status_label && !p.rationale) parts.push(p.status_label);
    var main = parts.length ? parts.join(' · ') : proposalLinkTitle(p, index);
    if (p.rationale) {
      main += ' · "' + truncateText(p.rationale, 80) + '"';
    }
    return main;
  }

  function renderProposalHeaderHtml(p) {
    var author =
      '<small class="text-muted">' + esc(p.author_name || 'Anonymous') + '</small>';
    if (p.rationale) {
      return '<div class="d-flex justify-content-end align-items-start gap-2 dp-proposal-list-header">' +
        author + '</div>';
    }
    return '<div class="d-flex justify-content-between align-items-start gap-2 dp-proposal-list-header">' +
      '<span class="badge ' + statusBadgeClass(p.status) + '">' + esc(p.status_label) + '</span>' +
      author + '</div>';
  }

  function referenceHost(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch (_e) {
      return 'link';
    }
  }

  function renderProposalMetaHtml(p) {
    var html = '';
    if (p.rationale) {
      html += '<div class="dp-proposal-meta-block"><div class="small text-muted mb-1">Rationale</div>' +
        '<div class="dp-proposal-rationale">' + esc(p.rationale) + '</div>';
      if (p.reference_url) {
        html += '<div class="small text-muted mb-1 mt-2">Reference</div>' +
          '<a class="dp-proposal-reference" href="' + esc(p.reference_url) + '" target="_blank" rel="noopener noreferrer">' +
          esc(referenceHost(p.reference_url)) + ' — ' + esc(p.reference_url) + '</a>';
      }
      html += '</div>';
    } else if (p.reference_url) {
      html += '<div class="dp-proposal-meta-block"><div class="small text-muted mb-1">Reference</div>' +
        '<a class="dp-proposal-reference" href="' + esc(p.reference_url) + '" target="_blank" rel="noopener noreferrer">' +
        esc(referenceHost(p.reference_url)) + ' — ' + esc(p.reference_url) + '</a></div>';
    }
    return html;
  }

  function proposalCharDeltaHtml(original, proposed) {
    if (display && display.formatCharDeltaHtml) {
      return display.formatCharDeltaHtml(original, proposed);
    }
    var o = String(original || '');
    var p = String(proposed || '');
    var added = Math.max(0, p.length - o.length);
    var removed = Math.max(0, o.length - p.length);
    var html = '<span class="dp-proposal-char-delta">';
    if (added) html += '<span class="dp-proposal-char-plus">+' + added + '</span>';
    if (removed) html += '<span class="dp-proposal-char-minus">-' + removed + '</span>';
    if (!added && !removed) html += '<span class="dp-proposal-char-neutral">0</span>';
    return html + '</span>';
  }

  function openHoverRowProposal(row) {
    if (!row) return;
    if (hoverHideTimer) {
      clearTimeout(hoverHideTimer);
      hoverHideTimer = null;
    }
    hideHoverPanel(true);
    openListModal(row.getAttribute('data-hash'), row.getAttribute('data-proposal-id'));
  }

  function commentHoverLabel(c) {
    var main = (c.author || 'Comment');
    if (c.text) {
      main += ' · "' + truncateText(c.text, 80) + '"';
    }
    return main;
  }

  function findCommentById(id) {
    var found = null;
    function walk(list) {
      (list || []).forEach(function (c) {
        if (c.id === id) {
          found = c;
        }
        walk(c.replies);
      });
    }
    walk(readerComments);
    return found;
  }

  function formatCommentTimestamp(iso) {
    if (!iso) return '';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString();
    } catch (_e) {
      return iso;
    }
  }

  function showCommentDetailInPanel(panel, c, bundle, hash) {
    if (!panel || !c) return;
    var scopeLabel = c.comment_scope === 'passage' ? 'Passage comment' : 'Whole-document comment';
    var excerpt = (c.passage_excerpt || c.original_text || '').trim();
    var html = '<button type="button" class="btn btn-sm btn-link dp-hover-back p-0 mb-2">&larr; Back to list</button>' +
      '<div class="dp-comment-detail">' +
      '<div class="small text-muted mb-1">' + esc(scopeLabel) + '</div>' +
      '<div class="fw-semibold mb-1">' + esc(c.author || 'Comment') + '</div>' +
      '<div class="small text-muted mb-2">' + esc(formatCommentTimestamp(c.timestamp)) + '</div>';
    if (excerpt && c.comment_scope === 'passage') {
      html += '<blockquote class="small text-muted border-start ps-2 mb-2">' + esc(excerpt) + '</blockquote>';
    }
    html += '<p class="dp-comment-detail-text mb-2">' + esc(c.text || '') + '</p>';
    var docLink = commentsPageUrl() + '#comment-' + encodeURIComponent(c.id);
    if (c.comment_scope === 'passage' && c.anchor_hash) {
      docLink = '/doc/draft/' + encodeURIComponent(draftRef) + '/read/#gh-anchor-' +
        encodeURIComponent(c.anchor_hash);
      html += '<a href="' + esc(docLink) +
        '" class="btn btn-sm btn-outline-info me-2">Go to highlighted passage</a>';
    }
    html += '<a href="' + esc(commentsPageUrl() + '#comment-' + encodeURIComponent(c.id)) +
      '" class="small">Open on Comments page</a></div>';
    if (c.can_edit || c.can_delete) {
      html += '<div class="dp-comment-detail-actions d-flex flex-wrap gap-2 mt-3">';
      if (c.can_edit) {
        html += '<button type="button" class="btn btn-sm btn-outline-warning dp-comment-edit-btn">Edit</button>';
      }
      if (c.can_delete) {
        html += '<button type="button" class="btn btn-sm btn-outline-danger dp-comment-delete-btn">Delete</button>';
      }
      html += '<span class="small text-muted align-self-center">Within ' +
        esc(String(c.edit_window_minutes || 15)) + ' min of posting</span></div>';
    }
    panel.innerHTML = html;
    panel.dataset.ghDetailCommentId = c.id;
    var backBtn = panel.querySelector('.dp-hover-back');
    if (backBtn) {
      backBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        delete panel.dataset.ghDetailCommentId;
        renderHoverPanelBody(panel, bundle, hash);
      });
    }
    var editBtn = panel.querySelector('.dp-comment-edit-btn');
    if (editBtn) {
      editBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var next = window.prompt('Edit your comment:', c.text || '');
        if (next == null) return;
        next = next.trim();
        if (!next) return;
        fetch(apiUrl('/reader-comments/' + encodeURIComponent(c.id) + '/'), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ text: next }),
        })
          .then(parseJsonResponse)
          .then(function (res) {
            if (!res.ok) {
              window.alert(res.data.error || 'Could not update comment');
              return;
            }
            loadReaderComments().then(rebuildPassageAnchors);
            hideHoverPanel(true);
          });
      });
    }
    var delBtn = panel.querySelector('.dp-comment-delete-btn');
    if (delBtn) {
      delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (!window.confirm('Delete this comment?')) return;
        fetch(apiUrl('/reader-comments/' + encodeURIComponent(c.id) + '/'), {
          method: 'DELETE',
          credentials: 'same-origin',
        })
          .then(parseJsonResponse)
          .then(function (res) {
            if (!res.ok) {
              window.alert(res.data.error || 'Could not delete comment');
              return;
            }
            loadReaderComments().then(rebuildPassageAnchors);
            hideHoverPanel(true);
          });
      });
    }
  }

  function renderHoverPanelBody(panel, bundle, hash) {
    delete panel.dataset.ghDetailCommentId;
    var html = '<div class="dp-hover-panel-title small fw-semibold mb-2">Context Menu</div>';
    if (bundle.proposals && bundle.proposals.length) {
      html += '<div class="small text-muted mb-1">' + esc(label('hover_section', 'Patches')) + '</div><ul class="dp-proposal-hover-links">';
      bundle.proposals.forEach(function (p, idx) {
        var deltaHtml = proposalCharDeltaHtml(p.original_text, p.proposed_text);
        var rowLabel = hoverRowLabel(p, idx);
        html += '<li class="dp-proposal-hover-row" role="button" tabindex="0"' +
          ' data-proposal-id="' + esc(p.id) + '" data-hash="' + esc(p.anchor_hash || hash) + '"' +
          ' title="' + esc(rowLabel) + '" aria-label="' + esc(rowLabel) + '">' +
          '<span class="dp-proposal-hover-link">' +
          '<i class="fas fa-pen-fancy" aria-hidden="true"></i>' +
          '<span class="dp-proposal-hover-link-main">' + esc(rowLabel) + '</span>' +
          deltaHtml + '</span></li>';
      });
      html += '</ul>';
    }
    if (bundle.comments && bundle.comments.length) {
      html += '<div class="small text-muted mb-1 mt-2">Comments</div><ul class="dp-proposal-hover-links">';
      bundle.comments.forEach(function (c) {
        var rowLabel = commentHoverLabel(c);
        html += '<li class="dp-proposal-hover-row dp-comment-hover-row" role="button" tabindex="0"' +
          ' data-comment-id="' + esc(c.id) + '" data-hash="' + esc(hash) + '"' +
          ' title="' + esc(rowLabel) + '" aria-label="' + esc(rowLabel) + '">' +
          '<span class="dp-proposal-hover-link">' +
          '<i class="fas fa-comment" aria-hidden="true"></i>' +
          '<span class="dp-proposal-hover-link-main">' + esc(rowLabel) + '</span></span></li>';
      });
      html += '</ul>';
    }
    html += '<div class="dp-proposal-hover-actions">' +
      '<button type="button" class="btn btn-primary btn-sm w-100 dp-proposal-create-btn">' +
      '<i class="fas fa-plus me-1"></i>' + esc(label('create_hover', 'Propose a patch')) + '</button>' +
      '<button type="button" class="btn btn-outline-info btn-sm w-100 dp-passage-add-comment-btn">' +
      '<i class="fas fa-comment-medical me-1"></i>Add comment</button>' +
      '<button type="button" class="btn btn-outline-secondary btn-sm w-100 dp-proposal-invite-passage-btn" data-hash="' +
      esc(hash) + '"><i class="fas fa-user-plus me-1"></i>Invite to edit</button>' +
      '</div>';
    panel.innerHTML = html;
    if (!panel.dataset.ghHoverPanelBound) {
      panel.dataset.ghHoverPanelBound = '1';
      panel.addEventListener('mousedown', function (e) {
        if (hoverHideTimer) {
          clearTimeout(hoverHideTimer);
          hoverHideTimer = null;
        }
        e.stopPropagation();
      });
    }
    panel.querySelectorAll('.dp-proposal-hover-row').forEach(function (row) {
      row.addEventListener('mousedown', function (e) {
        e.preventDefault();
        e.stopPropagation();
      });
      row.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (row.classList.contains('dp-comment-hover-row')) {
          var cid = row.getAttribute('data-comment-id');
          var comment = findCommentById(cid);
          if (comment) {
            showCommentDetailInPanel(panel, comment, bundle, hash);
          }
          return;
        }
        openHoverRowProposal(row);
      });
      row.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (row.classList.contains('dp-comment-hover-row')) {
            var cid = row.getAttribute('data-comment-id');
            var comment = findCommentById(cid);
            if (comment) {
              showCommentDetailInPanel(panel, comment, bundle, hash);
            }
            return;
          }
          openHoverRowProposal(row);
        }
      });
    });
    var createBtn = panel.querySelector('.dp-proposal-create-btn');
    if (createBtn) {
      createBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        hideHoverPanel(true);
        pendingSelection = {
          original: passageOriginalFromBundle(bundle),
          blockText: bodyEl.textContent || '',
        };
        setComposeMode('propose');
        whenBootstrapReady(openComposeModal);
      });
    }
    var commentBtn = panel.querySelector('.dp-passage-add-comment-btn');
    if (commentBtn) {
      commentBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        hideHoverPanel(true);
        pendingSelection = {
          original: passageOriginalFromBundle(bundle),
          blockText: bodyEl.textContent || '',
        };
        whenBootstrapReady(function () {
          openComposeModal({ composeMode: 'comment', commentScope: 'passage' });
        });
      });
    }
    var inviteBtn = panel.querySelector('.dp-proposal-invite-passage-btn');
    if (inviteBtn) {
      inviteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        hideHoverPanel(true);
        openPassageInvite(inviteBtn.getAttribute('data-hash') || hash, bundle.proposals);
      });
    }
  }

  function inviteUnavailable() {
    if (global.GhDialog && global.GhDialog.alert) {
      global.GhDialog.alert({
        title: 'Invite unavailable',
        message: 'Please refresh the page and try again.',
        variant: 'warning',
      });
      return;
    }
    window.alert('Invite is not ready. Please refresh the page.');
  }

  function openGhInvite(opts) {
    whenBootstrapReady(function () {
      if (!meta.authenticated) {
        window.location.href =
          '/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search);
        return;
      }
      if (!global.GhInvite || !global.GhInvite.open) {
        inviteUnavailable();
        return;
      }
      global.GhInvite.open(opts);
    });
  }

  function passageInviteTarget(anchorHash, group, originalText) {
    var target = {
      submission_id: meta.submission_id,
      draft_ref: draftRef,
    };
    if (anchorHash) {
      target.anchor_hash = anchorHash;
    }
    if (group && group[0] && group[0].context_anchor) {
      target.context_anchor = group[0].context_anchor;
    } else if (originalText) {
      target.context_anchor = {
        textQuote: tools.buildTextQuoteSelector(
          bodyEl.textContent || '',
          originalText
        ),
      };
    }
    return target;
  }

  function openPassageInvite(anchorHash, group) {
    openGhInvite({
      type: 'edit_document_passage',
      title: 'Invite to edit this passage',
      hint: 'They will get an email to open this document and propose a patch here.',
      target: passageInviteTarget(
        anchorHash,
        group,
        group && group[0] ? group[0].original_text : null
      ),
    });
  }

  function openComposePassageInvite() {
    if (!pendingSelection || !pendingSelection.original) {
      inviteUnavailable();
      return;
    }
    openGhInvite({
      type: 'edit_document_passage',
      title: 'Invite to edit this passage',
      hint: 'They will get an email to open this document and propose a patch on this passage.',
      target: passageInviteTarget(null, null, pendingSelection.original),
    });
  }

  function openDocumentInvite(btn) {
    openGhInvite({
      type: 'edit_document',
      title: 'Invite to edit this document',
      hint: 'They will get an email to review the full document and propose patches.',
      target: {
        submission_id: (btn && btn.getAttribute('data-submission-id')) || meta.submission_id,
        draft_ref: (btn && btn.getAttribute('data-draft-ref')) || draftRef,
      },
    });
  }

  function bindInviteControls() {
    if (document.body.dataset.ghReaderInviteBound) return;
    document.body.dataset.ghReaderInviteBound = '1';
    document.addEventListener('click', function (e) {
      var addCommentBtn = e.target.closest && e.target.closest('#draftReaderAddComment');
      if (addCommentBtn) {
        e.preventDefault();
        openDocumentCommentModal();
        return;
      }
      var toolbarBtn = e.target.closest && e.target.closest('#draftReaderInviteDoc');
      if (toolbarBtn) {
        e.preventDefault();
        openDocumentInvite(toolbarBtn);
        return;
      }
      var composeBtn = e.target.closest && e.target.closest('#dpProposalComposeInviteBtn');
      if (composeBtn) {
        e.preventDefault();
        openComposePassageInvite();
      }
    });
  }

  var HOVER_PANEL_FADE_MS = 200;
  var HOVER_PANEL_HIDE_DELAY_MS = 120;
  /** Delay before badge hover opens the panel (avoids open when badge fades in under cursor). */
  var BADGE_HOVER_OPEN_DELAY_MS = 220;
  var BADGE_POINTER_EVENTS_MIN_OPACITY = 0.45;

  function isDpProposalHoverTarget(el) {
    if (!el || !el.closest) return false;
    return !!el.closest(
      '.dp-proposal-hover-panel, .dp-proposal-pin, .dp-proposal-badge, .dp-proposal-highlight-rect'
    );
  }

  function finishHideHoverPanel(panel) {
    if (!panel) return;
    panel.classList.remove('is-open', 'is-fading-out');
    panel.style.left = '';
    panel.style.top = '';
    panel.style.visibility = '';
    var hash = panel.dataset.dpAnchorHash;
    if (hash) {
      var pin = document.querySelector('.dp-proposal-pin[data-dp-anchor-hash="' + hash + '"]');
      if (pin && panel.parentNode === document.body) {
        pin.appendChild(panel);
      }
    }
  }

  function hideHoverPanel(immediate) {
    if (hoverHideTimer) {
      clearTimeout(hoverHideTimer);
      hoverHideTimer = null;
    }
    var panels = document.querySelectorAll(
      '.dp-proposal-hover-panel.is-open, .dp-proposal-hover-panel.is-fading-out'
    );
    panels.forEach(function (panel) {
      if (immediate) {
        finishHideHoverPanel(panel);
        return;
      }
      if (panel.classList.contains('is-fading-out')) return;
      panel.classList.remove('is-open');
      panel.classList.add('is-fading-out');
      function onFadeEnd(e) {
        if (e.target !== panel || e.propertyName !== 'opacity') return;
        panel.removeEventListener('transitionend', onFadeEnd);
        finishHideHoverPanel(panel);
      }
      panel.addEventListener('transitionend', onFadeEnd);
      setTimeout(function () {
        if (panel.classList.contains('is-fading-out')) {
          panel.removeEventListener('transitionend', onFadeEnd);
          finishHideHoverPanel(panel);
        }
      }, HOVER_PANEL_FADE_MS + 80);
    });
    if (immediate || !panels.length) {
      activeHoverWrap = null;
    } else {
      setTimeout(function () {
        if (!document.querySelector('.dp-proposal-hover-panel.is-open')) {
          activeHoverWrap = null;
        }
      }, HOVER_PANEL_FADE_MS + 80);
    }
  }

  function scheduleHideHoverPanel(ev) {
    if (ev && ev.relatedTarget && isDpProposalHoverTarget(ev.relatedTarget)) {
      return;
    }
    if (hoverHideTimer) clearTimeout(hoverHideTimer);
    hoverHideTimer = setTimeout(function () {
      hoverHideTimer = null;
      hideHoverPanel(false);
    }, HOVER_PANEL_HIDE_DELAY_MS);
  }

  function ensurePanelInViewport(panel, pin) {
    if (!panel || !pin) return;
    var margin = 10;
    if (panel.parentNode !== document.body) {
      document.body.appendChild(panel);
    }
    panel.classList.add('is-open');
    panel.style.visibility = 'hidden';
    panel.style.display = 'block';
    var panelW = panel.offsetWidth;
    var panelH = panel.offsetHeight;
    panel.style.visibility = '';
    var pinRect = pin.getBoundingClientRect();
    var left = pinRect.right - panelW;
    if (left < margin) left = margin;
    if (left + panelW > window.innerWidth - margin) {
      left = window.innerWidth - panelW - margin;
    }
    var top = pinRect.bottom + 6;
    if (top + panelH > window.innerHeight - margin) {
      top = pinRect.top - panelH - 6;
    }
    if (top < margin) top = margin;
    if (top + panelH > window.innerHeight - margin) {
      top = window.innerHeight - panelH - margin;
    }
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
  }

  function highlightUnionViewport(entry) {
    if (!entry.boxes || !entry.boxes.length) return null;
    var minL = Infinity;
    var minT = Infinity;
    var maxR = -Infinity;
    var maxB = -Infinity;
    entry.boxes.forEach(function (box) {
      var r = box.getBoundingClientRect();
      if (r.width < 0.5 && r.height < 0.5) return;
      minL = Math.min(minL, r.left);
      minT = Math.min(minT, r.top);
      maxR = Math.max(maxR, r.right);
      maxB = Math.max(maxB, r.bottom);
    });
    if (minL === Infinity) return null;
    return {
      left: minL,
      top: minT,
      right: maxR,
      bottom: maxB,
      width: maxR - minL,
      height: maxB - minT,
    };
  }

  function positionPin(entry) {
    if (!entry.pin || !entry.boxes || !entry.boxes.length) return;
    var u = highlightUnionViewport(entry);
    if (!u) return;
    entry.viewportRect = u;
    entry.pin.style.left = u.right + 'px';
    entry.pin.style.top = u.top + 'px';
    entry.pin.style.transform = 'translate(-100%, 0)';
  }

  function repositionEntryOverlays(entry) {
    if (entry.overlay && tools.repositionHighlightOverlays) {
      tools.repositionHighlightOverlays(bodyEl, entry.overlay);
      entry.boxes = entry.overlay.boxes;
    }
  }

  function positionAllPins() {
    anchorRegistry.forEach(function (entry) {
      repositionEntryOverlays(entry);
      positionPin(entry);
    });
    if (displayMode === 'hidden') {
      document.querySelectorAll('.dp-proposal-highlight-rect').forEach(function (box) {
        box.classList.add('dp-proposal-highlight-hidden');
      });
    }
  }

  function showHoverPanel(entry, hash) {
    if (!entry || !entry.pin) return;
    hideHoverPanel(true);
    activeHoverWrap = entry.pin;
    positionPin(entry);
    var panel = entry.pin.querySelector('.dp-proposal-hover-panel');
    if (!panel) return;
    panel.classList.remove('is-fading-out');
    panel.dataset.dpAnchorHash = hash;
    renderHoverPanelBody(panel, {
      proposals: entry.proposals || [],
      comments: entry.comments || [],
    }, hash);
    ensurePanelInViewport(panel, entry.pin);
  }

  function bindHoverInteractions(entry, hash) {
    var pin = entry.pin;
    var badge = pin.querySelector('.dp-proposal-badge');
    var panel = pin.querySelector('.dp-proposal-hover-panel');
    var bundle = { proposals: entry.proposals || [], comments: entry.comments || [] };
    var total = passageActivityCount(bundle);
    entry.badgeHoverTimer = null;

    function cancelBadgeHoverOpen() {
      if (entry.badgeHoverTimer) {
        clearTimeout(entry.badgeHoverTimer);
        entry.badgeHoverTimer = null;
      }
    }

    function keepPanelOpen() {
      if (hoverHideTimer) {
        clearTimeout(hoverHideTimer);
        hoverHideTimer = null;
      }
      var livePanel = pin.querySelector('.dp-proposal-hover-panel') ||
        document.querySelector('.dp-proposal-hover-panel[data-dp-anchor-hash="' + hash + '"]');
      if (livePanel) {
        livePanel.classList.remove('is-fading-out');
      }
    }

    function openPanelFromUser() {
      cancelBadgeHoverOpen();
      keepPanelOpen();
      showHoverPanel(entry, hash);
    }

    function onBadgeEnter(ev) {
      if (!badge || badge.style.pointerEvents === 'none') return;
      var op = parseFloat(badge.style.opacity || '1');
      if (!isNaN(op) && op < BADGE_POINTER_EVENTS_MIN_OPACITY) return;
      cancelBadgeHoverOpen();
      entry.badgeHoverTimer = global.setTimeout(function () {
        entry.badgeHoverTimer = null;
        if (!badge.matches(':hover')) return;
        openPanelFromUser();
      }, BADGE_HOVER_OPEN_DELAY_MS);
    }

    function onBadgeLeave(ev) {
      cancelBadgeHoverOpen();
      if (ev && ev.relatedTarget && isDpProposalHoverTarget(ev.relatedTarget)) {
        return;
      }
      scheduleHideHoverPanel(ev);
    }

    function onPanelEnter() {
      keepPanelOpen();
    }

    function onPanelLeave(ev) {
      if (ev && ev.relatedTarget && isDpProposalHoverTarget(ev.relatedTarget)) {
        return;
      }
      scheduleHideHoverPanel(ev);
    }

    entry.boxes.forEach(function (box) {
      box.setAttribute('title', total + ' on this passage — click to open');
      box.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openPanelFromUser();
      });
    });
    if (badge) {
      badge.setAttribute('title', total + ' on this passage — hover or click badge');
      badge.addEventListener('mouseenter', onBadgeEnter);
      badge.addEventListener('mouseleave', onBadgeLeave);
      badge.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openPanelFromUser();
      });
      badge.addEventListener('focus', openPanelFromUser);
      badge.addEventListener('blur', scheduleHideHoverPanel);
    }
    if (panel) {
      panel.addEventListener('mouseenter', onPanelEnter);
      panel.addEventListener('mouseleave', onPanelLeave);
    }
  }

  function mountPassageAnchor(hash, bundle, overlay) {
    var total = passageActivityCount(bundle);
    var entry = {
      hash: hash,
      proposals: bundle.proposals || [],
      comments: bundle.comments || [],
      overlay: overlay,
      boxes: overlay && overlay.boxes ? overlay.boxes : [],
    };
    anchorRegistry.push(entry);

    if (overlay && overlay.boxes.length) {
      var pin = document.createElement('div');
      pin.className = 'dp-proposal-pin';
      pin.dataset.dpAnchorHash = hash;
      var badge = document.createElement('button');
      badge.type = 'button';
      badge.className = 'dp-proposal-badge';
      badge.dataset.dpAnchorHash = hash;
      badge.textContent = String(total);
      badge.title = total + ' on this passage — hover to preview';
      badge.setAttribute('aria-label', total + ' patches and comments on this passage');
      var panel = document.createElement('div');
      panel.className = 'dp-proposal-hover-panel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-label', 'Patches and comments on this passage');
      pin.appendChild(badge);
      pin.appendChild(panel);
      document.body.appendChild(pin);
      entry.pin = pin;
      positionPin(entry);
      bindHoverInteractions(entry, hash);
      return;
    }

    var floatingBadge = document.createElement('button');
    floatingBadge.type = 'button';
    floatingBadge.className = 'dp-proposal-badge dp-proposal-badge-floating';
    floatingBadge.dataset.dpAnchorHash = hash;
    floatingBadge.textContent = String(total);
    floatingBadge.title = total + ' — ' + label('location_not_found', 'location not found in document');
    floatingBadge.addEventListener('click', function () {
      if (bundle.proposals && bundle.proposals.length) {
        openListModal(hash);
      } else if (bundle.comments && bundle.comments.length) {
        scrollToGhAnchor(hash);
      }
    });
    document.body.appendChild(floatingBadge);
    entry.floatingBadge = floatingBadge;
  }

  function totalOverlayCount() {
    return proposals.length + countAllComments(readerComments);
  }

  function displayModeLabel(mode) {
    var suffix = ' (' + totalOverlayCount() + ')';
    if (mode === 'hidden') return 'Hidden' + suffix;
    if (mode === 'attention') return label('display_near', 'Near patch') + suffix;
    return 'Show all' + suffix;
  }

  function updateDisplayModeTrigger() {
    var iconWrap = document.getElementById('dpProposalDisplayIcon');
    var labelEl = document.getElementById('dpProposalDisplayLabel');
    var trigger = document.getElementById('dpProposalDisplayTrigger');
    if (!iconWrap || !labelEl) return;
    iconWrap.innerHTML = DISPLAY_MODE_ICONS[displayMode] || DISPLAY_MODE_ICONS.showAll;
    labelEl.textContent = displayModeLabel(displayMode);
    if (trigger) {
      trigger.setAttribute('title', label('toolbar_visibility_title', 'Patches visibility'));
      trigger.setAttribute('aria-label', displayModeLabel(displayMode));
    }
  }

  function refreshDisplayModeOptions() {
    var menu = document.getElementById('dpProposalDisplayMenu');
    if (!menu) return;
    var modes = [
      { value: 'hidden', label: displayModeLabel('hidden') },
      { value: 'attention', label: displayModeLabel('attention') },
      { value: 'showAll', label: displayModeLabel('showAll') },
    ];
    menu.innerHTML = modes.map(function (m) {
      return (
        '<li><button type="button" class="dropdown-item dp-proposal-display-option' +
        (displayMode === m.value ? ' active' : '') +
        '" data-mode="' + m.value + '">' +
        '<span class="dp-proposal-display-option-icon" aria-hidden="true">' +
        (DISPLAY_MODE_ICONS[m.value] || '') +
        '</span><span>' + esc(m.label) + '</span></button></li>'
      );
    }).join('');
    updateDisplayModeTrigger();
  }

  function injectToolbarControls() {
    var inner = document.querySelector('.draft-reader-toolbar-inner');
    if (!inner || document.getElementById('dpProposalToolbarControls')) return;
    var wrap = document.createElement('div');
    wrap.id = 'dpProposalToolbarControls';
    wrap.className = 'draft-reader-proposals-controls ms-auto';
    wrap.innerHTML =
      '<div class="dropdown dp-proposal-display-dropdown">' +
      '<button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle dp-proposal-display-trigger" ' +
      'id="dpProposalDisplayTrigger" data-bs-toggle="dropdown" aria-expanded="false" ' +
      'title="' + esc(label('toolbar_visibility_title', 'Patches visibility')) + '">' +
      '<span class="dp-proposal-display-icon" id="dpProposalDisplayIcon" aria-hidden="true"></span>' +
      '<span class="dp-proposal-display-label" id="dpProposalDisplayLabel"></span>' +
      '</button>' +
      '<ul class="dropdown-menu dropdown-menu-end" id="dpProposalDisplayMenu" ' +
      'aria-label="' + esc(label('toolbar_select_aria', 'Patches display')) + '"></ul>' +
      '</div>';
    inner.appendChild(wrap);
    refreshDisplayModeOptions();
    document.getElementById('dpProposalDisplayMenu').addEventListener('click', function (e) {
      var btn = e.target.closest('[data-mode]');
      if (!btn) return;
      setDisplayMode(btn.getAttribute('data-mode'));
      whenBootstrapReady(function () {
        var trigger = document.getElementById('dpProposalDisplayTrigger');
        if (trigger && window.bootstrap) {
          var inst = bootstrap.Dropdown.getInstance(trigger);
          if (inst) inst.hide();
        }
      });
    });
  }

  function stashPendingForLogin(selection) {
    try {
      sessionStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify({
        draftRef: draftRef,
        original: selection.original,
        blockText: selection.blockText,
      }));
    } catch (_e) { /* ignore */ }
  }

  function clearStashedPending() {
    try {
      sessionStorage.removeItem(PENDING_STORAGE_KEY);
    } catch (_e) { /* ignore */ }
  }

  function readStashedPending() {
    try {
      var raw = sessionStorage.getItem(PENDING_STORAGE_KEY);
      if (!raw) return null;
      var data = JSON.parse(raw);
      if (!data || data.draftRef !== draftRef) return null;
      return {
        original: data.original,
        blockText: data.blockText || bodyEl.textContent || '',
      };
    } catch (_e) {
      return null;
    }
  }

  function readComposeModeFromStorage() {
    try {
      var m = sessionStorage.getItem(COMPOSE_MODE_KEY);
      if (m === 'comment' || m === 'propose') return m;
    } catch (_e) { /* ignore */ }
    try {
      var params = new URLSearchParams(window.location.search);
      if (params.get('compose_mode') === 'comment') return 'comment';
    } catch (_e2) { /* ignore */ }
    return 'propose';
  }

  function setComposeMode(mode) {
    composeMode = mode === 'comment' ? 'comment' : 'propose';
    try {
      sessionStorage.setItem(COMPOSE_MODE_KEY, composeMode);
    } catch (_e) { /* ignore */ }
    if (composeMode === 'comment') {
      if (pendingSelection) {
        setCommentScopeMode('passage', { force: true });
      } else {
        setCommentScopeMode('document');
      }
    }
    var panePropose = document.getElementById('dpComposePanePropose');
    var paneComment = document.getElementById('dpComposePaneComment');
    var btnPropose = document.getElementById('dpComposeTabPropose');
    var btnComment = document.getElementById('dpComposeTabComment');
    var submitProp = document.getElementById('dpProposalSubmitBtn');
    var submitComm = document.getElementById('dpCommentSubmitBtn');
    if (panePropose) panePropose.classList.toggle('d-none', composeMode !== 'propose');
    if (paneComment) paneComment.classList.toggle('d-none', composeMode !== 'comment');
    if (btnPropose) {
      btnPropose.classList.toggle('btn-primary', composeMode === 'propose');
      btnPropose.classList.toggle('btn-outline-primary', composeMode !== 'propose');
      btnPropose.classList.toggle('active', composeMode === 'propose');
    }
    if (btnComment) {
      btnComment.classList.toggle('btn-primary', composeMode === 'comment');
      btnComment.classList.toggle('btn-outline-primary', composeMode !== 'comment');
      btnComment.classList.toggle('active', composeMode === 'comment');
    }
    if (submitProp) submitProp.classList.toggle('d-none', composeMode !== 'propose');
    if (submitComm) submitComm.classList.toggle('d-none', composeMode !== 'comment');
  }

  function commentsPageUrl() {
    return '/doc/draft/' + encodeURIComponent(draftRef) + '/comments/';
  }

  function showComposeMessage(message, type) {
    var err = document.getElementById('dpProposalComposeError');
    if (!err) {
      window.alert(message);
      return;
    }
    err.className = 'alert mt-3 ' + (type === 'success' ? 'alert-success' : 'alert-danger');
    err.innerHTML = message;
    err.classList.remove('d-none');
  }

  function hideComposeMessage() {
    var err = document.getElementById('dpProposalComposeError');
    if (err) {
      err.classList.add('d-none');
      err.textContent = '';
      err.className = 'alert alert-danger mt-3 d-none';
    }
  }

  function parseJsonResponse(r) {
    return r.text().then(function (text) {
      var data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (_parseErr) {
          return {
            ok: false,
            status: r.status,
            data: { error: 'Unexpected server response (HTTP ' + r.status + ')' },
          };
        }
      }
      return { ok: r.ok, status: r.status, data: data };
    });
  }

  function readCommentScopeFromStorage() {
    try {
      var s = sessionStorage.getItem(COMMENT_SCOPE_KEY);
      if (s === 'passage' || s === 'document') return s;
    } catch (_e) { /* ignore */ }
    return 'document';
  }

  function setCommentScopeMode(mode, opts) {
    opts = opts || {};
    var next = mode === 'passage' ? 'passage' : 'document';
    if (next === 'passage' && !pendingSelection && !opts.force) {
      next = 'document';
    }
    commentScopeMode = next;
    try {
      sessionStorage.setItem(COMMENT_SCOPE_KEY, commentScopeMode);
    } catch (_e) { /* ignore */ }
    updateCommentScopeUI();
    refreshCommentSubmitState();
  }

  function updateCommentScopeUI() {
    var passageBlock = document.getElementById('dpCommentPassageBlock');
    var hint = document.getElementById('dpCommentScopeHint');
    var btnDoc = document.getElementById('dpCommentScopeDocument');
    var btnPassage = document.getElementById('dpCommentScopePassage');
    var hasPassage = !!(pendingSelection && pendingSelection.original);
    if (btnPassage) {
      btnPassage.disabled = !hasPassage;
      btnPassage.title = hasPassage
        ? 'Comment on the text you selected'
        : 'Select text in the document first';
    }
    if (btnDoc) {
      btnDoc.classList.toggle('btn-primary', commentScopeMode === 'document');
      btnDoc.classList.toggle('btn-outline-primary', commentScopeMode !== 'document');
      btnDoc.classList.toggle('active', commentScopeMode === 'document');
    }
    if (btnPassage) {
      btnPassage.classList.toggle('btn-primary', commentScopeMode === 'passage');
      btnPassage.classList.toggle('btn-outline-primary', commentScopeMode !== 'passage');
      btnPassage.classList.toggle('active', commentScopeMode === 'passage');
    }
    if (passageBlock) {
      passageBlock.classList.toggle('d-none', commentScopeMode !== 'passage' || !hasPassage);
    }
    if (hint) {
      hint.textContent = commentScopeMode === 'passage' && hasPassage
        ? 'Your comment is linked to the highlighted passage.'
        : 'Your comment applies to the full document. It appears on the Comments page and does not highlight text.';
    }
  }

  function refreshCommentSubmitState() {
    var commentEl = document.getElementById('dpCommentText');
    var submitComm = document.getElementById('dpCommentSubmitBtn');
    if (!commentEl || !submitComm) return;
    var ok = !!commentEl.value.trim();
    if (commentScopeMode === 'passage' && !pendingSelection) {
      ok = false;
    }
    submitComm.disabled = !ok;
  }

  function bindCommentScopeToggle() {
    var btnDoc = document.getElementById('dpCommentScopeDocument');
    var btnPassage = document.getElementById('dpCommentScopePassage');
    if (btnDoc && !btnDoc.dataset.ghBound) {
      btnDoc.dataset.ghBound = '1';
      btnDoc.addEventListener('click', function () {
        setCommentScopeMode('document');
      });
    }
    if (btnPassage && !btnPassage.dataset.ghBound) {
      btnPassage.dataset.ghBound = '1';
      btnPassage.addEventListener('click', function () {
        if (!pendingSelection) {
          showComposeMessage('Select text in the document for a passage comment.', 'error');
          return;
        }
        setCommentScopeMode('passage');
      });
    }
  }

  function bindComposeTabs() {
    var btnPropose = document.getElementById('dpComposeTabPropose');
    var btnComment = document.getElementById('dpComposeTabComment');
    if (btnPropose) {
      btnPropose.addEventListener('click', function () {
        setComposeMode('propose');
      });
    }
    if (btnComment) {
      btnComment.addEventListener('click', function () {
        setComposeMode('comment');
      });
    }
    bindCommentScopeToggle();
    var commentEl = document.getElementById('dpCommentText');
    var submitComm = document.getElementById('dpCommentSubmitBtn');
    if (commentEl && submitComm) {
      commentEl.oninput = refreshCommentSubmitState;
      submitComm.onclick = submitComment;
    }
  }

  function populateComposeModal() {
    var orig = document.getElementById('dpProposalOriginal');
    var prop = document.getElementById('dpProposalProposed');
    var passageComment = document.getElementById('dpCommentPassage');
    var rationaleEl = document.getElementById('dpProposalRationale');
    var referenceEl = document.getElementById('dpProposalReferenceUrl');
    var submit = document.getElementById('dpProposalSubmitBtn');
    var submitComm = document.getElementById('dpCommentSubmitBtn');
    var commentEl = document.getElementById('dpCommentText');
    var isDocumentComment = commentScopeMode === 'document' && !pendingSelection;
    if (!commentEl || !submitComm) return false;
    if (!isDocumentComment && (!orig || !prop || !submit || !pendingSelection)) {
      return false;
    }
    if (pendingSelection && orig && prop) {
      orig.value = pendingSelection.original;
      prop.value = pendingSelection.original;
      if (passageComment) passageComment.value = pendingSelection.original;
    } else if (passageComment) {
      passageComment.value = '';
    }
    if (rationaleEl) rationaleEl.value = '';
    if (referenceEl) referenceEl.value = '';
    if (commentEl) commentEl.value = '';
    hideComposeMessage();
    if (submit) {
      submit.disabled = true;
      if (pendingSelection) {
        prop.oninput = function () {
          var o = orig.value.replace(/^\s+|\s+$/g, '');
          var v = prop.value.replace(/^\s+|\s+$/g, '');
          submit.disabled = !v || v === o;
        };
        submit.onclick = submitProposal;
      }
    }
    submitComm.onclick = submitComment;
    commentEl.oninput = refreshCommentSubmitState;
    updateCommentScopeUI();
    refreshCommentSubmitState();
    return true;
  }

  function openComposeModal(opts) {
    opts = opts || {};
    if (opts.documentComment) {
      commentScopeMode = 'document';
      pendingSelection = null;
    } else if (!pendingSelection) {
      return;
    } else if (opts.commentScope === 'passage') {
      commentScopeMode = 'passage';
    } else if (!opts.documentComment) {
      commentScopeMode = readCommentScopeFromStorage();
      if (commentScopeMode === 'passage' && pendingSelection) {
        /* keep passage */
      } else if (pendingSelection && readComposeModeFromStorage() === 'comment') {
        commentScopeMode = 'passage';
      }
    }
    if (!populateComposeModal()) return;
    setComposeMode(opts.composeMode || readComposeModeFromStorage());
    var modal = getComposeModal();
    if (modal) modal.show();
  }

  function openDocumentCommentModal() {
    if (!meta.authenticated) {
      var returnTo = window.location.pathname + window.location.search + window.location.hash;
      window.location.href = '/login/?next=' + encodeURIComponent(returnTo);
      return;
    }
    openComposeModal({ documentComment: true, composeMode: 'comment' });
  }

  function submitComment() {
    var passageEl = document.getElementById('dpCommentPassage');
    var commentEl = document.getElementById('dpCommentText');
    var submitComm = document.getElementById('dpCommentSubmitBtn');
    if (!commentEl) {
      return;
    }
    if (!meta.authenticated) {
      showComposeMessage('Sign in to post a comment.', 'error');
      return;
    }
    var text = commentEl.value.trim();
    if (!text) {
      showComposeMessage('Enter a comment.', 'error');
      return;
    }
    var scope = commentScopeMode === 'passage' ? 'passage' : 'document';
    if (scope === 'passage' && !pendingSelection) {
      showComposeMessage('Select text in the document, or switch to Whole document.', 'error');
      return;
    }
    var payload = {
      text: text,
      comment_scope: scope,
    };
    if (scope === 'passage') {
      var trimmed = trimTextsForSubmit(
        passageEl ? passageEl.value : pendingSelection.original,
        passageEl ? passageEl.value : pendingSelection.original
      );
      if (!trimmed.original) {
        showComposeMessage('Could not anchor to that passage. Try Whole document instead.', 'error');
        return;
      }
      payload.original_text = trimmed.original;
      payload.context_anchor = {
        textQuote: tools.buildTextQuoteSelector(
          bodyEl.textContent || pendingSelection.blockText || '',
          trimmed.original
        ),
      };
    }
    if (submitComm) {
      submitComm.disabled = true;
    }
    hideComposeMessage();
    fetch(apiUrl('/reader-comments/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    })
      .then(parseJsonResponse)
      .then(function (res) {
        if (!res.ok) {
          showComposeMessage(
            esc(res.data.error || ('Failed to post comment (HTTP ' + res.status + ')')),
            'error'
          );
          if (submitComm) {
            submitComm.disabled = false;
          }
          return;
        }
        commentEl.value = '';
        if (submitComm) {
          submitComm.disabled = true;
        }
        var commentsUrl = commentsPageUrl();
        showComposeMessage(
          'Comment posted. <a href="' + esc(commentsUrl) + '" class="alert-link">View comments</a>',
          'success'
        );
        loadReaderComments().then(rebuildPassageAnchors);
        global.setTimeout(function () {
        if (scope === 'passage') {
          pendingSelection = null;
        }
        var modal = getComposeModal();
        if (modal) {
          modal.hide();
        }
      }, 1800);
      })
      .catch(function () {
        showComposeMessage('Network error — check your connection and try again.', 'error');
        if (submitComm) {
          submitComm.disabled = false;
        }
      });
  }

  function beginProposalFromSelection(selection) {
    pendingSelection = selection;
    if (!meta.authenticated) {
      stashPendingForLogin(selection);
      var returnTo = window.location.pathname + window.location.search + window.location.hash;
      window.location.href = '/login/?next=' + encodeURIComponent(returnTo);
      return;
    }
    whenBootstrapReady(openComposeModal);
  }

  function resumePendingProposalAfterLogin() {
    if (!meta.authenticated) return;
    var stashed = readStashedPending();
    if (!stashed) return;
    clearStashedPending();
    pendingSelection = stashed;
    whenBootstrapReady(openComposeModal);
  }

  function openComposeFromInvitePayload(data) {
    if (!data || !meta.authenticated) return false;
    if (data.draft_ref && data.draft_ref !== draftRef) return false;
    var passageText = (data.passage_text || '').trim();
    if (!passageText) return false;
    var blockText = bodyEl.textContent || '';
    var textQuote = data.context_anchor && data.context_anchor.textQuote;
    var located = tools.locateTextInRoot(bodyEl, {
      original_text: passageText,
      textQuote: textQuote || null,
    });
    var original = passageText;
    if (located) {
      original = tools.expandSelectionToSentences
        ? tools.expandSelectionToSentences(blockText, located.start, located.end)
        : (tools.normalizeForMatch(blockText) || '').slice(located.start, located.end);
      if (tools.rangeFromOffsets && located.map) {
        var range = tools.rangeFromOffsets(located.map, located.start, located.end);
        if (range) {
          try {
            var el = range.startContainer.parentElement || range.startContainer;
            if (el && el.scrollIntoView) {
              el.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }
          } catch (_scrollErr) { /* ignore */ }
        }
      }
    } else if (tools.expandToSentences) {
      original = tools.expandToSentences(passageText, blockText);
    }
    pendingSelection = { original: original, blockText: blockText };
    if (global.GhInvite && global.GhInvite.clearPassageComposeStash) {
      global.GhInvite.clearPassageComposeStash();
    }
    whenBootstrapReady(openComposeModal);
    return true;
  }

  function resumeInvitePassageCompose() {
    if (!meta.authenticated) return Promise.resolve();

    var stash = global.GhInvite && global.GhInvite.readPassageComposeStash
      ? global.GhInvite.readPassageComposeStash()
      : null;
    if (stash && openComposeFromInvitePayload(stash)) {
      return Promise.resolve();
    }

    var composeParam = false;
    var inviteToken = null;
    try {
      var params = new URLSearchParams(window.location.search);
      composeParam = params.get('compose') === '1';
      inviteToken = params.get('invite');
    } catch (_e) { /* ignore */ }

    if (!composeParam || !inviteToken) {
      return Promise.resolve();
    }

    return fetch('/api/invitations/by-token/' + encodeURIComponent(inviteToken) + '/', {
      credentials: 'same-origin',
    })
      .then(function (r) {
        return r.json().then(function (d) {
          return { ok: r.ok, data: d || {} };
        });
      })
      .then(function (res) {
        if (!res.ok || !res.data.target) return;
        var target = res.data.target;
        var excerpt = global.GhInvite && global.GhInvite.passageExcerptFromTarget
          ? global.GhInvite.passageExcerptFromTarget(target)
          : '';
        if (!excerpt) return;
        if (global.GhInvite && global.GhInvite.stashPassageCompose) {
          global.GhInvite.stashPassageCompose(
            res.data.invite_type || 'edit_document_passage',
            target,
            target.draft_ref || draftRef
          );
        }
        openComposeFromInvitePayload({
          draft_ref: target.draft_ref || draftRef,
          passage_text: excerpt,
          context_anchor: target.context_anchor || null,
        });
      })
      .catch(function () { /* ignore */ });
  }

  function trimTextsForSubmit(original, proposed) {
    if (display && display.focusedPassageCore) {
      var core = display.focusedPassageCore(original, proposed);
      return {
        original: (core.original || '').replace(/^\s+|\s+$/g, ''),
        proposed: (core.proposed || '').replace(/^\s+|\s+$/g, ''),
      };
    }
    return {
      original: original.replace(/^\s+|\s+$/g, ''),
      proposed: proposed.replace(/^\s+|\s+$/g, ''),
    };
  }

  function submitProposal() {
    var orig = document.getElementById('dpProposalOriginal');
    var prop = document.getElementById('dpProposalProposed');
    var err = document.getElementById('dpProposalComposeError');
    var submit = document.getElementById('dpProposalSubmitBtn');
    if (!orig || !prop || !pendingSelection) return;
    submit.disabled = true;
    var trimmed = trimTextsForSubmit(orig.value, prop.value);
    if (!trimmed.original || !trimmed.proposed || trimmed.original === trimmed.proposed) {
      err.textContent = 'Proposed text must change at least one sentence in the selection.';
      err.classList.remove('d-none');
      submit.disabled = false;
      return;
    }
    var rationaleEl = document.getElementById('dpProposalRationale');
    var referenceEl = document.getElementById('dpProposalReferenceUrl');
    var payload = {
      original_text: trimmed.original,
      proposed_text: trimmed.proposed,
      scope: meta.scope || meta.mode || 'dp',
      context_anchor: {
        textQuote: tools.buildTextQuoteSelector(
          bodyEl.textContent || pendingSelection.blockText || '',
          trimmed.original
        ),
      },
    };
    if (rationaleEl && rationaleEl.value.trim()) {
      payload.rationale = rationaleEl.value.trim();
    }
    if (referenceEl && referenceEl.value.trim()) {
      payload.reference_url = referenceEl.value.trim();
    }
    fetch(apiUrl('/proposals/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, status: r.status, data: d }; });
      })
      .then(function (res) {
        if (!res.ok) {
          err.textContent = res.data.error || ('Request failed (' + res.status + ')');
          err.classList.remove('d-none');
          submit.disabled = false;
          return;
        }
        pendingSelection = null;
        clearStashedPending();
        var modal = getComposeModal();
        if (modal) modal.hide();
        setDisplayMode('showAll');
        loadProposals().then(loadReaderComments).then(rebuildPassageAnchors);
      })
      .catch(function () {
        err.textContent = 'Network error';
        err.classList.remove('d-none');
        submit.disabled = false;
      });
  }

  function captureSelectionFromEvent() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
    var range = sel.getRangeAt(0);
    if (!bodyEl.contains(range.commonAncestorContainer)) return null;
    if (!tools.userSelectionMeetsMinSentenceWordFraction(range)) return null;
    var block = tools.findBlockElement(range.commonAncestorContainer) || bodyEl;
    var off = tools.getSelectionCharOffsetsInBlock(block, range);
    if (!off) return null;
    var expanded = tools.expandSelectionToSentences
      ? tools.expandSelectionToSentences(off.blockText, off.start, off.end)
      : tools.expandToSentences(off.blockText.slice(off.start, off.end), off.blockText);
    return { original: expanded, blockText: off.blockText, block: off.block };
  }

  function onMouseUp(ev) {
    var target = ev && ev.target;
    if (target) {
      if (target.closest && target.closest('.dp-proposal-highlight-rect')) return;
      if (target.closest && target.closest('.dp-proposal-mark')) return;
      if (target.closest && target.closest('.dp-proposal-pin')) return;
      if (target.closest && target.closest('.dp-proposal-hover-panel')) return;
      if (target.closest && target.closest('.dp-proposal-badge')) return;
      if (composeModalEl && composeModalEl.contains(target)) return;
      if (listModalEl && listModalEl.contains(target)) return;
      if (target.closest && target.closest('.modal')) return;
    }
    // Defer so the browser finalizes the selection before we read it.
    setTimeout(function () {
      var selection = captureSelectionFromEvent();
      if (!selection) {
        pendingSelection = null;
        return;
      }
      beginProposalFromSelection(selection);
    }, 0);
  }

  function unwrapAnchorMark(mark) {
    if (!mark || !mark.parentNode) return;
    var wrap = mark.closest('.dp-proposal-anchor-wrap');
    var parent = wrap ? wrap.parentNode : mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, wrap || mark);
    }
    if (wrap) parent.removeChild(wrap);
    else parent.removeChild(mark);
  }

  function clearHighlights() {
    hideHoverPanel(true);
    var layer = bodyEl.querySelector('.dp-proposal-highlight-layer');
    if (layer) layer.innerHTML = '';
    bodyEl.querySelectorAll('.dp-proposal-mark').forEach(unwrapAnchorMark);
    document.querySelectorAll('.dp-proposal-pin').forEach(function (p) {
      if (p.parentNode) p.parentNode.removeChild(p);
    });
    document.querySelectorAll('.dp-proposal-badge-floating').forEach(function (b) {
      if (b.parentNode) b.parentNode.removeChild(b);
    });
    anchorRegistry = [];
  }

  function buildAnchorRegistry() {
    clearHighlights();
    var byAnchor = {};
    proposals.forEach(function (p) {
      if (!p.anchor_hash) return;
      if (!byAnchor[p.anchor_hash]) {
        byAnchor[p.anchor_hash] = { proposals: [], comments: [] };
      }
      byAnchor[p.anchor_hash].proposals.push(p);
    });
    flattenPassageComments(readerComments, []).forEach(function (c) {
      if (!c.anchor_hash) return;
      if (!byAnchor[c.anchor_hash]) {
        byAnchor[c.anchor_hash] = { proposals: [], comments: [] };
      }
      byAnchor[c.anchor_hash].comments.push(c);
    });
    var orphanIndex = 0;
    Object.keys(byAnchor).forEach(function (hash) {
      var bundle = byAnchor[hash];
      var located = null;
      if (bundle.proposals[0]) {
        located = locateProposalInDocument(bundle.proposals[0]);
      }
      if (!located && bundle.comments[0]) {
        located = locateCommentInDocument(bundle.comments[0]);
      }
      var overlay = null;
      if (located && tools.createHighlightOverlays) {
        overlay = tools.createHighlightOverlays(bodyEl, located, hash);
      }
      mountPassageAnchor(hash, bundle, overlay);
      if (!overlay || !overlay.boxes.length) {
        var badge = document.querySelector(
          '.dp-proposal-badge-floating[data-dp-anchor-hash="' + hash + '"]'
        );
        if (badge) {
          badge.style.right = (16 + orphanIndex * 36) + 'px';
          badge.style.top = (88 + orphanIndex * 36) + 'px';
          badge.style.left = 'auto';
          orphanIndex += 1;
        }
      }
    });
    positionAllPins();
    positionFloatingBadges();
    syncDisplayMode();
    scrollToGhAnchorFromLocation();
  }

  function rebuildPassageAnchors() {
    buildAnchorRegistry();
    refreshDisplayModeOptions();
  }

  function syncDisplayMode() {
    var hidden = displayMode === 'hidden';
    var flashActive = anchorFlashLock && Date.now() < anchorFlashLock.until;
    var layer = bodyEl.querySelector('.dp-proposal-highlight-layer');
    if (layer) {
      layer.classList.toggle('dp-proposal-highlight-layer-hidden', hidden && !flashActive);
    }
    document.querySelectorAll('.dp-proposal-highlight-rect').forEach(function (box) {
      if (box.classList.contains('gh-anchor-flash-hold')) {
        return;
      }
      box.classList.toggle('dp-proposal-highlight-hidden', hidden);
      box.classList.remove('dp-proposal-highlight-dim');
      if (hidden) {
        box.style.removeProperty('opacity');
        box.style.removeProperty('pointer-events');
      }
    });
    document.querySelectorAll('mark.dp-proposal-mark').forEach(function (m) {
      m.classList.toggle('dp-proposal-mark-hidden', hidden);
    });
    document.querySelectorAll('.dp-proposal-pin, .dp-proposal-badge-floating').forEach(function (el) {
      el.style.display = hidden ? 'none' : '';
    });
    updateDisplayModeTrigger();
    if (!hidden) {
      applyPointerProximity(lastPointer.x, lastPointer.y);
    }
  }

  function pointerInsideViewportRect(x, y, u) {
    return x >= u.left && x <= u.right && y >= u.top && y <= u.bottom;
  }

  function applyPointerProximity(x, y) {
    if (displayMode === 'hidden') return;
    positionAllPins();
    var pointerKnown = x >= 0 && y >= 0;
    anchorRegistry.forEach(function (entry) {
      if (entry.floatingBadge) {
        entry.floatingBadge.style.opacity = displayMode === 'showAll' ? '1' : '0.45';
        return;
      }
      var pin = entry.pin;
      if (!pin || !entry.boxes || !entry.boxes.length) return;

      if (isAnchorFlashActive(entry.hash)) {
        pin.style.display = '';
        entry.boxes.forEach(function (box) {
          box.classList.remove('dp-proposal-highlight-hidden', 'dp-proposal-highlight-dim');
          box.style.opacity = '1';
          box.style.visibility = 'visible';
          box.style.pointerEvents = 'auto';
        });
        var flashBadge = pin.querySelector('.dp-proposal-badge');
        if (flashBadge) {
          flashBadge.style.opacity = '1';
          flashBadge.style.pointerEvents = 'auto';
        }
        return;
      }

      if (displayMode === 'showAll') {
        pin.classList.remove('dp-proposal-pin-active', 'dp-proposal-pin-near', 'dp-proposal-pin-far');
        var badgeAll = pin.querySelector('.dp-proposal-badge');
        if (badgeAll) {
          badgeAll.style.removeProperty('opacity');
          badgeAll.style.pointerEvents = 'auto';
        }
        entry.boxes.forEach(function (box) {
          box.classList.remove('dp-proposal-highlight-hidden', 'dp-proposal-highlight-dim');
          box.style.opacity = '1';
          box.style.pointerEvents = 'auto';
        });
        return;
      }

      var u = entry.viewportRect || highlightUnionViewport(entry);
      if (!u) return;
      var cx = u.left + u.width / 2;
      var cy = u.top + u.height / 2;
      var dist = Math.hypot(x - cx, y - cy);
      if (pointerKnown && pointerInsideViewportRect(x, y, u)) {
        dist = 0;
      }
      var t = Math.max(0, 1 - dist / MAX_DISTANCE);
      var near = !pointerKnown || t > PROXIMITY_SHOW_THRESHOLD;

      pin.classList.remove('dp-proposal-pin-active');
      pin.classList.toggle('dp-proposal-pin-near', near);
      pin.classList.toggle('dp-proposal-pin-far', pointerKnown && !near);

      var badge = pin.querySelector('.dp-proposal-badge');
      if (badge) {
        var badgeOpacity;
        if (!pointerKnown) {
          badgeOpacity = 0.55;
        } else if (near) {
          badgeOpacity = Math.max(PROXIMITY_BADGE_MIN_OPACITY, t);
        } else {
          badgeOpacity = 0;
        }
        badge.style.opacity = String(badgeOpacity);
        badge.style.pointerEvents =
          badgeOpacity >= BADGE_POINTER_EVENTS_MIN_OPACITY ? 'auto' : 'none';
        if (badgeOpacity < BADGE_POINTER_EVENTS_MIN_OPACITY && entry.badgeHoverTimer) {
          clearTimeout(entry.badgeHoverTimer);
          entry.badgeHoverTimer = null;
        }
      }
      entry.boxes.forEach(function (box) {
        box.classList.remove('dp-proposal-highlight-hidden', 'dp-proposal-highlight-dim');
        if (!pointerKnown) {
          box.style.opacity = '0';
          box.style.pointerEvents = 'none';
        } else if (near) {
          box.style.opacity = String(t * 0.92);
          box.style.pointerEvents = t > PROXIMITY_SHOW_THRESHOLD ? 'auto' : 'none';
        } else {
          box.style.opacity = '0';
          box.style.pointerEvents = 'none';
        }
      });
    });
  }

  function renderProposalList(group) {
    var body = document.getElementById('dpProposalListBody');
    if (!body) return;
    var sections = { pending: [], accepted: [], declined: [], other: [] };
    group.forEach(function (p) {
      if (sections[p.status]) sections[p.status].push(p);
      else sections.other.push(p);
    });
    function renderSection(title, items) {
      if (!items.length) return '';
      var html = '<h6 class="mt-3">' + esc(title) + '</h6><div class="dp-proposal-list-items mb-2">';
      items.forEach(function (p) {
        html += '<div class="dp-proposal-list-item" id="dp-proposal-item-' + esc(p.id) + '">';
        if (p.rationale) {
          html += renderProposalMetaHtml(p) + renderProposalHeaderHtml(p);
        } else {
          html += renderProposalHeaderHtml(p);
        }
        html += renderProposalBody(p.original_text, p.proposed_text, showDiff);
        if (!p.rationale) {
          html += renderProposalMetaHtml(p);
        }
        if (p.status === 'pending' && meta.can_accept_amendments) {
          html += '<div class="btn-group btn-group-sm mt-3">' +
            '<button type="button" class="btn btn-success dp-proposal-accept" data-id="' +
            esc(p.id) + '">' + esc(label('accept_button', 'Merge patch')) + '</button>' +
            '<button type="button" class="btn btn-outline-secondary dp-proposal-decline" data-id="' +
            esc(p.id) + '">Decline</button>' +
            '</div>';
        }
        html += '</div>';
      });
      html += '</div>';
      return html;
    }
    body.innerHTML =
      renderSection(label('pending_plural', 'Patches'), sections.pending) +
      renderSection(label('accepted_plural', 'Merged'), sections.accepted) +
      renderSection('Declined', sections.declined) +
      renderSection('Other', sections.other);
    body.querySelectorAll('.dp-proposal-accept').forEach(function (btn) {
      btn.addEventListener('click', function () { reviewProposal(btn.dataset.id, 'accept'); });
    });
    body.querySelectorAll('.dp-proposal-decline').forEach(function (btn) {
      btn.addEventListener('click', function () { reviewProposal(btn.dataset.id, 'decline'); });
    });
  }

  function openListModal(anchorHash, focusProposalId) {
    var group = proposals.filter(function (p) { return p.anchor_hash === anchorHash; });
    if (!group.length) return;
    var addBtn = document.getElementById('dpProposalListAddBtn');
    var diffToggle = document.getElementById('dpProposalShowDiffToggle');
    if (diffToggle) {
      diffToggle.checked = showDiff;
      diffToggle.onchange = function () {
        showDiff = !!diffToggle.checked;
        localStorage.setItem('dpProposalShowDiff:' + draftRef, showDiff ? 'true' : 'false');
        renderProposalList(group);
      };
    }
    renderProposalList(group);
    if (addBtn) {
      addBtn.onclick = function () {
        pendingSelection = { original: group[0].original_text, blockText: bodyEl.textContent || '' };
        var listModal = getListModal();
        if (listModal) listModal.hide();
        whenBootstrapReady(openComposeModal);
      };
    }
    whenBootstrapReady(function () {
      var listModal = getListModal();
      if (listModal) {
        listModal.show();
        if (focusProposalId) {
          var target = document.getElementById('dp-proposal-item-' + focusProposalId);
          if (target) {
            target.classList.add('dp-proposal-item-focused');
            target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
        }
      }
    });
  }

  function reviewProposal(id, action) {
    fetch(apiUrl('/proposals/' + encodeURIComponent(id) + '/' + action + '/'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          alert(res.data.error || 'Action failed');
          return;
        }
        var listModal = getListModal();
        if (listModal) listModal.hide();
        loadProposals().then(loadReaderComments).then(rebuildPassageAnchors);
      });
  }

  function positionFloatingBadges() {
    anchorRegistry.forEach(function (entry) {
      if (!entry.floatingBadge) return;
      entry.floatingBadge.style.opacity = displayMode === 'hidden' ? '0' : '1';
    });
  }

  function countAllComments(list) {
    var total = 0;
    (list || []).forEach(function (c) {
      total += 1;
      if (c.replies && c.replies.length) {
        total += countAllComments(c.replies);
      }
    });
    return total;
  }

  function updateCommentsLinkCount() {
    var link = document.getElementById('draftReaderCommentsLink');
    if (!link) return;
    var n = countAllComments(readerComments);
    link.innerHTML = '<i class="fas fa-comments me-1"></i>Comments (' + n + ')';
    link.setAttribute('href', commentsPageUrl());
  }

  function loadReaderComments() {
    return fetch(apiUrl('/reader-comments/'), { credentials: 'same-origin' })
      .then(parseJsonResponse)
      .then(function (res) {
        if (!res.ok) {
          return;
        }
        readerComments = (res.data && res.data.comments) || [];
        updateCommentsLinkCount();
      })
      .catch(function () { /* ignore */ });
  }

  function loadProposals() {
    return fetch(apiUrl('/proposals/'), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('Failed to load patches (' + r.status + ')');
        return r.json();
      })
      .then(function (data) {
        proposals = data.proposals || [];
      })
      .catch(function (err) {
        console.error('Patches load failed:', err);
      });
  }

  document.addEventListener('mouseup', onMouseUp);
  document.addEventListener('mousemove', function (e) {
    lastPointer.x = e.clientX;
    lastPointer.y = e.clientY;
    applyPointerProximity(lastPointer.x, lastPointer.y);
  });
  window.addEventListener('scroll', function () {
    hideHoverPanel(true);
    positionAllPins();
    applyPointerProximity(lastPointer.x, lastPointer.y);
  }, { passive: true });
  window.addEventListener('resize', function () {
    positionAllPins();
    positionFloatingBadges();
    document.querySelectorAll('.dp-proposal-hover-panel.is-open').forEach(function (panel) {
      var hash = panel.dataset.dpAnchorHash;
      if (!hash) return;
      var pin = document.querySelector('.dp-proposal-pin[data-dp-anchor-hash="' + hash + '"]');
      if (pin) ensurePanelInViewport(panel, pin);
    });
  });

  injectToolbarControls();
  bindInviteControls();
  bindComposeTabs();
  function resumePatchFromUrl() {
    var patchId = null;
    try {
      patchId = new URLSearchParams(window.location.search).get('patch');
    } catch (_e) { /* ignore */ }
    if (!patchId) return;
    var target = proposals.find(function (p) { return p.id === patchId; });
    if (!target || !target.anchor_hash) return;
    setDisplayMode('showAll');
    whenBootstrapReady(function () {
      openListModal(target.anchor_hash, patchId);
    });
  }

  loadProposals()
    .then(loadReaderComments)
    .then(rebuildPassageAnchors)
    .then(function () {
      resumePendingProposalAfterLogin();
      return resumeInvitePassageCompose();
    })
    .then(function () {
      resumePatchFromUrl();
    });
  global.addEventListener('hashchange', scrollToGhAnchorFromLocation);
})(typeof window !== 'undefined' ? window : globalThis);
