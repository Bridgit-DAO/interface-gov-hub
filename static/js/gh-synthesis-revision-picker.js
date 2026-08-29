/**
 * Gov Hub revision picker – loads Canopi workgroup synthesis export per passage.
 */
(function () {
  'use strict';

  var cfg = window.GH_PATCHES_PAGE || {};
  var draftRef = cfg.draftRef || '';

  function apiUrl(proposalId) {
    return (
      '/api/doc/draft/' +
      encodeURIComponent(draftRef) +
      '/passage-synthesis/' +
      encodeURIComponent(proposalId) +
      '/'
    );
  }

  function esc(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function removeModal() {
    var el = document.getElementById('ghSynthesisRevisionModal');
    if (el) el.remove();
  }

  function showError(message) {
    if (window.GhDialog && window.GhDialog.alert) {
      window.GhDialog.alert({
        title: 'Synthesis export failed',
        message: message,
        variant: 'danger',
      });
    }
  }

  function renderVariantRow(variant) {
    return (
      '<li class="mb-2">' +
      '<div class="small text-muted">' +
      esc(variant.judgeCount) +
      ' judge(s)</div>' +
      '<pre class="gh-synthesis-variant-pre mb-0">' +
      esc(variant.text) +
      '</pre>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary mt-1 gh-synthesis-use-text">Copy text</button>' +
      '</li>'
    );
  }

  function renderInstanceRow(row) {
    return (
      '<tr>' +
      '<td><code class="small">' +
      esc(row.instanceId) +
      '</code></td>' +
      '<td>' +
      esc(row.kind) +
      '</td>' +
      '<td>' +
      esc(row.enabledJudgeCount) +
      '</td>' +
      '</tr>'
    );
  }

  function renderJudgeRow(judge) {
    var rationale = judge.rationale ? '<div class="small text-muted">' + esc(judge.rationale) + '</div>' : '';
    return (
      '<li class="mb-2 border-bottom pb-2">' +
      '<div class="small"><strong>Judge</strong> ' +
      esc(judge.userId) +
      ' · ' +
      esc(judge.lens) +
      ' · ' +
      esc(judge.approvedAt) +
      '</div>' +
      rationale +
      '</li>'
    );
  }

  function bindCopyButtons(modal) {
    modal.querySelectorAll('.gh-synthesis-use-text').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var pre = btn.parentElement && btn.parentElement.querySelector('.gh-synthesis-variant-pre');
        var text = pre ? pre.textContent || '' : '';
        if (!text) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function () {
            if (window.GhDialog && window.GhDialog.alert) {
              window.GhDialog.alert({
                title: 'Copied',
                message: 'Passage text copied. Paste into your revision draft.',
                variant: 'success',
              });
            }
          });
        }
      });
    });
  }

  function openModal(exportBundle) {
    removeModal();
    var summary = exportBundle.summary || {};
    var judges = exportBundle.judges || [];
    var variants = exportBundle.editedSnapshotVariants || [];
    var tally = exportBundle.instanceTally || [];
    var scope = exportBundle.scope || {};

    var body =
      '<div class="small text-muted mb-3">' +
      'Advisory synthesis from Canopi embed judges for this anchor. ' +
      'Pick canonical wording in your revision workflow.' +
      '</div>' +
      '<p class="mb-2"><strong>Approved judgments:</strong> ' +
      esc(summary.approvedJudgmentCount || 0) +
      ' (' +
      esc(summary.distinctJudgeCount || 0) +
      ' judges)</p>' +
      '<p class="mb-3 small text-muted">Scope: ' +
      esc(scope.pageId) +
      ' · union ' +
      esc(scope.anchorUnionHash) +
      '</p>';

    if (variants.length) {
      body +=
        '<h6 class="mt-3">Edited passage variants</h6><ul class="list-unstyled">' +
        variants.map(renderVariantRow).join('') +
        '</ul>';
    }

    if (tally.length) {
      body +=
        '<h6 class="mt-3">Instance tally</h6>' +
        '<table class="table table-sm"><thead><tr><th>Instance</th><th>Kind</th><th>Judges</th></tr></thead><tbody>' +
        tally.map(renderInstanceRow).join('') +
        '</tbody></table>';
    }

    if (judges.length) {
      body +=
        '<h6 class="mt-3">Judges</h6><ul class="list-unstyled mb-0">' +
        judges.map(renderJudgeRow).join('') +
        '</ul>';
    }

    if (!variants.length && !judges.length) {
      body +=
        '<div class="alert alert-secondary mb-0">No approved personal judgments yet for this passage on the embed.</div>';
    }

    var modal = document.createElement('div');
    modal.id = 'ghSynthesisRevisionModal';
    modal.className = 'modal fade';
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-labelledby', 'ghSynthesisRevisionTitle');
    modal.innerHTML =
      '<div class="modal-dialog modal-lg modal-dialog-scrollable">' +
      '<div class="modal-content">' +
      '<div class="modal-header">' +
      '<h5 class="modal-title" id="ghSynthesisRevisionTitle">Synthesis revision picker</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
      '</div>' +
      '<div class="modal-body">' +
      body +
      '</div>' +
      '<div class="modal-footer">' +
      '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>' +
      '</div>' +
      '</div></div>';

    document.body.appendChild(modal);
    bindCopyButtons(modal);

    if (window.bootstrap && window.bootstrap.Modal) {
      var instance = window.bootstrap.Modal.getOrCreateInstance(modal);
      modal.addEventListener('hidden.bs.modal', removeModal, { once: true });
      instance.show();
    } else {
      modal.classList.add('show');
      modal.style.display = 'block';
    }
  }

  async function loadSynthesis(proposalId) {
    try {
      var res = await fetch(apiUrl(proposalId), {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      var data = await res.json();
      if (!res.ok) {
        showError(data.error || 'Request failed');
        return;
      }
      openModal(data.export || {});
    } catch (err) {
      showError(err && err.message ? err.message : 'Network error');
    }
  }

  document.addEventListener('click', function (ev) {
    var btn = ev.target && ev.target.closest('.gh-passage-synthesis-btn');
    if (!btn) return;
    var proposalId = btn.getAttribute('data-proposal-id');
    if (!proposalId) return;
    ev.preventDefault();
    loadSynthesis(proposalId);
  });
})();
