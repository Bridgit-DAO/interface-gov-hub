"""DP Proposal API and admin dashboard (scaffolding)."""
import html as html_mod

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from extensions import db
from models import DpProposal
from services.dp_proposals import (
    accept_proposal,
    can_accept_amendments,
    can_manage_amendments,
    consider_proposal,
    create_dp_proposal,
    dashboard_dp_activity,
    decline_proposal,
    list_proposals_for_submission,
    proposal_counts,
    require_dp_proposals_enabled,
    resolve_submission_for_proposals,
    user_from_session,
    validate_create_payload,
    validate_proposal_scope_for_submission,
    expected_proposal_scope,
    workgroup_for_submission,
)
from services.api_auth import get_api_user, require_api_auth
from services.identity import get_current_user, require_auth, require_role
from services.rendering import generate_user_menu, render_page
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module

bp = Blueprint('dp_proposals', __name__, url_prefix='/api/doc/draft')
admin_bp = Blueprint('dp_proposals_admin', __name__, url_prefix='')


@admin_bp.route('/dp-proposals/')
@admin_bp.route('/dp-proposals')
def dp_proposals_shortcut():
    """Redirect common mistyped path to the admin dashboard."""
    return redirect(url_for('dp_proposals_admin.dp_proposals_dashboard'))


def _submission_feature_guard(submission):
    from services.proposal_modes import is_mode_enabled, proposal_mode_for_submission

    mode = proposal_mode_for_submission(submission)
    if not is_mode_enabled(mode):
        from flask import jsonify
        from services.proposal_modes import get_proposal_mode

        flag = get_proposal_mode(mode)['feature_flag']
        return jsonify({
            'error': 'Proposals are not enabled for this document type.',
            'error_code': 'FEATURE_DISABLED',
            'feature': flag,
        }), 403
    return None


