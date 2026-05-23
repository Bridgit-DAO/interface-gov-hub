"""Votes API: create, list, get, ballot, close, candidates, cancel."""
import html as html_mod
import json
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, url_for

from extensions import db
from models import (
    Layer, User, Vote, Ballot, VoteCandidate, VoteEligibilitySnapshot,
    Role, LayerMember,
)
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin, close_vote, _election_candidates_ordered
from services.submissions import get_submission_by_ref
from services.events import emit_event
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module

bp = Blueprint('votes', __name__, url_prefix='/api')
bp_pages = Blueprint('votes_pages', __name__, url_prefix='')


def _resolve_vote(vote_id):
    """Resolve vote by id or public_id UUID."""
    if len(vote_id) == 36 and '-' in vote_id:
        return Vote.query.filter_by(public_id=vote_id).first_or_404()
    return Vote.query.get_or_404(vote_id)


@bp.route('/layers/<layer_id>/votes/', methods=['POST'])
@require_auth
def create_vote(layer_id):
    """Create a new vote for a project."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can create votes'}), 403

    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    submission_id = data.get('submission_id', '').strip()
    role_id = data.get('role_id', '').strip()
    vote_type = data.get('vote_type', 'approval')
    start_at_str = data.get('start_at', '').strip()
    end_at_str = data.get('end_at', '').strip()
    quorum_count = data.get('quorum_count')
    win_threshold = data.get('win_threshold', 0.5)
    seats = max(1, int(data.get('seats', 1)))

    if not title:
        return jsonify({'error': 'Vote title is required'}), 400
    if not start_at_str or not end_at_str:
        return jsonify({'error': 'Start and end times are required'}), 400
    if quorum_count is None or quorum_count < 1:
        return jsonify({'error': 'Quorum count must be at least 1'}), 400
    if not (0.0 <= win_threshold <= 1.0):
        return jsonify({'error': 'Win threshold must be between 0.0 and 1.0'}), 400

    submission = None
    artifact_id = None
    if vote_type == 'election':
        if not role_id:
            return jsonify({'error': 'Role is required for election votes'}), 400
        role = Role.query.get(role_id)
        if not role or role.layer_id != layer_id:
            return jsonify({'error': 'Role not found or not in this layer'}), 404
    else:
        if not submission_id:
            return jsonify({'error': 'Submission ID is required for approval votes'}), 400
        submission = get_submission_by_ref(submission_id)
        if not submission:
            return jsonify({'error': 'Submission not found'}), 404
        artifact_id = submission.artifact_id

    try:
        start_at = datetime.fromisoformat(start_at_str.replace('Z', '+00:00'))
        end_at = datetime.fromisoformat(end_at_str.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use ISO 8601 format.'}), 400

    start_at = start_at.replace(tzinfo=None)
    end_at = end_at.replace(tzinfo=None)
    now = datetime.utcnow()
    if start_at <= now:
        return jsonify({'error': 'Start time must be in the future'}), 400
    if end_at <= start_at:
        return jsonify({'error': 'End time must be after start time'}), 400

    vote = Vote(
        layer_id=layer_id,
        submission_id=submission_id if submission_id else None,
        artifact_id=artifact_id,
        created_by_id=current_user['id'],
        title=title,
        description=description or None,
        start_at=start_at,
        end_at=end_at,
        quorum_count=quorum_count,
        win_threshold=win_threshold,
        status='scheduled',
        vote_type=data.get('vote_type') or 'approval',
        role_id=data.get('role_id'),
        seats=max(1, int(data.get('seats', 1))),
    )
    db.session.add(vote)
    db.session.commit()

    return jsonify({
        'success': True,
        'vote': {
            'id': vote.id,
            'public_id': vote.public_id,
            'title': vote.title,
            'description': vote.description,
            'status': vote.status,
            'start_at': vote.start_at.isoformat(),
            'end_at': vote.end_at.isoformat(),
            'quorum_count': vote.quorum_count,
            'win_threshold': vote.win_threshold
        }
    }), 201


@bp.route('/layers/<layer_id>/votes/', methods=['GET'])
def list_votes(layer_id):
    """List votes for a project."""
    try:
        project = Layer.query.get_or_404(layer_id)
        status_filter = request.args.get('status')
        query = Vote.query.filter_by(layer_id=layer_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        votes = query.order_by(Vote.created_at.desc()).all()
        return jsonify({
            'votes': [{
                'id': v.id,
                'public_id': v.public_id,
                'title': v.title,
                'description': v.description,
                'status': v.status,
                'result': v.result,
                'start_at': v.start_at.isoformat() if v.start_at else None,
                'end_at': v.end_at.isoformat() if v.end_at else None,
                'created_at': v.created_at.isoformat() if v.created_at else None
            } for v in votes]
        })
    except Exception as e:
        current_app.logger.error(f"Error in list_votes for layer {layer_id}: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@bp.route('/votes/<vote_id>/', methods=['GET'])
def get_vote(vote_id):
    """Get vote details."""
    vote = _resolve_vote(vote_id)
    ballot_count = Ballot.query.filter_by(vote_id=vote.id).count()
    eligible_count = VoteEligibilitySnapshot.query.filter_by(vote_id=vote.id, is_eligible=True).count()
    result_summary = None
    if vote.result_summary:
        try:
            result_summary = json.loads(vote.result_summary)
        except Exception:
            pass

    candidates = []
    if getattr(vote, 'vote_type', 'approval') == 'election':
        for c in _election_candidates_ordered(vote):
            u = User.query.get(c.user_id)
            candidates.append({
                'id': c.id, 'user_id': c.user_id,
                'display_name': c.display_name or (u.displayName or u.username if u else str(c.user_id)),
            })

    return jsonify({
        'id': vote.id,
        'public_id': vote.public_id,
        'layer_id': vote.layer_id,
        'submission_id': vote.submission_id,
        'title': vote.title,
        'description': vote.description,
        'status': vote.status,
        'result': vote.result,
        'result_summary': result_summary,
        'vote_type': getattr(vote, 'vote_type', 'approval'),
        'role_id': getattr(vote, 'role_id', None),
        'seats': getattr(vote, 'seats', 1),
        'candidates': candidates,
        'start_at': vote.start_at.isoformat() if vote.start_at else None,
        'end_at': vote.end_at.isoformat() if vote.end_at else None,
        'quorum_count': vote.quorum_count,
        'win_threshold': vote.win_threshold,
        'ballot_count': ballot_count,
        'eligible_count': eligible_count,
        'created_at': vote.created_at.isoformat() if vote.created_at else None,
        'closed_at': vote.closed_at.isoformat() if vote.closed_at else None
    })


@bp.route('/votes/<vote_id>/ballot/', methods=['POST'])
@require_auth
def cast_ballot(vote_id):
    """Cast or update a ballot."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    vote = _resolve_vote(vote_id)
    if vote.status != 'active':
        return jsonify({'error': 'Vote is not active'}), 400

    eligibility = VoteEligibilitySnapshot.query.filter_by(
        vote_id=vote.id,
        person_id=current_user['id']
    ).first()
    if not eligibility or not eligibility.is_eligible:
        return jsonify({'error': 'You are not eligible to vote in this election'}), 403

    data = request.get_json()
    choice_raw = data.get('choice', '')
    choice = str(choice_raw).strip() if choice_raw is not None else ''

    vote_type = getattr(vote, 'vote_type', 'approval') or 'approval'
    if vote_type == 'election':
        valid_ids = [str(c.id) for c in vote.candidates.filter(VoteCandidate.status == 'approved').all()]
        if choice not in valid_ids:
            return jsonify({'error': 'Invalid candidate choice'}), 400
    else:
        choice = choice.lower()
        if choice not in ['yes', 'no', 'abstain']:
            return jsonify({'error': 'Choice must be yes, no, or abstain'}), 400

    existing_ballot = Ballot.query.filter_by(
        vote_id=vote.id,
        person_id=current_user['id']
    ).first()

    if existing_ballot:
        existing_ballot.choice = choice
        existing_ballot.cast_at = datetime.utcnow()
    else:
        ballot = Ballot(
            vote_id=vote.id,
            person_id=current_user['id'],
            choice=choice
        )
        db.session.add(ballot)
        emit_event('ballot_cast', actor_type='user', actor_id=current_user['id'],
                   subject_type='ballot', subject_id=ballot.id, layer_id=vote.layer_id,
                   payload={'vote_id': vote.id, 'choice': choice})

    db.session.commit()
    return jsonify({
        'success': True,
        'choice': choice,
        'cast_at': datetime.utcnow().isoformat()
    })


