"""Workgroup external URL and linked document draft helpers."""
import html
import re
from typing import Any, Optional

from extensions import db
from services.groups import dp_image_url, extract_dp_number
from services.submissions import get_submission_by_ref

_DP_TITLE_RE = re.compile(r'^DP\s*(\d+)\b', re.IGNORECASE)


def is_dp_workgroup(workgroup) -> bool:
    """True when acronym or title identifies a Desirable Property workgroup."""
    if extract_dp_number(getattr(workgroup, 'acronym', '') or ''):
        return True
    return extract_dp_number_from_title(getattr(workgroup, 'name', '') or '') is not None


def workgroup_layer_ids(workgroup) -> set[str]:
    """Primary layer_id plus any secondary layer links."""
    ids = set()
    primary = getattr(workgroup, 'layer_id', None)
    if primary:
        ids.add(primary)
    for link in workgroup.secondary_layer_links.all():
        if link.layer_id:
            ids.add(link.layer_id)
    return ids


def workgroup_available_on_layer(workgroup, layer_id: Optional[str]) -> bool:
    if not layer_id:
        return False
    return layer_id in workgroup_layer_ids(workgroup)


META_LAYER_GOVERNANCE_SLUG = 'meta-layer-governance'


def ensure_meta_layer_governance_on_layer(layer_slug: str = 'the-metaweb') -> bool:
    """Link Meta-Layer Governance workgroup to a layer for draft assignment (secondary)."""
    from models import Layer, Workgroup

    layer = Layer.query.filter_by(slug=layer_slug).first()
    workgroup = Workgroup.query.filter_by(slug=META_LAYER_GOVERNANCE_SLUG).first()
    if not layer or not workgroup:
        return False
    if link_workgroup_secondary_layer(workgroup, layer.id):
        db.session.commit()
        return True
    return False


def link_workgroup_secondary_layer(workgroup, layer_id: str) -> bool:
    """Add secondary layer link. Returns True if a new row was created."""
    from models import WorkgroupLayerLink

    if not layer_id or workgroup.layer_id == layer_id:
        return False
    existing = WorkgroupLayerLink.query.filter_by(
        workgroup_id=workgroup.id,
        layer_id=layer_id,
    ).first()
    if existing:
        return False
    db.session.add(WorkgroupLayerLink(workgroup_id=workgroup.id, layer_id=layer_id))
    return True


def layer_has_secondary_workgroups(layer_id: Optional[str]) -> bool:
    """True when any workgroup is linked to this layer via workgroup_layer_link."""
    if not layer_id:
        return False
    from models import WorkgroupLayerLink

    return (
        db.session.query(WorkgroupLayerLink.id)
        .filter(WorkgroupLayerLink.layer_id == layer_id)
        .first()
        is not None
    )


def query_workgroups_for_layer(
    layer_id: Optional[str],
    *,
    status: str = 'active',
):
    """Workgroups whose primary or secondary layer matches ``layer_id``."""
    from models import Workgroup, WorkgroupLayerLink

    if not layer_id:
        return []

    primary_q = Workgroup.query.filter_by(layer_id=layer_id)
    if status:
        primary_q = primary_q.filter_by(status=status)

    linked_wg_ids = [
        row[0]
        for row in db.session.query(WorkgroupLayerLink.workgroup_id)
        .filter(WorkgroupLayerLink.layer_id == layer_id)
        .all()
    ]
    secondary_q = Workgroup.query.filter(Workgroup.id.in_(linked_wg_ids)) if linked_wg_ids else None
    if secondary_q is not None and status:
        secondary_q = secondary_q.filter_by(status=status)

    seen: set[str] = set()
    rows: list = []
    for wg in primary_q.all() + (secondary_q.all() if secondary_q is not None else []):
        if wg.id in seen:
            continue
        seen.add(wg.id)
        rows.append(wg)
    rows.sort(key=workgroup_display_sort_key)
    return rows


