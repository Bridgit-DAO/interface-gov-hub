/**
 * Nav pill newcomer tips + animation container hooks.
 */
(function () {
  'use strict';

  var OPT_OUT_KEY = 'ghNavPillTipsOptOut';
  var showTimer = null;
  var hideTimer = null;
  var tipHost = null;
  var activeBtn = null;

  function optedOut() {
    try {
      return localStorage.getItem(OPT_OUT_KEY) === '1';
    } catch (_e) {
      return false;
    }
  }

  function setOptedOut() {
    try {
      localStorage.setItem(OPT_OUT_KEY, '1');
    } catch (_e) { /* ignore */ }
  }

  function ensureTipHost() {
    if (tipHost) return tipHost;
    tipHost = document.createElement('div');
    tipHost.className = 'gh-nav-pill-tip-host';
    tipHost.setAttribute('role', 'tooltip');
    tipHost.hidden = true;
    tipHost.innerHTML =
      '<p class="gh-nav-pill-tip-text"></p>' +
      '<label class="gh-nav-pill-tip-optout">' +
      '<input type="checkbox" class="form-check-input gh-nav-pill-tip-checkbox">' +
      '<span>Don\u2019t show tips again</span></label>';
    document.body.appendChild(tipHost);
    tipHost.querySelector('.gh-nav-pill-tip-checkbox').addEventListener('change', function (e) {
      if (e.target.checked) {
        setOptedOut();
        hideTip(true);
      }
    });
    return tipHost;
  }

  function hideTip(immediate) {
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    if (!tipHost) return;
    tipHost.classList.remove('is-visible');
    hideTimer = setTimeout(function () {
      tipHost.hidden = true;
      activeBtn = null;
    }, immediate ? 0 : 180);
  }

  function positionTip(btn) {
    var host = ensureTipHost();
    var rect = btn.getBoundingClientRect();
    var top = rect.bottom + 8;
    var left = rect.left;
    host.style.top = top + 'px';
    host.style.left = left + 'px';
    if (left + host.offsetWidth > window.innerWidth - 12) {
      host.style.left = Math.max(12, window.innerWidth - host.offsetWidth - 12) + 'px';
    }
    if (top + host.offsetHeight > window.innerHeight - 12) {
      host.style.top = Math.max(12, rect.top - host.offsetHeight - 8) + 'px';
    }
  }

  function showTip(btn) {
    if (optedOut()) return;
    var container = btn.closest('[data-gh-nav-pills]');
    if (!container || container.getAttribute('data-gh-nav-tooltips') === 'false') return;
    var text = btn.getAttribute('data-gh-pill-tip');
    if (!text) return;

    var host = ensureTipHost();
    host.querySelector('.gh-nav-pill-tip-text').textContent = text;
    host.hidden = false;
    activeBtn = btn;
    positionTip(btn);
    requestAnimationFrame(function () {
      host.classList.add('is-visible');
    });
  }

  function bindContainer(container) {
    if (container.getAttribute('data-gh-nav-pills-bound') === '1') return;
    container.setAttribute('data-gh-nav-pills-bound', '1');

    container.querySelectorAll('.nav-link[data-gh-pill-tip]').forEach(function (btn) {
      btn.classList.add('gh-nav-pill');
      btn.addEventListener('mouseenter', function () {
        clearTimeout(hideTimer);
        showTimer = setTimeout(function () {
          showTip(btn);
        }, 350);
      });
      btn.addEventListener('mouseleave', function () {
        clearTimeout(showTimer);
        if (activeBtn === btn) hideTip(false);
      });
      btn.addEventListener('focus', function () {
        showTip(btn);
      });
      btn.addEventListener('blur', function () {
        if (activeBtn === btn) hideTip(false);
      });
    });
  }

  function init() {
    document.querySelectorAll('[data-gh-nav-pills]').forEach(bindContainer);
    window.addEventListener('scroll', function () {
      if (activeBtn) positionTip(activeBtn);
    }, true);
    window.addEventListener('resize', function () {
      if (activeBtn) positionTip(activeBtn);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.GhNavPills = { init: init, bindContainer: bindContainer };
})();