@bp.route('/votes/<vote_id>/close/', methods=['POST'])
@require_auth
def close_vote_route(vote_id):
    """Close an active vote (project admins only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    vote = _resolve_vote(vote_id)
    project = Layer.query.get_or_404(vote.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can close votes'}), 403

    if vote.status != 'active':
        return jsonify({'error': 'Only active votes can be closed'}), 400

    success, msg = close_vote(vote)
    if not success:
        return jsonify({'error': msg}), 400

    return jsonify({
        'success': True,
        'result': vote.result,
        'message': msg
    })


@bp.route('/votes/<vote_id>/candidates/', methods=['POST'])
@require_auth
def add_vote_candidate(vote_id):
    """Self-register or add a candidate to an election vote."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    vote = _resolve_vote(vote_id)
    vote_type = getattr(vote, 'vote_type', None) or 'approval'
    if vote_type != 'election':
        return jsonify({'error': 'Only election votes have candidates'}), 400

    if vote.status not in ['scheduled', 'active']:
        return jsonify({'error': 'Vote is not open for candidates'}), 400

    data = request.get_json() or {}
    target_user_id = data.get('user_id')

    if target_user_id is None:
        target_user_id = current_user['id']
        is_admin_add = False
    else:
        project = Layer.query.get_or_404(vote.layer_id)
        if not is_layer_admin(project, current_user):
            return jsonify({'error': 'Only layer admins can add other users as candidates'}), 403
        target_user_id = str(target_user_id)
        is_admin_add = True

    member = LayerMember.query.filter_by(
        layer_id=vote.layer_id,
        user_id=target_user_id,
        status='active'
    ).first()
    if not member:
        return jsonify({'error': 'User must be an active layer member to be a candidate'}), 403

    existing = VoteCandidate.query.filter_by(
        vote_id=vote.id,
        user_id=target_user_id
    ).first()
    if existing:
        return jsonify({'error': 'User is already a candidate'}), 400

    max_order = db.session.query(db.func.max(VoteCandidate.display_order)).filter_by(vote_id=vote.id).scalar() or 0
    cand = VoteCandidate(
        vote_id=vote.id,
        user_id=target_user_id,
        display_order=max_order + 1,
        status='approved'
    )
    db.session.add(cand)
    db.session.commit()

    emit_event('vote_candidate_added', actor_type='user', actor_id=current_user['id'],
               subject_type='vote_candidate', subject_id=cand.id, layer_id=vote.layer_id,
               payload={'vote_id': vote.id, 'user_id': target_user_id, 'self_register': not is_admin_add})

    u = User.query.get(target_user_id)
    name = (u.displayName or u.username or u.oauthName or f'User {target_user_id}') if u else f'User {target_user_id}'
    return jsonify({
        'success': True,
        'candidate': {'id': cand.id, 'user_id': target_user_id, 'name': name}
    })