def workgroup_display_sort_key(workgroup) -> tuple:
    """DP workgroups by number ascending; others A–Z by name."""
    dp = extract_dp_number(workgroup.acronym or '') or extract_dp_number_from_title(
        workgroup.name or ''
    )
    if dp is not None:
        return (0, dp, '')
    name = (workgroup.name or workgroup.acronym or '').casefold()
    return (1, 0, name)


def workgroup_belongs_to_layer(acronym: str, layer_id: Optional[str], *, status: str = 'active') -> bool:
    """True if acronym is empty or matches a workgroup on the layer (primary or secondary)."""
    if not acronym:
        return True
    if not layer_id:
        return False
    from models import Workgroup

    query = Workgroup.query.filter_by(acronym=acronym.strip())
    if status:
        query = query.filter_by(status=status)
    wg = query.first()
    if not wg:
        return False
    return workgroup_available_on_layer(wg, layer_id)


def workgroup_option_label(workgroup, viewing_layer_id: Optional[str]) -> str:
    """Display label; suffix home layer when shown via secondary association."""
    label = workgroup.name or workgroup.acronym or ''
    if (
        viewing_layer_id
        and workgroup.layer_id
        and workgroup.layer_id != viewing_layer_id
        and workgroup.layer
    ):
        return f'{label} ({workgroup.layer.name})'
    return label


def workgroup_select_options_html(
    layer_id: Optional[str],
    selected_acronym: Optional[str] = None,
    *,
    placeholder: str = 'Select a Workgroup',
    pending_layer_message: str = 'Select a layer first',
    status: str = 'active',
) -> str:
    """Build HTML <option> elements for a workgroup dropdown."""
    selected = (selected_acronym or '').strip()
    options = [f'<option value="">{html.escape(placeholder)}</option>']
    if not layer_id:
        options.append(
            f'<option value="" disabled>{html.escape(pending_layer_message)}</option>'
        )
        return '\n                                        '.join(options)

    for wg in query_workgroups_for_layer(layer_id, status=status):
        if not wg.acronym:
            continue
        sel = ' selected' if wg.acronym == selected else ''
        label = html.escape(workgroup_option_label(wg, layer_id))
        value = html.escape(wg.acronym, quote=True)
        options.append(f'<option value="{value}"{sel}>{label}</option>')
    return '\n                                        '.join(options)


