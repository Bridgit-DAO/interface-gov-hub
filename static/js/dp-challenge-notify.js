/**
 * DP Challenge pre-launch notify modal (join waitlist + DP interests).
 */
(function () {
  'use strict';

  var cfg = window.DP_CHALLENGE_NOTIFY || {};
  var page = window.DP_CHALLENGE_PAGE || {};
  var modalEl = document.getElementById('dpChallengeNotifyModal');
  if (!modalEl) return;

  var selectEl = document.getElementById('dpChallengeNotifyDpSelect');
  var submitBtn = document.getElementById('dpChallengeNotifySubmitBtn');
  var openBtn = document.getElementById('dpChallengeNotifyOpenBtn');
  var msgEl = document.getElementById('dpChallengeNotifyMsg');
  var modal = typeof bootstrap !== 'undefined' ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

  function showMessage(text, isError) {
    if (!msgEl) return;
    msgEl.textContent = text || '';
    msgEl.classList.toggle('text-danger', !!isError);
    msgEl.classList.toggle('text-success', !isError && !!text);
  }

  function populateOptions() {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    var options = cfg.dp_options || [];
    var selected = {};
    (cfg.dp_interests || []).forEach(function (item) {
      if (item && item.submission_id) selected[item.submission_id] = true;
    });
    if (!options.length) {
      var empty = document.createElement('option');
      empty.textContent = 'No approved DP drafts yet';
      empty.disabled = true;
      selectEl.appendChild(empty);
      return;
    }
    options.forEach(function (opt) {
      var option = document.createElement('option');
      option.value = opt.submission_id;
      option.textContent = opt.label || opt.draft_ref || opt.submission_id;
      if (selected[opt.submission_id]) option.selected = true;
      selectEl.appendChild(option);
    });
  }

  function openModal() {
    populateOptions();
    showMessage('');
    if (modal) modal.show();
  }

  function selectedSubmissionIds() {
    if (!selectEl) return [];
    return Array.from(selectEl.selectedOptions).map(function (o) { return o.value; });
  }

  async function submitNotify() {
    if (!cfg.notify_api_path) {
      showMessage('Notify list is not configured yet.', true);
      return;
    }
    if (submitBtn) submitBtn.disabled = true;
    showMessage('Saving…');
    try {
      var res = await fetch(cfg.notify_api_path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          dp_interests: selectedSubmissionIds(),
          source: 'dp-challenge-notify',
          source_url: window.location.href,
        }),
      });
      var data = await res.json().catch(function () { return {}; });
      if (!res.ok) throw new Error(data.error || res.statusText);

      cfg.joined = true;
      cfg.dp_interests = data.dp_interests || [];
      if (typeof GhDialog !== 'undefined') {
        await GhDialog.alert({
          title: 'You are on the notify list',
          message: 'We will notify you when the DP Challenge opens in mid-July.',
          variant: 'success',
        });
      }
      if (modal) modal.hide();
      window.location.reload();
    } catch (e) {
      showMessage(e.message || 'Could not join the notify list.', true);
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  if (openBtn) openBtn.addEventListener('click', openModal);
  if (submitBtn) submitBtn.addEventListener('click', submitNotify);

  if (!cfg.joined && page.signedIn !== false) {
    window.setTimeout(openModal, 400);
  }
})();