@bp.route('/votes/<vote_id>/candidates/<candidate_id>/withdraw/', methods=['POST'])
@require_auth
def withdraw_vote_candidate(vote_id, candidate_id):
    """Withdraw a candidate from an election vote."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    vote = _resolve_vote(vote_id)
    cand = VoteCandidate.query.filter_by(vote_id=vote.id, id=candidate_id).first_or_404()
    if cand.status != 'approved':
        return jsonify({'error': 'Candidate is already withdrawn'}), 400

    vote_type = getattr(vote, 'vote_type', None) or 'approval'
    if vote_type != 'election':
        return jsonify({'error': 'Only election votes have candidates'}), 400

    if vote.status not in ['scheduled', 'active']:
        return jsonify({'error': 'Cannot withdraw after vote has closed'}), 400

    project = Layer.query.get_or_404(vote.layer_id)
    is_self = str(cand.user_id) == str(current_user['id'])
    is_admin = is_layer_admin(project, current_user)
    if not is_self and not is_admin:
        return jsonify({'error': 'Only the candidate or a layer admin can withdraw'}), 403

    cand.status = 'withdrawn'
    db.session.commit()

    emit_event('vote_candidate_withdrawn', actor_type='user', actor_id=current_user['id'],
               subject_type='vote_candidate', subject_id=cand.id, layer_id=vote.layer_id,
               payload={'vote_id': vote.id, 'user_id': cand.user_id})

    return jsonify({'success': True, 'message': 'Candidate withdrawn'})


@bp.route('/votes/<vote_id>/cancel/', methods=['POST'])
@require_auth
def cancel_vote(vote_id):
    """Cancel a vote."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    vote = _resolve_vote(vote_id)
    project = Layer.query.get_or_404(vote.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can cancel votes'}), 403

    if vote.status not in ['scheduled', 'active']:
        return jsonify({'error': 'Only scheduled or active votes can be canceled'}), 400

    vote.status = 'canceled'
    vote.result = 'canceled'
    vote.closed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'vote': {
            'id': vote.id,
            'public_id': vote.public_id,
            'status': vote.status,
            'result': vote.result
        }
    })


