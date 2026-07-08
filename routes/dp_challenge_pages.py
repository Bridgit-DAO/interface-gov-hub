"""Public proposal hubs: DP Challenge and Suggest an Edit (shared template, mode-driven labels/lists)."""
from __future__ import annotations

import html as html_mod
import json
import re
from typing import List, Optional

from flask import Blueprint, jsonify, request, session

from services.directory_ui import gh_breadcrumb, gh_living_module, gh_page_header
from services.dp_proposals import (
    challenge_recent_events,
    dashboard_dp_activity,
    dashboard_dp_by_participant,
    dashboard_dp_challenge_stats,
    list_approved_submissions_for_mode,
    parse_challenge_since_param,
    submission_draft_ref,
)
from services.identity import get_current_user
from services.layer_programs import hub_access_state, resolve_program_for_hub
from services.proposal_modes import ProposalMode, get_proposal_mode, is_mode_enabled
from services.read_navigation import read_page_url
from services.rendering import generate_user_menu, render_page
from services.workgroup_links import extract_dp_number_from_title

bp = Blueprint('dp_challenge', __name__)


def _format_activity_time(iso: Optional[str]) -> str:
    if not iso:
        return '–'
    return html_mod.escape(iso[:19].replace('T', ' '))


def _build_doc_table_rows(rows: list, mode_cfg: dict) -> str:
    hub_path = mode_cfg['hub_path']
    labels = mode_cfg['labels']
    show_dp = mode_cfg.get('show_dp_column', True)
    if not rows:
        return f'''
            <tr>
                <td colspan="9" class="text-center text-muted py-4">
                    {html_mod.escape(mode_cfg['empty_docs'])}
                </td>
            </tr>'''
    out = []
    for row in rows:
        draft_ref = html_mod.escape(row.get('draft_ref') or '')
        title_short = html_mod.escape(row.get('title_short') or row.get('title') or 'Untitled')
        title_full = html_mod.escape(row.get('title') or 'Untitled')
        ml = html_mod.escape(row.get('ml_number') or '–')
        dp_num = row.get('dp_number')
        dp_label = html_mod.escape(f'DP{dp_num}') if dp_num is not None else '–'
        c = row.get('counts') or {}
        doc_href = html_mod.escape(read_page_url(draft_ref, hub_path))
        dp_cell = ''
        if show_dp:
            dp_cell = f'<td class="dp-challenge-col-dp"><span class="badge bg-primary">{dp_label}</span></td>'
        out.append(f'''
            <tr>
                {dp_cell}
                <td class="dp-challenge-col-title">
                    <a href="{doc_href}" class="dp-challenge-doc-link text-decoration-none" title="{title_full}">{title_short}</a>
                </td>
                <td class="dp-challenge-col-ml text-muted">{ml}</td>
                <td class="dp-challenge-col-num">{int(row.get('contributors') or 0)}</td>
                <td class="dp-challenge-col-num"><span class="badge bg-primary">{int(c.get('pending', 0))}</span></td>
                <td class="dp-challenge-col-num"><span class="badge bg-success">{int(c.get('accepted', 0))}</span></td>
                <td class="dp-challenge-col-num"><span class="badge bg-secondary">{int(c.get('declined', 0))}</span></td>
                <td class="dp-challenge-col-num">{int(c.get('total', 0))}</td>
                <td class="dp-challenge-col-action text-end">
                    <a href="{doc_href}" class="btn btn-sm btn-outline-primary text-nowrap">{html_mod.escape(mode_cfg['read_button'])}</a>
                </td>
            </tr>''')
    return ''.join(out)


