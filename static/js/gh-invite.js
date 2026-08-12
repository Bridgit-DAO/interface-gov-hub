/**
 * Platform invitations: landing welcome modal (?invite=) + send-invite modal.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'gh_platform_invite_dismissed';
  var PASSAGE_COMPOSE_KEY = 'ghInvitePassageCompose';
  var INVITE_MSG_DRAFT_PREFIX = 'ghInviteDraftMsg:';
  var copyToastTimer = null;
  var invitePickedUsers = [];

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
      edit_document: 'propose patches on a document',
      edit_document_passage: 'propose a patch on a specific passage',
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
        '<li class="mb-1">The <strong>Propose a patch</strong> panel opens with that text.</li>' +
        '<li>Edit the patched wording and submit your patch.</li>' +
        '</ol>'
      );
    }
    if (inviteType === 'edit_document') {
      return (
        '<p class="small text-muted mb-2">After you accept:</p>' +
        '<ol class="small mb-0 ps-3">' +
        '<li class="mb-1">You will open the full document below.</li>' +
        '<li class="mb-1"><strong>Select</strong> the sentence(s) you want to change in the text.</li>' +
        '<li class="mb-1">The <strong>Propose a patch</strong> panel opens – submit your patch.</li>' +
        '</ol>'
      );
    }
    if (inviteType === 'review_document') {
      return '<p class="small text-muted mb-0">After you accept, you can read the document and follow any review guidance from the inviter.</p>';
    }
    if (inviteType === 'join_workgroup') {
      return '<p class="small text-muted mb-0">After you accept, you will be joined or asked to join the workgroup (approval may be required). Sign in with any email – the invite link is what authorizes you.</p>';
    }
    if (inviteType === 'participate_dp') {
      return '<p class="small text-muted mb-0">After you accept, you can browse DP drafts and propose patches from the DP Challenge page.</p>';
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

    if (preview.shareable) {
      html +=
        '<p class="small mb-3 text-muted">Anyone with this link can participate after signing in (any email).</p>';
    } else if (preview.invite_type !== 'join_workgroup' && preview.invitee_email_masked) {
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
      '<strong>Not signed in?</strong> Sign in with Google or email to continue. ' +
      '<span class="text-muted">Wallet sign-in may not work on all flows.</span></p>'
    );
  }

  function inviteComposeModeToggleHtml(inviteType) {
    if (inviteType !== 'edit_document' && inviteType !== 'edit_document_passage') {
      return '';
    }
    return (
      '<div class="mb-3" id="ghInviteComposeModeWrap">' +
      '<p class="small text-muted mb-2">After you accept, open the document as:</p>' +
      '<div class="btn-group btn-group-sm" role="group">' +
      '<button type="button" class="btn btn-primary active" data-gh-compose-mode="propose">Patch</button>' +
      '<button type="button" class="btn btn-outline-primary" data-gh-compose-mode="comment">Comment</button>' +
      '</div></div>'
    );
  }

  function bindInviteComposeModeToggle() {
    var wrap = document.getElementById('ghInviteComposeModeWrap');
    if (!wrap) return 'propose';
    var mode = 'propose';
    wrap.querySelectorAll('[data-gh-compose-mode]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        mode = btn.getAttribute('data-gh-compose-mode') === 'comment' ? 'comment' : 'propose';
        wrap.querySelectorAll('[data-gh-compose-mode]').forEach(function (b) {
          var on = b.getAttribute('data-gh-compose-mode') === mode;
          b.classList.toggle('btn-primary', on);
          b.classList.toggle('btn-outline-primary', !on);
          b.classList.toggle('active', on);
        });
        try {
          sessionStorage.setItem('gh_compose_mode', mode);
        } catch (_e) { /* ignore */ }
      });
    });
    return mode;
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
    try {
      var mode = sessionStorage.getItem('gh_compose_mode') || 'propose';
      sessionStorage.setItem('gh_compose_mode', mode);
    } catch (_e) { /* ignore */ }
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
    var inviteType = preview && preview.invite_type;
    var isWorkgroupInvite = inviteType === 'join_workgroup';
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
              isWorkgroupInvite
                ? 'Please sign in, then accept again.'
                : 'Please sign in with the invited email (or Google/OAuth linked to it), then accept again.',
              'warning'
            );
            updateWelcomeAuthUi(false);
            return;
          });
        }
        if (res.status === 401) {
          setWelcomeAlert(
            isWorkgroupInvite
              ? 'Your session expired. Sign in again, then accept.'
              : 'Your session expired. Sign in again with the invited email, then accept.',
            'warning'
          );
          updateWelcomeAuthUi(false);
          return;
        }
        if (!res.ok) {
          var errMsg = res.data.error || 'Could not accept invitation';
          if (!isWorkgroupInvite && res.status === 403 && errMsg.toLowerCase().indexOf('email') >= 0) {
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
    document.getElementById('ghInviteWelcomeBody').innerHTML =
      inviteComposeModeToggleHtml(preview.invite_type) + buildInviteWelcomeBody(preview);
    bindInviteComposeModeToggle();
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
          if (!preview.shareable && preview.invitee_email) {
            try {
              sessionStorage.setItem('gh_invite_login_hint', String(preview.invitee_email).trim().toLowerCase());
            } catch (_e) {}
          } else {
            try {
              sessionStorage.removeItem('gh_invite_login_hint');
            } catch (_e2) {}
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
      '<div class="modal-dialog modal-lg"><div class="modal-content">' +
      '<div class="modal-header"><h5 class="modal-title" id="ghInviteModalTitle">Invite someone</h5>' +
      '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
      '<div class="modal-body">' +
      '<div id="ghInviteAlert" class="alert d-none" role="alert"></div>' +
      '<div id="ghInviteShareableBlock" class="card bg-secondary bg-opacity-10 mb-3 d-none">' +
      '<div class="card-body py-3">' +
      '<p class="small fw-semibold mb-2"><i class="fas fa-link me-1"></i>Shareable invitation link</p>' +
      '<p class="small text-muted mb-2">Anyone with this link can open the invite after signing in. ' +
      'Use the same link for every person – email is optional below.</p>' +
      '<div class="input-group input-group-sm">' +
      '<input type="text" class="form-control font-monospace" id="ghInviteShareableUrl" readonly>' +
      '<button type="button" class="btn btn-outline-primary" id="ghInviteShareableCopyBtn">' +
      '<i class="fas fa-copy me-1"></i>Copy</button>' +
      '<button type="button" class="btn btn-outline-danger" id="ghInviteShareableRevokeBtn" title="Revoke this link">' +
      '<i class="fas fa-ban me-1"></i>Revoke</button></div></div></div>' +
      '<p class="text-muted small" id="ghInviteHint"></p>' +
      '<p class="small text-muted mb-2" id="ghInviteEmailDivider" class="d-none">Or invite specific people by email</p>' +
      '<label class="form-label" for="ghInviteRecipients">People to invite</label>' +
      '<div class="position-relative mb-1">' +
      '<textarea class="form-control" id="ghInviteRecipients" rows="3" ' +
      'placeholder="Emails (comma or new line) and @handles for Gov Hub members"></textarea>' +
      '<div id="ghInviteUserSuggest" class="list-group position-absolute w-100 shadow-sm d-none" ' +
      'style="z-index: 1100; max-height: 200px; overflow-y: auto;"></div></div>' +
      '<p class="form-text mb-3">Type <strong>@</strong> and choose a name from the list. ' +
      'Add email addresses separately (comma or new line, up to 25 total).</p>' +
      '<div id="ghInvitePickedUsers" class="d-flex flex-wrap gap-1 mb-3"></div>' +
      '<label class="form-label" for="ghInviteMessage">Personal note (optional)</label>' +
      '<textarea class="form-control" id="ghInviteMessage" rows="3"></textarea>' +
      '</div><div class="modal-footer">' +
      '<button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>' +
      '<button type="button" class="btn btn-primary" id="ghInviteSubmitBtn">' +
      '<i class="fas fa-paper-plane me-1"></i>Send invitations</button>' +
      '</div></div></div></div>';
    document.body.appendChild(wrap.firstChild);
    return document.getElementById('ghInviteModal');
  }

  function parseRecipientEmails(text) {
    return String(text || '')
      .split(/[\s,;]+/)
      .map(function (s) {
        return s.trim();
      })
      .filter(function (s) {
        return s && s.indexOf('@') !== 0 && s.indexOf('@') > 0;
      });
  }

  /** @handles left in the textarea (not picked as chips) – not valid emails. */
  function extractAtHandles(text) {
    var seen = {};
    var out = [];
    var re = /@([a-zA-Z0-9_.-]{2,})/g;
    var m;
    while ((m = re.exec(String(text || ''))) !== null) {
      var handle = m[1];
      var key = handle.toLowerCase();
      if (!seen[key]) {
        seen[key] = true;
        out.push(handle);
      }
    }
    return out;
  }

  function resolveHandleToUser(handle) {
    return fetch(
      '/api/users/search/?q=' + encodeURIComponent(handle),
      { credentials: 'same-origin' }
    )
      .then(parseJsonFetch)
      .then(function (res) {
        if (!res.ok) return null;
        var users = res.data.users || [];
        var want = handle.toLowerCase();
        for (var i = 0; i < users.length; i++) {
          var u = users[i];
          if (!u || !u.id) continue;
          var h = (u.handle || '').toLowerCase();
          var un = (u.username || '').toLowerCase();
          if (h === want || un === want) return u;
        }
        return null;
      })
      .catch(function () {
        return null;
      });
  }

  function mergeInviteUserIds(picked, extraUsers, pickedContainer) {
    var ids = [];
    var seen = {};
    function addId(id) {
      if (!id || seen[id]) return;
      seen[id] = true;
      ids.push(id);
    }
    function addUser(u) {
      if (u && u.id) addId(u.id);
    }
    (picked || []).forEach(addUser);
    (extraUsers || []).forEach(addUser);
    if (pickedContainer) {
      pickedContainer.querySelectorAll('[data-user-id]').forEach(function (chip) {
        addId(chip.getAttribute('data-user-id'));
      });
    }
    return ids;
  }

  function formatBatchInviteSuccess(data) {
    var results = data.results || [];
    var okRows = results.filter(function (r) {
      return r.ok;
    });
    var failRows = results.filter(function (r) {
      return !r.ok;
    });
    var stats = data.stats || {};
    var unique = stats.unique_recipients || okRows.length + failRows.length;
    var parts = [
      'Sent ' +
        okRows.length +
        ' of ' +
        unique +
        ' invitation' +
        (unique === 1 ? '' : 's'),
    ];
    if (stats.user_ids_resolved > 0) {
      parts.push(
        '(' +
          stats.user_ids_resolved +
          ' from chips' +
          (stats.emails_parsed > 0
            ? ', ' + stats.emails_parsed + ' typed email' + (stats.emails_parsed === 1 ? '' : 's')
            : '') +
          ')'
      );
    } else if (stats.emails_parsed > 0) {
      parts.push('(' + stats.emails_parsed + ' typed email' + (stats.emails_parsed === 1 ? '' : 's') + ')');
    }
    if (stats.user_ids_requested > 0 && stats.user_ids_resolved === 0) {
      parts.push(
        '– chips were not sent; refresh the page and try again'
      );
    }
    if (failRows.length) {
      parts.push(
        'Could not invite: ' +
          failRows
            .map(function (r) {
              var err = r.error ? String(r.error).replace(/\.+$/, '') : '';
              return (r.email || 'unknown') + (err ? ' – ' + err : '');
            })
            .join('; ')
      );
    }
    var msg = parts.join('. ');
    return msg.endsWith('.') ? msg : msg + '.';
  }

  function renderPickedUsers(container, picked) {
    if (!container) return;
    container.innerHTML = '';
    picked.forEach(function (u) {
      if (!u || !u.id) return;
      var chip = document.createElement('span');
      chip.className = 'badge bg-secondary d-inline-flex align-items-center gap-1';
      chip.setAttribute('data-user-id', u.id);
      chip.innerHTML =
        esc(u.display_name || u.username || u.handle || 'User') +
        ' <button type="button" class="btn-close btn-close-white btn-sm" aria-label="Remove"></button>';
      chip.querySelector('button').addEventListener('click', function () {
        var idx = picked.findIndex(function (x) {
          return x.id === u.id;
        });
        if (idx >= 0) picked.splice(idx, 1);
        renderPickedUsers(container, picked);
      });
      container.appendChild(chip);
    });
  }

  function bindInviteUserSuggest(textarea, suggestEl, pickedContainer, picked) {
    var searchTimer = null;
    var activeIdx = -1;

    function hideSuggest() {
      if (suggestEl) {
        suggestEl.classList.add('d-none');
        suggestEl.innerHTML = '';
      }
      activeIdx = -1;
    }

    function atQuery() {
      var val = textarea.value;
      var pos = textarea.selectionStart;
      var before = val.slice(0, pos);
      // Only @-mentions at word boundaries – not the @ inside email addresses.
      var match = before.match(/(?:^|[\s,;\n])@([a-zA-Z0-9_.-]*)$/);
      if (!match) return null;
      return match[1];
    }

    function emailTokenBeforeCursor(val, pos) {
      var before = val.slice(0, pos);
      // Allow partial emails (e.g. bitracer1@ or bitracer@gmail) while typing.
      var match = before.match(/(?:^|[\s,;\n]+)?([a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]*)$/);
      if (!match || !match[1] || match[1].indexOf('@') < 1) return null;
      var local = match[1].split('@')[0];
      if (!local || local.length < 2) return null;
      return match[1];
    }

    function insertPickedUser(user) {
      var val = textarea.value;
      var pos = textarea.selectionStart;
      var before = val.slice(0, pos);
      var after = val.slice(pos);
      var emailTok = emailTokenBeforeCursor(val, pos);
      if (emailTok) {
        before = before.replace(new RegExp(emailTok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'), '');
      } else {
        var m = before.match(/(?:^|[\s,;\n])@([a-zA-Z0-9_.-]*)$/);
        if (m) {
          before = before.slice(0, before.length - m[0].length);
        }
      }
      textarea.value = before + after;
      if (!picked.some(function (x) {
        return x.id === user.id;
      })) {
        picked.push(user);
        renderPickedUsers(pickedContainer, picked);
      }
      hideSuggest();
      textarea.focus();
    }

    function showSuggestions(users) {
      if (!suggestEl || !users.length) {
        hideSuggest();
        return;
      }
      suggestEl.innerHTML = '';
      users.forEach(function (u, i) {
        var item = document.createElement('button');
        item.type = 'button';
        item.className = 'list-group-item list-group-item-action py-2';
        var label = u.display_name || u.username || u.handle || 'User';
        var handle = u.handle || u.username || '';
        item.innerHTML =
          '<strong>' +
          esc(label) +
          '</strong>' +
          (handle ? ' <span class="text-muted small">@' + esc(handle) + '</span>' : '');
        item.addEventListener('mousedown', function (e) {
          e.preventDefault();
          insertPickedUser(u);
        });
        item.dataset.idx = String(i);
        suggestEl.appendChild(item);
      });
      suggestEl.classList.remove('d-none');
      activeIdx = 0;
    }

    textarea.addEventListener('input', function () {
      var pos = textarea.selectionStart;
      var q = atQuery();
      var searchParam = null;
      if (q !== null) {
        if (q.length < 2) {
          hideSuggest();
          return;
        }
        searchParam = '@' + q;
      } else {
        var emailTok = emailTokenBeforeCursor(textarea.value, pos);
        if (!emailTok) {
          hideSuggest();
          return;
        }
        searchParam = emailTok;
      }
      if (searchTimer) global.clearTimeout(searchTimer);
      searchTimer = global.setTimeout(function () {
        fetch('/api/users/search/?q=' + encodeURIComponent(searchParam), { credentials: 'same-origin' })
          .then(parseJsonFetch)
          .then(function (res) {
            if (!res.ok) {
              hideSuggest();
              return;
            }
            var users = (res.data.users || []).filter(function (u) {
              return u.id && !picked.some(function (p) {
                return p.id === u.id;
              });
            });
            showSuggestions(users);
          })
          .catch(function () {
            hideSuggest();
          });
      }, 200);
    });

    textarea.addEventListener('keydown', function (e) {
      if (suggestEl.classList.contains('d-none')) return;
      var items = suggestEl.querySelectorAll('.list-group-item');
      if (!items.length) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
        items[activeIdx].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
        items[activeIdx].focus();
      } else if (e.key === 'Enter' && activeIdx >= 0) {
        e.preventDefault();
        items[activeIdx].dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      } else if (e.key === 'Escape') {
        hideSuggest();
      }
    });

    textarea.addEventListener('blur', function () {
      global.setTimeout(hideSuggest, 150);
    });
  }

  function bootstrapApi() {
    return global.bootstrap || window.bootstrap;
  }

  function inviteDraftStorageKey(target) {
    var t = target || {};
    var parts = [t.submission_id, t.draft_ref, t.layer_slug, t.workgroup_id].filter(Boolean);
    return INVITE_MSG_DRAFT_PREFIX + (parts.join('|') || 'default');
  }

  function bindInviteMessageDraft(msgEl) {
    if (!msgEl || msgEl.dataset.ghDraftBound) return;
    msgEl.dataset.ghDraftBound = '1';
    msgEl.addEventListener('input', function () {
      var key = msgEl.dataset.ghInviteDraftKey;
      if (!key) return;
      try {
        sessionStorage.setItem(key, msgEl.value);
      } catch (_e) { /* ignore */ }
    });
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
    document.getElementById('ghInviteModalTitle').textContent = opts.title || 'Invite people';
    document.getElementById('ghInviteHint').textContent = opts.hint || '';
    var recipientsEl = document.getElementById('ghInviteRecipients');
    var pickedContainer = document.getElementById('ghInvitePickedUsers');
    var suggestEl = document.getElementById('ghInviteUserSuggest');
    recipientsEl.value = '';
    var msgEl = document.getElementById('ghInviteMessage');
    bindInviteMessageDraft(msgEl);
    var draftKey = inviteDraftStorageKey(opts.target);
    msgEl.dataset.ghInviteDraftKey = draftKey;
    try {
      msgEl.value = sessionStorage.getItem(draftKey) || '';
    } catch (_e) {
      msgEl.value = '';
    }
    // Clear in place – do not reassign [] or @picker keeps writing to a stale array.
    invitePickedUsers.length = 0;
    renderPickedUsers(pickedContainer, invitePickedUsers);
    if (!recipientsEl.dataset.ghSuggestBound) {
      recipientsEl.dataset.ghSuggestBound = '1';
      bindInviteUserSuggest(recipientsEl, suggestEl, pickedContainer, invitePickedUsers);
    }

    var alertEl = document.getElementById('ghInviteAlert');
    alertEl.className = 'alert d-none';
    alertEl.innerHTML = '';

    var state = {
      type: opts.type,
      target: opts.target || {},
      shareable: false,
      sharePath: '',
      shareToken: '',
    };

    function inviteTokenFromPath(path) {
      if (!path) return '';
      try {
        var q = path.indexOf('?') >= 0 ? path.slice(path.indexOf('?')) : path;
        return new URLSearchParams(q).get('invite') || '';
      } catch (_e) {
        return '';
      }
    }

    function setShareableUi(path) {
      var block = document.getElementById('ghInviteShareableBlock');
      var urlInput = document.getElementById('ghInviteShareableUrl');
      var divider = document.getElementById('ghInviteEmailDivider');
      if (!block || !urlInput) return;
      if (!path) {
        block.classList.add('d-none');
        if (divider) divider.classList.add('d-none');
        state.shareable = false;
        state.sharePath = '';
        state.shareToken = '';
        return;
      }
      var full = path.indexOf('http') === 0 ? path : global.location.origin + path;
      urlInput.value = full;
      block.classList.remove('d-none');
      if (divider) divider.classList.remove('d-none');
      state.shareable = true;
      state.sharePath = path;
      state.shareToken = inviteTokenFromPath(path);
      var copyBtn = document.getElementById('ghInviteShareableCopyBtn');
      if (copyBtn && !copyBtn.dataset.ghBound) {
        copyBtn.dataset.ghBound = '1';
        copyBtn.addEventListener('click', function () {
          copyTextToClipboard(full).then(showCopiedToast).catch(function () {
            showInviteMessage({
              title: 'Copy failed',
              message: 'Could not copy the link.',
              variant: 'warning',
            });
          });
        });
      }
      var revokeBtn = document.getElementById('ghInviteShareableRevokeBtn');
      if (revokeBtn && !revokeBtn.dataset.ghBound) {
        revokeBtn.dataset.ghBound = '1';
        revokeBtn.addEventListener('click', function () {
          var tok = state.shareToken;
          if (!tok) return;
          if (!global.confirm('Revoke this invitation link? It will stop working for everyone.')) return;
          fetch('/api/invitations/by-token/' + encodeURIComponent(tok) + '/revoke/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
          })
            .then(parseJsonFetch)
            .then(function (res) {
              if (res.ok) {
                showInviteMessage({
                  title: 'Link revoked',
                  message: 'This invitation link no longer works.',
                  variant: 'success',
                });
                setShareableUi('');
              } else {
                showInviteMessage({
                  title: 'Revoke failed',
                  message: res.data.error || 'Could not revoke',
                  variant: 'danger',
                });
              }
            });
        });
      }
    }

    setShareableUi('');
    fetch('/api/invitations/campaign/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        type: state.type,
        target: state.target,
        message: document.getElementById('ghInviteMessage').value.trim() || null,
      }),
    })
      .then(parseJsonFetch)
      .then(function (res) {
        if (res.ok && res.data && res.data.invite_path) {
          setShareableUi(res.data.invite_path);
        }
      })
      .catch(function () { /* non-shareable types */ });

    document.getElementById('ghInviteSubmitBtn').onclick = function () {
      var btn = document.getElementById('ghInviteSubmitBtn');
      var rawText = recipientsEl.value;
      var emails = parseRecipientEmails(rawText);
      var handlesInText = extractAtHandles(rawText);

      function sendInviteBatch(userIds) {
        if (!emails.length && !userIds.length) {
          alertEl.className = 'alert alert-danger';
          alertEl.textContent =
            'Add at least one email, or @mention and pick Gov Hub members from the list';
          return;
        }
        btn.disabled = true;
        var useBatch = emails.length + userIds.length > 1 || userIds.length > 0;
        var url = useBatch ? '/api/invitations/batch/' : '/api/invitations/';
        if (typeof console !== 'undefined' && console.debug) {
          console.debug('GhInvite batch', {
            emails: emails.length,
            userIds: userIds.length,
            chips: pickedContainer
              ? pickedContainer.querySelectorAll('[data-user-id]').length
              : 0,
          });
        }
        var body = useBatch
          ? {
              type: state.type,
              emails: emails.join('\n'),
              invitee_user_ids: userIds,
              message: document.getElementById('ghInviteMessage').value.trim() || null,
              target: state.target,
            }
          : {
              type: state.type,
              email: emails[0],
              message: document.getElementById('ghInviteMessage').value.trim() || null,
              target: state.target,
            };
        fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(body),
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
            if (!res.ok && res.status !== 207) {
              alertEl.className = 'alert alert-danger';
              alertEl.textContent = res.data.error || 'Failed to send invitations';
              return;
            }
            if (res.data.results && res.data.results.length) {
              var errN = res.data.error_count || 0;
              alertEl.className = errN ? 'alert alert-warning' : 'alert alert-success';
              alertEl.textContent = formatBatchInviteSuccess(res.data);
              if (!errN) {
                recipientsEl.value = '';
                invitePickedUsers.length = 0;
                renderPickedUsers(pickedContainer, invitePickedUsers);
                try {
                  sessionStorage.removeItem(msgEl.dataset.ghInviteDraftKey || '');
                } catch (_e) { /* ignore */ }
              }
              return;
            }
            var linkPath = res.data.invite_path || state.sharePath || '';
            var link = linkPath ? global.location.origin + linkPath : '';
            if (linkPath) setShareableUi(linkPath);
            var msg = res.data.message || res.data.duplicate
              ? res.data.message || 'Invitation noted.'
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
            recipientsEl.value = '';
            invitePickedUsers.length = 0;
            renderPickedUsers(pickedContainer, invitePickedUsers);
          })
          .catch(function () {
            btn.disabled = false;
            alertEl.className = 'alert alert-danger';
            alertEl.textContent =
              'We could not reach the server. Check your connection and try again.';
          });
      }

      var handlesToResolve = handlesInText.filter(function (h) {
        var want = h.toLowerCase();
        return !invitePickedUsers.some(function (p) {
          var ph = (p.handle || p.username || '').toLowerCase();
          return ph === want;
        });
      });

      btn.disabled = true;
      alertEl.className = 'alert d-none';
      alertEl.textContent = '';

      Promise.all(handlesToResolve.map(resolveHandleToUser))
        .then(function (resolved) {
          var extra = resolved.filter(Boolean);
          if (handlesToResolve.length && extra.length < handlesToResolve.length) {
            alertEl.className = 'alert alert-warning';
            alertEl.textContent =
              'Some @mentions in the box were not found on Gov Hub. ' +
              'Click each name in the dropdown so they appear as chips below the box.';
            alertEl.classList.remove('d-none');
          }
          var userIds = mergeInviteUserIds(
            invitePickedUsers,
            extra,
            pickedContainer
          );
          sendInviteBatch(userIds);
        })
        .catch(function () {
          btn.disabled = false;
          alertEl.className = 'alert alert-danger';
          alertEl.textContent = 'Could not look up @mentions. Try again.';
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
