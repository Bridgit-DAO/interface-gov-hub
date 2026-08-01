/* BRC333 Badges admin — Gov Hub (Metaweb Academy v1) */
(function () {
  'use strict';

  var app = document.getElementById('brc333-admin-app');
  if (!app) return;

  var PROJECT_ID = app.getAttribute('data-project-id');
  var PREVIEW_BASE = app.getAttribute('data-preview-base') || '';
  var SUPER_ADMIN = app.getAttribute('data-super-admin') === '1';
  var LAYER_ADMIN_KEYS = ['primary', 'infoTitle', 'description', 'brc333message', 'defaultCohort'];
  var statusEl = document.getElementById('brc333-save-status');
  var monacoEditor = null;
  var monacoPath = '';
  var state = {
    sourcesSat: null,
    config: null,
    certifications: null,
  };

  function api(path, opts) {
    opts = opts || {};
    return fetch('/api/brc333-badges/' + PROJECT_ID + path, opts).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(body.error || r.statusText);
        return body;
      });
    });
  }

  function setStatus(msg, isErr) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = isErr ? 'err' : '';
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function reloadPreview() {
    var frame = document.getElementById('brc333-preview-frame');
    if (!frame) return;
    var u = new URL(frame.src, window.location.origin);
    u.searchParams.set('_v', String(Date.now()));
    frame.src = u.toString();
  }

  function alertOk(title, message) {
    if (window.GhDialog) {
      return GhDialog.alert({ title: title, message: message, variant: 'success' });
    }
    window.alert(message);
  }

  function alertErr(message) {
    if (window.GhDialog) {
      return GhDialog.alert({ title: 'Save failed', message: message, variant: 'danger' });
    }
    window.alert(message);
  }

  /* --- Tabs --- */
  document.querySelectorAll('.brc333-admin-tabs button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var tab = btn.getAttribute('data-tab');
      document.querySelectorAll('.brc333-admin-tabs button').forEach(function (b) {
        b.classList.toggle('active', b === btn);
      });
      document.querySelectorAll('.brc333-panel').forEach(function (p) {
        p.classList.toggle('active', p.getAttribute('data-panel') === tab);
      });
      if (tab === 'rails-editor' && !monacoEditor) initMonaco('');
      if (tab === 'diff') loadDiff(document.getElementById('brc333-diff-path')?.value || 'sources-sat.json');
    });
  });

  /* --- Rails (sources-sat) --- */
  function renderRailsPanel() {
    var panel = document.querySelector('[data-panel="rails"]');
    if (!panel || !state.sourcesSat) return;
    var doc = state.sourcesSat;
    var rows = (doc.sources || []).map(function (row, i) {
      return (
        '<tr data-idx="' + i + '">' +
        '<td><input class="brc333-in" data-field="railKey" value="' + esc(row.railKey || '') + '"></td>' +
        '<td><input class="brc333-in" data-field="label" value="' + esc(row.label || '') + '"></td>' +
        '<td><input class="brc333-in" data-field="local" value="' + esc(row.local || '') + '"></td>' +
        '<td><input class="brc333-in" data-field="status" value="' + esc(row.status || '') + '"></td>' +
        '<td><input class="brc333-in brc333-in-wide" data-field="reason" value="' + esc(row.reason || '') + '"></td>' +
        '<td><button type="button" class="brc333-btn-danger" data-act="remove-rail">×</button></td>' +
        '</tr>'
      );
    }).join('');
    panel.innerHTML =
      '<div class="brc333-toolbar">' +
      '<button type="button" class="gh-btn gh-btn-primary" id="brc333-save-rails">Save rails</button>' +
      '<button type="button" class="gh-btn gh-btn-secondary" id="brc333-add-rail">Add rail</button>' +
      '<span class="muted">infrastructureRails[] is rebuilt automatically on save.</span>' +
      '</div>' +
      '<div class="brc333-table-wrap"><table class="brc333-table"><thead><tr>' +
      '<th>Rail key</th><th>Label</th><th>Local</th><th>Status</th><th>Reason</th><th></th>' +
      '</tr></thead><tbody id="brc333-rails-body">' + rows + '</tbody></table></div>';

    panel.querySelector('#brc333-add-rail').onclick = function () {
      doc.sources = doc.sources || [];
      doc.sources.push({ railKey: 'new_rail', label: 'New rail', local: '', status: 'draft', reinscribable: true, reason: '' });
      renderRailsPanel();
    };
    panel.querySelector('#brc333-save-rails').onclick = saveRails;
    panel.querySelectorAll('[data-act="remove-rail"]').forEach(function (btn) {
      btn.onclick = function () {
        var tr = btn.closest('tr');
        var idx = parseInt(tr.getAttribute('data-idx'), 10);
        doc.sources.splice(idx, 1);
        renderRailsPanel();
      };
    });
  }

  function collectRailsFromDom() {
    var doc = JSON.parse(JSON.stringify(state.sourcesSat));
    var body = document.getElementById('brc333-rails-body');
    if (!body) return doc;
    doc.sources = [];
    body.querySelectorAll('tr').forEach(function (tr) {
      var row = { reinscribable: true };
      tr.querySelectorAll('[data-field]').forEach(function (inp) {
        var v = inp.value.trim();
        row[inp.getAttribute('data-field')] = v || null;
      });
      if (row.railKey) doc.sources.push(row);
    });
    return doc;
  }

  function saveRails() {
    setStatus('Saving sources-sat.json…');
    var doc = collectRailsFromDom();
    api('/files/sources-sat.json', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json: doc }),
    }).then(function (res) {
      state.sourcesSat = doc;
      setStatus('Saved sources-sat.json' + (res.commit ? ' (' + res.commit + ')' : ''));
      reloadPreview();
      alertOk('Rails saved', 'sources-sat.json updated.' + (res.commit ? ' Commit ' + res.commit : ''));
    }).catch(function (e) {
      setStatus(e.message, true);
      alertErr(e.message);
    });
  }

  /* --- Config --- */
  function configEntries(kind) {
    return (state.config.sources || []).filter(function (e) {
      if (kind === 'script') return e.script;
      if (kind === 'sat') return e.sat != null && !e.script;
      if (kind === 'key') return e.key;
      if (kind === 'other') return e.sources || e.oracle || e.system;
      return false;
    });
  }

  function isConfigKeyEditable(key) {
    if (SUPER_ADMIN) return true;
    return LAYER_ADMIN_KEYS.indexOf(key) !== -1;
  }

  function richTextToolbarHtml(configKey) {
    return (
      '<div class="brc333-richtext-toolbar" data-for="' + esc(configKey) + '">' +
      '<button type="button" class="brc333-rt-btn" data-cmd="bold" title="Bold"><i class="fas fa-bold"></i></button>' +
      '<button type="button" class="brc333-rt-btn" data-cmd="italic" title="Italic"><i class="fas fa-italic"></i></button>' +
      '<button type="button" class="brc333-rt-btn" data-cmd="class" data-class="title-text" title="Title">Title</button>' +
      '<button type="button" class="brc333-rt-btn" data-cmd="class" data-class="subtitle-text" title="Subtitle">Subtitle</button>' +
      '<button type="button" class="brc333-rt-btn" data-cmd="class" data-class="normal" title="Body">Body</button>' +
      '<button type="button" class="brc333-rt-btn" data-cmd="class" data-class="bold" title="Bold span">Bold span</button>' +
      '<span class="muted brc333-rt-hint">Select text, then click a style. Uses &lt;span class&gt; and &lt;strong&gt; (sanitized on save).</span>' +
      '</div>'
    );
  }

  function wireRichTextToolbars(panel) {
    panel.querySelectorAll('.brc333-richtext-toolbar').forEach(function (bar) {
      var key = bar.getAttribute('data-for');
      var editor = panel.querySelector('.brc333-richtext[data-config-key="' + key + '"]');
      if (!editor) return;
      bar.querySelectorAll('.brc333-rt-btn').forEach(function (btn) {
        btn.addEventListener('mousedown', function (e) { e.preventDefault(); });
        btn.addEventListener('click', function () {
          editor.focus();
          var cmd = btn.getAttribute('data-cmd');
          if (cmd === 'bold') {
            document.execCommand('bold', false, null);
            return;
          }
          if (cmd === 'italic') {
            document.execCommand('italic', false, null);
            return;
          }
          var cls = btn.getAttribute('data-class');
          if (!cls) return;
          var sel = window.getSelection();
          if (!sel || !sel.rangeCount) return;
          var range = sel.getRangeAt(0);
          if (range.collapsed) return;
          var span = document.createElement('span');
          span.className = cls;
          try {
            range.surroundContents(span);
          } catch (err) {
            document.execCommand('insertHTML', false, '<span class="' + cls + '">' + sel.toString() + '</span>');
          }
        });
      });
    });
  }

  function renderConfigPanel() {
    var panel = document.querySelector('[data-panel="config"]');
    if (!panel || !state.config) return;
    var keys = configEntries('key');
    var html = '<div class="brc333-toolbar"><button type="button" class="gh-btn gh-btn-primary" id="brc333-save-config">Save config</button></div>';
    html += '<h3 class="brc333-section-title">Info modal (rich text — sanitized on save)</h3>';
    keys.forEach(function (entry) {
      if (entry.key !== 'description' && entry.key !== 'brc333message') return;
      html +=
        '<label class="brc333-label">' + esc(entry.key) +
        richTextToolbarHtml(entry.key) +
        '<div class="brc333-richtext" contenteditable="true" data-config-key="' + esc(entry.key) + '">' +
        (entry.value || '') + '</div></label>';
    });
    html += '<h3 class="brc333-section-title">Theme & keys</h3><div class="brc333-kv-grid">';
    keys.forEach(function (entry) {
      if (entry.key === 'description' || entry.key === 'brc333message') return;
      var editable = isConfigKeyEditable(entry.key);
      var ro = !editable;
      var title = ro ? ' title="Super-admin only — set at project activation"' : '';
      html +=
        '<label class="brc333-label">' + esc(entry.key) +
        '<input class="brc333-in' + (ro ? ' brc333-in-readonly' : '') + '" data-config-key="' + esc(entry.key) + '" value="' + esc(entry.value) + '"' +
        (ro ? ' readonly' + title : '') + '></label>';
    });
    html += '</div>';
    if (SUPER_ADMIN) {
      html += '<h3 class="brc333-section-title">Scripts & sat pointers</h3>';
      html += '<p class="muted">Infrastructure sats (Oracle, TimeTravel, Data, hookSat) are assigned at project activation.</p>';
      html += '<pre class="brc333-json-preview">' + esc(JSON.stringify(state.config.sources.filter(function (e) {
        return e.script || e.sat || e.sources || e.oracle;
      }), null, 2)) + '</pre>';
    } else {
      html += '<p class="muted">Project identity (sourceId, chain, medium, protocol) and infrastructure sats (hook, oracle, time travel) are managed by site super-admins.</p>';
    }
    panel.innerHTML = html;
    panel.querySelector('#brc333-save-config').onclick = saveConfig;
    wireRichTextToolbars(panel);
  }

  function saveConfig() {
    var doc = JSON.parse(JSON.stringify(state.config));
    doc.sources = doc.sources.map(function (entry) {
      if (!entry.key) return entry;
      var rt = document.querySelector('.brc333-richtext[data-config-key="' + entry.key + '"]');
      if (rt) return Object.assign({}, entry, { value: rt.innerHTML });
      var inp = document.querySelector('.brc333-in[data-config-key="' + entry.key + '"]');
      if (inp && !inp.readOnly) return Object.assign({}, entry, { value: inp.value });
      return entry;
    });
    setStatus('Saving config.json…');
    api('/files/config.json', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json: doc }),
    }).then(function (res) {
      state.config = doc;
      setStatus('Saved config.json' + (res.commit ? ' (' + res.commit + ')' : ''));
      reloadPreview();
      alertOk('Config saved', 'config.json updated.');
    }).catch(function (e) {
      setStatus(e.message, true);
      alertErr(e.message);
    });
  }

  /* --- Certifications --- */
  function renderCertPanel() {
    var panel = document.querySelector('[data-panel="certifications"]');
    if (!panel) return;
    panel.innerHTML =
      '<div class="brc333-toolbar">' +
      '<button type="button" class="gh-btn gh-btn-primary" id="brc333-save-certs">Save certifications</button>' +
      '<button type="button" class="gh-btn gh-btn-secondary" id="brc333-open-certs-monaco">Open in editor</button>' +
      '</div>' +
      '<textarea id="brc333-certs-json" class="brc333-json-area" spellcheck="false"></textarea>';
    document.getElementById('brc333-certs-json').value = JSON.stringify(state.certifications, null, 2);
    document.getElementById('brc333-save-certs').onclick = saveCerts;
    document.getElementById('brc333-open-certs-monaco').onclick = function () {
      document.querySelector('[data-tab="rails-editor"]').click();
      initMonaco('data/certifications.json');
    };
  }

  function saveCerts() {
    var raw = document.getElementById('brc333-certs-json').value;
    var doc;
    try {
      doc = JSON.parse(raw);
    } catch (e) {
      alertErr('Invalid JSON: ' + e.message);
      return;
    }
    api('/files/data/certifications.json', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ json: doc }),
    }).then(function (res) {
      state.certifications = doc;
      setStatus('Saved certifications' + (res.commit ? ' (' + res.commit + ')' : ''));
      reloadPreview();
      alertOk('Certifications saved', 'data/certifications.json updated.');
    }).catch(function (e) {
      alertErr(e.message);
    });
  }

  /* --- Monaco rail editor --- */
  function initMonaco(path) {
    var panel = document.querySelector('[data-panel="rails-editor"]');
    if (!panel) return;
    if (!panel.querySelector('#brc333-monaco-toolbar')) {
      panel.innerHTML =
        '<div class="brc333-toolbar" id="brc333-monaco-toolbar">' +
        '<select id="brc333-rail-select"></select>' +
        '<button type="button" class="gh-btn gh-btn-primary" id="brc333-save-rail-file">Save file</button>' +
        '<span class="muted" id="brc333-rail-protected-note"></span></div>' +
        '<div id="brc333-monaco" class="brc333-monaco"></div>';
      document.getElementById('brc333-save-rail-file').onclick = saveMonacoFile;
    }
    api('/rails').then(function (data) {
      var sel = document.getElementById('brc333-rail-select');
      sel.innerHTML = (data.rails || []).map(function (r) {
        var label = (r.railKey || '') + ' — ' + (r.local || '');
        return '<option value="' + esc(r.local) + '" data-protected="' + (r.protected ? '1' : '0') + '">' + esc(label) + '</option>';
      }).join('');
      sel.onchange = function () { loadMonacoFile(sel.value); };
      loadMonacoFile(path || sel.value);
    });
  }

  function loadMonacoFile(relPath) {
    if (!relPath) return;
    monacoPath = relPath;
    var sel = document.getElementById('brc333-rail-select');
    var opt = sel && sel.querySelector('option[value="' + relPath.replace(/"/g, '\\"') + '"]');
    var protectedFile = opt && opt.getAttribute('data-protected') === '1';
    document.getElementById('brc333-rail-protected-note').textContent = protectedFile
      ? 'Super-admin only' : '';
    api('/files/' + relPath.split('/').map(encodeURIComponent).join('/')).then(function (data) {
      if (data.protected && !SUPER_ADMIN) {
        document.getElementById('brc333-monaco').innerHTML =
          '<p class="brc333-protected-msg">This rail is restricted to site super-admins.</p>';
        return;
      }
      var lang = relPath.endsWith('.js') ? 'javascript' : relPath.endsWith('.htm') ? 'html' : 'json';
      require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' } });
      require(['vs/editor/editor.main'], function () {
        if (monacoEditor) monacoEditor.dispose();
        monacoEditor = monaco.editor.create(document.getElementById('brc333-monaco'), {
          value: data.content || '',
          language: lang,
          theme: 'vs-dark',
          automaticLayout: true,
          minimap: { enabled: false },
          readOnly: !!(data.protected && !SUPER_ADMIN),
        });
      });
    }).catch(function (e) { alertErr(e.message); });
  }

  function saveMonacoFile() {
    if (!monacoEditor || !monacoPath) return;
    setStatus('Saving ' + monacoPath + '…');
    api('/files/' + monacoPath.split('/').map(encodeURIComponent).join('/'), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: monacoEditor.getValue() }),
    }).then(function (res) {
      setStatus('Saved ' + monacoPath + (res.commit ? ' (' + res.commit + ')' : ''));
      reloadPreview();
      alertOk('File saved', monacoPath + ' updated.');
    }).catch(function (e) { alertErr(e.message); });
  }

  /* --- Assets --- */
  function renderAssetsPanel() {
    var panel = document.querySelector('[data-panel="assets"]');
    panel.innerHTML =
      '<div class="brc333-toolbar">' +
      '<label class="brc333-label">Path under assets/ (e.g. assets/seal-base.png)' +
      '<input class="brc333-in" id="brc333-upload-path" value="assets/seal-base.png"></label>' +
      '<input type="file" id="brc333-upload-file" accept="image/png,image/webp">' +
      '<button type="button" class="gh-btn gh-btn-primary" id="brc333-upload-btn">Upload</button></div>' +
      '<p class="muted">PNG or WebP only. Committed to git on upload.</p>';
    document.getElementById('brc333-upload-btn').onclick = function () {
      var path = document.getElementById('brc333-upload-path').value.trim();
      var file = document.getElementById('brc333-upload-file').files[0];
      if (!file || !path) return;
      var fd = new FormData();
      fd.append('path', path);
      fd.append('file', file);
      fetch('/api/brc333-badges/' + PROJECT_ID + '/upload', { method: 'POST', body: fd })
        .then(function (r) { return r.json().then(function (b) { if (!r.ok) throw new Error(b.error); return b; }); })
        .then(function () {
          alertOk('Uploaded', path);
          reloadPreview();
        }).catch(function (e) { alertErr(e.message); });
    };
  }

  /* --- Diff --- */
  function renderDiffPanel() {
    var panel = document.querySelector('[data-panel="diff"]');
    panel.innerHTML =
      '<div class="brc333-toolbar">' +
      '<select id="brc333-diff-path">' +
      '<option value="sources-sat.json">sources-sat.json</option>' +
      '<option value="config.json">config.json</option>' +
      '<option value="data/certifications.json">data/certifications.json</option>' +
      '</select>' +
      '<button type="button" class="gh-btn gh-btn-secondary" id="brc333-diff-refresh">Refresh diff</button></div>' +
      '<pre id="brc333-diff-out" class="brc333-diff-out"></pre>';
    document.getElementById('brc333-diff-refresh').onclick = function () {
      loadDiff(document.getElementById('brc333-diff-path').value);
    };
  }

  function loadDiff(path) {
    api('/diff/' + path.split('/').map(encodeURIComponent).join('/')).then(function (data) {
      var out = document.getElementById('brc333-diff-out');
      if (out) out.textContent = data.diff || '(no uncommitted changes)';
    });
  }

  /* --- Boot --- */
  Promise.all([
    api('/files/sources-sat.json'),
    api('/files/config.json'),
    api('/files/data/certifications.json'),
  ]).then(function (results) {
    state.sourcesSat = results[0].json;
    state.config = results[1].json;
    state.certifications = results[2].json;
    renderRailsPanel();
    renderConfigPanel();
    renderCertPanel();
    renderAssetsPanel();
    renderDiffPanel();
    setStatus('Loaded project files');
  }).catch(function (e) {
    setStatus(e.message, true);
    alertErr(e.message);
  });
})();
