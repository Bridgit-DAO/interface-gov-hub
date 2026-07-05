"""Inline HTML/JS for layer standalone artifact page: edit modal + collections."""
import html as html_mod


def render_layer_artifact_editor_and_collections(
    artifact_id: str,
    layer_id: str,
    layer_slug: str,
    artifact_type_options: tuple,
) -> str:
    """Edit artifact (incl. contribution type) + collections sidebar for signed-in editors."""
    opts = "".join(
        f'<option value="{html_mod.escape(t)}">{html_mod.escape(t)}</option>'
        for t in artifact_type_options
    )
    aid = html_mod.escape(artifact_id)
    lid = html_mod.escape(str(layer_id))
    lslug = html_mod.escape(layer_slug)
    return f'''
            <button type="button" class="btn btn-primary btn-sm mt-2 w-100" data-bs-toggle="modal" data-bs-target="#layerArtifactModal">
                <i class="fas fa-edit me-1"></i>Edit artifact
            </button>
            <div class="card mt-3">
                <div class="card-body">
                    <h6 class="card-title">Collections</h6>
                    <p class="small text-muted mb-2">Group artifacts (e.g. constitution sets).</p>
                    <div id="la-collections-list" class="small mb-2">Loading…</div>
                    <button type="button" class="btn btn-outline-primary btn-sm w-100 mb-2" data-bs-toggle="modal" data-bs-target="#laNewCollectionModal">New collection</button>
                    <label class="form-label small mb-1">Add this artifact to</label>
                    <select class="form-select form-select-sm mb-2" id="la-collection-pick"><option value="">– Choose –</option></select>
                    <button type="button" class="btn btn-outline-secondary btn-sm w-100" id="la-add-to-collection-btn">Add to collection</button>
                    <div id="la-collection-alert" class="alert alert-danger d-none small mt-2 mb-0 py-2"></div>
                </div>
            </div>
            <div class="modal fade" id="layerArtifactModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit artifact</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="la-artifact-alert" class="alert d-none mb-2"></div>
                            <div class="mb-2"><label class="form-label">Type</label>
                                <select class="form-select" id="la-artifact-type"><option value="">–</option>{opts}</select></div>
                            <div class="mb-2"><label class="form-label">Subtype</label>
                                <input type="text" class="form-control" id="la-artifact-subtype"></div>
                            <div class="mb-2"><label class="form-label">Title</label>
                                <input type="text" class="form-control" id="la-artifact-title"></div>
                            <div class="mb-2"><label class="form-label">Summary</label>
                                <textarea class="form-control" id="la-artifact-summary" rows="2"></textarea></div>
                            <div class="mb-2"><label class="form-label">Body</label>
                                <textarea class="form-control" id="la-artifact-body" rows="4"></textarea></div>
                            <div class="mb-2"><label class="form-label">URI</label>
                                <input type="text" class="form-control" id="la-artifact-uri"></div>
                            <div class="mb-2"><label class="form-label">Status</label>
                                <select class="form-select" id="la-artifact-status">
                                    <option value="draft">draft</option>
                                    <option value="published">published</option>
                                    <option value="archived">archived</option>
                                    <option value="submitted">submitted</option>
                                    <option value="under_review">under_review</option>
                                    <option value="adopted">adopted</option>
                                </select></div>
                            <div class="row mb-2"><div class="col-6"><label class="form-label">Source language</label>
                                <input type="text" class="form-control" id="la-artifact-source-lang" placeholder="en"></div>
                                <div class="col-6"><label class="form-label">Current language</label>
                                <input type="text" class="form-control" id="la-artifact-current-lang" placeholder="en"></div></div>
                            <div class="mb-2 border-top pt-2 mt-2" id="la-kl-contribution-wrap" style="display:none;">
                                <label class="form-label">Contribution type <span class="text-muted">(optional)</span></label>
                                <select class="form-select" id="la-kl-contribution-type"><option value="">– Not set</option></select>
                                <p class="small text-muted mb-0">Helps others understand how to engage with this contribution.</p>
                            </div>
                            <div class="mb-2" id="la-kl-scaffold-wrap" style="display:none;"></div>
                            <div class="mb-2 border-top pt-2" id="la-tags-wrap" style="display:none;">
                                <label class="form-label">Tags <span class="text-muted">(optional)</span></label>
                                <input type="text" class="form-control" id="la-artifact-tags" placeholder="governance, climate-policy (comma-separated)">
                                <p class="small text-muted mb-0">Up to 10 tags per artifact. New labels are created for this layer.</p>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="la-artifact-save-btn">Save</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="laNewCollectionModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">New collection</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <label class="form-label">Title</label>
                            <input type="text" class="form-control" id="la-new-coll-title" placeholder="e.g. Layer constitution draft">
                            <div id="la-new-coll-alert" class="alert alert-danger d-none small mt-2 mb-0"></div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="la-new-coll-save">Create</button>
                        </div>
                    </div>
                </div>
            </div>
            <script>
            (function() {{
                const aid = '{aid}';
                const layerId = '{lid}';
                const layerSlug = '{lslug}';
                const fields = ['artifact_type','artifact_subtype','title','summary','body','uri','status','source_language','current_language'];
                const ids = {{artifact_type:'la-artifact-type',artifact_subtype:'la-artifact-subtype',title:'la-artifact-title',summary:'la-artifact-summary',body:'la-artifact-body',uri:'la-artifact-uri',status:'la-artifact-status',source_language:'la-artifact-source-lang',current_language:'la-artifact-current-lang'}};
                const KL_SCAFFOLD = {{
                    inquiry: [{{k:'what_is_unclear',l:'What is unclear?',t:'ta'}},{{k:'status',l:'Status',t:'sel',o:['open','closed']}}],
                    principle: [{{k:'why_matters',l:'Why does this matter?',t:'ta'}}],
                    model: [{{k:'key_assumptions',l:'Key assumptions',t:'ta'}}],
                    claim: [{{k:'why_believe',l:'Why do you believe this?',t:'ta'}}],
                    decision: [{{k:'what_resolves',l:'What does this resolve?',t:'ta'}},{{k:'status',l:'Status',t:'sel',o:['draft','final']}}],
                    gloss: [{{k:'definition',l:'Definition',t:'ta'}}],
                    scenario: [{{k:'actors_context',l:'Actors / context',t:'ta'}}]
                }};
                let klSchema = null;
                async function ensureKlSchema() {{
                    if (klSchema) return klSchema;
                    try {{
                        const r = await fetch('/api/knowledge-layer/schema/', {{credentials:'same-origin'}});
                        klSchema = await r.json();
                    }} catch (e) {{ klSchema = null; }}
                    return klSchema;
                }}
                function laShowAlert(msg, type) {{
                    const el = document.getElementById('la-artifact-alert');
                    if (!el) return;
                    el.textContent = msg;
                    el.className = 'alert alert-' + type;
                    el.classList.remove('d-none');
                }}
                function laRebuildContribution() {{
                    const wrap = document.getElementById('la-kl-contribution-wrap');
                    const sel = document.getElementById('la-kl-contribution-type');
                    const atEl = document.getElementById('la-artifact-type');
                    if (!wrap || !sel || !atEl) return;
                    if (!klSchema || !klSchema.feature_flags || !klSchema.feature_flags.knowledge_contribution_type_enabled) {{
                        wrap.style.display = 'none';
                        return;
                    }}
                    wrap.style.display = 'block';
                    const at = (atEl.value || '').trim();
                    const spec = klSchema.artifact_types && klSchema.artifact_types[at];
                    const prev = sel.value;
                    sel.innerHTML = '<option value="">– Not set</option>';
                    if (spec && spec.allowed) {{
                        spec.allowed.forEach(function(v) {{ sel.add(new Option(v, v)); }});
                        if (prev && [...sel.options].some(function(o) {{ return o.value === prev; }})) sel.value = prev;
                    }}
                }}
                function laRenderScaffold() {{
                    const sw = document.getElementById('la-kl-scaffold-wrap');
                    const kls = document.getElementById('la-kl-contribution-type');
                    if (!sw || !kls) return;
                    if (!klSchema || !klSchema.feature_flags || !klSchema.feature_flags.knowledge_scaffold_enabled) {{
                        sw.style.display = 'none';
                        sw.innerHTML = '';
                        return;
                    }}
                    const form = kls.value;
                    const rows = form && KL_SCAFFOLD[form];
                    if (!rows) {{ sw.style.display = 'none'; sw.innerHTML = ''; return; }}
                    sw.style.display = 'block';
                    const data = window.__laScaffoldData || {{}};
                    let html = '<div class="border rounded p-2 bg-light"><div class="small fw-bold mb-2">Optional details</div>';
                    rows.forEach(function(row) {{
                        const id = 'la-sc-' + row.k;
                        const v = data[row.k] != null ? String(data[row.k]) : '';
                        if (row.t === 'sel') {{
                            html += '<div class="mb-2"><label class="form-label small">' + row.l + '</label><select class="form-select form-select-sm" id="'+id+'" data-la-scaffold="'+row.k+'"><option value=""></option>';
                            (row.o || []).forEach(function(o) {{ html += '<option value="'+o+'"'+(v===o?' selected':'')+'>'+o+'</option>'; }});
                            html += '</select></div>';
                        }} else {{
                            html += '<div class="mb-2"><label class="form-label small">'+row.l+'</label><textarea class="form-control form-control-sm" id="'+id+'" rows="2" data-la-scaffold="'+row.k+'"></textarea></div>';
                        }}
                    }});
                    html += '</div>';
                    sw.innerHTML = html;
                    rows.forEach(function(row) {{
                        const el = document.getElementById('la-sc-' + row.k);
                        if (el && row.t !== 'sel' && data[row.k] != null) el.value = data[row.k];
                    }});
                }}
                function laCollectScaffold(form) {{
                    if (!form || !KL_SCAFFOLD[form]) return null;
                    const out = {{}};
                    document.querySelectorAll('[data-la-scaffold]').forEach(function(el) {{
                        const k = el.getAttribute('data-la-scaffold');
                        if (el.tagName === 'SELECT') {{ if (el.value) out[k] = el.value; }}
                        else {{ const t = el.value.trim(); if (t) out[k] = t; }}
                    }});
                    return Object.keys(out).length ? out : null;
                }}
                function laGetPayload() {{
                    const p = {{}};
                    for (const f of fields) {{
                        const el = document.getElementById(ids[f]);
                        if (el) p[f] = el.value === '' ? null : el.value;
                    }}
                    if (klSchema && klSchema.feature_flags && klSchema.feature_flags.knowledge_contribution_type_enabled) {{
                        const kls = document.getElementById('la-kl-contribution-type');
                        const vf = kls && kls.value ? kls.value : null;
                        p.knowledge_form = vf;
                        if (klSchema.feature_flags.knowledge_scaffold_enabled && vf) {{
                            p.knowledge_scaffold = laCollectScaffold(vf);
                        }}
                    }}
                    if (klSchema && klSchema.feature_flags && (klSchema.feature_flags.layer_tags_enabled || klSchema.feature_flags.artifact_tags_enabled)) {{
                        const tagEl = document.getElementById('la-artifact-tags');
                        const raw = tagEl ? tagEl.value.trim() : '';
                        p.tag_slugs = raw ? raw.split(/[,\\s]+/).map(function(s) {{ return s.trim(); }}).filter(Boolean) : [];
                    }}
                    return p;
                }}
                function laRebuildTags() {{
                    const wrap = document.getElementById('la-tags-wrap');
                    if (!wrap) return;
                    if (!klSchema || !klSchema.feature_flags || !(klSchema.feature_flags.layer_tags_enabled || klSchema.feature_flags.artifact_tags_enabled)) {{
                        wrap.style.display = 'none';
                        return;
                    }}
                    wrap.style.display = 'block';
                }}
                function laSetFields(art) {{
                    for (const f of fields) {{
                        const el = document.getElementById(ids[f]);
                        if (el && art[f] !== undefined) el.value = art[f] || '';
                    }}
                    window.__laScaffoldData = art.knowledge_scaffold || null;
                    laRebuildContribution();
                    const kls = document.getElementById('la-kl-contribution-type');
                    var kf = art.knowledge_form;
                    if (kf === 'conviction') kf = 'claim';
                    if (kls && kf && [...kls.options].some(function(o){{return o.value===kf;}})) kls.value = kf;
                    else if (kls) kls.value = '';
                    laRenderScaffold();
                    laRebuildTags();
                    const tagEl = document.getElementById('la-artifact-tags');
                    if (tagEl) {{
                        const tags = art.tags || [];
                        tagEl.value = tags.map(function(t) {{ return t.slug || t.label || ''; }}).filter(Boolean).join(', ');
                    }}
                }}
                document.getElementById('la-artifact-type').addEventListener('change', function() {{
                    laRebuildContribution();
                    document.getElementById('la-kl-contribution-type').value = '';
                    window.__laScaffoldData = null;
                    laRenderScaffold();
                }});
                document.addEventListener('change', function(e) {{
                    if (e.target && e.target.id === 'la-kl-contribution-type') laRenderScaffold();
                }});
                document.getElementById('layerArtifactModal').addEventListener('show.bs.modal', async function() {{
                    await ensureKlSchema();
                    laRebuildTags();
                    try {{
                        const r = await fetch('/api/artifacts/' + aid + '/', {{credentials:'same-origin'}});
                        const d = await r.json();
                        if (r.ok) laSetFields(d);
                        else laShowAlert(d.error || 'Failed to load', 'danger');
                    }} catch (e) {{ laShowAlert(e.message, 'danger'); }}
                }});
                document.getElementById('la-artifact-save-btn').addEventListener('click', async function() {{
                    const btn = this;
                    btn.disabled = true;
                    document.getElementById('la-artifact-alert').classList.add('d-none');
                    try {{
                        const r = await fetch('/api/artifacts/' + aid + '/', {{
                            method: 'PATCH',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify(laGetPayload()),
                            credentials: 'same-origin'
                        }});
                        const d = await r.json();
                        if (r.ok) {{ location.reload(); return; }}
                        laShowAlert(d.error || 'Failed', 'danger');
                    }} catch (e) {{ laShowAlert(e.message, 'danger'); }}
                    btn.disabled = false;
                }});
                function laEsc(s) {{
                    return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
                }}
                async function laLoadCollections() {{
                    const listEl = document.getElementById('la-collections-list');
                    const pick = document.getElementById('la-collection-pick');
                    if (!listEl || !pick) return;
                    try {{
                        const r = await fetch('/api/layers/' + layerId + '/collections/', {{credentials:'same-origin'}});
                        const d = await r.json();
                        if (!r.ok) {{ listEl.textContent = 'Unable to load.'; return; }}
                        const cols = d.collections || [];
                        if (cols.length === 0) listEl.innerHTML = '<p class="text-muted mb-0">No collections yet.</p>';
                        else {{
                            listEl.innerHTML = '<ul class="list-unstyled mb-0">' + cols.map(function(c) {{
                                const n = (c.artifact_ids || []).length;
                                const t = laEsc(c.title || c.id);
                                return '<li class="mb-1">' + t + ' <span class="text-muted">(' + n + ')</span></li>';
                            }}).join('') + '</ul>';
                        }}
                        const cur = pick.value;
                        pick.innerHTML = '<option value="">– Choose –</option>';
                        cols.forEach(function(c) {{
                            pick.add(new Option(c.title || c.id, c.id));
                        }});
                        if (cur && [...pick.options].some(function(o){{return o.value===cur;}})) pick.value = cur;
                    }} catch (e) {{ listEl.textContent = 'Error loading collections.'; }}
                }}
                laLoadCollections();
                document.getElementById('la-add-to-collection-btn').addEventListener('click', async function() {{
                    const pick = document.getElementById('la-collection-pick');
                    const alertEl = document.getElementById('la-collection-alert');
                    alertEl.classList.add('d-none');
                    const cid = pick && pick.value;
                    if (!cid) {{ alertEl.textContent = 'Choose a collection.'; alertEl.classList.remove('d-none'); return; }}
                    try {{
                        const r = await fetch('/api/collections/' + cid + '/artifacts/', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{artifact_id: aid}}),
                            credentials: 'same-origin'
                        }});
                        const d = await r.json();
                        if (r.ok) {{ laLoadCollections(); pick.value = ''; return; }}
                        alertEl.textContent = d.error || 'Failed';
                        alertEl.classList.remove('d-none');
                    }} catch (e) {{ alertEl.textContent = e.message; alertEl.classList.remove('d-none'); }}
                }});
                document.getElementById('la-new-coll-save').addEventListener('click', async function() {{
                    const btn = this;
                    const title = (document.getElementById('la-new-coll-title').value || '').trim();
                    const alertEl = document.getElementById('la-new-coll-alert');
                    alertEl.classList.add('d-none');
                    if (!title) {{ alertEl.textContent = 'Title required'; alertEl.classList.remove('d-none'); return; }}
                    btn.disabled = true;
                    try {{
                        const r = await fetch('/api/layers/' + layerId + '/collections/', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{title: title}}),
                            credentials: 'same-origin'
                        }});
                        const d = await r.json();
                        if (r.ok) {{
                            bootstrap.Modal.getInstance(document.getElementById('laNewCollectionModal')).hide();
                            document.getElementById('la-new-coll-title').value = '';
                            laLoadCollections();
                        }} else {{
                            alertEl.textContent = d.error || 'Failed';
                            alertEl.classList.remove('d-none');
                        }}
                    }} catch (e) {{ alertEl.textContent = e.message; alertEl.classList.remove('d-none'); }}
                    btn.disabled = false;
                }});
            }})();
            </script>
    '''