def _get_page_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    return _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER


@bp_pages.route('/votes/<vote_public_id>/')
def vote_detail(vote_public_id):
    """Vote detail page."""
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER = _get_page_imports()

    vote = Vote.query.filter_by(public_id=vote_public_id).first_or_404()
    project = Layer.query.get_or_404(vote.layer_id)
    submission = get_submission_by_ref(vote.submission_id) if vote.submission_id else None
    role = Role.query.get(vote.role_id) if vote.role_id else None
    is_election = getattr(vote, 'vote_type', 'approval') == 'election'

    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'dark'
    user_menu = generate_user_menu()

    # Check if current user is eligible
    is_eligible = False
    has_voted = False
    user_ballot = None

    if current_user:
        eligibility = VoteEligibilitySnapshot.query.filter_by(
            vote_id=vote.id,
            person_id=current_user['id']
        ).first()
        is_eligible = eligibility and eligibility.is_eligible

        user_ballot = Ballot.query.filter_by(
            vote_id=vote.id,
            person_id=current_user['id']
        ).first()
        has_voted = user_ballot is not None

    # Get ballot counts
    ballot_count = Ballot.query.filter_by(vote_id=vote.id).count()
    eligible_count = VoteEligibilitySnapshot.query.filter_by(vote_id=vote.id, is_eligible=True).count()

    # Parse result summary
    result_summary = None
    if vote.result_summary:
        try:
            result_summary = json.loads(vote.result_summary)
        except Exception:
            pass

    # Status badge colors
    status_colors = {
        'scheduled': 'secondary',
        'active': 'primary',
        'closed': 'success',
        'canceled': 'danger'
    }
    status_color = status_colors.get(vote.status, 'secondary')

    # Result badge colors
    result_colors = {
        'passed': 'success',
        'failed': 'danger',
        'no_quorum': 'warning',
        'canceled': 'secondary'
    }
    result_color = result_colors.get(vote.result, 'secondary') if vote.result else 'secondary'

    # Build result HTML if available
    result_html = ''
    if vote.result:
        result_text = vote.result.upper() if vote.result else 'PENDING'
        result_html = f'<p><strong>Result:</strong> <span class="badge bg-{result_color}">{result_text}</span></p>'

    # Build ballot form if eligible and active
    ballot_form_html = ''
    candidates = []
    if is_election:
        for c in _election_candidates_ordered(vote):
            u = User.query.get(c.user_id)
            name = (u.displayName or u.username or u.oauthName or f'User {c.user_id}') if u else f'Candidate {c.id}'
            candidates.append({'id': c.id, 'name': name})
    if vote.status == 'active' and is_eligible:
        voted_msg = ''
        if has_voted:
            choice_display = user_ballot.choice
            if is_election and candidates:
                for c in candidates:
                    if str(c['id']) == str(user_ballot.choice):
                        choice_display = c['name']
                        break
            voted_msg = f'<p class="text-success">✓ You have already voted: <strong>{choice_display}</strong></p>'
        if is_election and candidates:
            seats = getattr(vote, 'seats', 1)
            seat_note = f' (top {seats} will win)' if seats > 1 else ''
            candidate_radios = ''.join(f'<div class="form-check"><input class="form-check-input" type="radio" name="vote-candidate" id="cand-{c["id"]}" value="{c["id"]}"><label class="form-check-label" for="cand-{c["id"]}">{html_mod.escape(c["name"])}</label></div>' for c in candidates)
            ballot_form_html = f'''<div class="card mb-3">
                <div class="card-header"><h5>Cast Your Ballot</h5></div>
                <div class="card-body">
                    <p>You are eligible to vote in this election. Choose one candidate{seat_note}:</p>
                    {voted_msg}
                    <div class="mb-2">{candidate_radios}</div>
                    <button class="btn btn-primary btn-sm" onclick="castBallotCandidate()">Submit Vote</button>
                    <div id="ballot-status" class="mt-2"></div>
                </div>
            </div>'''
        else:
            ballot_form_html = f'''<div class="card mb-3">
                <div class="card-header"><h5>Cast Your Ballot</h5></div>
                <div class="card-body">
                    <p>You are eligible to vote in this election.</p>
                    {voted_msg}
                    <div class="btn-group" role="group">
                        <button class="btn btn-success" onclick="castBallot('yes')">Vote YES</button>
                        <button class="btn btn-danger" onclick="castBallot('no')">Vote NO</button>
                        <button class="btn btn-secondary" onclick="castBallot('abstain')">Abstain</button>
                    </div>
                    <div id="ballot-status" class="mt-2"></div>
                </div>
            </div>'''

    # Build results HTML
    results_html = ''
    if vote.status == 'closed' or result_summary:
        if result_summary:
            if is_election and 'by_candidate' in result_summary:
                rows = ''.join(f'<p><strong>{html_mod.escape(str(c.get("name", c.get("candidate_id", "?"))))}:</strong> {c.get("votes", 0)} votes</p>' for c in result_summary.get('by_candidate', []))
                seats = result_summary.get('seats', 1)
                winners_label = f'Winners (top {seats})' if seats > 1 else 'Winner'
                results_content = f'''{rows}
                    <p><strong>Total Votes Cast:</strong> {result_summary.get('votes_cast', 0)} / {result_summary.get('eligible', 0)} eligible</p>
                    <p><strong>{winners_label}:</strong> {', '.join(html_mod.escape(str(w)) for w in result_summary.get('winner_names', result_summary.get('winners', [])))}</p>'''
            else:
                quorum_text = 'Yes' if result_summary.get('quorum_met') else 'No'
                results_content = f'''<p><strong>Yes:</strong> {result_summary.get('yes', 0)}</p>
                    <p><strong>No:</strong> {result_summary.get('no', 0)}</p>
                    <p><strong>Abstain:</strong> {result_summary.get('abstain', 0)}</p>
                    <p><strong>Total Votes Cast:</strong> {result_summary.get('votes_cast', 0)} / {result_summary.get('eligible', 0)} eligible</p>
                    <p><strong>Quorum Met:</strong> {quorum_text}</p>
                    <p><strong>Yes Ratio:</strong> {int((result_summary.get('yes_ratio') or 0) * 100)}%</p>'''
        else:
            results_content = f'<p>Votes cast: {ballot_count} / {eligible_count} eligible</p>'
        results_html = f'''<div class="card mb-3">
            <div class="card-header"><h5>Results</h5></div>
            <div class="card-body">{results_content}</div>
        </div>'''

    # Build user status HTML
    user_status_html = ''
    if current_user:
        status_text = '✓ Eligible' if is_eligible else '✗ Not Eligible'
        user_status_html = f'<p><strong>Your Status:</strong> {status_text}</p>'

    # Run for this role: is_election, scheduled/active, user is layer member, not already candidate
    is_layer_member = bool(current_user and LayerMember.query.filter_by(
        layer_id=vote.layer_id, user_id=current_user['id'], status='active'
    ).first())
    user_candidate = VoteCandidate.query.filter_by(
        vote_id=vote.id, user_id=current_user['id'], status='approved'
    ).first() if current_user else None
    is_candidate = bool(user_candidate)
    show_run_for_role = is_election and vote.status in ('scheduled', 'active') and current_user and is_layer_member and not is_candidate
    run_for_role_html = ''
    if show_run_for_role:
        run_for_role_html = f'''<div class="card mb-3">
            <div class="card-header"><h5>Run for this Role</h5></div>
            <div class="card-body">
                <p>You are a layer member. Declare your candidacy for this election.</p>
                <button class="btn btn-primary" onclick="runForRole()"><i class="fas fa-user-plus me-2"></i>Run for this Role</button>
                <div id="run-for-role-status" class="mt-2"></div>
            </div>
        </div>'''
    # Withdraw: user is approved candidate, vote is scheduled/active
    withdraw_for_role_html = ''
    if is_candidate and user_candidate and vote.status in ('scheduled', 'active'):
        withdraw_for_role_html = f'''<div class="card mb-3">
            <div class="card-header"><h5>Your Candidacy</h5></div>
            <div class="card-body">
                <p>You are running for this role. You may withdraw before the vote closes.</p>
                <button class="btn btn-outline-warning" onclick="withdrawCandidate('{user_candidate.id}')"><i class="fas fa-user-minus me-2"></i>Withdraw</button>
                <div id="withdraw-status" class="mt-2"></div>
            </div>
        </div>'''

    layer_url = url_for('layer_detail', layer_slug=project.slug)
    layer_roles_url = url_for('layer_detail', layer_slug=project.slug) + '#roles'
    draft_url = url_for('documents.draft_detail', draft_name=submission.draft_name) if submission else ''

    if is_election and role:
        role_or_draft_line = f'<p><strong>Role:</strong> <a href="{layer_roles_url}">{role.title_guild}</a></p>'
    elif submission:
        role_or_draft_line = f'<p><strong>Draft:</strong> <a href="{draft_url}">{submission.title}</a></p>'
    else:
        role_or_draft_line = ''

    seats_line = (
        f'<p><strong>Seats:</strong> Elect up to {vote.seats} winner(s)</p>'
        if is_election and getattr(vote, 'seats', 1) > 1 else ''
    )
    vote_details_body = (
        f'<p><strong>Status:</strong> <span class="badge bg-{status_color}">{vote.status.upper()}</span></p>'
        f'{result_html}'
        f'<p><strong>Layer:</strong> <a href="{layer_url}">{project.name}</a></p>'
        f'{role_or_draft_line}'
        f'<p><strong>Start:</strong> {vote.start_at.strftime("%Y-%m-%d %H:%M UTC")}</p>'
        f'<p><strong>End:</strong> {vote.end_at.strftime("%Y-%m-%d %H:%M UTC")}</p>'
        f'<p><strong>Quorum Required:</strong> {vote.quorum_count} votes</p>'
        f'<p><strong>Win Threshold:</strong> {int(vote.win_threshold * 100)}%</p>'
        f'{seats_line}'
    )
    vote_details_module = gh_living_module('Vote Details', vote_details_body, 'fa-info-circle')
    participation_module = gh_living_module(
        'Participation',
        f'<p><strong>Eligible Voters:</strong> {eligible_count}</p>'
        f'<p><strong>Ballots Cast:</strong> {ballot_count}</p>'
        f'{user_status_html}',
        'fa-users',
    )

    content = f'''
    <div class="gh-page container mt-4">
        {gh_page_header(html_mod.escape(vote.title), vote.description or '', 'fa-vote-yea', breadcrumb_html=gh_breadcrumb([('Home', '/'), (project.name, layer_url), (vote.title, None)]))}
        <div class="gh-detail-layout">
        <div class="row">
            <div class="col-md-8">
                {vote_details_module}

                {run_for_role_html}
                {withdraw_for_role_html}
                {ballot_form_html}
                {results_html}
            </div>

            <div class="col-md-4">
                {participation_module}
            </div>
        </div>
        </div>
    </div>

    <script>
    const votePublicId = '{vote.public_id}';
    function castBallot(choice) {{
        fetch('/api/votes/{vote.public_id}/ballot/', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{choice: choice}})
        }})
        .then(res => res.json())
        .then(data => {{
            if (data.success) {{
                document.getElementById('ballot-status').innerHTML = '<div class="alert alert-success">Ballot cast successfully: ' + choice.toUpperCase() + '</div>';
                setTimeout(() => location.reload(), 1500);
            }} else {{
                document.getElementById('ballot-status').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            }}
        }})
        .catch(err => {{
            document.getElementById('ballot-status').innerHTML = '<div class="alert alert-danger">Error casting ballot</div>';
        }});
    }}
    function castBallotCandidate() {{
        const sel = document.querySelector('input[name="vote-candidate"]:checked');
        if (!sel) {{
            document.getElementById('ballot-status').innerHTML = '<div class="alert alert-warning">Please select a candidate</div>';
            return;
        }}
        castBallot(sel.value);
    }}
    async function runForRole() {{
        const statusEl = document.getElementById('run-for-role-status');
        statusEl.innerHTML = '<span class="text-muted">Registering...</span>';
        try {{
            const res = await fetch('/api/votes/' + votePublicId + '/candidates/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok && data.success) {{
                statusEl.innerHTML = '<div class="alert alert-success">You are now a candidate. Refresh to see the ballot.</div>';
                setTimeout(() => location.reload(), 1500);
            }} else {{
                statusEl.innerHTML = '<div class="alert alert-danger">' + (data.error || 'Failed to register') + '</div>';
            }}
        }} catch (e) {{
            statusEl.innerHTML = '<div class="alert alert-danger">Error: ' + e.message + '</div>';
        }}
    }}
    async function withdrawCandidate(candidateId) {{
        const statusEl = document.getElementById('withdraw-status');
        if (statusEl) statusEl.innerHTML = '<span class="text-muted">Withdrawing...</span>';
        try {{
            const res = await fetch('/api/votes/' + votePublicId + '/candidates/' + candidateId + '/withdraw/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok && data.success) {{
                if (statusEl) statusEl.innerHTML = '<div class="alert alert-success">You have withdrawn. Refresh to update.</div>';
                setTimeout(() => location.reload(), 1500);
            }} else {{
                if (statusEl) statusEl.innerHTML = '<div class="alert alert-danger">' + (data.error || 'Failed to withdraw') + '</div>';
            }}
        }} catch (e) {{
            if (statusEl) statusEl.innerHTML = '<div class="alert alert-danger">Error: ' + e.message + '</div>';
        }}
    }}
    </script>
    '''

    return _format_base_template(title=f"Vote: {vote.title}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)