def submit_workgroup_layer_script(*, fixed_layer_id: Optional[str] = None) -> str:
    """JS to sync submit-form workgroup dropdowns when the layer selector changes."""
    if fixed_layer_id:
        return ''
    return '''
    let submitWorkgroupLoadSeq = 0;
    async function loadSubmitWorkgroups(layerId, selectedAcronym) {
        const seq = ++submitWorkgroupLoadSeq;
        const selects = [document.getElementById('group'), document.getElementById('ordinalGroup')];
        const placeholder = '<option value="">Select a Workgroup</option>';
        document.querySelectorAll('.submit-layer-id-field').forEach(function(el) {
            el.value = layerId || '';
        });
        if (!layerId) {
            selects.forEach(function(sel) {
                if (!sel) return;
                sel.innerHTML = placeholder + '<option value="" disabled>Select a layer first</option>';
            });
            return;
        }
        try {
            const response = await fetch('/api/layers/' + encodeURIComponent(layerId) + '/workgroups/?status=active');
            if (seq !== submitWorkgroupLoadSeq) return;
            const data = await response.json();
            const workgroups = (response.ok && Array.isArray(data.workgroups)) ? data.workgroups.slice() : [];
            workgroups.sort(function(a, b) {
                function dpNum(wg) {
                    const text = (wg.acronym || wg.name || '');
                    const m = text.match(/^dp\\s*(\\d+)/i) || text.match(/^dp(\\d+)/i);
                    return m ? parseInt(m[1], 10) : null;
                }
                const da = dpNum(a), db = dpNum(b);
                if (da !== null && db !== null) return da - db;
                if (da !== null) return -1;
                if (db !== null) return 1;
                return (a.name || a.acronym || '').localeCompare(b.name || b.acronym || '', undefined, { numeric: true, sensitivity: 'base' });
            });
            let html = placeholder;
            workgroups.forEach(function(wg) {
                if (!wg.acronym) return;
                const selected = selectedAcronym && wg.acronym === selectedAcronym ? ' selected' : '';
                let name = (wg.name || wg.acronym || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
                if (wg.layer_id && wg.layer_id !== layerId && wg.layer_name) {
                    const home = wg.layer_name.replace(/&/g, '&amp;').replace(/</g, '&lt;');
                    name += ' (' + home + ')';
                }
                const acr = (wg.acronym || '').replace(/"/g, '&quot;');
                html += '<option value="' + acr + '"' + selected + '>' + name + '</option>';
            });
            selects.forEach(function(sel) {
                if (sel) sel.innerHTML = html;
            });
        } catch (err) {
            if (seq !== submitWorkgroupLoadSeq) return;
            console.error('Failed to load workgroups for layer', layerId, err);
        }
    }
    function bindSubmitLayerControls() {
        const layerSelect = document.getElementById('layer_id');
        if (layerSelect && layerSelect.tagName === 'SELECT') {
            layerSelect.addEventListener('change', function() {
                loadSubmitWorkgroups(layerSelect.value);
            });
            if (layerSelect.value) {
                loadSubmitWorkgroups(layerSelect.value);
            }
            return;
        }
        const fixed = document.querySelector('.submit-layer-id-field');
        if (fixed && fixed.value) {
            loadSubmitWorkgroups(fixed.value);
        }
    }
    bindSubmitLayerControls();
    function syncSubmitLayerIdToForms() {
        const layerSelect = document.getElementById('layer_id');
        const val = layerSelect && layerSelect.tagName === 'SELECT' ? layerSelect.value : '';
        if (val) {
            document.querySelectorAll('.submit-layer-id-field').forEach(function(el) {
                el.value = val;
            });
        }
    }
    document.getElementById('uploadForm')?.addEventListener('submit', syncSubmitLayerIdToForms);
    document.getElementById('ordinalForm')?.addEventListener('submit', syncSubmitLayerIdToForms);
    '''


def extract_dp_number_from_title(title: str) -> Optional[int]:
    """Return DP number from titles like 'DP11 - Safe and Ethical AI'."""
    if not title:
        return None
    match = _DP_TITLE_RE.match(title.strip())
    return int(match.group(1)) if match else None


def find_dp_draft_ref(dp_num: int):
    """Return submission id for the best matching DP draft title, or None."""
    from models import Submission

    status_rank = {'approved': 0, 'submitted': 1, 'rejected': 2}
    best = None
    best_rank = 99
    best_approved_at = None

    for submission in Submission.query.filter_by(doc_type='draft').all():
        title = (submission.title or '').strip()
        match = _DP_TITLE_RE.match(title)
        if not match or int(match.group(1)) != dp_num:
            continue
        rank = status_rank.get(submission.status or '', 3)
        approved_at = submission.approved_at
        if (
            rank < best_rank
            or (
                rank == best_rank
                and approved_at
                and (best_approved_at is None or approved_at > best_approved_at)
            )
        ):
            best = submission
            best_rank = rank
            best_approved_at = approved_at

    return best.id if best else None


def find_workgroup_for_dp_num(dp_num: int):
    """Return the workgroup whose acronym is dp{N}-..., if any."""
    from models import Workgroup

    for wg in Workgroup.query.all():
        if extract_dp_number(wg.acronym or '') == dp_num:
            return wg
    return None


def assign_dp_draft_to_workgroup(workgroup, *, force: bool = False) -> bool:
    """
    Persist document_draft_name for a DP workgroup when a matching draft exists.
    Returns True if the workgroup was updated (caller should commit).
    """
    dp_num = extract_dp_number(workgroup.acronym or '')
    if dp_num is None:
        return False
    draft_ref = find_dp_draft_ref(dp_num)
    if not draft_ref:
        return False
    if not force and (workgroup.document_draft_name or '').strip():
        return False
    if workgroup.document_draft_name == draft_ref:
        return False
    workgroup.document_draft_name = draft_ref
    return True


