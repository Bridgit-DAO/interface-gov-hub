/**
 * First-visit reader guide modal on document read pages.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'gh_reader_guide_v1_dismissed';

  function forceShow() {
    try {
      var q = new URLSearchParams(global.location.search);
      return q.get('reader_guide') === '1';
    } catch (_e) {
      return false;
    }
  }

  function dismissed() {
    if (forceShow()) {
      return false;
    }
    try {
      return localStorage.getItem(STORAGE_KEY) === '1';
    } catch (_e) {
      return false;
    }
  }

  function markDismissed() {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch (_e) { /* ignore */ }
  }

  function whenBootstrapReady(fn) {
    if (global.bootstrap && global.bootstrap.Modal) {
      fn();
      return;
    }
    var n = 0;
    var t = global.setInterval(function () {
      n += 1;
      if (global.bootstrap && global.bootstrap.Modal) {
        global.clearInterval(t);
        fn();
      } else if (n > 120) {
        global.clearInterval(t);
      }
    }, 50);
  }

  function reloadGuideGifs(modalEl) {
    var imgs = modalEl.querySelectorAll('.gh-guide-gif img[data-gh-guide-src]');
    for (var i = 0; i < imgs.length; i += 1) {
      var img = imgs[i];
      var base = img.getAttribute('data-gh-guide-src');
      if (!base) {
        continue;
      }
      var sep = base.indexOf('?') >= 0 ? '&' : '?';
      img.src = base + sep + '_t=' + String(Date.now());
    }
  }

  function showGuide(modalEl) {
    whenBootstrapReady(function () {
      try {
        var modal = global.bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      } catch (_e) { /* ignore */ }
    });
  }

  function init() {
    var modalEl = document.getElementById('ghReaderGuideModal');
    if (!modalEl) {
      return;
    }

    modalEl.addEventListener('show.bs.modal', function () {
      reloadGuideGifs(modalEl);
    });

    var dismissCb = document.getElementById('ghReaderGuideDismiss');
    modalEl.addEventListener('hidden.bs.modal', function () {
      if (dismissCb && dismissCb.checked) {
        markDismissed();
      }
    });

    if (!dismissed()) {
      showGuide(modalEl);
    }
  }

  /**
   * Run fn after the reader guide is not blocking the page (already dismissed or modal closed).
   */
  function whenBypassed(fn) {
    if (typeof fn !== 'function') {
      return;
    }
    if (dismissed()) {
      fn();
      return;
    }
    var modalEl = document.getElementById('ghReaderGuideModal');
    if (!modalEl) {
      fn();
      return;
    }
    modalEl.addEventListener('hidden.bs.modal', function () {
      fn();
    }, { once: true });
  }

  global.GhReaderGuide = {
    dismissed: dismissed,
    whenBypassed: whenBypassed,
  };

  function start() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }

  if (document.readyState === 'complete') {
    start();
  } else {
    global.addEventListener('load', start);
  }
})(typeof window !== 'undefined' ? window : globalThis);
