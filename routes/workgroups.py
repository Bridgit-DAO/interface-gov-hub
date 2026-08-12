"""Workgroups API: layer workgroups, workgroup CRUD, chairs, members."""
import re
from datetime import datetime, date
from urllib.parse import urlparse
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, redirect, request
from sqlalchemy import text, or_, func

from extensions import db
from models import Layer, Workgroup, StatusChange, WorkingGroupChair, User
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.utils import create_slug, coerce_storage_bool
from services.workgroup_links import (
    assign_dp_draft_to_workgroup,
    enrich_workgroup_dict,
    list_assigned_documents_for_workgroup,
    list_draft_documents_for_picker,
    list_draft_documents_for_workgroup_picker,
    normalize_document_draft_ref,
    query_workgroups_for_layer,
    resolve_document_draft,
    search_draft_documents,
    workgroup_display_sort_key,
    _canonical_parent_for_picker,
)
from services.workgroup_authority import can_invite_workgroup_member, can_manage_workgroup, user_is_dp_coordinator
from services.workgroup_membership import (
    join_or_request_workgroup_membership,
    leave_workgroup_membership,
)
from services.workgroup_links import is_dp_workgroup
from services.dp_welcome import (
    deliver_dp_welcome,
    list_dp_welcome_notifications,
    require_nominee_email,
)
from services.workgroup_nomination_flow import (
    RESPONSE_FORBIDDEN_ERROR,
    caller_matches_nomination,
    record_nominee_response,
    resolve_nominee_identity,
)
from services.api_auth import get_api_user, require_api_auth
from services.workgroup_positions import (
    WORKGROUP_POSITIONS,
    ACTIVE_NOMINATION_STATUSES,
    NOMINATION_STATUS_PENDING_NOMINEE,
    NOMINATION_STATUS_APPROVED,
    NOMINATION_STATUS_REJECTED,
    detect_self_nomination,
    initial_nomination_status,
    positions_for_api,
    position_label,
    status_label,
)
from services.workgroup_nomination_mail import (
    send_nomination_submitted,
    send_nominee_accepted,
    send_nominee_declined,
)

bp = Blueprint('workgroups', __name__, url_prefix='/api')


def _normalize_email(email):
    return (email or '').strip().lower()


def _is_valid_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''))


def _normalize_profile_url(url):
    raw = (url or '').strip()
    if not raw:
        return ''
    if '://' not in raw:
        raw = 'https://' + raw
    return raw


def _is_valid_profile_url(url):
    normalized = _normalize_profile_url(url)
    if not normalized:
        return False
    try:
        parsed = urlparse(normalized)
        return bool(parsed.netloc and '.' in parsed.netloc)
    except Exception:
        return False


@bp.route('/layers/<layer_id>/workgroups/', methods=['GET'])
def list_workgroups(layer_id):
    """List workgroups for a layer (primary home + secondary links)."""
    Layer.query.get_or_404(layer_id)
    status = request.args.get('status') or 'active'
    approval_status = request.args.get('approval_status')

    workgroups = query_workgroups_for_layer(layer_id, status=status if status else None)
    if approval_status:
        workgroups = [wg for wg in workgroups if wg.approval_status == approval_status]

    return jsonify({
        'workgroups': [enrich_workgroup_dict(wg.to_dict(), wg) for wg in workgroups],
        'count': len(workgroups),
    })


@bp.route('/layers/<layer_id>/workgroups/', methods=['POST'])
@require_auth
def create_workgroup(layer_id):
    """Create a new workgroup."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    Layer.query.get_or_404(layer_id)

    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    charter = (data.get('charter') or '').strip() or None
    goals = (data.get('goals') or '').strip() or None

    if not name:
        return jsonify({'error': 'Workgroup name is required'}), 400

    slug = create_slug(name)
    counter = 1
    original_slug = slug
    while Workgroup.query.filter_by(layer_id=layer_id, slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    acronym = create_slug(name)
    counter = 1
    original_acronym = acronym
    while Workgroup.query.filter_by(acronym=acronym).first():
        acronym = f"{original_acronym}-{counter}"
        counter += 1

    workgroup = Workgroup(
        acronym=acronym,
        name=name,
        slug=slug,
        layer_id=layer_id,
        coordinator_id=current_user['id'],
        description=description,
        charter=charter,
        goals=goals,
        status='active',
        approval_status='pending'
    )
    db.session.add(workgroup)
    assign_dp_draft_to_workgroup(workgroup)
    db.session.commit()

    return jsonify({'success': True, 'workgroup': workgroup.to_dict()}), 201


@bp.route('/workgroups/<workgroup_id>/', methods=['GET'])
def get_workgroup(workgroup_id):
    """Get workgroup details."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    d = enrich_workgroup_dict(workgroup.to_dict(), workgroup)
    current_user = get_api_user()
    d['can_edit'] = can_manage_workgroup(workgroup, current_user)
    d['can_invite_members'] = can_invite_workgroup_member(workgroup, current_user)
    return jsonify(d)


