/**
 * Platform invitations: landing welcome modal (?invite=) + send-invite modal.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'gh_platform_invite_dismissed';
  var PASSAGE_COMPOSE_KEY = 'ghInvitePassageCompose';
  var copyToastTimer = null;

  function passageExcerptFromTarget(target) {
    if (!target || typeof target !== 'object') return '';
    var anchor = target.context_anchor;
    if (!anchor || !anchor.textQuote) return '';
    return String(anchor.textQuote.exact || '').trim();
  }

  function stashPassageCompose(inviteType, target, draftRef) {
    if (inviteType !== 'edit_document_passage' || !target) return;
    var excerpt = passageExcerptFromTarget(target);
    if (!excerpt) return;
    try {
      sessionStorage.setItem(
        PASSAGE_COMPOSE_KEY,
        JSON.stringify({
          invite_type: inviteType,
          draft_ref: (target.draft_ref || draftRef || '').trim(),
          context_anchor: target.context_anchor || null,
          passage_text: excerpt,
        })
      );
    } catch (_e) { /* ignore */ }
  }

  function readPassageComposeStash() {
    try {
      var raw = sessionStorage.getItem(PASSAGE_COMPOSE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  function clearPassageComposeStash() {
    try {
      sessionStorage.removeItem(PASSAGE_COMPOSE_KEY);
    } catch (_e) { /* ignore */ }
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function getTokenFromUrl() {
    try {
      return new URL(global.location.href).searchParams.get('invite');
    } catch (_e) {
      return null;
    }
  }

  function loginNextUrl() {
    return global.location.pathname + global.location.search + global.location.hash;
  }

  function redirectToLogin() {
    global.location.href = '/login/?next=' + encodeURIComponent(loginNextUrl());
  }

  function showCopiedToast() {
    var host = document.getElementById('gh-copy-toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'gh-copy-toast-host';
      host.className = 'gh-copy-toast-host';
      host.setAttribute('aria-live', 'polite');
      host.setAttribute('aria-atomic', 'true');
      document.body.appendChild(host);
    }
    if (copyToastTimer) {
      global.clearTimeout(copyToastTimer);
      copyToastTimer = null;
    }
    host.innerHTML = '';
    var toast = document.createElement('div');
    toast.className = 'gh-copy-toast is-visible';
    toast.textContent = 'Copied';
    host.appendChild(toast);
    copyToastTimer = global.setTimeout(function () {
      toast.classList.add('is-fading');
      global.setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 220);
      copyToastTimer = null;
    }, 1800);
  }

  function copyTextToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        if (document.execCommand('copy')) resolve();
        else reject(new Error('copy failed'));
      } catch (e) {
        reject(e);
      } finally {
        document.body.removeChild(ta);
      }
    });
  }

  function showInviteMessage(opts) {
    opts = opts || {};
    if (global.GhDialog && global.GhDialog.alert) {
      return global.GhDialog.alert({
        title: opts.title || 'Invitation',
        message: opts.message || '',
        variant: opts.variant || 'info',
        confirmLabel: opts.confirmLabel || 'OK',
      });
    }
    global.alert((opts.title ? opts.title + '\n\n' : '') + (opts.message || ''));
    return Promise.resolve();
  }

  function parseJsonFetch(r) {
    var ct = (r.headers.get('content-type') || '').toLowerCase();
    if (!ct.includes('application/json')) {
      return Promise.resolve({
        ok: false,
        status: r.status,
        data: { error: 'Unexpected server response. Please try again.' },
      });
    }
    return r.json().then(
      function (d) {
        return { ok: r.ok, status: r.status, data: d || {} };
      },
      function () {
        return {
          ok: false,
          status: r.status,
          data: { error: 'Could not read the server response. Please try again.' },
        };
      }
    );
  }

  function inviteTypeLabel(type) {
    var map = {
      participate_dp: 'join the DP Challenge',
      edit_document: 'suggest edits on a document',
      edit_document_passage: 'propose an edit on a specific passage',
      review_document: 'review a document',
      join_workgroup: 'join a workgroup',
    };
    return map[type] || 'participate on Gov Hub';
  }

  function inviteStepsHtml(inviteType) {
    if (inviteType === 'edit_document_passage') {
      return (
        '<p class="small text-muted mb-2">After you accept:</p>' +
        '<ol class="small mb-0 ps-3">' +
        '<li class="mb-1">You will open the document with the passage below highlighted.</li>' +
        '<li class="mb-1">The <strong>Suggest a change</strong> panel opens with that text.</li>' +
        '<li>Edit the proposed wording and post your proposal.</li>' +
        '</ol>'
      );
    }
    if (inviteType === 'edit_document') {
      return (
        '<p class="small text-muted mb-2">After you accept:</p>' +
        '<ol class="small mb-0 ps-3">' +
        '<li class="mb-1">You will open the full document below.</li>' +
        '<li class="mb-1"><strong>Select</strong> the sentence(s) you want to change in the text.</li>' +
        '<li class="mb-1">The <strong>Suggest a change</strong> panel opens — post your edit.</li>' +
        '</ol>'
      );
    }
    if (inviteType === 'review_document') {
      return '<p class="small text-muted mb-0">After you accept, you can read the document and follow any review guidance from the inviter.</p>';
    }
    if (inviteType === 'join_workgroup') {
      return '<p class="small text-muted mb-0">After you accept, you will be joined or asked to join the workgroup (approval may be required).</p>';
    }
    if (inviteType === 'participate_dp') {
      return '<p class="small text-muted mb-0">After you accept, you can browse DP drafts and propose edits from the DP Challenge page.</p>';
    }
    return '';
  }

  function buildInviteWelcomeBody(preview) {
    var inviter = esc(preview.inviter_name || 'Someone');
    var title = esc(preview.target_title || 'Gov Hub');
    var action = esc(inviteTypeLabel(preview.invite_type));
    var html =
      '<p class="mb-2"><strong>' + inviter + '</strong> invited you to ' + action +
      ' on <strong>' + title + '</strong>.</p>';

    if (preview.invitee_email_masked) {
      html +=
        '<p class="small mb-3">This invitation was sent to <strong>' +
        esc(preview.invitee_email_masked) +
        '</strong>.</p>';
    }

    if (preview.message && String(preview.message).trim()) {
      html +=
        '<div class="gh-invite-panel mb-3"><em>' +
        esc(String(preview.message).trim()) +
        '</em></div>';
    }

    var passage = (preview.passage_excerpt || '').trim() || passageExcerptFromTarget(preview.target || {});
    if (passage) {
      html +=
        '<p class="gh-invite-label mb-1">Passage to edit</p>' +
        '<blockquote class="gh-invite-passage mb-3">' +
        esc(passage) +
        '</blockquote>';
    } else if ((preview.document_abstract || '').trim()) {
      html +=
        '<p class="gh-invite-label mb-1">About this document</p>' +
        '<div class="gh-invite-panel gh-invite-panel--scroll mb-3">' +
        esc(preview.document_abstract.trim()) +
        '</div>';
    }

    html += inviteStepsHtml(preview.invite_type);
    return html;
  }

  function signInNoteHtml(isAuthenticated) {
    if (isAuthenticated) {
      return (
        '<p class="small text-muted mb-0 mt-3 pt-3 border-top">' +
        'You are signed in. Accept to continue to the invited page.</p>'
      );
    }
    return (
      '<p class="small mb-0 mt-3 pt-3 border-top" id="ghInviteWelcomeSignInNote">' +
      '<strong>Not signed in?</strong> Use <strong>Google</strong> or <strong>email</strong> with the same address this invitation was sent to ' +
      '(above), or an OAuth account linked to that email. ' +
      '<span class="text-muted">Wallet sign-in often does not work for invitations.</span></p>'
    );
  }

  function ensureInviteWelcomeModal() {
    var el = document.getElementById('ghInviteWelcomeModal');
    if (el) return el;
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="modal fade" id="ghInviteWelcomeModal" tabindex="-1" aria-labelledby="ghInviteWelcomeTitle" aria-hidden="true" style="z-index: 1096;">' +
      '<div class="modal-dialog modal-dialog-centered modal-lg modal-dialog-scrollable">' +
      '<div class="modal-content">' +
      '<div class="modal-header">' +
      '<h5 class="modal-title" id="ghInviteWelcomeTitle">Invitation</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>' +
      '</div>' +
      '<div class="modal-body">' +
      '<div id="ghInviteWelcomeAlert" class="alert d-none" role="alert"></div>' +
      '<div id="ghInviteWelcomeBody"></div>' +
      '<div id="ghInviteWelcomeSignIn"></div>' +
      '</div>' +
      '<div class="modal-footer flex-wrap gap-2">' +
      '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Not now</button>' +
      '<button type="button" class="btn btn-primary" id="ghInviteWelcomePrimaryBtn">Accept invitation</button>' +
      '</div></div></div></div>';
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('ghInviteWelcomeModal');
  }

  function setWelcomeAlert(message, variant) {
    var alertEl = document.getElementById('ghInviteWelcomeAlert');
    if (!alertEl) return;
    if (!message) {
      alertEl.className = 'alert d-none';
      alertEl.textContent = '';
      return;
    }
    alertEl.className = 'alert alert-' + (variant || 'danger');
    alertEl.textContent = message;
  }

  function inviteStorageState(token) {
    return sessionStorage.getItem(STORAGE_KEY + ':' + token);
  }

  function shouldSkipInviteFlow(token) {
    return inviteStorageState(token) === 'accepted';
  }

  function extractInviteTokenFromPath(path) {
    if (!path || path.indexOf('invite=') < 0) return null;
    try {
      var query = path.indexOf('?') >= 0 ? path.slice(path.indexOf('?') + 1) : '';
      return new URLSearchParams(query).get('invite');
    } catch (_e) {
      return null;
    }
  }

  function applyAcceptResult(token, data) {
    sessionStorage.setItem(STORAGE_KEY + ':' + token, 'accepted');
    if (data.invite_type === 'edit_document_passage' && data.target) {
      stashPassageCompose(
        data.invite_type,
        data.target,
        (data.target.draft_ref || '').trim()
      );
    }
  }

  function fetchSessionAuthenticated() {
    return fetch('/api/user/me', { credentials: 'same-origin' })
      .then(function (r) {
        return r.ok;
      })
      .catch(function () {
        return false;
      });
  }

  function updateWelcomeAuthUi(authed) {
    var btn = document.getElementById('ghInviteWelcomePrimaryBtn');
    var signInEl = document.getElementById('ghInviteWelcomeSignIn');
    if (btn) {
      btn.disabled = false;
      btn.textContent = authed ? 'Accept invitation' : 'Sign in to accept';
    }
    if (signInEl) {
      signInEl.innerHTML = signInNoteHtml(authed);
    }
  }

  function acceptInvitation(token, preview, onDone, retryOn401) {
    return fetch('/api/invitations/by-token/' + encodeURIComponent(token) + '/accept/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    })
      .then(parseJsonFetch)
      .then(function (res) {
        if (res.status === 401 && !retryOn401) {
          return fetchSessionAuthenticated().then(function (authed) {
            if (authed) {
              return acceptInvitation(token, preview, onDone, true);
            }
            setWelcomeAlert(
              'Please sign in with the invited email (or Google/OAuth linked to it), then accept again.',
              'warning'
            );
            updateWelcomeAuthUi(false);
            return;
          });
        }
        if (res.status === 401) {
          setWelcomeAlert(
            'Your session expired. Sign in again with the invited email, then accept.',
            'warning'
          );
          updateWelcomeAuthUi(false);
          return;
        }
        if (!res.ok) {
          var errMsg = res.data.error || 'Could not accept invitation';
          if (res.status === 403 && errMsg.toLowerCase().indexOf('email') >= 0) {
            errMsg =
              'This invitation was sent to a different email address. Sign in with the invited account, or ask ' +
              (preview.inviter_name || 'the sender') +
              ' to send a new invite.';
          }
          setWelcomeAlert(errMsg, 'danger');
          var retryBtn = document.getElementById('ghInviteWelcomePrimaryBtn');
          if (retryBtn) retryBtn.disabled = false;
          return;
        }
        applyAcceptResult(token, res.data);
        if (onDone) {
          onDone(res.data);
        } else if (res.data.redirect_path) {
          global.location.replace(res.data.redirect_path);
        }
      })
      .catch(function () {
        setWelcomeAlert(
          'We could not reach the server. Check your connection and try again.',
          'danger'
        );
        var btn = document.getElementById('ghInviteWelcomePrimaryBtn');
        if (btn) btn.disabled = false;
      });
  }

  function finishLoginWithInviteAccept(returnPath) {
    var path = returnPath || '/';
    var token = extractInviteTokenFromPath(path);
    if (!token) {
      return Promise.resolve(path);
    }
    return fetchSessionAuthenticated().then(function (authed) {
      if (!authed) {
        return path;
      }
      return fetch('/api/invitations/by-token/' + encodeURIComponent(token) + '/accept/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
      })
        .then(parseJsonFetch)
        .then(function (res) {
          if (!res.ok) {
            return path;
          }
          applyAcceptResult(token, res.data);
          return res.data.redirect_path || path;
        })
        .catch(function () {
          return path;
        });
    });
  }

  function showInviteWelcomeModal(preview) {
    var token = getTokenFromUrl();
    if (!token) return;
    if (shouldSkipInviteFlow(token)) return;
    if (inviteStorageState(token) === 'dismissed') return;

    var bs = bootstrapApi();
    if (!bs) {
      showInviteMessage({
        title: 'Invitation',
        message: preview.inviter_name + ' invited you. Sign in and return to this link to accept.',
        variant: 'info',
      });
      return;
    }

    var modalEl = ensureInviteWelcomeModal();
    document.getElementById('ghInviteWelcomeBody').innerHTML = buildInviteWelcomeBody(preview);
    setWelcomeAlert('', '');

    var primaryBtn = document.getElementById('ghInviteWelcomePrimaryBtn');
    primaryBtn.onclick = function () {
      fetchSessionAuthenticated().then(function (authed) {
        if (!authed) {
          try {
            sessionStorage.setItem('gh_invite_pending_login', token);
          } catch (_e) { /* ignore */ }
          redirectToLogin();
          return;
        }
        primaryBtn.disabled = true;
        acceptInvitation(token, preview, function (data) {
          var modal = bs.Modal.getInstance(modalEl);
          if (modal) modal.hide();
          if (data.redirect_path) {
            global.location.replace(data.redirect_path);
          }
        });
      });
    };

    fetchSessionAuthenticated().then(function (authed) {
      updateWelcomeAuthUi(authed);
    });

    var modal = bs.Modal.getOrCreateInstance(modalEl, { backdrop: 'static', keyboard: true });
    modalEl.addEventListener(
      'hidden.bs.modal',
      function onHidden() {
        modalEl.removeEventListener('hidden.bs.modal', onHidden);
        if (inviteStorageState(token) !== 'accepted') {
          sessionStorage.setItem(STORAGE_KEY + ':' + token, 'dismissed');
        }
      },
      { once: true }
    );
    modal.show();
    var backdrops = document.querySelectorAll('.modal-backdrop');
    if (backdrops.length) {
      backdrops[backdrops.length - 1].style.zIndex = '1090';
    }
    modalEl.style.zIndex = '1096';
  }

  function loadInviteFromUrl() {
    var path = global.location.pathname || '';
    if (path === '/login' || path === '/login/') return;

    var token = getTokenFromUrl();
    if (!token) return;
    if (shouldSkipInviteFlow(token)) return;

    fetch('/api/invitations/by-token/' + encodeURIComponent(token) + '/', {
      credentials: 'same-origin',
    })
      .then(parseJsonFetch)
      .then(function (res) {
        if (!res.ok || !res.data.valid) return;
        var preview = res.data;
          if (preview.invitee_email) {
            try {
              sessionStorage.setItem('gh_invite_login_hint', String(preview.invitee_email).trim().toLowerCase());
            } catch (_e) {}
          }
        return fetchSessionAuthenticated().then(function (meOk) {
          var authed = !!preview.authenticated || meOk;
          var pendingLogin = false;
          try {
            pendingLogin = sessionStorage.getItem('gh_invite_pending_login') === token;
            if (pendingLogin) {
              sessionStorage.removeItem('gh_invite_pending_login');
            }
          } catch (_e) { /* ignore */ }

          if (authed && pendingLogin) {
            return acceptInvitation(token, preview, function (data) {
              global.location.replace(data.redirect_path || global.location.pathname);
            });
          }
          if (inviteStorageState(token) === 'dismissed') return;
          showInviteWelcomeModal(preview);
        });
      })
      .catch(function () {});
  }

  function ensureModal() {
    var el = document.getElementById('ghInviteModal');
    if (el) return el;
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="modal fade" id="ghInviteModal" tabindex="-1" aria-hidden="true" style="z-index: 1095;">' +
      '<div class="modal-dialog"><div class="modal-content">' +
      '<div class="modal-header"><h5 class="modal-title" id="ghInviteModalTitle">Invite someone</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
      '<div class="modal-body">' +
      '<div id="ghInviteAlert" class="alert d-none" role="alert"></div>' +
      '<p class="text-muted small" id="ghInviteHint"></p>' +
      '<label class="form-label" for="ghInviteEmail">Email</label>' +
      '<input type="email" class="form-control mb-3" id="ghInviteEmail" required>' +
      '<label class="form-label" for="ghInviteMessage">Personal note (optional)</label>' +
      '<textarea class="form-control" id="ghInviteMessage" rows="3"></textarea>' +
      '</div><div class="modal-footer">' +
      '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>' +
      '<button type="button" class="btn btn-primary" id="ghInviteSubmitBtn">' +
      '<i class="fas fa-paper-plane me-1"></i>Send invitation</button>' +
      '</div></div></div></div>';
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('ghInviteModal');
  }

  function bootstrapApi() {
    return global.bootstrap || window.bootstrap;
  }

  function inviteDialogUnavailable() {
    if (global.GhDialog && global.GhDialog.alert) {
      global.GhDialog.alert({
        title: 'Invite unavailable',
        message: 'The invite dialog could not open. Refresh the page and try again.',
        variant: 'warning',
      });
      return;
    }
    global.alert('Invite dialog is not available. Please refresh the page.');
  }

  function openInviteModal(opts) {
    opts = opts || {};
    var modalEl = ensureModal();
    var bs = bootstrapApi();
    if (!modalEl || !bs) {
      inviteDialogUnavailable();
      return;
    }
    document.getElementById('ghInviteModalTitle').textContent = opts.title || 'Invite someone';
    document.getElementById('ghInviteHint').textContent = opts.hint || '';
    document.getElementById('ghInviteEmail').value = '';
    document.getElementById('ghInviteMessage').value = '';
    var alertEl = document.getElementById('ghInviteAlert');
    alertEl.className = 'alert d-none';
    alertEl.innerHTML = '';

    var state = {
      type: opts.type,
      target: opts.target || {},
    };

    document.getElementById('ghInviteSubmitBtn').onclick = function () {
      var btn = document.getElementById('ghInviteSubmitBtn');
      var email = document.getElementById('ghInviteEmail').value.trim();
      if (!email) {
        alertEl.className = 'alert alert-danger';
        alertEl.textContent = 'Email is required';
        return;
      }
      btn.disabled = true;
      fetch('/api/invitations/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
          type: state.type,
          email: email,
          message: document.getElementById('ghInviteMessage').value.trim() || null,
          target: state.target,
        }),
      })
        .then(parseJsonFetch)
        .then(function (res) {
          btn.disabled = false;
          if (res.status === 401) {
            showInviteMessage({
              title: 'Sign in required',
              message: 'Sign in to send invitations.',
              variant: 'info',
              confirmLabel: 'Sign in',
            }).then(function () {
              redirectToLogin();
            });
            return;
          }
          if (!res.ok) {
            alertEl.className = 'alert alert-danger';
            alertEl.textContent = res.data.error || 'Failed to send invitation';
            return;
          }
          var link = res.data.invite_path
            ? global.location.origin + res.data.invite_path
            : '';
          var msg = res.data.message || res.data.duplicate
            ? (res.data.message || 'Invitation noted.')
            : 'Invitation sent' + (res.data.email_sent ? ' by email' : '') + '.';
          alertEl.className = 'alert alert-success';
          alertEl.innerHTML = esc(msg);
          if (link) {
            alertEl.innerHTML +=
              ' <button type="button" class="btn btn-sm btn-outline-secondary ms-2" data-copy="' +
              esc(link) + '">Copy link</button>';
            var copyBtn = alertEl.querySelector('[data-copy]');
            if (copyBtn) {
              copyBtn.addEventListener('click', function () {
                copyTextToClipboard(link)
                  .then(function () {
                    showCopiedToast();
                  })
                  .catch(function () {
                    showInviteMessage({
                      title: 'Copy failed',
                      message: 'Could not copy the link. Select and copy it manually.',
                      variant: 'warning',
                    });
                  });
              });
            }
          }
        })
        .catch(function () {
          btn.disabled = false;
          alertEl.className = 'alert alert-danger';
          alertEl.textContent =
            'We could not reach the server. Check your connection and try again.';
        });
    };

    var modal = bs.Modal.getOrCreateInstance(modalEl);
    modal.show();
    var backdrops = document.querySelectorAll('.modal-backdrop');
    if (backdrops.length) {
      backdrops[backdrops.length - 1].style.zIndex = '1090';
    }
    modalEl.style.zIndex = '1095';
  }

  /** No-op: welcome is combined into invite landing modal. */
  function showDocumentEditWelcomeIfNeeded() {
    return Promise.resolve();
  }

  global.GhInvite = {
    open: openInviteModal,
    refreshBanner: loadInviteFromUrl,
    loadInviteFromUrl: loadInviteFromUrl,
    finishLoginWithInviteAccept: finishLoginWithInviteAccept,
    showCopiedToast: showCopiedToast,
    copyText: copyTextToClipboard,
    stashPassageCompose: stashPassageCompose,
    readPassageComposeStash: readPassageComposeStash,
    clearPassageComposeStash: clearPassageComposeStash,
    passageExcerptFromTarget: passageExcerptFromTarget,
    showDocumentEditWelcomeIfNeeded: showDocumentEditWelcomeIfNeeded,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadInviteFromUrl);
  } else {
    loadInviteFromUrl();
  }
})(window);
