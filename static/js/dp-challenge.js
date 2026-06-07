/**
 * Patch hub (DP Challenge / Suggest an Edit): doc picker CTA + live activity toasts.
 */
(function () {
  'use strict';

  var cfg = window.DP_CHALLENGE_PAGE || {};
  var pollMs = cfg.pollIntervalMs || 30000;
  var currentUserId = cfg.currentUserId || null;
  var returnTo = cfg.returnTo || '/dp-challenge/';
  var recentApiPath = cfg.recentApiPath || '/api/dp-challenge/recent';
  var labels = cfg.labels || {};
  var seenKeys = {};
  var toastQueue = [];
  var activeToast = null;
  var pollTimer = null;
  var lastPollAt = new Date().toISOString();

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function label(key, fallback) {
    return labels[key] || fallback;
  }

  function eventKey(ev) {
    return (ev.type || '') + ':' + (ev.proposal_id || '') + ':' + (ev.at || '');
  }

  function inviteUnavailableMessage() {
    if (window.GhDialog && window.GhDialog.alert) {
      window.GhDialog.alert({
        title: 'Invite unavailable',
        message: 'Please wait a moment and try again, or refresh the page.',
        variant: 'warning',
      });
      return;
    }
    window.alert('Invite is not ready yet. Please refresh and try again.');
  }

  function bindDpChallengeInvite() {
    var btn = document.getElementById('dpChallengeInviteBtn');
    if (!btn || btn.dataset.ghInviteBound) return;
    btn.dataset.ghInviteBound = '1';
    var invite = cfg.invite || {};
    btn.addEventListener('click', function () {
      if (!window.GhInvite) {
        inviteUnavailableMessage();
        return;
      }
      window.GhInvite.open({
        type: invite.type || 'participate_dp',
        title: invite.title || 'Invite a colleague',
        hint: invite.hint || 'Invite a colleague to participate.',
        target: invite.target || {},
      });
    });
  }

  function readUrlForRef(ref) {
    return typeof window.ghReadUrl === 'function'
      ? window.ghReadUrl(ref, returnTo)
      : '/doc/draft/' + encodeURIComponent(ref) + '/read/?return_to=' + encodeURIComponent(returnTo);
  }

  function bindDocPicker() {
    var root = document.getElementById('dpChallengeDocPicker');
    var input = document.getElementById('dpChallengeDocPickerInput');
    var list = document.getElementById('dpChallengeDocPickerList');
    if (!root || !input || !list) return;

    var docs = cfg.pickerDocs || [];
    var emptyMsg = cfg.pickerEmpty || root.getAttribute('data-empty') || 'No documents available';
    var activeIndex = -1;
    var blurTimer = null;

    function docSearchText(d) {
      return [d.label, d.ref, d.ml, d.dp].filter(Boolean).join(' ').toLowerCase();
    }

    function filteredDocs(query) {
      var q = (query || '').trim().toLowerCase();
      if (!q) return docs.slice();
      return docs.filter(function (d) {
        return docSearchText(d).indexOf(q) >= 0;
      });
    }

    function optionLabel(d) {
      return d.label || d.ref || '';
    }

    function setListOpen(open) {
      input.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        list.hidden = false;
        root.classList.add('is-open');
      } else {
        list.hidden = true;
        root.classList.remove('is-open');
        activeIndex = -1;
      }
    }

    function renderList(items) {
      list.innerHTML = '';
      if (!docs.length) {
        var empty = document.createElement('li');
        empty.className = 'dp-doc-picker-empty';
        empty.textContent = emptyMsg;
        empty.setAttribute('role', 'presentation');
        list.appendChild(empty);
        return;
      }
      if (!items.length) {
        var none = document.createElement('li');
        none.className = 'dp-doc-picker-empty';
        none.textContent = 'No matches';
        none.setAttribute('role', 'presentation');
        list.appendChild(none);
        return;
      }
      items.forEach(function (d, idx) {
        var li = document.createElement('li');
        li.className = 'dp-doc-picker-option';
        li.setAttribute('role', 'option');
        li.dataset.ref = d.ref;
        li.dataset.index = String(idx);
        li.textContent = optionLabel(d);
        li.addEventListener('mousedown', function (e) {
          e.preventDefault();
        });
        li.addEventListener('click', function () {
          openDoc(d.ref);
        });
        list.appendChild(li);
      });
    }

    function highlightActive() {
      var options = list.querySelectorAll('.dp-doc-picker-option');
      options.forEach(function (el, i) {
        el.classList.toggle('is-active', i === activeIndex);
        if (i === activeIndex) el.setAttribute('aria-selected', 'true');
        else el.removeAttribute('aria-selected');
      });
    }

    function openDoc(ref) {
      if (!ref) return;
      window.location.href = readUrlForRef(ref);
    }

    function refreshList() {
      var items = filteredDocs(input.value);
      renderList(items);
      if (activeIndex >= items.length) activeIndex = items.length - 1;
      highlightActive();
    }

    input.addEventListener('focus', function () {
      if (blurTimer) {
        clearTimeout(blurTimer);
        blurTimer = null;
      }
      refreshList();
      setListOpen(true);
    });

    input.addEventListener('input', function () {
      activeIndex = -1;
      refreshList();
      setListOpen(true);
    });

    input.addEventListener('keydown', function (e) {
      var options = list.querySelectorAll('.dp-doc-picker-option');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!list.hidden) {
          activeIndex = Math.min(activeIndex + 1, options.length - 1);
          highlightActive();
          if (options[activeIndex]) options[activeIndex].scrollIntoView({ block: 'nearest' });
        } else {
          refreshList();
          setListOpen(true);
        }
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        highlightActive();
        if (options[activeIndex]) options[activeIndex].scrollIntoView({ block: 'nearest' });
        return;
      }
      if (e.key === 'Escape') {
        setListOpen(false);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        if (activeIndex >= 0 && options[activeIndex]) {
          openDoc(options[activeIndex].dataset.ref);
          return;
        }
        var items = filteredDocs(input.value);
        if (items.length === 1) {
          openDoc(items[0].ref);
        }
      }
    });

    input.addEventListener('blur', function () {
      blurTimer = setTimeout(function () {
        setListOpen(false);
      }, 150);
    });

    refreshList();
  }

  function toastMessage(ev) {
    var who = esc(ev.author_name || 'Someone');
    var doc = esc(ev.doc_title || 'a document');
    var href = ev.doc_href ? esc(ev.doc_href) : '';
    var docLink = href
      ? '<a href="' + href + '">' + doc + '</a>'
      : doc;
    if (ev.type === 'accepted') {
      return (
        '<div class="dp-challenge-toast-type is-accepted">' + esc(label('toast_accepted', 'Patch merged')) + '</div>' +
        '<div>A patch by ' + who + ' on ' + docLink + ' was merged.</div>'
      );
    }
    return (
      '<div class="dp-challenge-toast-type">' + esc(label('toast_new', 'New patch')) + '</div>' +
      '<div><strong>' + who + '</strong> submitted a patch on ' + docLink + '.</div>'
    );
  }

  function showNextToast() {
    if (activeToast || !toastQueue.length) return;
    var item = toastQueue.shift();
    var host = document.getElementById('dpChallengeToastHost');
    if (!host) return;

    var el = document.createElement('div');
    el.className = 'dp-challenge-toast';
    el.setAttribute('role', 'status');
    el.innerHTML = item.html;
    host.appendChild(el);
    activeToast = el;

    requestAnimationFrame(function () {
      el.classList.add('is-visible');
    });

    setTimeout(function () {
      el.classList.remove('is-visible');
      el.classList.add('is-fading');
    }, 5200);

    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
      activeToast = null;
      showNextToast();
    }, 5800);
  }

  function enqueueToast(ev, isInitial) {
    var key = eventKey(ev);
    if (seenKeys[key]) return;
    seenKeys[key] = true;
    if (!isInitial && toastQueue.length >= 3) {
      toastQueue.shift();
    }
    toastQueue.push({ html: toastMessage(ev) });
    showNextToast();
  }

  function shouldSkipEvent(ev) {
    return currentUserId && ev.author_user_id && ev.author_user_id === currentUserId;
  }

  function handleEvents(events, isInitial) {
    if (!events || !events.length) return;
    var sorted = events.slice().sort(function (a, b) {
      return (b.at || '').localeCompare(a.at || '');
    });
    sorted.forEach(function (ev) {
      if (shouldSkipEvent(ev)) return;
      enqueueToast(ev, isInitial);
    });
  }

  function pollRecent() {
    if (document.hidden) return;
    var since = lastPollAt;
    var url = recentApiPath + '?since=' + encodeURIComponent(since);
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.enabled) return;
        lastPollAt = new Date().toISOString();
        handleEvents(data.events || [], false);
      })
      .catch(function () { /* ignore */ });
  }

  function startPolling() {
    fetch(recentApiPath, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.enabled) return;
        (data.events || []).forEach(function (ev) {
          seenKeys[eventKey(ev)] = true;
        });
      })
      .catch(function () { /* ignore */ });

    pollTimer = setInterval(pollRecent, pollMs);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) pollRecent();
    });
  }

  function init() {
    bindDocPicker();
    bindDpChallengeInvite();
    startPolling();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