def _build_contributor_rows(rows: list, current_user_id: Optional[str], mode_cfg: dict) -> str:
    if not rows:
        return f'''
            <tr>
                <td colspan="6" class="text-center text-muted py-4">
                    {html_mod.escape(mode_cfg['empty_contributors'])}
                </td>
            </tr>'''
    pinned = []
    rest = []
    for row in rows:
        if current_user_id and row.get('author_user_id') == current_user_id:
            pinned.append(row)
        else:
            rest.append(row)
    ordered = pinned + rest
    out = []
    for row in ordered:
        name = html_mod.escape(row.get('display_name') or 'Participant')
        profile = row.get('profile_href')
        name_cell = (
            f'<a href="{html_mod.escape(profile)}" class="text-decoration-none fw-semibold">{name}</a>'
            if profile
            else f'<span class="fw-semibold">{name}</span>'
        )
        if current_user_id and row.get('author_user_id') == current_user_id:
            name_cell += ' <span class="badge bg-info ms-1">You</span>'
        c = row.get('counts') or {}
        out.append(f'''
            <tr{" class='table-info'" if current_user_id and row.get('author_user_id') == current_user_id else ''}>
                <td>{name_cell}</td>
                <td>{int(c.get('total', 0))}</td>
                <td>{int(c.get('docs', 0))}</td>
                <td><span class="badge bg-success">{int(c.get('accepted', 0))}</span></td>
                <td class="text-muted small">{_format_activity_time(row.get('last_activity'))}</td>
                <td class="text-end">
                    {f'<a href="{html_mod.escape(profile)}" class="btn btn-sm btn-outline-secondary">Profile</a>' if profile else ''}
                </td>
            </tr>''')
    return ''.join(out)


def _picker_sort_key(sub, mode: str) -> tuple:
    if mode == 'dp':
        dp_num = extract_dp_number_from_title(sub.title or '')
        return (dp_num if dp_num is not None else 9999, (sub.title or '').lower())
    return ((sub.ml_number or ''), (sub.title or '').lower())


def _short_dp_name(title: str) -> str:
    """Title without leading 'DP11 - ' prefix."""
    t = (title or '').strip()
    m = re.match(r'^DP\s*(\d+)\s*[-––:]\s*(.+)$', t, re.IGNORECASE)
    return m.group(2).strip() if m else t


def format_dp_picker_label(sub) -> str:
    """DPnn - [name] for the hub doc picker."""
    dp_num = extract_dp_number_from_title(sub.title or '')
    name = _short_dp_name(sub.title or '') or (sub.title or '').strip() or 'Draft'
    dp_part = f'DP{dp_num:02d}' if dp_num is not None else 'DP'
    return f'{dp_part} - {name}'


def _build_picker_docs(mode: str, program=None) -> List[dict]:
    """Approved submissions for the searchable doc picker (JSON to the client)."""
    subs = list_approved_submissions_for_mode(mode, program=program)
    subs.sort(key=lambda s: _picker_sort_key(s, mode))
    docs = []
    for sub in subs:
        ref = submission_draft_ref(sub)
        label = format_dp_picker_label(sub) if mode == 'dp' else (sub.title or ref).strip()
        entry = {
            'ref': ref,
            'label': label,
        }
        if sub.ml_number:
            entry['ml'] = sub.ml_number
        if mode == 'dp':
            dp_num = extract_dp_number_from_title(sub.title or '')
            if dp_num is not None:
                entry['dp'] = f'DP{dp_num:02d}'
        docs.append(entry)
    return docs