@bp.route('/<path:draft_ref>/proposals/', methods=['GET'])
def list_proposals(draft_ref):
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard
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
@require_api_auth
def create_proposal(draft_ref):
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    user = user_from_session(current_user)
    if not user:
        return jsonify({'error': 'User not found'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    else:
        body = dict(body)
    if not body.get('scope'):
        body['scope'] = expected_proposal_scope(submission)

    payload, val_err = validate_create_payload(body)
    if val_err:
        return jsonify({'error': val_err}), 400

    scope_err = validate_proposal_scope_for_submission(submission, payload['scope'])
    if scope_err:
        return jsonify({'error': scope_err}), 400

    from services.dp_proposals import passage_exists_in_current_document

    if not passage_exists_in_current_document(submission, payload['original_text']):
        return jsonify({
            'error': 'Selected passage was not found in the current document. '
                     'Refresh the reader and select text again.',
            'error_code': 'PASSAGE_NOT_FOUND',
        }), 400

    row = create_dp_proposal(
        submission,
        author_user_id=user.id,
        original_text=payload['original_text'],
        proposed_text=payload['proposed_text'],
        context_anchor=payload.get('context_anchor'),
        scope=payload['scope'],
        rationale=payload.get('rationale'),
        reference_url=payload.get('reference_url'),
    )
    db.session.flush()  # ensure row.id is populated before emit_event reads it
    from services.events import emit_event
    from services.document_follow_notifications import draft_key_for_submission

    draft_key = draft_key_for_submission(submission)
    emit_event(
        'dp_proposal_submitted',
        actor_type='user',
        actor_id=user.id,
        subject_type='dp_proposal',
        subject_id=row.id,
        layer_id=submission.layer_id,
        payload={
            'draft_name': draft_key,
            'ml_number': submission.ml_number,
            'submission_id': submission.id,
            'proposal_id': row.id,
            'scope': row.scope,
        },
    )
    from services.contribution_pipeline import enqueue_contribution_pipeline_event, pipeline_payload_for_proposal

    try:
        enqueue_contribution_pipeline_event(
            subject_type='dp_proposal',
            subject_id=row.id,
            event_type='submitted',
            source_channel=row.source_channel or 'gov-hub',
            payload=pipeline_payload_for_proposal(row, submission),
        )
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(
                '[ContributionPipeline] Failed to enqueue submitted for proposal %s: %s',
                row.id,
                e,
            )
        except RuntimeError:
            pass
    db.session.commit()
    return jsonify({'proposal': row.to_dict(), 'status_label': row.status_label()}), 201


@bp.route('/<path:draft_ref>/proposals/<proposal_id>/accept/', methods=['POST'])
@require_auth
def accept_proposal_route(draft_ref, proposal_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard

    wg = workgroup_for_submission(submission)
    if not can_accept_amendments(current_user, wg):
        return jsonify({'error': 'You do not have permission to accept amendments on this document'}), 403

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
        'message': 'Patch merged',
    })


@bp.route('/<path:draft_ref>/proposals/<proposal_id>/consider/', methods=['POST'])
@require_auth
def consider_proposal_route(draft_ref, proposal_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard

    wg = workgroup_for_submission(submission)
    if not can_manage_amendments(current_user, wg):
        return jsonify({'error': 'Not authorized to review proposals for this DP'}), 403

    proposal = DpProposal.query.filter_by(id=proposal_id, submission_id=submission.id).first()
    if not proposal:
        return jsonify({'error': 'Proposal not found'}), 404
    if proposal.status != 'pending':
        return jsonify({'error': f'Cannot mark proposal as considered in status {proposal.status}'}), 400

    user = user_from_session(current_user)
    consider_proposal(proposal, user.id if user else current_user.get('id'))
    db.session.commit()
    return jsonify({
        'proposal': proposal.to_dict(),
        'status_label': proposal.status_label(),
        'message': 'Marked as considered',
    })


@bp.route('/<path:draft_ref>/proposals/<proposal_id>/decline/', methods=['POST'])
@require_auth
def decline_proposal_route(draft_ref, proposal_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard

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
        'message': 'Patch declined',
    })


@bp.route('/<path:draft_ref>/reader-comments/', methods=['GET'])
def list_reader_comments_route(draft_ref):
    from services.document_reader_comments import list_reader_comments_for_draft
    from services.identity import get_current_user

    body, status = list_reader_comments_for_draft(draft_ref, current_user=get_current_user())
    return jsonify(body), status


@bp.route('/<path:draft_ref>/assist/context/', methods=['POST'])
@require_auth
def assist_context_route(draft_ref):
    from services.assist import assemble_context, get_available_actions, llm_configured

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    context, err = assemble_context(draft_ref, body)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    return jsonify({
        'ok': True,
        'context': context,
        'sources': context.get('sources') or {},
        'actions': get_available_actions(context.get('mode') or 'comment'),
        'llm_configured': llm_configured(),
    })


@bp.route('/<path:draft_ref>/assist/generate/', methods=['POST'])
@require_auth
def assist_generate_route(draft_ref):
    from services.assist import (
        LlmCallFailed,
        LlmTemporarilyBusy,
        generate_draft,
    )

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    action = (body.get('action') or '').strip()
    context = body.get('context')
    if not action or not isinstance(context, dict):
        return jsonify({'error': 'action and context are required'}), 400
    try:
        result = generate_draft(
            action,
            context,
            user_prompt=body.get('user_prompt'),
            user_id=current_user.get('id'),
        )
    except ValueError as e:
        return jsonify({'ok': False, 'error': str(e), 'transient': False}), 400
    except LlmTemporarilyBusy as e:
        # Upstream overloaded / gateway hiccup / network. The frontend uses
        # `transient: true` to show a "try again in a minute" warning dialog
        # instead of the raw provider error.
        current_app.logger.warning('Assist transient failure: %s', e)
        return jsonify({
            'ok': False,
            'error': str(e),
            'transient': True,
        }), 503
    except LlmCallFailed as e:
        current_app.logger.exception('Assist non-transient failure')
        return jsonify({
            'ok': False,
            'error': str(e),
            'transient': False,
        }), 502
    except RuntimeError as e:
        return jsonify({
            'ok': False,
            'error': 'AI Assist unavailable',
            'details': str(e),
            'transient': False,
        }), 503
    except Exception as e:
        current_app.logger.exception('Assist generation failed')
        return jsonify({
            'ok': False,
            'error': 'AI Assist failed unexpectedly.',
            'transient': False,
        }), 500
    return jsonify({'ok': True, **result})


@bp.route('/<path:draft_ref>/reader-comments/', methods=['POST'])
@require_api_auth
def create_reader_comment_route(draft_ref):
    from services.document_reader_comments import create_reader_comment_for_draft

    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    resp, status = create_reader_comment_for_draft(
        draft_ref,
        author_user_id=current_user['id'],
        body=body,
    )
    return jsonify(resp), status


@bp.route('/<path:draft_ref>/reader-comments/<comment_id>/', methods=['PATCH'])
@require_auth
def update_reader_comment_route(draft_ref, comment_id):
    from services.document_reader_comments import update_reader_comment

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    resp, status = update_reader_comment(
        draft_ref,
        comment_id,
        author_user_id=current_user['id'],
        text=body.get('text') or '',
    )
    return jsonify(resp), status


@bp.route('/<path:draft_ref>/reader-comments/<comment_id>/', methods=['DELETE'])
@require_auth
def delete_reader_comment_route(draft_ref, comment_id):
    from services.document_reader_comments import delete_reader_comment

    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    resp, status = delete_reader_comment(
        draft_ref,
        comment_id,
        author_user_id=current_user['id'],
    )
    return jsonify(resp), status


@bp.route('/<path:draft_ref>/read-meta/', methods=['GET'])
def read_meta(draft_ref):
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return jsonify({'error': err}), 404 if err == 'Document not found' else 400
    guard = _submission_feature_guard(submission)
    if guard:
        return guard
    from services.draft_reader import load_draft_document_body, build_draft_context
    from services.dp_proposal_reader import build_read_meta

    draft, sub = build_draft_context(draft_ref)
    if not draft or not sub:
        return jsonify({'error': 'Document not found'}), 404
    content, render_html, _, _ = load_draft_document_body(
        draft, sub, draft_ref, pdf_iframe_height='800px'
    )
    return jsonify(build_read_meta(sub, draft_ref, render_html=render_html, document_content=content))


@admin_bp.route('/admin/dp-proposals/')
@require_role('admin')
def dp_proposals_dashboard():
    blocked = require_dp_proposals_enabled()
    if blocked:
        return blocked

    rows = dashboard_dp_activity()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    table_rows = ''
    for row in rows:
        submission_id = row.get('submission_id') or ''
        title = html_mod.escape(row.get('title') or submission_id or 'Untitled')
        ml = html_mod.escape(row.get('ml_number') or '–')
        wg = html_mod.escape(row.get('workgroup_name') or row.get('workgroup_acronym') or '–')
        c = row.get('counts') or {}
        pending = int(c.get('pending', 0))
        accepted = int(c.get('accepted', 0))
        declined = int(c.get('declined', 0))
        total = int(c.get('total', 0))
        last = row.get('last_activity')
        last_display = html_mod.escape(last[:19].replace('T', ' ') if last else '–')
        doc_href = html_mod.escape(f'/doc/draft/{submission_id}/read/')
        table_rows += f'''
            <tr>
                <td><a href="{doc_href}" class="text-decoration-none">{title}</a></td>
                <td>{ml}</td>
                <td>{wg}</td>
                <td><span class="badge bg-primary">{pending}</span></td>
                <td><span class="badge bg-success">{accepted}</span></td>
                <td><span class="badge bg-secondary">{declined}</span></td>
                <td>{total}</td>
                <td class="text-muted small">{last_display}</td>
            </tr>'''

    if not table_rows:
        table_rows = '''
            <tr>
                <td colspan="8" class="text-center text-muted py-4">
                    No patches yet. Activity will appear here once readers submit patches on read pages.
                </td>
            </tr>'''

    table_html = f'''
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead>
                    <tr>
                        <th>DP / Title</th>
                        <th>ML #</th>
                        <th>Workgroup</th>
                        <th>Patches</th>
                        <th>Merged</th>
                        <th>Declined</th>
                        <th>Total</th>
                        <th>Last activity</th>
                    </tr>
                </thead>
                <tbody>{table_rows}</tbody>
            </table>
        </div>'''

    header = gh_page_header(
        'Patches',
        'Patch activity by document – most active first',
        'fa-highlighter',
        breadcrumb_html=gh_breadcrumb([
            ('Admin Dashboard', '/admin/'),
            ('Patches', None),
        ]),
        actions_html=(
            '<a href="/admin/" class="btn btn-outline-secondary btn-sm">'
            '<i class="fas fa-arrow-left me-1"></i>Admin</a>'
        ),
    )

    content = f'''
    <div class="gh-page container mt-4 gh-admin-page">
        {header}
        {gh_living_module('By DP', table_html, 'fa-list', extra_class='mb-0')}
    </div>
    '''
    return render_page(
        'Patches – Admin',
        content,
        theme=current_theme,
        user_menu=user_menu,
    )