@bp.route('/workgroups/by-slug/<workgroup_slug>/', methods=['GET'])
def get_workgroup_by_slug(workgroup_slug):
    """Direct workgroup lookup by slug – used by the /workgroups/<slug>/ page bootstrap."""
    # Historical slug renames: redirect API consumers to the canonical slug.
    _WORKGROUP_SLUG_REDIRECTS = {
        'dp22---epistemic-continuity-digital-artifacts':
            'dp22-civic-memory-epistemic-continuity',
    }
    if workgroup_slug in _WORKGROUP_SLUG_REDIRECTS:
        return redirect(
            f"/api/workgroups/by-slug/{_WORKGROUP_SLUG_REDIRECTS[workgroup_slug]}/",
            code=301,
        )

    wg = (
        db.session.query(Workgroup)
        .join(Layer, Layer.id == Workgroup.layer_id)
        .filter(Workgroup.slug == workgroup_slug)
        .first()
    )
    if not wg:
        return jsonify({'error': 'not found'}), 404
    current_user = get_api_user()
    d = enrich_workgroup_dict(wg.to_dict(), wg)
    d['layer_name'] = wg.layer.name if wg.layer else None
    d['can_edit'] = can_manage_workgroup(wg, current_user)
    d['can_invite_members'] = can_invite_workgroup_member(wg, current_user)
    return jsonify(d)


@bp.route('/workgroups/<workgroup_id>/', methods=['PATCH'])
@require_auth
def update_workgroup(workgroup_id):
    """Update workgroup details (coordinator, project admin, or site admin)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)
    if not can_manage_workgroup(workgroup, current_user):
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()

    if 'name' in data and data['name']:
        workgroup.name = data['name'].strip()
    if 'description' in data:
        workgroup.description = data['description']
    if 'charter' in data:
        val = data['charter']
        workgroup.charter = val.strip() if val and str(val).strip() else None
    if 'goals' in data:
        val = data['goals']
        workgroup.goals = val.strip() if val and str(val).strip() else None
    if 'image_url' in data:
        workgroup.image_url = data['image_url'].strip() if data['image_url'] else None
    if 'external_url' in data:
        val = data['external_url']
        workgroup.external_url = val.strip() if val and str(val).strip() else None
    if 'document_draft_name' in data:
        val = data['document_draft_name']
        if val is None or not str(val).strip():
            workgroup.document_draft_name = None
        else:
            normalized = normalize_document_draft_ref(val)
            if not normalized:
                return jsonify({'error': 'Document not found. Use a draft ID, ML number, or draft name.'}), 400
            submission = resolve_document_draft(normalized)
            if submission:
                workgroup.document_draft_name = _canonical_parent_for_picker(submission).id
            else:
                workgroup.document_draft_name = normalized
    if 'status' in data and data['status'] in ['active', 'inactive', 'completed', 'archived']:
        old_status = workgroup.status
        workgroup.status = data['status']
        if old_status != workgroup.status:
            status_change = StatusChange(
                entity_type='workgroup',
                entity_id=workgroup_id,
                field_name='status',
                from_value=old_status,
                to_value=workgroup.status,
                changed_by_id=current_user['id']
            )
            db.session.add(status_change)

    if 'badge_enabled' in data:
        workgroup.badge_enabled = bool(data['badge_enabled'])

    for field in ['badge_submission_days', 'badge_voting_days', 'badge_delay_days',
                  'badge_cycle_spacing_days']:
        if field in data:
            setattr(workgroup, field, int(data[field]) if data[field] is not None else None)

    for field in ['badge_earliest_start', 'badge_end_date']:
        if field in data:
            val = data[field]
            if val:
                try:
                    setattr(workgroup, field, date.fromisoformat(val))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(workgroup, field, None)

    for field in ['badge_end_at_next_closing', 'badge_voting_regular',
                  'badge_voting_time_weighted', 'badge_voting_quadratic']:
        if field in data:
            setattr(workgroup, field, bool(data[field]))

    if 'badge_skin_id' in data:
        workgroup.badge_skin_id = data['badge_skin_id'] or None

    workgroup.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'workgroup': enrich_workgroup_dict(workgroup.to_dict(), workgroup)})


@bp.route('/documents/', methods=['GET'])
def list_documents():
    """List drafts for workgroup document dropdown."""
    workgroup_id = (request.args.get('workgroup_id') or '').strip() or None
    layer_id = request.args.get('layer_id') or None
    if workgroup_id:
        documents = list_draft_documents_for_workgroup_picker(workgroup_id)
    else:
        documents = list_draft_documents_for_picker(layer_id)
    return jsonify({'documents': documents, 'count': len(documents)})


@bp.route('/documents/search/', methods=['GET'])
def search_documents():
    """Search drafts to link from workgroup edit."""
    q = request.args.get('q', '')
    return jsonify({'documents': search_draft_documents(q)})


@bp.route('/workgroups/<workgroup_id>/assigned-documents/', methods=['GET'])
def list_workgroup_assigned_documents(workgroup_id):
    """Drafts assigned to this workgroup via submission.group (not the primary linked doc)."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    documents = list_assigned_documents_for_workgroup(workgroup)
    return jsonify({'documents': documents, 'count': len(documents)})


