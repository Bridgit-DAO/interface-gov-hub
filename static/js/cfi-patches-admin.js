/**
 * CFI admin page – promote proposed patches to Canopi Discuss.
 */
(function () {
  'use strict';

  function showError(message) {
    if (window.GhDialog && window.GhDialog.alert) {
      window.GhDialog.alert({
        title: 'Promote failed',
        message: message,
        variant: 'danger',
      });
    }
  }

  function showSuccess(message) {
    if (window.GhDialog && window.GhDialog.alert) {
      window.GhDialog.alert({
        title: 'Promoted to Canopi',
        message: message,
        variant: 'success',
      });
    }
  }

  async function confirmPromote(title, message) {
    if (!window.GhDialog || !window.GhDialog.confirm) return false;
    return window.GhDialog.confirm({
      title: title,
      message: message,
      variant: 'warning',
      confirmLabel: 'Promote to Canopi',
    });
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try {
      data = await res.json();
    } catch (_e) {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data.error || 'Request failed (' + res.status + ')');
    }
    return data;
  }

  async function promotePatch(btn) {
    const patchId = btn.getAttribute('data-patch-id');
    if (!patchId) return;
    const ok = await confirmPromote(
      'Promote patch to Canopi',
      'Publish this CFI proposal to Canopi Discuss on the DP book overlay?'
    );
    if (!ok) return;

    btn.disabled = true;
    try {
      const data = await postJson('/api/admin/cfi-patches/promote', { patch_id: patchId });
      if (data.discussHref) {
        showSuccess('Patch is live on Canopi Discuss.');
        window.location.reload();
        return;
      }
      showSuccess('Patch promoted to Canopi.');
      window.location.reload();
    } catch (err) {
      showError(err.message || 'Promote failed');
      btn.disabled = false;
    }
  }

  async function promoteSubmission(btn) {
    const submissionId = btn.getAttribute('data-submission-id');
    if (!submissionId) return;
    const ok = await confirmPromote(
      'Promote submission to Canopi',
      'Publish all unpromoted patches from this CFI submission to Canopi Discuss?'
    );
    if (!ok) return;

    btn.disabled = true;
    try {
      const data = await postJson('/api/admin/cfi-patches/promote-submission', {
        submission_id: submissionId,
      });
      const published = data.published || 0;
      const failed = data.failed || 0;
      if (failed > 0) {
        showSuccess('Promoted ' + published + ' patch(es). ' + failed + ' failed – reload to review.');
      } else {
        showSuccess('Promoted ' + published + ' patch(es) to Canopi Discuss.');
      }
      window.location.reload();
    } catch (err) {
      showError(err.message || 'Promote failed');
      btn.disabled = false;
    }
  }

  document.querySelectorAll('.gh-cfi-promote-patch').forEach(function (btn) {
    btn.addEventListener('click', function () {
      promotePatch(btn);
    });
  });

  document.querySelectorAll('.gh-cfi-promote-submission').forEach(function (btn) {
    btn.addEventListener('click', function () {
      promoteSubmission(btn);
    });
  });
})();
