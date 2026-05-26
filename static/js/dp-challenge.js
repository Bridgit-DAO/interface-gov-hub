/**
 * DP Challenge hub: doc picker CTA + live activity toasts (30s poll).
 */
(function () {
  'use strict';

  var cfg = window.DP_CHALLENGE_PAGE || {};
  var pollMs = cfg.pollIntervalMs || 30000;
  var currentUserId = cfg.currentUserId || null;
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

  function eventKey(ev) {
    return (ev.type || '') + ':' + (ev.proposal_id || '') + ':' + (ev.at || '');
  }

  function bindDocPicker() {
    var picker = document.getElementById('dpChallengeDocPicker');
    var btn = document.getElementById('dpChallengeGoRead');
    if (!picker || !btn) return;
    btn.addEventListener('click', function () {
      var ref = (picker.value || '').trim();
      if (!ref) {
        picker.focus();
        return;
      }
      window.location.href =
        typeof window.ghReadUrl === 'function'
          ? window.ghReadUrl(ref, '/dp-challenge/')
          : '/doc/draft/' + encodeURIComponent(ref) + '/read/?return_to=' + encodeURIComponent('/dp-challenge/');
    });
  }

  function toastMessage(ev) {
    var who = esc(ev.author_name || 'Someone');
    var doc = esc(ev.doc_title || 'a DP draft');
    var href = ev.doc_href ? esc(ev.doc_href) : '';
    var docLink = href
      ? '<a href="' + href + '">' + doc + '</a>'
      : doc;
    if (ev.type === 'accepted') {
      return (
        '<div class="dp-challenge-toast-type is-accepted">Amendment accepted</div>' +
        '<div>An edit by ' + who + ' on ' + docLink + ' was accepted.</div>'
      );
    }
    return (
      '<div class="dp-challenge-toast-type">New proposal</div>' +
      '<div><strong>' + who + '</strong> proposed an edit on ' + docLink + '.</div>'
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
    var url = '/api/dp-challenge/recent?since=' + encodeURIComponent(since);
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
    var bootUrl = '/api/dp-challenge/recent';
    fetch(bootUrl, { credentials: 'same-origin' })
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

  bindDocPicker();
  startPolling();
})();