def assign_dp_workgroup_for_submission(submission) -> bool:
    """
    When a DP draft is approved, link workgroup ↔ document both ways.
    Returns True if anything was updated (caller should commit).
    """
    updated = False
    if assign_submission_dp_workgroup(submission, force=True):
        updated = True
    if _assign_dp_draft_to_workgroup_for_submission(submission):
        updated = True
    return updated


def _assign_dp_draft_to_workgroup_for_submission(submission) -> bool:
    """Set workgroup.document_draft_name when a DP draft is approved."""
    if (getattr(submission, 'doc_type', None) or 'draft') != 'draft':
        return False
    dp_num = extract_dp_number_from_title(submission.title or '')
    if dp_num is None:
        return False
    workgroup = find_workgroup_for_dp_num(dp_num)
    if not workgroup:
        return False
    best_ref = find_dp_draft_ref(dp_num)
    if not best_ref:
        return False
    if workgroup.document_draft_name == best_ref:
        return False
    workgroup.document_draft_name = best_ref
    return True


def assign_submission_dp_workgroup(submission, *, force: bool = False) -> bool:
    """
    Set submission.group to the matching DP workgroup acronym.
    Returns True if updated (caller should commit).
    """
    if (getattr(submission, 'doc_type', None) or 'draft') != 'draft':
        return False
    dp_num = extract_dp_number_from_title(submission.title or '')
    if dp_num is None:
        return False
    workgroup = find_workgroup_for_dp_num(dp_num)
    if not workgroup:
        return False
    acronym = workgroup.acronym
    if not force and (submission.group or '').strip():
        return False
    if submission.group == acronym:
        return False
    submission.group = acronym
    return True


def sync_all_dp_submission_groups(*, force: bool = False) -> dict[str, int]:
    """
    Backfill submission.group for every DP-titled draft.
    force=True overwrites existing group values.
    """
    from models import Submission

    stats = {'updated': 0, 'skipped': 0, 'missing_wg': 0, 'not_dp': 0}
    for submission in Submission.query.filter_by(doc_type='draft').all():
        dp_num = extract_dp_number_from_title(submission.title or '')
        if dp_num is None:
            stats['not_dp'] += 1
            continue
        workgroup = find_workgroup_for_dp_num(dp_num)
        if not workgroup:
            stats['missing_wg'] += 1
            continue
        if not force and (submission.group or '').strip():
            stats['skipped'] += 1
            continue
        if submission.group == workgroup.acronym:
            stats['skipped'] += 1
            continue
        submission.group = workgroup.acronym
        stats['updated'] += 1
    return stats


def assign_dp_image_to_workgroup(workgroup, *, force: bool = False) -> bool:
    """
    Set image_url for a DP workgroup from static DP card assets.
    Returns True if the workgroup was updated (caller should commit).
    """
    dp_num = extract_dp_number(workgroup.acronym or '')
    if dp_num is None:
        return False
    url = dp_image_url(dp_num)
    if not url:
        return False
    if not force and (workgroup.image_url or '').strip():
        return False
    if workgroup.image_url == url:
        return False
    workgroup.image_url = url
    return True


def clear_all_workgroup_images() -> dict[str, int]:
    """Remove image_url from every workgroup. Returns stats (caller should commit)."""
    from models import Workgroup

    stats = {'cleared': 0, 'already_empty': 0}
    for wg in Workgroup.query.all():
        if not (wg.image_url or '').strip():
            stats['already_empty'] += 1
            continue
        wg.image_url = None
        stats['cleared'] += 1
    return stats


def sync_all_dp_workgroup_images(*, force: bool = False) -> dict[str, int]:
    """
    Assign static DP card images to every DP workgroup.
    force=True overwrites existing image_url values.
    """
    from models import Workgroup

    stats = {'updated': 0, 'skipped': 0, 'missing_image': 0, 'not_dp': 0}
    for wg in Workgroup.query.all():
        dp_num = extract_dp_number(wg.acronym or '')
        if dp_num is None:
            stats['not_dp'] += 1
            continue
        if not dp_image_url(dp_num):
            stats['missing_image'] += 1
            continue
        if not force and (wg.image_url or '').strip():
            stats['skipped'] += 1
            continue
        url = dp_image_url(dp_num)
        if wg.image_url == url:
            stats['skipped'] += 1
            continue
        wg.image_url = url
        stats['updated'] += 1
    return stats


