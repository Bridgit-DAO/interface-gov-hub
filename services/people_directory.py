"""People directory: row data, badges, and HTML fragments."""
from __future__ import annotations

import html as html_mod
import re
from typing import Any, Optional

from models import (
    User,
    Layer,
    LayerMember,
    LayerAdmin,
    Workgroup,
    WorkingGroupChair,
    WorkingGroupMember,
    Submission,
    Comment,
)
from services.groups import (
    GROUPS,
    format_dp_display_name,
    DP_DESCRIPTIONS,
    extract_dp_number,
    strip_workgroup_suffix,
)
from services.site_roles import site_role_badge_class, site_role_label
from services.event_subscriptions import count_distinct_drafts_followed

PILL_MAX_LEN = 26
MAX_WORKGROUP_PILLS = 4
MAX_LAYER_PILLS = 5
MAX_ROLE_PILLS = 6


def truncate_label(text: str, max_len: int = PILL_MAX_LEN) -> str:
    text = (text or '').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + '…'


_DP_NAME_PREFIX_RE = re.compile(r'^DP\s*\d+', re.IGNORECASE)


def workgroup_label_for_acronym(acronym: str, wg_by_acronym: dict[str, Workgroup]) -> str:
    acronym = (acronym or '').strip()
    if not acronym:
        return ''
    wg = wg_by_acronym.get(acronym)
    if wg:
        name = (wg.name or wg.acronym or '').strip()
        if extract_dp_number(wg.acronym or acronym) is not None:
            if _DP_NAME_PREFIX_RE.match(name):
                return strip_workgroup_suffix(name)
            return format_dp_display_name(wg.acronym or acronym, name)
        return strip_workgroup_suffix(name) or acronym
    dp = DP_DESCRIPTIONS.get(acronym)
    if dp:
        return format_dp_display_name(acronym, dp['title'])
    entry = next((g for g in GROUPS if g.get('acronym') == acronym), None)
    if entry:
        return entry.get('name') or acronym
    return format_dp_display_name(acronym, acronym.replace('-', ' ').title())


def _workgroup_href(wg: Optional[Workgroup], acronym: str) -> str:
    if wg and wg.slug:
        return f'/workgroups/{html_mod.escape(wg.slug)}/'
    return '#'


def _pill_link(href: str, label: str, title: str, badge_class: str) -> str:
    short = truncate_label(label)
    full = html_mod.escape(title or label)
    return (
        f'<a href="{href}" class="badge {badge_class} gh-pill-truncate text-decoration-none me-1 mb-1" '
        f'title="{full}">{html_mod.escape(short)}</a>'
    )


def _pill_span(label: str, title: str, badge_class: str) -> str:
    short = truncate_label(label)
    full = html_mod.escape(title or label)
    return (
        f'<span class="badge {badge_class} gh-pill-truncate me-1 mb-1" title="{full}">'
        f'{html_mod.escape(short)}</span>'
    )


def _overflow_pill(count: int) -> str:
    return f'<span class="badge bg-secondary gh-pill-truncate me-1 mb-1" title="{count} more">+{count}</span>'


def build_people_lookup_tables() -> dict[str, Any]:
    """Bulk-load membership maps used when rendering the people table."""
    wg_by_acronym: dict[str, Workgroup] = {}
    for wg in Workgroup.query.all():
        if wg.acronym:
            wg_by_acronym[wg.acronym] = wg

    layers_by_id = {layer.id: layer for layer in Layer.query.all()}

    chairs_by_user: dict[str, list[str]] = {}
    for row in WorkingGroupChair.query.all():
        if row and row.user_id and row.group_acronym:
            chairs_by_user.setdefault(row.user_id, []).append(row.group_acronym)

    members_by_user: dict[str, list[str]] = {}
    for row in WorkingGroupMember.query.all():
        if row and row.user_id and row.group_acronym:
            members_by_user.setdefault(row.user_id, []).append(row.group_acronym)

    layer_admin_ids_by_user: dict[str, set[str]] = {}
    for row in LayerAdmin.query.all():
        layer_admin_ids_by_user.setdefault(row.user_id, set()).add(row.layer_id)

    layer_members_by_user: dict[str, list[LayerMember]] = {}
    for row in LayerMember.query.filter(LayerMember.status == 'active').all():
        layer_members_by_user.setdefault(row.user_id, []).append(row)

    initiator_layers_by_user: dict[str, list[str]] = {}
    for layer in layers_by_id.values():
        if layer.initiator_id:
            initiator_layers_by_user.setdefault(layer.initiator_id, []).append(layer.id)

    return {
        'wg_by_acronym': wg_by_acronym,
        'layers_by_id': layers_by_id,
        'chairs_by_user': chairs_by_user,
        'members_by_user': members_by_user,
        'layer_admin_ids_by_user': layer_admin_ids_by_user,
        'layer_members_by_user': layer_members_by_user,
        'initiator_layers_by_user': initiator_layers_by_user,
    }