def _render_prelaunch_hub_page(
    mode_cfg: dict,
    program: dict,
    notify_config: dict,
    current_user,
    hub_path: str,
) -> str:
    launch_label = html_mod.escape(
        notify_config.get('launch_at_label') or 'mid-July 2026 at 9:00 AM Pacific'
    )
    layer_slug = html_mod.escape(program.get('layer_slug') or 'the-metaweb')
    layer_name = html_mod.escape(program.get('layer_name') or 'The Metaweb')
    program_name = html_mod.escape(program.get('name') or mode_cfg['page_title'])
    joined = bool(notify_config.get('joined'))
    login_next = html_mod.escape(hub_path)
    signed_in = bool(current_user)

    hero_section = ''
    if mode_cfg.get('show_hero'):
        hero_light = html_mod.escape(mode_cfg['hero_image_light'])
        hero_dark = html_mod.escape(mode_cfg['hero_image_dark'])
        hero_alt = html_mod.escape(mode_cfg['hero_aria'])
        hero_section = f'''
        <section class="dp-challenge-hero living-module mb-4 dp-challenge-hero--prelaunch" aria-label="{hero_alt}">
            <div class="dp-challenge-hero-banner">
                <img src="{hero_light}" alt="" width="1024" height="576" loading="eager"
                    class="dp-challenge-hero-img dp-challenge-hero-img--light dp-challenge-hero-img--dim" />
                <img src="{hero_dark}" alt="" width="1024" height="576" loading="eager"
                    class="dp-challenge-hero-img dp-challenge-hero-img--dark dp-challenge-hero-img--dim" aria-hidden="true" />
            </div>
        </section>'''

    status_alert = ''
    if joined:
        status_alert = (
            '<div class="alert alert-success py-2 px-3 mb-4">'
            '<i class="fas fa-bell me-2"></i>You are on the notify list. We will email you when the Challenge opens.'
            '</div>'
        )

    content = f'''
    <link rel="stylesheet" href="/static/css/dp-challenge.css?v=9">
    <div class="gh-page container mt-4 dp-challenge-page dp-challenge-page--prelaunch">
        {gh_page_header(
            mode_cfg['page_title'],
            'Opening soon – join the notify list for the start of public input.',
            mode_cfg['icon'],
            breadcrumb_html=gh_breadcrumb([('Participate', None), (mode_cfg['breadcrumb'], None)]),
        )}

        <div class="alert alert-secondary py-3 px-3 mb-4">
            <p class="small mb-2">
                <i class="fas fa-layer-group me-1"></i>
                <strong>The {html_mod.escape(mode_cfg['page_title'])}</strong> is a program on
                <a href="/layers/{layer_slug}/" class="alert-link">{layer_name}</a>.
                Opens <strong>{launch_label}</strong>.
            </p>
            <p class="small mb-2">
                Learn more at the
                <a href="https://desirableproperties.org/challenge" target="_blank" rel="noopener" class="alert-link">Desirable Properties site</a>.
                Here are things you can do now:
            </p>
            <ul class="small mb-0">
                <li>
                    Familiarize yourself with the
                    <a href="https://desirableproperties.org/#dps" target="_blank" rel="noopener" class="alert-link">desirable properties</a>.
                </li>
                <li>
                    <a href="https://desirableproperties.org/workgroups/join" target="_blank" rel="noopener" class="alert-link">Join or nominate someone to a DP workgroup</a>.
                </li>
                <li>
                    Review and comment on the
                    <a href="https://book.desirableproperties.org" target="_blank" rel="noopener" class="alert-link">0.77 Desirable Properties book</a>.
                </li>
            </ul>
        </div>

        {status_alert}
        {hero_section}

        <div class="living-module mb-4">
            <div class="living-module-body">
                <h2 class="h5 mb-2">Be first to propose patches</h2>
                <p class="text-muted mb-3">
                    The {html_mod.escape(mode_cfg['page_title'])} opens in mid-July.
                    Join the notify list and tell us which DP drafts you want to work on.
                    We will let you know when patching goes live.
                </p>
                <button type="button" class="btn btn-primary" id="dpChallengeNotifyOpenBtn">
                    <i class="fas fa-bell me-2"></i>{'Update my DP interests' if joined else 'Notify me when it opens'}
                </button>
            </div>
        </div>
    </div>

    <div class="modal fade" id="dpChallengeNotifyModal" tabindex="-1" aria-labelledby="dpChallengeNotifyModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="dpChallengeNotifyModalLabel">
                        <i class="fas fa-bell me-2"></i>Notify me when the Challenge opens
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted small">Opens {launch_label}. Select the DP drafts you want to patch (optional).</p>
                    {'<p class="mb-3"><a href="/login/?next=' + login_next + '" class="btn btn-primary btn-sm">Sign in to join the notify list</a></p>' if not signed_in else ''}
                    <div id="dpChallengeNotifyFormWrap" {'hidden' if not signed_in else ''}>
                        <label class="form-label" for="dpChallengeNotifyDpSelect">DPs of interest</label>
                        <select class="form-select" id="dpChallengeNotifyDpSelect" multiple size="8"
                            aria-describedby="dpChallengeNotifyDpHelp"></select>
                        <div id="dpChallengeNotifyDpHelp" class="form-text">
                            Hold Ctrl (Windows/Linux) or Cmd (Mac) to select multiple drafts.
                        </div>
                        <p class="small text-muted mt-3 mb-0" id="dpChallengeNotifyMsg"></p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>
                    {'<button type="button" class="btn btn-primary" id="dpChallengeNotifySubmitBtn"><i class="fas fa-check me-1"></i>Join notify list</button>' if signed_in else ''}
                </div>
            </div>
        </div>
    </div>

    <script>
    window.DP_CHALLENGE_NOTIFY = {json.dumps(notify_config)};
    window.DP_CHALLENGE_PAGE = {{ returnTo: {json.dumps(hub_path)}, signedIn: {json.dumps(signed_in)} }};
    </script>
    <script src="/static/js/dp-challenge-notify.js?v=1" defer></script>
    '''

    return render_page(
        f'{mode_cfg["page_title"]} – opening soon – GovHub',
        content,
        theme=session.get('theme', 'dark'),
        user_menu=generate_user_menu(),
    )