@bp.route('/workgroups/<workgroup_id>/approve/', methods=['POST'])
@require_auth
def approve_workgroup(workgroup_id):
    """Approve or reject a workgroup (project admin/initiator or site admin)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)

    is_site_admin = current_user.get('role') in ['admin', 'editor']
    is_project_initiator = workgroup.layer and is_layer_admin(workgroup.layer, current_user)

    if not (is_site_admin or is_project_initiator):
        return jsonify({'error': 'Only project admin or site admin can approve workgroups'}), 403

    data = request.get_json()
    action = data.get('action')

    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400

    old_status = workgroup.approval_status
    workgroup.approval_status = 'approved' if action == 'approve' else 'rejected'
    workgroup.approved_by_id = current_user['id']
    workgroup.approved_at = datetime.utcnow()

    status_change = StatusChange(
        entity_type='workgroup',
        entity_id=workgroup_id,
        field_name='approval_status',
        from_value=old_status,
        to_value=workgroup.approval_status,
        note=data.get('note'),
        changed_by_id=current_user['id']
    )
    db.session.add(status_change)
    db.session.commit()

    return jsonify({'success': True, 'workgroup': workgroup.to_dict()})


@bp.route('/workgroups/positions/', methods=['GET'])
def list_workgroup_positions():
    """List nominatable workgroup position types."""
    return jsonify({'positions': positions_for_api()})


@bp.route('/workgroups/<workgroup_id>/chairs/', methods=['GET'])
def list_workgroup_chairs(workgroup_id):
    """List position nominations for a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    chairs_query = text("""
        SELECT id, group_acronym, chair_name, approved, set_at, user_id,
               position_key, status
        FROM working_group_chair
        WHERE group_acronym = :acronym
        ORDER BY set_at DESC
    """)
    result = db.session.execute(chairs_query, {'acronym': workgroup.acronym})
    chairs = []
    for row in result:
        status = row[7] or (NOMINATION_STATUS_APPROVED if coerce_storage_bool(row[3]) else NOMINATION_STATUS_PENDING_NOMINEE)
        chairs.append({
            'id': row[0],
            'group_acronym': row[1],
            'chair_name': row[2],
            'approved': coerce_storage_bool(row[3]),
            'set_at': row[4],
            'user_id': row[5],
            'position_key': row[6] or 'chair',
            'position_label': position_label(row[6] or 'chair'),
            'status': status,
            'status_label': status_label(status),
        })

    return jsonify({'chairs': chairs, 'nominations': chairs, 'count': len(chairs)})


