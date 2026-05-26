"""DP Proposal API and admin dashboard (scaffolding)."""
from flask import Blueprint, jsonify, redirect, request, url_for

from extensions import db
from models import DpProposal
from services.dp_proposals import (
    accept_proposal,
    can_manage_amendments,
    create_dp_proposal,
    dashboard_dp_activity,
    decline_proposal,
    list_proposals_for_submission,
    proposal_counts,
    require_dp_proposals_enabled,
    resolve_submission_for_proposals,
    user_from_session,
    validate_create_payload,
    workgroup_for_submission,
)
from services.identity import get_current_user, require_auth, require_role
from services.rendering import generate_user_menu, render_page
from services.directory_ui import gh_page_header, gh_breadcrumb

bp = Blueprint('dp_proposals', __name__, url_prefix='/api/doc/draft')
admin_bp = Blueprint('dp_proposals_admin', __name__, url_prefix='')


@admin_bp.route('/dp-proposals/')
@admin_bp.route('/dp-proposals')
def dp_proposals_shortcut():
    """Redirect common mistyped path to the admin dashboard."""
    return redirect(url_for('dp_proposals_admin.dp_proposals_dashboard'))


def _feature_guard():
    blocked = require_dp_proposals_enabled()
    if blocked:
        return blocked
    return None


@bp.route('/<path:draft_ref>/proposals/', methods=['GET'])
def list_proposals(draft_ref):
    guard = _feature_guard()
    if guard:
        return guard
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    rows = list_proposals_for_submission(submission.id)
    counts = proposal_counts(rows)
    return jsonify({
        'submission_id': submission.id,
        'draft_ref': draft_ref,
        'proposals': [row.to_dict() for row in rows],
        'count': counts['total'],
        'counts_by_status': counts['by_status'],
        'counts_by_anchor': counts['by_anchor'],
    })


@bp.route('/<path:draft_ref>/proposals/', methods=['POST'])
@require_auth
def create_proposal(draft_ref):
    guard = _feature_guard()
    if guard:
        return guard
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    user = user_from_session(current_user)
    if not user:
        return jsonify({'error': 'User not found'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400

    payload, val_err = validate_create_payload(request.get_json(silent=True))
    if val_err:
        return jsonify({'error': val_err}), 400

    row = create_dp_proposal(
        submission,
        author_user_id=user.id,
        original_text=payload['original_text'],
        proposed_text=payload['proposed_text'],
        context_anchor=payload.get('context_anchor'),
        scope=payload['scope'],
    )
    db.session.commit()
    return jsonify({'proposal': row.to_dict(), 'status_label': row.status_label()}), 201


@bp.route('/<path:draft_ref>/proposals/<proposal_id>/accept/', methods=['POST'])
@require_auth
def accept_proposal_route(draft_ref, proposal_id):
    guard = _feature_guard()
    if guard:
        return guard
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400

    wg = workgroup_for_submission(submission)
    if not can_manage_amendments(current_user, wg):
        return jsonify({'error': 'Not authorized to accept amendments for this DP'}), 403

    proposal = DpProposal.query.filter_by(id=proposal_id, submission_id=submission.id).first()
    if not proposal:
        return jsonify({'error': 'Proposal not found'}), 404
    if proposal.status != 'pending':
        return jsonify({'error': f'Cannot accept proposal in status {proposal.status}'}), 400

    user = user_from_session(current_user)
    accept_proposal(proposal, user.id if user else current_user.get('id'))
    db.session.commit()
    return jsonify({
        'proposal': proposal.to_dict(),
        'status_label': proposal.status_label(),
        'message': 'Accepted as amendment',
    })


@bp.route('/<path:draft_ref>/proposals/<proposal_id>/decline/', methods=['POST'])
@require_auth
def decline_proposal_route(draft_ref, proposal_id):
    guard = _feature_guard()
    if guard:
        return guard
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400

    wg = workgroup_for_submission(submission)
    if not can_manage_amendments(current_user, wg):
        return jsonify({'error': 'Not authorized to decline proposals for this DP'}), 403

    proposal = DpProposal.query.filter_by(id=proposal_id, submission_id=submission.id).first()
    if not proposal:
        return jsonify({'error': 'Proposal not found'}), 404
    if proposal.status != 'pending':
        return jsonify({'error': f'Cannot decline proposal in status {proposal.status}'}), 400

    user = user_from_session(current_user)
    decline_proposal(proposal, user.id if user else current_user.get('id'))
    db.session.commit()
    return jsonify({
        'proposal': proposal.to_dict(),
        'status_label': proposal.status_label(),
        'message': 'Proposal declined',
    })


@admin_bp.route('/admin/dp-proposals/')
@require_role('admin')
def dp_proposals_dashboard():
    guard = _feature_guard()
    if guard:
        return guard
    rows = dashboard_dp_activity()
    user_menu = generate_user_menu()
    table_rows = ''
    for row in rows:
        title = row.get('title') or row.get('submission_id') or 'Untitled'
        ml = row.get('ml_number') or '—'
        wg = row.get('workgroup_name') or row.get('workgroup_acronym') or '—'
        c = row.get('counts') or {}
        table_rows += (
            f'<tr>'
            f'<td>{title}</td>'
            f'<td>{ml}</td>'
            f'<td>{wg}</td>'
            f'<td>{c.get("pending", 0)}</td>'
            f'<td>{c.get("accepted", 0)}</td>'
            f'<td>{c.get("declined", 0)}</td>'
            f'<td>{c.get("total", 0)}</td>'
            f'<td>{row.get("last_activity") or "—"}</td>'
            f'</tr>'
        )
    if not table_rows:
        table_rows = (
            '<tr><td colspan="8" class="text-muted text-center py-4">'
            'No DP Proposals yet. Activity will appear here once readers submit proposals.'
            '</td></tr>'
        )
    content = f'''
    {gh_breadcrumb([('Admin', '/admin/'), ('DP Proposals', None)])}
    {gh_page_header('DP Proposals', 'Activity by Desirable Property (most active first)', 'fa-highlighter')}
    <div class="table-responsive">
      <table class="table table-striped align-middle">
        <thead>
          <tr>
            <th>DP / Title</th>
            <th>ML #</th>
            <th>Workgroup</th>
            <th>Proposals</th>
            <th>Amendments</th>
            <th>Declined</th>
            <th>Total</th>
            <th>Last activity</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
    <p class="text-muted small">API: <code>GET /api/doc/draft/&lt;ref&gt;/proposals/</code></p>
    '''
    return render_page('DP Proposals — Admin', content, user_menu=user_menu)