def _merged_workgroups(user_id: str, lookup: dict[str, Any]) -> list[tuple[str, bool]]:
    """Unique acronyms with is_chair flag; chairs first, then alpha by label."""
    chair_set = set(lookup['chairs_by_user'].get(user_id, []))
    member_set = set(lookup['members_by_user'].get(user_id, []))
    acronyms = chair_set | member_set
    wg_by = lookup['wg_by_acronym']
    items = [
        (ac, ac in chair_set)
        for ac in acronyms
    ]
    items.sort(
        key=lambda t: (
            0 if t[1] else 1,
            workgroup_label_for_acronym(t[0], wg_by).lower(),
        )
    )
    return items


def _layer_entries(user_id: str, lookup: dict[str, Any]) -> list[tuple[Layer, str]]:
    """Layers for user with best role label per layer."""
    layers_by_id = lookup['layers_by_id']
    admin_ids = lookup['layer_admin_ids_by_user'].get(user_id, set())
    initiator_ids = lookup['initiator_layers_by_user'].get(user_id, [])
    member_rows = {
        m.layer_id: m for m in lookup['layer_members_by_user'].get(user_id, [])
    }

    seen: dict[str, str] = {}
    for lid in initiator_ids:
        if lid in layers_by_id:
            seen[lid] = 'initiator'
    for lid in admin_ids:
        if lid in layers_by_id:
            seen[lid] = 'admin'
    for lid, member in member_rows.items():
        if lid not in layers_by_id:
            continue
        role = (member.role or 'member').strip() or 'member'
        if lid not in seen or seen[lid] == 'member':
            seen[lid] = role

    entries = []
    for lid, role in seen.items():
        layer = layers_by_id[lid]
        entries.append((layer, role))
    entries.sort(key=lambda e: (e[0].name or '').lower())
    return entries


def _role_pills_html(user: User, layer_entries: list[tuple[Layer, str]]) -> str:
    """Site role plus elevated layer roles (not repeated in Layers column)."""
    pills = [
        _pill_span(
            site_role_label(user.role),
            f'Site role: {site_role_label(user.role)}',
            f'bg-{site_role_badge_class(user.role)}',
        )
    ]
    elevated = [
        (layer, role)
        for layer, role in layer_entries
        if role not in ('member', 'contributor')
    ]
    overflow = 0
    for layer, role in elevated:
        if len(pills) >= MAX_ROLE_PILLS:
            overflow += 1
            continue
        label = truncate_label(role.replace('_', ' ').title())
        title = f'{layer.name}: {role}'
        pills.append(_pill_span(label, title, 'bg-info text-dark'))
    if overflow:
        pills.append(_overflow_pill(overflow))
    return ''.join(pills) if pills else '<span class="text-muted">—</span>'


def _layers_pills_html(layer_entries: list[tuple[Layer, str]]) -> str:
    if not layer_entries:
        return '<span class="text-muted">—</span>'
    pills = []
    overflow = 0
    for layer, role in layer_entries:
        if len(pills) >= MAX_LAYER_PILLS:
            overflow += 1
            continue
        name = layer.name or layer.slug or 'Layer'
        role_bit = truncate_label(role.replace('_', ' '), max_len=12)
        label = truncate_label(f'{name} · {role_bit}', max_len=PILL_MAX_LEN + 4)
        href = f'/layers/{html_mod.escape(layer.slug or "")}/'
        pills.append(
            _pill_link(href, label, f'{name} ({role})', 'bg-primary')
        )
    if overflow:
        pills.append(_overflow_pill(overflow))
    return ''.join(pills)


def _workgroups_pills_html(
    merged: list[tuple[str, bool]],
    wg_by_acronym: dict[str, Workgroup],
) -> str:
    if not merged:
        return '<span class="text-muted">—</span>'
    pills = []
    overflow = 0
    for acronym, is_chair in merged:
        if len(pills) >= MAX_WORKGROUP_PILLS:
            overflow += 1
            continue
        wg = wg_by_acronym.get(acronym)
        label = workgroup_label_for_acronym(acronym, wg_by_acronym)
        if is_chair:
            label = truncate_label(f'{label} ★', max_len=PILL_MAX_LEN + 2)
        href = _workgroup_href(wg, acronym)
        badge = 'bg-warning text-dark' if is_chair else 'bg-secondary'
        pills.append(_pill_link(href, label, label, badge))
    if overflow:
        pills.append(_overflow_pill(overflow))
    return ''.join(pills)