@bp.route('/workgroups/<workgroup_id>/members/', methods=['GET'])
def list_workgroup_members(workgroup_id):
    """List members for a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    members_query = text("""
        SELECT id, group_acronym, user_name, joined_at, user_id
        FROM working_group_member
        WHERE group_acronym = :acronym
        ORDER BY joined_at DESC
    """)
    result = db.session.execute(members_query, {'acronym': workgroup.acronym})
    members = []
    for row in result:
        members.append({
            'id': row[0],
            'group_acronym': row[1],
            'user_name': row[2],
            'joined_at': row[3],
            'user_id': row[4]
        })

    return jsonify({'members': members, 'count': len(members)})


@bp.route('/workgroups/<workgroup_id>/messages/', methods=['GET'])
def list_workgroup_messages_api(workgroup_id):
    """List workgroup chat messages (teaser for non-members, full for members)."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    current_user = get_api_user()
    full = request.args.get('full', '').lower() in ('1', 'true', 'yes')
    payload = __import__('services.workgroup_chat', fromlist=['list_workgroup_messages']).list_workgroup_messages(
        workgroup,
        viewer=current_user,
        full=full,
    )
    return jsonify(payload)


@bp.route('/workgroups/<workgroup_id>/messages/', methods=['POST'])
@require_api_auth
def create_workgroup_message_api(workgroup_id):
    """Post a workgroup chat message (members only)."""
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    data = request.get_json(silent=True) or {}
    body = data.get('body') or data.get('message') or ''
    from services.workgroup_chat import create_workgroup_message
    payload, status = create_workgroup_message(workgroup, current_user, body)
    return jsonify(payload), status


@bp.route('/workgroups/<workgroup_id>/invite-ai/research/', methods=['POST'])
@require_api_auth
def workgroup_invite_ai_research(workgroup_id):
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    data = request.get_json(silent=True) or {}
    from services.workgroup_invite_ai import research_external_contact
    payload, status = research_external_contact(
        workgroup=workgroup,
        inviter=current_user,
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        linkedin_url=(data.get('linkedin_url') or data.get('linkedin') or '').strip(),
        previous_interaction=(data.get('previous_interaction') or '').strip(),
        extra_links=data.get('extra_links') or [],
        selected_candidate_index=data.get('selected_candidate_index'),
    )
    return jsonify(payload), status


@bp.route('/workgroups/<workgroup_id>/invite-ai/draft/', methods=['POST'])
@require_api_auth
def workgroup_invite_ai_draft(workgroup_id):
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    data = request.get_json(silent=True) or {}
    from services.workgroup_invite_ai import draft_invitation_email
    payload, status = draft_invitation_email(
        workgroup=workgroup,
        inviter=current_user,
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        tone=(data.get('tone') or 'warm').strip(),
        length=(data.get('length') or 'medium').strip(),
        previous_interaction=(data.get('previous_interaction') or '').strip(),
        extra_guidance=(data.get('extra_guidance') or '').strip(),
        resolved_person=data.get('resolved_person'),
        additional_workgroup_ids=data.get('additional_workgroup_ids') or [],
        prior_invitations=data.get('prior_invitations'),
        invite_content=data.get('invite_content'),
        regenerate=bool(data.get('regenerate')),
        previous_draft=(data.get('previous_draft') or '').strip(),
    )
    return jsonify(payload), status


@bp.route('/workgroups/<workgroup_id>/invite-ai/send/', methods=['POST'])
@require_api_auth
def workgroup_invite_ai_send(workgroup_id):
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    data = request.get_json(silent=True) or {}
    from services.workgroup_invite_ai import send_ai_workgroup_invitations
    payload, status = send_ai_workgroup_invitations(
        workgroup=workgroup,
        inviter_id=current_user['id'],
        name=(data.get('name') or '').strip(),
        email=(data.get('email') or '').strip(),
        body=(data.get('body') or data.get('draft') or '').strip(),
        additional_workgroup_ids=data.get('additional_workgroup_ids') or [],
        send_mode=(data.get('send_mode') or 'platform').strip(),
    )
    return jsonify(payload), status


