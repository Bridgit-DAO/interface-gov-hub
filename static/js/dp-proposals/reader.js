/**
 * DP Proposal read-page UI: selection → compose modal → badges → list modal.
 */
(function () {
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
    var word = label('count_word', 'proposal');
    return String(n) + ' ' + word + (n === 1 ? '' : 's');
  }

  var draftRef = root.getAttribute('data-draft-ref') || meta.draft_ref;
  var bodyEl = document.getElementById('dp-reader-selectable-body');
  if (!bodyEl || !window.DpSentenceTools) return;

  var tools = window.DpSentenceTools;
  var proposals = [];
  var anchorRegistry = [];
  var displayMode = localStorage.getItem('dpProposalDisplay:' + draftRef) || 'showAll';
  var showDiff = localStorage.getItem('dpProposalShowDiff:' + draftRef) === 'true';
  var composeModalEl = document.getElementById('dpProposalComposeModal');
  var listModalEl = document.getElementById('dpProposalListModal');
  var pendingSelection = null;
  var MAX_DISTANCE = 320;
  var lastPointer = { x: -1, y: -1 };
  var hoverHideTimer = null;
  var activeHoverWrap = null;

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
    var sel = document.getElementById('dpProposalDisplayMode');
    if (sel) sel.value = displayMode;
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
      '<div class="dp-proposal-card-label mt-3">Proposed replacement</div>' +
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
    return label('link_prefix', 'Proposal') + ' ' + (index + 1);
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

  function renderHoverPanelBody(panel, group, hash) {
    var html = '<ul class="dp-proposal-hover-links">';
    group.forEach(function (p, idx) {
      var deltaHtml = proposalCharDeltaHtml(p.original_text, p.proposed_text);
      html += '<li><a href="#" class="dp-proposal-hover-link" data-proposal-id="' + esc(p.id) + '" data-hash="' +
        esc(p.anchor_hash || hash) + '">' +
        '<i class="fas fa-comment-dots" aria-hidden="true"></i>' +
        '<span class="dp-proposal-hover-link-title">' + esc(proposalLinkTitle(p, idx)) + '</span>' +
        deltaHtml + '</a></li>';
    });
    html += '</ul>';
    html += '<button type="button" class="btn btn-primary btn-sm w-100 mt-2 dp-proposal-create-btn">' +
      '<i class="fas fa-plus me-1"></i>' + esc(label('create_hover', 'Suggest a change')) + '</button>';
    panel.innerHTML = html;
    panel.querySelectorAll('.dp-proposal-hover-link').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        hideHoverPanel(true);
        openListModal(link.dataset.hash, link.dataset.proposalId);
      });
    });
    var createBtn = panel.querySelector('.dp-proposal-create-btn');
    if (createBtn) {
      createBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        hideHoverPanel(true);
        pendingSelection = {
          original: group[0].original_text,
          blockText: bodyEl.textContent || '',
        };
        whenBootstrapReady(openComposeModal);
      });
    }
  }

  var HOVER_PANEL_FADE_MS = 200;
  var HOVER_PANEL_HIDE_DELAY_MS = 120;

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
    renderHoverPanelBody(panel, entry.proposals, hash);
    ensurePanelInViewport(panel, entry.pin);
  }

  function bindHoverInteractions(entry, hash) {
    var pin = entry.pin;
    var badge = pin.querySelector('.dp-proposal-badge');
    var panel = pin.querySelector('.dp-proposal-hover-panel');
    var group = entry.proposals;
    function onEnter(ev) {
      if (hoverHideTimer) {
        clearTimeout(hoverHideTimer);
        hoverHideTimer = null;
      }
      var livePanel = pin.querySelector('.dp-proposal-hover-panel') ||
        document.querySelector('.dp-proposal-hover-panel[data-dp-anchor-hash="' + hash + '"]');
      if (livePanel) {
        livePanel.classList.remove('is-fading-out');
      }
      showHoverPanel(entry, hash);
    }
    var hoverTargets = [badge, panel, pin];
    entry.boxes.forEach(function (box) {
      box.setAttribute('title', countPhrase(group.length) + ' — hover to preview');
      hoverTargets.push(box);
    });
    hoverTargets.forEach(function (el) {
      if (!el) return;
      el.addEventListener('mouseenter', onEnter);
      el.addEventListener('mouseleave', scheduleHideHoverPanel);
    });
    if (panel) {
      panel.addEventListener('mouseenter', onEnter);
      panel.addEventListener('mouseleave', scheduleHideHoverPanel);
    }
    if (badge) {
      badge.addEventListener('focus', onEnter);
      badge.addEventListener('blur', scheduleHideHoverPanel);
    }
  }

  function mountProposalAnchor(hash, group, overlay) {
    var entry = {
      hash: hash,
      proposals: group,
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
      badge.textContent = String(group.length);
      badge.title = countPhrase(group.length) + ' — hover to preview';
      badge.setAttribute('aria-label', countPhrase(group.length) + ' on this passage');
      var panel = document.createElement('div');
      panel.className = 'dp-proposal-hover-panel';
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-label', 'Proposals on this passage');
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
    floatingBadge.textContent = String(group.length);
    floatingBadge.title = countPhrase(group.length) + ' — ' + label('location_not_found', 'location not found in document');
    floatingBadge.addEventListener('click', function () { openListModal(hash); });
    document.body.appendChild(floatingBadge);
    entry.floatingBadge = floatingBadge;
  }

  function refreshDisplayModeOptions() {
    var sel = document.getElementById('dpProposalDisplayMode');
    if (!sel) return;
    var parent = sel.closest('.draft-reader-proposals-controls');
    if (parent) {
      var oldCount = parent.querySelector('.dp-proposal-count-label');
      if (oldCount) oldCount.remove();
    }
    var n = proposals.length;
    var suffix = ' (' + n + ')';
    var modes = [
      { value: 'hidden', label: 'Hide all' + suffix },
      { value: 'attention', label: label('display_near', 'Near proposal') + suffix },
      { value: 'showAll', label: 'Show all' + suffix },
    ];
    sel.innerHTML = modes.map(function (m) {
      return '<option value="' + m.value + '">' + m.label + '</option>';
    }).join('');
    sel.value = displayMode;
  }

  function injectToolbarControls() {
    var inner = document.querySelector('.draft-reader-toolbar-inner');
    if (!inner || document.getElementById('dpProposalToolbarControls')) return;
    var wrap = document.createElement('div');
    wrap.id = 'dpProposalToolbarControls';
    wrap.className = 'draft-reader-proposals-controls ms-auto';
    wrap.innerHTML =
      '<span class="dp-proposal-toolbar-label">' + esc(label('toolbar_label', 'DP Props')) + '</span>' +
      '<label class="visually-hidden" for="dpProposalDisplayMode">' + esc(label('toolbar_select_aria', 'DP Props display')) + '</label>' +
      '<select id="dpProposalDisplayMode" class="form-select form-select-sm" title="' + esc(label('toolbar_visibility_title', 'DP Props visibility')) + '">' +
      '</select>';
    inner.appendChild(wrap);
    var sel = document.getElementById('dpProposalDisplayMode');
    refreshDisplayModeOptions();
    sel.value = displayMode;
    sel.addEventListener('change', function () {
      displayMode = sel.value;
      localStorage.setItem('dpProposalDisplay:' + draftRef, displayMode);
      syncDisplayMode();
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

  function populateComposeModal() {
    var orig = document.getElementById('dpProposalOriginal');
    var prop = document.getElementById('dpProposalProposed');
    var err = document.getElementById('dpProposalComposeError');
    var submit = document.getElementById('dpProposalSubmitBtn');
    if (!orig || !prop || !submit || !pendingSelection) return false;
    orig.value = pendingSelection.original;
    prop.value = pendingSelection.original;
    err.classList.add('d-none');
    submit.disabled = true;
    prop.oninput = function () {
      var o = orig.value.replace(/^\s+|\s+$/g, '');
      var v = prop.value.replace(/^\s+|\s+$/g, '');
      submit.disabled = !v || v === o;
    };
    submit.onclick = submitProposal;
    return true;
  }

  function openComposeModal() {
    if (!pendingSelection) return;
    if (!populateComposeModal()) return;
    var modal = getComposeModal();
    if (modal) modal.show();
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
        loadProposals();
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
    var exact = sel.toString();
    var expanded = tools.expandToSentences(exact, off.blockText);
    return { original: expanded, blockText: off.blockText, block: off.block };
  }

  function onMouseUp(ev) {
    var target = ev && ev.target;
    if (target) {
      if (target.closest && target.closest('.dp-proposal-highlight-rect')) return;
      if (target.closest && target.closest('.dp-proposal-mark')) return;
      if (target.closest && target.closest('.dp-proposal-pin')) return;
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
      if (!byAnchor[p.anchor_hash]) byAnchor[p.anchor_hash] = [];
      byAnchor[p.anchor_hash].push(p);
    });
    var orphanIndex = 0;
    Object.keys(byAnchor).forEach(function (hash) {
      var group = byAnchor[hash];
      var proposal = group[0];
      var located = locateProposalInDocument(proposal);
      var overlay = null;
      if (located && tools.createHighlightOverlays) {
        overlay = tools.createHighlightOverlays(bodyEl, located, hash);
      }
      mountProposalAnchor(hash, group, overlay);
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
  }

  function syncDisplayMode() {
    var hidden = displayMode === 'hidden';
    var layer = bodyEl.querySelector('.dp-proposal-highlight-layer');
    if (layer) {
      layer.classList.toggle('dp-proposal-highlight-layer-hidden', hidden);
    }
    document.querySelectorAll('.dp-proposal-highlight-rect').forEach(function (box) {
      box.classList.toggle('dp-proposal-highlight-hidden', hidden);
      box.classList.remove('dp-proposal-highlight-dim');
    });
    document.querySelectorAll('mark.dp-proposal-mark').forEach(function (m) {
      m.classList.toggle('dp-proposal-mark-hidden', hidden);
    });
    document.querySelectorAll('.dp-proposal-pin, .dp-proposal-badge-floating').forEach(function (el) {
      el.style.display = hidden ? 'none' : '';
    });
    if (!hidden) {
      applyPointerProximity(lastPointer.x, lastPointer.y);
    }
  }

  function applyPointerProximity(x, y) {
    if (displayMode === 'hidden') return;
    positionAllPins();
    var useAttention = displayMode === 'attention';
    anchorRegistry.forEach(function (entry) {
      var pin = entry.pin;
      if (!pin || !entry.boxes || !entry.boxes.length) {
        if (entry.floatingBadge) {
          entry.floatingBadge.style.opacity = '0.45';
        }
        return;
      }
      var u = entry.viewportRect || highlightUnionViewport(entry);
      if (!u) return;
      var cx = u.left + u.width / 2;
      var cy = u.top + u.height / 2;
      var dist = Math.hypot(x - cx, y - cy);
      var t = Math.max(0, 1 - dist / MAX_DISTANCE);
      var near = !useAttention || t > 0.3;
      pin.classList.toggle('dp-proposal-pin-near', near);
      pin.classList.toggle('dp-proposal-pin-far', useAttention && !near);
      var badge = pin.querySelector('.dp-proposal-badge');
      if (badge) {
        badge.style.opacity = useAttention ? String(Math.min(1, 0.2 + t * 0.8)) : '1';
      }
      entry.boxes.forEach(function (box) {
        if (displayMode !== 'hidden') {
          box.classList.remove('dp-proposal-highlight-hidden');
        }
        if (useAttention) {
          box.classList.toggle('dp-proposal-highlight-dim', t < 0.15);
        } else {
          box.classList.remove('dp-proposal-highlight-dim');
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
      var html = '<h6 class="mt-3">' + esc(title) + '</h6><div class="list-group mb-2">';
      items.forEach(function (p) {
        html += '<div class="list-group-item" id="dp-proposal-item-' + esc(p.id) + '">' +
          '<div class="d-flex justify-content-between align-items-start gap-2">' +
          '<span class="badge ' + statusBadgeClass(p.status) + '">' + esc(p.status_label) + '</span>' +
          '<small class="text-muted">' + esc(p.author_name || 'Anonymous') + '</small></div>' +
          renderProposalBody(p.original_text, p.proposed_text, showDiff);
        if (p.status === 'pending' && meta.can_accept_amendments) {
          html += '<div class="btn-group btn-group-sm mt-3">' +
            '<button type="button" class="btn btn-success dp-proposal-accept" data-id="' +
            esc(p.id) + '">Accept as amendment</button>' +
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
      renderSection(label('pending_plural', 'Proposals'), sections.pending) +
      renderSection(label('accepted_plural', 'Amendments'), sections.accepted) +
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
        loadProposals();
      });
  }

  function positionFloatingBadges() {
    anchorRegistry.forEach(function (entry) {
      if (!entry.floatingBadge) return;
      entry.floatingBadge.style.opacity = displayMode === 'hidden' ? '0' : '1';
    });
  }

  function loadProposals() {
    return fetch(apiUrl('/proposals/'), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) throw new Error('Failed to load proposals (' + r.status + ')');
        return r.json();
      })
      .then(function (data) {
        proposals = data.proposals || [];
        buildAnchorRegistry();
        refreshDisplayModeOptions();
      })
      .catch(function (err) {
        console.error('DP proposals load failed:', err);
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
  loadProposals().then(resumePendingProposalAfterLogin);
})();