def sync_all_dp_workgroup_documents(*, force: bool = False) -> dict[str, int]:
    """
    Link every DP workgroup to its corresponding DP draft submission.
    force=True reassigns even when document_draft_name is already set.
    """
    from models import Workgroup

    stats = {'updated': 0, 'skipped': 0, 'missing_draft': 0, 'not_dp': 0}
    for wg in Workgroup.query.all():
        dp_num = extract_dp_number(wg.acronym or '')
        if dp_num is None:
            stats['not_dp'] += 1
            continue
        draft_ref = find_dp_draft_ref(dp_num)
        if not draft_ref:
            stats['missing_draft'] += 1
            continue
        if not force and (wg.document_draft_name or '').strip():
            stats['skipped'] += 1
            continue
        if wg.document_draft_name == draft_ref:
            stats['skipped'] += 1
            continue
        wg.document_draft_name = draft_ref
        stats['updated'] += 1
    return stats


def effective_document_draft_ref(workgroup) -> Optional[str]:
    """Stored document ref, or inferred DP draft when unset."""
    ref = (workgroup.document_draft_name or '').strip() or None
    if ref:
        return ref
    dp_num = extract_dp_number(workgroup.acronym or '')
    if dp_num is not None:
        return find_dp_draft_ref(dp_num)
    return None


def resolve_document_draft(ref: Optional[str]):
    """Resolve a draft reference to a Submission, or None."""
    if not ref or not str(ref).strip():
        return None
    return get_submission_by_ref(str(ref).strip())


def normalize_document_draft_ref(ref: Optional[str]) -> Optional[str]:
    """Validate and normalize a draft reference to submission id."""
    if ref is None:
        return None
    trimmed = str(ref).strip()
    if not trimmed:
        return None
    submission = resolve_document_draft(trimmed)
    if not submission:
        return None
    return submission.id


def enrich_workgroup_dict(data: dict, workgroup) -> dict:
    """Add document_href, document_label, and effective document ref to workgroup dict."""
    ref = effective_document_draft_ref(workgroup)
    data['document_draft_name'] = workgroup.document_draft_name
    data['document_draft_ref'] = ref
    data['document_href'] = None
    data['document_label'] = None
    if ref:
        submission = resolve_document_draft(ref)
        if submission:
            data['document_href'] = f'/doc/draft/{submission.id}/'
            data['document_label'] = format_draft_display_name(submission)
    return data


def format_draft_display_name(submission) -> str:
    """Human-readable draft label for UI (title first, not ML number alone)."""
    title = (submission.title or '').strip()
    ml = (submission.ml_number or '').strip()
    if title and ml:
        return f'{title} ({ml})'
    return title or ml or submission.id


META_LAYER_ECOSYSTEM_SLUGS = frozenset({'the-metaweb', 'the-overweb', 'canopi'})


def _canonical_parent_for_picker(submission):
    """One picker row per document family — always the parent submission."""
    from services.ml_numbering import is_parent_submission

    if is_parent_submission(submission):
        return submission
    ref = (submission.parent_draft_name or '').strip()
    if ref:
        parent = resolve_document_draft(ref)
        if parent and parent.id != submission.id:
            return _canonical_parent_for_picker(parent)
    return submission


def _draft_picker_row(submission, *, version_count: Optional[int] = None) -> dict[str, Any]:
    label = format_draft_display_name(submission)
    if version_count and version_count > 1:
        label = f'{label} — {version_count} versions'
    return {
        'id': submission.id,
        'title': submission.title or submission.ml_number or submission.id,
        'label': label,
        'ml_number': submission.ml_number,
        'status': submission.status,
        'href': f'/doc/draft/{submission.id}/',
    }