def build_person_row(
    user: User,
    lookup: dict[str, Any],
    *,
    show_admin_actions: bool,
) -> dict[str, Any]:
    """Build sort/filter fields and table cell HTML for one person."""
    display = user.name or user.displayName or user.oauthName or user.username
    name_variants = [x for x in (user.name, user.displayName, user.oauthName, user.username) if x]
    submissions_count = (
        Submission.query.filter(Submission.submitted_by.in_(name_variants)).count()
        if name_variants
        else 0
    )
    follows_count = count_distinct_drafts_followed(user.id)
    comments_count = (
        Comment.query.filter(Comment.author.in_(name_variants)).count()
        if name_variants
        else 0
    )
    activity_total = submissions_count + follows_count + comments_count

    last_ts = 0
    if user.last_login:
        last_ts = int(user.last_login.timestamp() * 1000)
        last_active_html = user.last_login.strftime('%Y-%m-%d')
    else:
        last_active_html = '<span class="text-muted">Never</span>'

    merged_wg = _merged_workgroups(user.id, lookup)
    layer_entries = _layer_entries(user.id, lookup)
    wg_by = lookup['wg_by_acronym']

    primary_wg_sort = ''
    if merged_wg:
        primary_wg_sort = workgroup_label_for_acronym(merged_wg[0][0], wg_by).lower()

    search_bits = [display, user.username, site_role_label(user.role)]
    for ac, _ in merged_wg:
        search_bits.append(workgroup_label_for_acronym(ac, wg_by))
        search_bits.append(ac)
    for layer, role in layer_entries:
        search_bits.extend([layer.name or '', layer.slug or '', role])

    group_keys = ' '.join(sorted({ac for ac, _ in merged_wg}))

    actions_td = ''
    if show_admin_actions:
        actions_td = (
            f'<td><a href="/admin/users/{user.id}/add-coordinator" '
            f'class="btn btn-outline-primary btn-sm">Add coordinator</a></td>'
        )

    activity_html = (
        f'<span class="gh-people-activity" title="{submissions_count} submissions, '
        f'{follows_count} followed, {comments_count} comments">'
        f'<span class="gh-people-activity-item" title="Submissions">'
        f'<i class="fas fa-file-alt text-muted me-1"></i>{submissions_count}</span>'
        f'<span class="gh-people-activity-item ms-2" title="Followed drafts">'
        f'<i class="fas fa-bookmark text-muted me-1"></i>{follows_count}</span>'
        f'<span class="gh-people-activity-item ms-2" title="Comments">'
        f'<i class="fas fa-comment text-muted me-1"></i>{comments_count}</span></span>'
    )

    from services.avatar import get_avatar_url

    avatar_src = get_avatar_url(user, 36)
    profile_link = f'/profile/{html_mod.escape(user.username)}/'
    avatar_html = (
        f'<img src="{html_mod.escape(avatar_src)}" alt="" class="rounded-circle me-2" '
        f'style="width:36px;height:36px;object-fit:cover" '
        f'onerror="this.onerror=null;this.src=\'/static/images/default-avatar.png\'">'
    )
    name_html = (
        f'<td><div class="d-flex align-items-center">{avatar_html}<div>'
        f'<a href="{profile_link}" class="fw-bold text-decoration-none">'
        f'{html_mod.escape(display)}</a><br>'
        f'<small class="text-muted">@{html_mod.escape(user.username)}</small></div></div></td>'
    )

    row_html = (
        f'<tr data-search="{html_mod.escape(" ".join(search_bits).lower())}" '
        f'data-groups="{html_mod.escape(group_keys)}" '
        f'data-name="{html_mod.escape(display.lower())}" '
        f'data-last-active="{last_ts}" '
        f'data-submissions="{submissions_count}" '
        f'data-activity="{activity_total}" '
        f'data-workgroup="{html_mod.escape(primary_wg_sort)}" '
        f'data-role="{html_mod.escape(site_role_label(user.role))}">'
        f'{name_html}'
        f'<td class="gh-people-pills-cell">{_role_pills_html(user, layer_entries)}</td>'
        f'<td class="gh-people-pills-cell">{_layers_pills_html(layer_entries)}</td>'
        f'<td class="gh-people-pills-cell">{_workgroups_pills_html(merged_wg, wg_by)}</td>'
        f'<td>{last_active_html}</td>'
        f'<td>{activity_html}</td>'
        f'{actions_td}</tr>'
    )

    return {
        'row_html': row_html,
        'display': display,
        'group_keys': group_keys,
        'sort_name': display.lower(),
        'sort_last_active': last_ts,
        'sort_submissions': submissions_count,
        'sort_activity': activity_total,
        'sort_workgroup': primary_wg_sort,
        'sort_role': site_role_label(user.role),
    }


def workgroup_filter_options(lookup: dict[str, Any]) -> list[tuple[str, str]]:
    """Distinct workgroup acronyms → (value, label) for filter dropdown."""
    wg_by = lookup['wg_by_acronym']
    acronyms: set[str] = set()
    for rows in lookup['chairs_by_user'].values():
        acronyms.update(rows)
    for rows in lookup['members_by_user'].values():
        acronyms.update(rows)
    options = [
        (ac, workgroup_label_for_acronym(ac, wg_by))
        for ac in acronyms
    ]
    options.sort(key=lambda x: x[1].lower())
    return options
