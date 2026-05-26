"""Public DP Challenge hub: activity by doc and contributor."""
from __future__ import annotations

import html as html_mod
import json
from typing import List, Optional

from flask import Blueprint, jsonify, request, session

from services.directory_ui import gh_breadcrumb, gh_living_module, gh_page_header
from services.dp_proposals import (
    challenge_recent_events,
    dashboard_dp_activity,
    dashboard_dp_by_participant,
    dashboard_dp_challenge_stats,
    list_approved_dp_submissions,
    parse_challenge_since_param,
    submission_draft_ref,
)
from services.workgroup_links import extract_dp_number_from_title
from services.identity import get_current_user
from services.product_rollout import is_feature_enabled
from services.read_navigation import read_page_url
from services.rendering import generate_user_menu, render_page

bp = Blueprint('dp_challenge', __name__)


def _format_activity_time(iso: Optional[str]) -> str:
    if not iso:
        return '—'
    return html_mod.escape(iso[:19].replace('T', ' '))


def _build_doc_table_rows(rows: list) -> str:
    if not rows:
        return '''
            <tr>
                <td colspan="9" class="text-center text-muted py-4">
                    No proposals yet. Open a DP draft, select a sentence, and be the first to suggest a change.
                </td>
            </tr>'''
    out = []
    for row in rows:
        draft_ref = html_mod.escape(row.get('draft_ref') or '')
        title_short = html_mod.escape(row.get('title_short') or row.get('title') or 'Untitled')
        title_full = html_mod.escape(row.get('title') or 'Untitled')
        ml = html_mod.escape(row.get('ml_number') or '—')
        dp_num = row.get('dp_number')
        dp_label = html_mod.escape(f'DP{dp_num}') if dp_num is not None else '—'
        c = row.get('counts') or {}
        doc_href = html_mod.escape(read_page_url(draft_ref, '/dp-challenge/'))
        out.append(f'''
            <tr>
                <td class="dp-challenge-col-dp"><span class="badge bg-primary">{dp_label}</span></td>
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
                    <a href="{doc_href}" class="btn btn-sm btn-outline-primary text-nowrap">Read &amp; propose</a>
                </td>
            </tr>''')
    return ''.join(out)


