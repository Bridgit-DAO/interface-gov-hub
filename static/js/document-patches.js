/**
 * Document patches page — merge/decline via API (passage-anchored patches only).
 */
(function () {
  'use strict';

  var cfg = window.GH_PATCHES_PAGE || {};
  var draftRef = cfg.draftRef || '';

  function apiUrl(path) {
    return '/api/doc/draft/' + encodeURIComponent(draftRef) + path;
  }

  function showError(message) {
    if (window.GhDialog && window.GhDialog.alert) {
      window.GhDialog.alert({
        title: 'Action failed',
        message: message,
        variant: 'danger',
      });
      return;
    }
    window.alert(message);
  }

  async function reviewPatch(patchId, action) {
    var isMerge = action === 'accept';
    var title = isMerge ? 'Merge patch' : 'Decline patch';
    var message = isMerge
      ? 'Merge this patch into the document standard?'
      : 'Decline this patch?';
    var variant = isMerge ? 'warning' : 'danger';
    var confirmLabel = isMerge ? 'Merge patch' : 'Decline';

    if (window.GhDialog && window.GhDialog.confirm) {
      var ok = await window.GhDialog.confirm({
        title: title,
        message: message,
        variant: variant,
        confirmLabel: confirmLabel,
      });
      if (!ok) return;
    } else if (!window.confirm(message)) {
      return;
    }

    try {
      var r = await fetch(apiUrl('/proposals/' + encodeURIComponent(patchId) + '/' + action + '/'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
      });
      var data = {};
      try {
        data = await r.json();
      } catch (_e) {
        data = {};
      }
      if (!r.ok) {
        showError(data.error || 'Request failed (' + r.status + ')');
        return;
      }
      window.location.reload();
    } catch (_err) {
      showError('Network error. Please try again.');
    }
  }

  document.querySelectorAll('[data-gh-patch-action]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var patchId = btn.getAttribute('data-patch-id');
      var action = btn.getAttribute('data-gh-patch-action');
      if (!patchId || !action) return;
      reviewPatch(patchId, action);
    });
  });
})();