def _program_context_banner(program) -> str:
    if not program:
        return ''
    layer_name = html_mod.escape(program.get('layer_name') or 'The Metaweb')
    layer_slug = html_mod.escape(program.get('layer_slug') or 'the-metaweb')
    program_name = html_mod.escape(program.get('name') or 'Program')
    return f'''
        <div class="alert alert-secondary py-2 px-3 mb-4 d-flex flex-wrap align-items-center justify-content-between gap-2">
            <span class="small mb-0">
                <i class="fas fa-layer-group me-1"></i>
                <strong>{program_name}</strong> is a program on
                <a href="/layers/{layer_slug}/" class="alert-link">{layer_name}</a>.
            </span>
            <span class="badge text-bg-success text-uppercase">{html_mod.escape(program.get("status") or "active")}</span>
        </div>'''


def _render_proposal_hub_page(mode: ProposalMode):
    mode_cfg = get_proposal_mode(mode)
    if not is_mode_enabled(mode):
        return render_page(
            f'{mode_cfg["page_title"]} – GovHub',
            f'<div class="container mt-5"><p class="text-muted">{html_mod.escape(mode_cfg["page_title"])} is not available on this site yet.</p></div>',
            theme=session.get('theme', 'dark'),
            user_menu=generate_user_menu(),
        )

    current_user = get_current_user()
    program_row = resolve_program_for_hub(
        mode_cfg['hub_path'],
        program_slug=(request.args.get('program') or '').strip() or None,
        layer_slug=(request.args.get('layer') or '').strip() or None,
    )
    program = None
    if program_row:
        from services.layer_programs import notify_config_for_program, program_public_view

        program = program_public_view(program_row, current_user)
        access = hub_access_state(program_row, current_user)
        if access == 'waitlist':
            notify_config = notify_config_for_program(program_row, current_user)
            return _render_prelaunch_hub_page(
                mode_cfg, program, notify_config, current_user, mode_cfg['hub_path']
            )
        if access == 'draft' and not current_user:
            notify_config = notify_config_for_program(program_row, current_user)
            return _render_prelaunch_hub_page(
                mode_cfg, program, notify_config, current_user, mode_cfg['hub_path']
            )

    stats = dashboard_dp_challenge_stats(mode=mode, program=program_row)
    doc_rows = dashboard_dp_activity(mode=mode, program=program_row)
    participant_rows = dashboard_dp_by_participant(mode=mode, program=program_row)
    current_user_id = current_user.get('id') if current_user else None
    labels = mode_cfg['labels']
    hub_path = mode_cfg['hub_path']
    show_dp = mode_cfg.get('show_dp_column', True)

    picker_docs = _build_picker_docs(mode, program=program_row)
    picker_placeholder = html_mod.escape(mode_cfg['picker_placeholder'])
    picker_empty = html_mod.escape(mode_cfg['picker_empty'])
    dp_header = ''
    if show_dp:
        dp_header = '<th class="dp-challenge-col-dp">DP</th>'
    doc_table = f'''
        <div class="table-responsive dp-challenge-table-wrap">
            <table class="table table-hover align-middle mb-0 dp-challenge-doc-table" id="dpChallengeDocTable">
                <thead>
                    <tr>
                        {dp_header}
                        <th class="dp-challenge-col-title">Title</th>
                        <th class="dp-challenge-col-ml">ML #</th>
                        <th class="dp-challenge-col-num">Contributors</th>
                        <th class="dp-challenge-col-num">{html_mod.escape(labels["pending_plural"])}</th>
                        <th class="dp-challenge-col-num">{html_mod.escape(labels["accepted_plural"])}</th>
                        <th class="dp-challenge-col-num">Declined</th>
                        <th class="dp-challenge-col-num">Total</th>
                        <th class="dp-challenge-col-action"></th>
                    </tr>
                </thead>
                <tbody>{_build_doc_table_rows(doc_rows, mode_cfg)}</tbody>
            </table>
        </div>'''

    contributor_table = f'''
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" id="dpChallengeContributorTable">
                <thead>
                    <tr>
                        <th>Contributor</th>
                        <th>{html_mod.escape(labels["pending_plural"])}</th>
                        <th>{html_mod.escape(mode_cfg["contributor_docs_col"])}</th>
                        <th>{html_mod.escape(labels["accepted_plural"])}</th>
                        <th>Last active</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>{_build_contributor_rows(participant_rows, current_user_id, mode_cfg)}</tbody>
            </table>
        </div>'''

    login_cta = ''
    if not current_user:
        login_cta = (
            f'<p class="mb-0 mt-2"><a href="/login/?next={html_mod.escape(hub_path)}" class="btn btn-sm btn-primary">'
            'Sign in to patch</a></p>'
        )

    hero_section = ''
    if mode_cfg.get('show_hero'):
        hero_light = html_mod.escape(mode_cfg['hero_image_light'])
        hero_dark = html_mod.escape(mode_cfg['hero_image_dark'])
        hero_alt = html_mod.escape(mode_cfg['hero_aria'])
        hero_section = f'''
        <section class="dp-challenge-hero living-module mb-4" aria-label="{hero_alt}">
            <div class="dp-challenge-hero-banner">
                <img
                    src="{hero_light}"
                    alt="{hero_alt}"
                    width="1024"
                    height="576"
                    loading="eager"
                    decoding="async"
                    class="dp-challenge-hero-img dp-challenge-hero-img--light"
                />
                <img
                    src="{hero_dark}"
                    alt=""
                    width="1024"
                    height="576"
                    loading="eager"
                    decoding="async"
                    class="dp-challenge-hero-img dp-challenge-hero-img--dark"
                    aria-hidden="true"
                />
            </div>
            {login_cta}
        </section>'''
    elif login_cta:
        hero_section = f'<div class="mb-4">{login_cta}</div>'

    program_banner = _program_context_banner(program)

    content = f'''
    <link rel="stylesheet" href="/static/css/dp-challenge.css?v=9">
    <div class="gh-page container mt-4 dp-challenge-page">
        {gh_page_header(
            mode_cfg['page_title'],
            mode_cfg['page_tagline'],
            mode_cfg['icon'],
            breadcrumb_html=gh_breadcrumb([('Participate', None), (mode_cfg['breadcrumb'], None)]),
        )}
        {program_banner}

        <div class="dp-challenge-cta-bar mb-4">
            <div class="dp-doc-picker" id="dpChallengeDocPicker" data-empty="{picker_empty}">
                <input
                    type="text"
                    id="dpChallengeDocPickerInput"
                    class="form-control form-control-sm dp-doc-picker-input"
                    placeholder="{picker_placeholder}"
                    autocomplete="off"
                    spellcheck="false"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded="false"
                    aria-controls="dpChallengeDocPickerList"
                />
                <ul
                    id="dpChallengeDocPickerList"
                    class="dp-doc-picker-list"
                    role="listbox"
                    hidden
                ></ul>
            </div>
            {'<button type="button" class="btn btn-outline-secondary btn-sm text-nowrap" id="dpChallengeInviteBtn"><i class="fas fa-user-plus me-1"></i>Invite a colleague</button>' if current_user else ''}
        </div>

        {hero_section}

        <div class="dp-challenge-stats row g-3 mb-4">
            <div class="col-md-4">
                <div class="dp-challenge-stat-card">
                    <div class="dp-challenge-stat-value">{stats['total_proposals']}</div>
                    <div class="dp-challenge-stat-label">{html_mod.escape(labels['pending_plural'])}</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="dp-challenge-stat-card">
                    <div class="dp-challenge-stat-value">{stats['contributors']}</div>
                    <div class="dp-challenge-stat-label">Contributors</div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="dp-challenge-stat-card">
                    <div class="dp-challenge-stat-value">{stats['documents']}</div>
                    <div class="dp-challenge-stat-label">{html_mod.escape(mode_cfg['stat_docs_label'])}</div>
                </div>
            </div>
        </div>

        <ul class="nav nav-tabs dp-challenge-tabs mb-3" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-by-doc" data-bs-toggle="tab"
                    data-bs-target="#panel-by-doc" type="button" role="tab">By Doc</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-by-contributor" data-bs-toggle="tab"
                    data-bs-target="#panel-by-contributor" type="button" role="tab">Contributors</button>
            </li>
        </ul>
        <div class="tab-content">
            <div class="tab-pane fade show active" id="panel-by-doc" role="tabpanel">
                {gh_living_module('By Doc', doc_table, 'fa-file-alt', extra_class='mb-0')}
            </div>
            <div class="tab-pane fade" id="panel-by-contributor" role="tabpanel">
                {gh_living_module('Contributors', contributor_table, 'fa-users', extra_class='mb-0')}
            </div>
        </div>
    </div>

    <div id="dpChallengeToastHost" class="dp-challenge-toast-host" aria-live="polite" aria-atomic="false"></div>
    <script>
    window.DP_CHALLENGE_PAGE = {{
        pollIntervalMs: 30000,
        currentUserId: {json.dumps(current_user_id)},
        returnTo: {json.dumps(hub_path)},
        recentApiPath: {json.dumps(mode_cfg['recent_api_path'])},
        labels: {json.dumps(labels)},
        pickerDocs: {json.dumps(picker_docs)},
        pickerPlaceholder: {json.dumps(mode_cfg['picker_placeholder'])},
        pickerEmpty: {json.dumps(mode_cfg['picker_empty'])},
        invite: {{
            type: 'participate_dp',
            title: {json.dumps('Invite to ' + mode_cfg['page_title'])},
            hint: {json.dumps(
                'Invite a colleague to read DP drafts and propose patches.'
                if mode == 'dp'
                else 'Invite a colleague to read living documents and propose patches.'
            )},
            target: {{}}
        }}
    }};
    </script>
    <script src="/static/js/dp-challenge.js?v=6" defer></script>
    '''

    return render_page(
        f'{mode_cfg["page_title"]} – GovHub',
        content,
        theme=session.get('theme', 'dark'),
        user_menu=generate_user_menu(),
    )


def _recent_api(mode: ProposalMode):
    if not is_mode_enabled(mode):
        return jsonify({'events': [], 'enabled': False}), 200
    mode_cfg = get_proposal_mode(mode)
    program_row = resolve_program_for_hub(
        mode_cfg['hub_path'],
        program_slug=(request.args.get('program') or '').strip() or None,
        layer_slug=(request.args.get('layer') or '').strip() or None,
    )
    since = parse_challenge_since_param(request.args.get('since'))
    events = challenge_recent_events(since=since, limit=25, mode=mode, program=program_row)
    return jsonify({'events': events, 'enabled': True})


@bp.route('/dp-challenge/')
@bp.route('/dp-challenge')
def dp_challenge_page():
    return _render_proposal_hub_page('dp')


@bp.route('/suggest-edit/')
@bp.route('/suggest-edit')
def suggest_edit_page():
    return _render_proposal_hub_page('document')


@bp.route('/api/dp-challenge/recent')
def dp_challenge_recent_api():
    return _recent_api('dp')


@bp.route('/api/suggest-edit/recent')
def suggest_edit_recent_api():
    return _recent_api('document')
