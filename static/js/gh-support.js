(function () {
  'use strict';

  var CATEGORIES = [
    { value: 'workgroup_help', label: 'Workgroup help' },
    { value: 'layer_governance', label: 'Layer / governance' },
    { value: 'nominations', label: 'Nominations & roles' },
    { value: 'technical_support', label: 'Technical support' },
    { value: 'content_clarification', label: 'Content clarification' },
    { value: 'general', label: 'General' },
  ];

  var root = document.getElementById('gh-support-app');
  if (!root) return;
  var mode = root.getAttribute('data-mode') || 'user';

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function readFilesAsBase64(files) {
    var list = Array.prototype.slice.call(files, 0, 5);
    return Promise.all(
      list.map(function (file) {
        return new Promise(function (resolve, reject) {
          var reader = new FileReader();
          reader.onload = function () {
            var result = String(reader.result || '');
            resolve({
              filename: file.name,
              mimeType: file.type || 'image/png',
              dataBase64: result.indexOf(',') >= 0 ? result.split(',')[1] : result,
            });
          };
          reader.onerror = function () { reject(reader.error); };
          reader.readAsDataURL(file);
        });
      })
    );
  }

  if (mode === 'admin') {
    renderAdmin();
    return;
  }

  renderUser();

  function renderUser() {
    var catOpts = CATEGORIES.map(function (c) {
      return '<option value="' + esc(c.value) + '">' + esc(c.label) + '</option>';
    }).join('');

    root.innerHTML =
      '<form id="gh-support-form" class="gh-card p-4">' +
      '<div class="mb-3"><label class="form-label">Subject *</label>' +
      '<input class="form-control" name="subject" maxlength="200" required></div>' +
      '<div class="row g-3 mb-3">' +
      '<div class="col-md-6"><label class="form-label">Category</label>' +
      '<select class="form-select" name="category">' + catOpts + '</select></div>' +
      '<div class="col-md-6"><label class="form-label">Urgency</label>' +
      '<select class="form-select" name="urgency">' +
      '<option value="non_blocking">Non-blocking</option>' +
      '<option value="blocking">Blocking</option>' +
      '<option value="critical">Critical</option></select></div></div>' +
      '<div class="mb-3"><label class="form-label">Message *</label>' +
      '<textarea class="form-control" name="body" rows="6" maxlength="8000" required></textarea></div>' +
      '<div id="gh-tech-fields" style="display:none" class="border rounded p-3 mb-3">' +
      '<div class="mb-2"><label class="form-label">Steps to reproduce</label><textarea class="form-control" name="steps" rows="2"></textarea></div>' +
      '<div class="mb-2"><label class="form-label">Expected behavior</label><input class="form-control" name="expected"></div>' +
      '<div class="mb-2"><label class="form-label">Actual behavior</label><input class="form-control" name="actual"></div>' +
      '<div class="mb-2"><label class="form-label">What I already tried</label><textarea class="form-control" name="tried" rows="2"></textarea></div>' +
      '<div class="form-check"><input class="form-check-input" type="checkbox" id="gh-tech-ack" name="techAck">' +
      '<label class="form-check-label" for="gh-tech-ack">I cannot attach a screenshot now but will follow up with one *</label></div></div>' +
      '<div class="mb-3"><label class="form-label">Screenshots (optional)</label>' +
      '<input type="file" class="form-control" id="gh-screenshots" accept="image/*" multiple></div>' +
      '<div class="form-check mb-3"><input class="form-check-input" type="checkbox" id="gh-diag" checked>' +
      '<label class="form-check-label" for="gh-diag">Include page diagnostics</label></div>' +
      '<button type="submit" class="btn btn-primary">Submit request</button></form>' +
      '<div id="gh-tickets" class="mt-4"></div>';

    var form = document.getElementById('gh-support-form');
    var category = form.querySelector('[name=category]');
    var techFields = document.getElementById('gh-tech-fields');
    category.addEventListener('change', function () {
      techFields.style.display = category.value === 'technical_support' ? 'block' : 'none';
    });

    loadTickets();

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var fd = new FormData(form);
      var files = document.getElementById('gh-screenshots').files;
      var isTech = fd.get('category') === 'technical_support';
      var techAck = document.getElementById('gh-tech-ack').checked;
      if (isTech && !techAck && (!files || !files.length)) {
        GhDialog.alert({ title: 'Screenshot needed', message: 'For technical support, attach a screenshot or confirm the acknowledgement.', variant: 'warning' });
        return;
      }
      readFilesAsBase64(files || []).then(function (screenshots) {
        var diag = document.getElementById('gh-diag').checked
          ? {
              pageUrl: location.href,
              userAgent: navigator.userAgent,
              platform: navigator.platform,
              language: navigator.language,
            }
          : null;
        return fetch('/api/support/tickets', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            subject: fd.get('subject'),
            body: fd.get('body'),
            category: fd.get('category'),
            urgency: fd.get('urgency'),
            screenshotAcknowledged: techAck,
            screenshots: screenshots,
            pageUrl: location.href,
            browser: navigator.userAgent,
            os: navigator.platform,
            stepsToReproduce: fd.get('steps'),
            expectedBehavior: fd.get('expected'),
            actualBehavior: fd.get('actual'),
            triedAlready: fd.get('tried'),
            diagnosticBundle: diag,
          }),
        });
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (!data.ok) {
          GhDialog.alert({ title: 'Could not submit', message: data.message || data.error || 'Try again.', variant: 'danger' });
          return;
        }
        GhDialog.alert({ title: 'Request submitted', message: 'We received your support request and sent a confirmation email if we have your address on file.', variant: 'success' });
        form.reset();
        loadTickets();
      }).catch(function () {
        GhDialog.alert({ title: 'Error', message: 'Network error. Try again.', variant: 'danger' });
      });
    });
  }

  function loadTickets() {
    fetch('/api/support/tickets', { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var el = document.getElementById('gh-tickets');
        if (!el || !data.ok || !data.tickets || !data.tickets.length) {
          if (el) el.innerHTML = '';
          return;
        }
        el.innerHTML = '<h2 class="h6">Your recent requests</h2><ul class="list-group">' +
          data.tickets.map(function (t) {
            return '<li class="list-group-item d-flex justify-content-between"><span>' + esc(t.subject) +
              '</span><span class="text-muted small">' + esc(t.status) + ' · ' + esc(t.createdAt && t.createdAt.slice(0, 10)) + '</span></li>';
          }).join('') + '</ul>';
      });
  }

  function renderAdmin() {
    root.innerHTML = '<div class="row g-3 mb-3">' +
      '<div class="col-md-3"><select id="gh-filter-status" class="form-select"><option value="">All statuses</option>' +
      '<option value="open">Open</option><option value="triaged">Triaged</option><option value="closed">Closed</option></select></div>' +
      '<div class="col-md-3"><button id="gh-refresh" class="btn btn-outline-primary">Refresh</button></div></div>' +
      '<div class="row"><div class="col-md-5"><div id="gh-queue" class="list-group"></div></div>' +
      '<div class="col-md-7"><div id="gh-detail"></div></div></div>';

    document.getElementById('gh-refresh').addEventListener('click', loadQueue);
    document.getElementById('gh-filter-status').addEventListener('change', loadQueue);
    loadQueue();

    function loadQueue() {
      var status = document.getElementById('gh-filter-status').value;
      var q = status ? '?status=' + encodeURIComponent(status) : '';
      fetch('/api/support/admin/tickets' + q, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var el = document.getElementById('gh-queue');
          if (!data.ok) { el.innerHTML = '<p class="text-danger">Could not load queue.</p>'; return; }
          el.innerHTML = (data.tickets || []).map(function (t) {
            return '<button type="button" class="list-group-item list-group-item-action gh-ticket-row" data-id="' + esc(t.id) + '">' +
              '<strong>' + esc(t.subject) + '</strong><br><small class="text-muted">' + esc(t.urgency) + ' · ' + esc(t.category) + '</small></button>';
          }).join('') || '<p class="text-muted">No tickets.</p>';
          el.querySelectorAll('.gh-ticket-row').forEach(function (btn) {
            btn.addEventListener('click', function () { loadDetail(btn.getAttribute('data-id')); });
          });
        });
    }

    function loadDetail(id) {
      fetch('/api/support/admin/tickets/' + encodeURIComponent(id), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.ok) return;
          var t = data.ticket;
          var dr = t.draftReply || {};
          document.getElementById('gh-detail').innerHTML =
            '<div class="gh-card p-3"><h2 class="h6">' + esc(t.subject) + '</h2>' +
            '<p class="small text-muted">' + esc(t.email || t.handle || t.userId) + '</p>' +
            '<pre class="small bg-light p-2 rounded">' + esc(t.body) + '</pre>' +
            '<div class="mb-2"><label class="form-label">Draft reply subject</label>' +
            '<input id="gh-reply-subj" class="form-control" value="' + esc(dr.subject || ('Re: ' + t.subject)) + '"></div>' +
            '<div class="mb-2"><label class="form-label">Draft reply body</label>' +
            '<textarea id="gh-reply-body" class="form-control" rows="6">' + esc(dr.body || '') + '</textarea></div>' +
            '<div class="d-flex gap-2">' +
            '<button id="gh-save-draft" class="btn btn-outline-secondary btn-sm">Save draft</button>' +
            '<button id="gh-send-reply" class="btn btn-primary btn-sm">Send reply</button>' +
            '<select id="gh-status" class="form-select form-select-sm" style="width:auto">' +
            '<option value="open"' + (t.status === 'open' ? ' selected' : '') + '>Open</option>' +
            '<option value="triaged"' + (t.status === 'triaged' ? ' selected' : '') + '>Triaged</option>' +
            '<option value="closed"' + (t.status === 'closed' ? ' selected' : '') + '>Closed</option></select></div></div>';

          document.getElementById('gh-save-draft').addEventListener('click', function () {
            patch(id, {
              draftReply: { subject: document.getElementById('gh-reply-subj').value, body: document.getElementById('gh-reply-body').value },
              status: document.getElementById('gh-status').value,
            });
          });
          document.getElementById('gh-send-reply').addEventListener('click', function () {
            fetch('/api/support/admin/tickets/' + encodeURIComponent(id) + '/send-reply', {
              method: 'POST',
              credentials: 'same-origin',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                subject: document.getElementById('gh-reply-subj').value,
                body: document.getElementById('gh-reply-body').value,
              }),
            }).then(function (r) { return r.json(); }).then(function (res) {
              if (res.ok) GhDialog.alert({ title: 'Reply sent', message: 'Email sent to submitter.', variant: 'success' });
              else GhDialog.alert({ title: 'Send failed', message: res.error || 'Try again.', variant: 'danger' });
            });
          });
        });
    }

    function patch(id, body) {
      fetch('/api/support/admin/tickets/' + encodeURIComponent(id), {
        method: 'PATCH',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(function (r) { return r.json(); }).then(function (res) {
        if (res.ok) GhDialog.alert({ title: 'Saved', message: 'Ticket updated.', variant: 'success' });
      });
    }
  }
})();