def _submissions_to_picker_rows(submissions, *, limit: int = 500) -> list[dict[str, Any]]:
    """Collapse revisions to one option per ML number (parent submission)."""
    from services.ml_numbering import _family_members, is_parent_submission

    by_key: dict[str, Any] = {}
    for submission in submissions:
        parent = _canonical_parent_for_picker(submission)
        key = ((parent.ml_number or '').strip().casefold()) or parent.id
        existing = by_key.get(key)
        if not existing:
            by_key[key] = parent
            continue
        if is_parent_submission(parent) and not is_parent_submission(existing):
            by_key[key] = parent

    ordered = sorted(
        by_key.values(),
        key=lambda s: (format_draft_display_name(s).casefold(), s.submitted_at or ''),
    )
    rows: list[dict[str, Any]] = []
    for parent in ordered[:limit]:
        version_count = len(_family_members(parent))
        rows.append(_draft_picker_row(parent, version_count=version_count))
    return rows


def layer_ids_for_workgroup_document_picker(workgroup) -> set[str]:
    """Layers whose drafts appear in the workgroup document dropdown."""
    ids: set[str] = set()
    if workgroup.layer_id:
        ids.add(workgroup.layer_id)
    for link in workgroup.secondary_layer_links.all():
        if link.layer_id:
            ids.add(link.layer_id)
    from models import Layer

    layers = [Layer.query.get(lid) for lid in ids if lid]
    if any(layer and layer.slug in META_LAYER_ECOSYSTEM_SLUGS for layer in layers):
        for slug in META_LAYER_ECOSYSTEM_SLUGS:
            layer = Layer.query.filter_by(slug=slug).first()
            if layer:
                ids.add(layer.id)
    return ids