@bp.route('/workgroups/<workgroup_id>/join/', methods=['POST'])
@require_api_auth
def join_workgroup(workgroup_id):
    """Join a workgroup as a member (session cookie or Bearer idToken)."""
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)
    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if workgroup.approval_status != 'approved':
        return jsonify({'error': 'Workgroup must be approved before joining'}), 400

    result = join_or_request_workgroup_membership(
        acronym=workgroup.acronym,
        user=user,
    )
    if result.get('duplicate'):
        db.session.rollback()
        return jsonify({'error': 'You are already a member of this workgroup'}), 400
    if result.get('status') == 'already_pending':
        return jsonify({'error': 'Membership request already pending'}), 400

    # Membership and the welcome notification commit together, so a failure
    # never leaves a member without their welcome (or the reverse).
    welcome_url = None
    if result.get('joined') and is_dp_workgroup(workgroup):
        welcome_url = deliver_dp_welcome(
            user_id=user.id,
            workgroup=workgroup,
            variant='member',
        )
    db.session.commit()

    if result.get('pending_approval'):
        return jsonify({
            'success': True,
            'pending_approval': True,
            'message': 'Membership requested; pending approval',
        })
    payload = {'success': True, 'message': 'Successfully joined workgroup'}
    if welcome_url:
        payload['welcome_url'] = welcome_url
    return jsonify(payload)


@bp.route('/workgroups/<workgroup_id>/leave/', methods=['POST'])
@require_api_auth
def leave_workgroup(workgroup_id):
    """Leave a workgroup (session cookie or Bearer idToken)."""
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)
    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    result = leave_workgroup_membership(workgroup=workgroup, user=user)
    if not result.get('ok'):
        return jsonify({'error': result.get('error') or 'Leave failed'}), result.get(
            'status_code', 400
        )

    db.session.commit()

    if result.get('left'):
        message = 'Successfully left workgroup'
    else:
        message = 'Membership request cancelled'
    return jsonify({
        'success': True,
        'message': message,
        'left': bool(result.get('left')),
        'cancelled_request': bool(result.get('cancelled_request')),
    })


@bp.route('/me/dp-welcome/', methods=['GET'])
@require_api_auth
def api_me_dp_welcome():
    """DP welcome links for the signed-in user (Gov Hub session or Bearer idToken).

    Always JSON so cross-origin callers can distinguish outcomes without
    depending on proxy behaviour: 401 when the session cookie or Bearer token is
    missing/invalid, 200 with an empty list when the user simply has no welcome.
    """
    current_user = get_api_user()
    if not current_user:
        return jsonify({
            'error': 'Authentication required',
            'code': 'authentication_required',
        }), 401
    welcomes = list_dp_welcome_notifications(current_user['id'])
    return jsonify({
        'welcomes': welcomes,
        'count': len(welcomes),
        'user_id': current_user['id'],
        'is_coordinator': user_is_dp_coordinator(current_user['id']),
    })