def _build_contributor_rows(rows: list, current_user_id: Optional[str]) -> str:
    if not rows:
        return '''
            <tr>
                <td colspan="6" class="text-center text-muted py-4">
                    No contributors yet. Be the first to propose an edit on a DP draft.
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


def _dp_picker_sort_key(sub) -> tuple:
    dp_num = extract_dp_number_from_title(sub.title or '')
    return (dp_num if dp_num is not None else 9999, (sub.title or '').lower())


def _build_dp_picker_options() -> str:
    subs = list_approved_dp_submissions()
    subs.sort(key=_dp_picker_sort_key)
    if not subs:
        return '<option value="">No approved DP drafts yet</option>'
    opts = ['<option value="">Choose a DP draft…</option>']
    for sub in subs:
        ref = submission_draft_ref(sub)
        label = (sub.title or ref).strip()
        opts.append(
            f'<option value="{html_mod.escape(ref)}">{html_mod.escape(label)}</option>'
        )
    return ''.join(opts)


@bp.route('/dp-challenge/')
@bp.route('/dp-challenge')
def dp_challenge_page():
    if not is_feature_enabled('dp_proposals'):
        return render_page(
            'DP Challenge — MLGH',
            '<div class="container mt-5"><p class="text-muted">DP Challenge is not available on this site yet.</p></div>',
            theme=session.get('theme', 'dark'),
            user_menu=generate_user_menu(),
        )

    stats = dashboard_dp_challenge_stats()
    doc_rows = dashboard_dp_activity()
    participant_rows = dashboard_dp_by_participant()
    current_user = get_current_user()
    current_user_id = current_user.get('id') if current_user else None

    picker_options = _build_dp_picker_options()
    doc_table = f'''
        <div class="table-responsive dp-challenge-table-wrap">
            <table class="table table-hover align-middle mb-0 dp-challenge-doc-table" id="dpChallengeDocTable">
                <thead>
                    <tr>
                        <th class="dp-challenge-col-dp">DP</th>
                        <th class="dp-challenge-col-title">Title</th>
                        <th class="dp-challenge-col-ml">ML #</th>
                        <th class="dp-challenge-col-num">Contributors</th>
                        <th class="dp-challenge-col-num">Proposals</th>
                        <th class="dp-challenge-col-num">Amendments</th>
                        <th class="dp-challenge-col-num">Declined</th>
                        <th class="dp-challenge-col-num">Total</th>
                        <th class="dp-challenge-col-action"></th>
                    </tr>
                </thead>
                <tbody>{_build_doc_table_rows(doc_rows)}</tbody>
            </table>
        </div>'''

    contributor_table = f'''
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" id="dpChallengeContributorTable">
                <thead>
                    <tr>
                        <th>Contributor</th>
                        <th>Proposals</th>
                        <th>DPs touched</th>
                        <th>Amendments</th>
                        <th>Last active</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>{_build_contributor_rows(participant_rows, current_user_id)}</tbody>
            </table>
        </div>'''

    login_cta = ''
    if not current_user:
        login_cta = (
            '<p class="mb-0 mt-2"><a href="/login/?next=/dp-challenge/" class="btn btn-sm btn-primary">'
            'Sign in to propose</a></p>'
        )

    content = f'''
    <link rel="stylesheet" href="/static/css/dp-challenge.css?v=3">
    <div class="gh-page container mt-4 dp-challenge-page">
        {gh_page_header(
            'DP Challenge',
            'Your line can become the standard — propose edits on DP drafts.',
            'fa-highlighter',
            breadcrumb_html=gh_breadcrumb([('Participate', None), ('DP Challenge', None)]),
        )}

        <div class="dp-challenge-cta-bar mb-4">
            <select id="dpChallengeDocPicker" class="form-select form-select-sm dp-challenge-picker">
                {picker_options}</select>
            <button type="button" class="btn btn-primary btn-sm text-nowrap" id="dpChallengeGoRead">
                <i class="fas fa-pen me-1"></i>Start a DP Proposal</button>
        </div>

        <section class="dp-challenge-hero living-module mb-4" aria-label="How to submit a DP proposal">
            <div class="dp-challenge-hero-banner">
                <img
                    src="/static/images/dp-challenge-hero.png"
                    alt="How to submit a DP proposal: read the draft, select a sentence, and propose a clearer replacement."
                    width="1024"
                    height="576"
                    loading="eager"
                    decoding="async"
                    class="dp-challenge-hero-img"
                />
            </div>
            {login_cta}
        </section>

        <div class="dp-challenge-stats row g-3 mb-4">
            <div class="col-md-4">
                <div class="dp-challenge-stat-card">
                    <div class="dp-challenge-stat-value">{stats['total_proposals']}</div>
                    <div class="dp-challenge-stat-label">Proposals</div>
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
                    <div class="dp-challenge-stat-label">DPs with activity</div>
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
    <script src="/static/js/dp-challenge.js?v=1" defer></script>
    <script>
    window.DP_CHALLENGE_PAGE = {{
        pollIntervalMs: 30000,
        currentUserId: {json.dumps(current_user_id)}
    }};
    </script>
    '''

    return render_page(
        'DP Challenge — MLGH',
        content,
        theme=session.get('theme', 'dark'),
        user_menu=generate_user_menu(),
    )


@bp.route('/api/dp-challenge/recent')
def dp_challenge_recent_api():
    if not is_feature_enabled('dp_proposals'):
        return jsonify({'events': [], 'enabled': False}), 200
    since = parse_challenge_since_param(request.args.get('since'))
    events = challenge_recent_events(since=since, limit=25)
    return jsonify({'events': events, 'enabled': True})