def list_draft_documents_for_picker(layer_id: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
    """All linkable drafts for workgroup document dropdown (single layer)."""
    from models import Submission

    query = Submission.query.filter(
        Submission.doc_type == 'draft',
        Submission.status.in_(['approved', 'submitted']),
    )
    if layer_id:
        query = query.filter(Submission.layer_id == layer_id)
    rows = query.order_by(Submission.title.asc(), Submission.submitted_at.desc()).all()
    return _submissions_to_picker_rows(rows, limit=limit)


def list_draft_documents_for_workgroup_picker(workgroup_id: str, limit: int = 500) -> list[dict[str, Any]]:
    """
    Drafts linkable from a workgroup edit form: primary/secondary layers, Meta-Layer
    ecosystem cross-layer drafts, and drafts already assigned via submission.group.
    """
    from models import Submission, Workgroup

    workgroup = Workgroup.query.get(workgroup_id)
    if not workgroup:
        return []

    base_filter = (
        Submission.doc_type == 'draft',
        Submission.status.in_(['approved', 'submitted']),
    )
    by_id: dict[str, Any] = {}

    layer_ids = layer_ids_for_workgroup_document_picker(workgroup)
    if layer_ids:
        for submission in Submission.query.filter(
            *base_filter, Submission.layer_id.in_(layer_ids)
        ).all():
            by_id[submission.id] = submission

    acronym = (workgroup.acronym or '').strip()
    if acronym:
        for submission in Submission.query.filter(
            *base_filter, Submission.group == acronym
        ).all():
            by_id[submission.id] = submission

    return _submissions_to_picker_rows(by_id.values(), limit=limit)


def build_document_workgroup_index() -> dict[str, dict]:
    """Preload workgroup maps for document catalog / detail pages."""
    from models import Workgroup

    by_acronym: dict[str, dict] = {}
    by_draft_ref: dict[str, dict] = {}
    by_dp_num: dict[int, dict] = {}

    for wg in Workgroup.query.all():
        slug = (wg.slug or wg.acronym or wg.id or '').strip()
        meta = {
            'group': (wg.acronym or '').strip() or None,
            'workgroup_name': (wg.name or wg.acronym or '').strip() or None,
            'workgroup_slug': slug or None,
            'workgroup_href': f'/workgroups/{slug}/' if slug else None,
        }
        if wg.acronym:
            by_acronym[wg.acronym.strip().lower()] = meta
        ref = effective_document_draft_ref(wg)
        if ref:
            by_draft_ref[ref] = meta
            submission = resolve_document_draft(ref)
            if submission:
                by_draft_ref[submission.id] = meta
                if submission.draft_name:
                    by_draft_ref[submission.draft_name] = meta
                if submission.ml_number:
                    by_draft_ref[submission.ml_number] = meta
        dp = extract_dp_number(wg.acronym or '')
        if dp is not None:
            by_dp_num[dp] = meta

    return {'by_acronym': by_acronym, 'by_draft_ref': by_draft_ref, 'by_dp_num': by_dp_num}


def resolve_document_workgroup_meta(
    *,
    name: Optional[str] = None,
    group: Optional[str] = None,
    title: Optional[str] = None,
    index: Optional[dict] = None,
) -> dict[str, Optional[str]]:
    """Workgroup label + href for a document; empty when none applies."""
    empty: dict[str, Optional[str]] = {
        'group': None,
        'workgroup_name': None,
        'workgroup_slug': None,
        'workgroup_href': None,
    }
    idx = index or build_document_workgroup_index()
    g = (group or '').strip()
    if g.lower() in ('n/a', 'none', ''):
        g = ''

    if g:
        hit = idx['by_acronym'].get(g.lower())
        if hit:
            return {**empty, **hit, 'group': hit.get('group') or g}

    ref = (name or '').strip()
    if ref:
        hit = idx['by_draft_ref'].get(ref)
        if hit:
            return {**empty, **hit}

    dp = extract_dp_number_from_title(title or '')
    if dp is not None:
        hit = idx['by_dp_num'].get(dp)
        if hit:
            return {**empty, **hit}

    if g:
        return {**empty, 'group': g, 'workgroup_name': g}
    return empty


def list_assigned_documents_for_workgroup(workgroup) -> list[dict[str, Any]]:
    """
    Drafts assigned to this workgroup via submission.group at submit time.
    Excludes the workgroup's primary document (document_draft_name) — that is shown separately.
    """
    from models import Submission
    from services.ml_numbering import is_parent_submission

    acronym = (workgroup.acronym or '').strip()
    if not acronym:
        return []

    primary_ref = effective_document_draft_ref(workgroup)
    primary_ids = {primary_ref} if primary_ref else set()
    if primary_ref:
        primary_sub = resolve_document_draft(primary_ref)
        if primary_sub:
            primary_ids.add(primary_sub.id)
            if primary_sub.draft_name:
                primary_ids.add(primary_sub.draft_name)

    query = Submission.query.filter(
        Submission.doc_type == 'draft',
        Submission.group == acronym,
    )
    if workgroup.layer_id:
        query = query.filter(Submission.layer_id == workgroup.layer_id)

    rows = query.order_by(Submission.submitted_at.desc()).all()
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for submission in rows:
        if not is_parent_submission(submission):
            continue
        if submission.id in seen:
            continue
        if submission.id in primary_ids or (submission.draft_name and submission.draft_name in primary_ids):
            continue
        seen.add(submission.id)
        docs.append({
            'id': submission.id,
            'ml_number': submission.ml_number,
            'title': submission.title,
            'status': submission.status,
            'label': format_draft_display_name(submission),
            'href': f'/doc/draft/{submission.id}/',
            'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
        })
    return docs


def search_draft_documents(query: str, limit: int = 15) -> list[dict[str, Any]]:
    """Search drafts by title, ML number, id, or draft_name."""
    from models import Submission

    q = (query or '').strip()
    if len(q) < 2:
        return []

    pattern = f'%{q}%'
    rows = Submission.query.filter(
        Submission.doc_type == 'draft',
        db.or_(
            Submission.title.ilike(pattern),
            Submission.ml_number.ilike(pattern),
            Submission.id.ilike(pattern),
            Submission.draft_name.ilike(pattern),
        ),
    ).order_by(Submission.submitted_at.desc()).all()
    return _submissions_to_picker_rows(rows, limit=limit)