@bp.route('/workgroups/<workgroup_id>/nominate-chair/', methods=['POST'])
@bp.route('/workgroups/<workgroup_id>/nominate/', methods=['POST'])
@require_api_auth
def nominate_position(workgroup_id):
    """Nominate a person (self or another) for a workgroup position (chair, co-lead, editor, etc.).

    Accepts Flask session or Authorization: Bearer idToken (challenge-site proxy).
    """
    current_user = get_api_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    position_key = (data.get('position_key') or data.get('position') or 'chair').strip().lower()
    if position_key not in WORKGROUP_POSITIONS:
        return jsonify({'error': 'Invalid position type'}), 400

    nominee_user_id = (data.get('nominee_user_id') or '').strip() or None
    nominee_name = (data.get('nominee_name') or '').strip()
    nominee_email = _normalize_email(data.get('nominee_email'))
    nominee_profile_url = _normalize_profile_url(data.get('nominee_profile_url'))
    statement = (data.get('statement') or '').strip()

    if not nominee_name:
        return jsonify({'error': 'Nominee name is required'}), 400
    if not _is_valid_profile_url(nominee_profile_url):
        return jsonify({'error': 'A valid CV or LinkedIn URL is required'}), 400
    if not statement:
        return jsonify({'error': 'Statement is required'}), 400

    workgroup = Workgroup.query.get_or_404(workgroup_id)
    if workgroup.approval_status != 'approved':
        return jsonify({'error': 'Workgroup must be approved before nominating'}), 400

    # When an account is named, its own email is authoritative: a nominator must
    # not be able to attach an address they control to somebody else's account.
    identity = resolve_nominee_identity(
        nominee_user_id=nominee_user_id,
        nominee_email=nominee_email,
    )
    if identity.error:
        return jsonify({'error': identity.error}), 400
    nominee_user_id = identity.user_id
    nominee_email = identity.email
    if not _is_valid_email(nominee_email):
        return jsonify({'error': 'A valid nominee email is required'}), 400

    is_self_nomination = detect_self_nomination(
        nominee_user_id=nominee_user_id,
        nominee_email=nominee_email,
        current_user_id=current_user.get('id'),
        current_user_email=current_user.get('email'),
    )

    duplicate_filters = [func.lower(WorkingGroupChair.nominee_email) == nominee_email]
    if nominee_user_id:
        duplicate_filters.append(WorkingGroupChair.user_id == nominee_user_id)
    existing = WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == workgroup.acronym,
        WorkingGroupChair.position_key == position_key,
        WorkingGroupChair.status.in_(list(ACTIVE_NOMINATION_STATUSES)),
        or_(*duplicate_filters),
    ).first()
    if existing:
        return jsonify({'error': 'This person already has an active nomination for this position'}), 400

    initial_status = initial_nomination_status(is_self_nomination)

    chair = WorkingGroupChair(
        group_acronym=workgroup.acronym,
        position_key=position_key,
        user_id=nominee_user_id,
        chair_name=nominee_name,
        approved=False,
        set_at=datetime.utcnow(),
        statement=statement,
        nominated_by_user_id=current_user['id'],
        is_self_nomination=is_self_nomination,
        nominee_email=nominee_email,
        nominee_profile_url=nominee_profile_url,
        status=initial_status,
    )
    db.session.add(chair)
    db.session.flush()
    # The nomination, its response token and the in-app notifications commit
    # together; email delivery is reported and never rolls the nomination back.
    email_ok = send_nomination_submitted(chair)
    db.session.commit()

    pos_label = position_label(position_key)
    if is_self_nomination:
        message = f'Your {pos_label} nomination was submitted and is pending administrator approval.'
    else:
        message = f'Nomination sent. {nominee_name} will receive an email with your statement and a link to accept or decline.'
    return jsonify({'success': True, 'message': message, 'notifications_sent': email_ok})


def _respond_to_nomination(nomination_id, accept: bool):
    """Shared logic for accept/decline. Returns a Flask response tuple."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    row = WorkingGroupChair.query.get_or_404(nomination_id)

    # Only the nominated person may answer: the linked account when the
    # nomination names one, otherwise the account holding the nominee email.
    if not caller_matches_nomination(row, current_user):
        return jsonify({'error': RESPONSE_FORBIDDEN_ERROR}), 403

    if row.status != NOMINATION_STATUS_PENDING_NOMINEE:
        return jsonify({
            'error': f'Nomination is not pending nominee action (current status: {row.status})'
        }), 400

    if accept:
        email_error = require_nominee_email(row)
        if email_error:
            return jsonify({'error': email_error}), 400

    record_nominee_response(row, accept=accept)
    db.session.commit()

    # Notifications must never undo a recorded response. In-app notifications
    # (including the layer admins' review item) are part of this commit; email
    # failures are logged and reported, not rolled back.
    email_ok = send_nominee_accepted(row) if accept else send_nominee_declined(row)
    db.session.commit()
    if not email_ok:
        current_app.logger.warning(
            'Response emails incomplete for nomination %s', row.id
        )

    return jsonify({
        'ok': True,
        'status': row.status,
        'status_label': status_label(row.status),
        'notifications_sent': email_ok,
    })


@bp.route('/workgroup-nominations/<nomination_id>/accept/', methods=['POST'])
@require_auth
def accept_workgroup_nomination(nomination_id):
    """The nominee accepts their own pending nomination (willingness only)."""
    return _respond_to_nomination(nomination_id, accept=True)


@bp.route('/workgroup-nominations/<nomination_id>/decline/', methods=['POST'])
@require_auth
def decline_workgroup_nomination(nomination_id):
    """The nominee declines their own pending nomination."""
    return _respond_to_nomination(nomination_id, accept=False)
