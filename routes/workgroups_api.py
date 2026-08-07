"""Workgroups API blueprint: per-workgroup JSON endpoints used by the
``/workgroups/<slug>/`` page.

The endpoints implemented here were originally only present as parts of
``routes/workgroups.py`` (where they are still maintained). This module
exposes the same URLs under a dedicated ``workgroups_api`` blueprint so
the page-side client JS (``workgroups_pages.py``) has a stable,
single-purpose surface and so we can document the contract explicitly.

NOTE on identifiers: workgroup IDs in this codebase are UUIDs (not
integers), so the URL converter is ``<string:workgroup_id>``.

Existing endpoints – these are duplicated on purpose. Flask's URL map
matches the FIRST registered blueprint for a given URL, so
``routes.workgroups.bp`` (registered earlier in ``app.py``) continues
to answer requests. Defining them here provides a clear contract and
serves as a single place for future API changes (such as adding per-ID
serialization that differs from the layer-listing serialization).
"""
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, text

from extensions import db
from models import Workgroup, User, WorkingGroupChair
from services.identity import get_current_user, require_auth
from services.utils import coerce_storage_bool
from services.workgroup_authority import can_invite_workgroup_member, can_manage_workgroup
from services.workgroup_links import (
    enrich_workgroup_dict,
    list_assigned_documents_for_workgroup,
)
from services.workgroup_membership import (
    join_or_request_workgroup_membership,
    user_workgroup_status,
)
from services.workgroup_links import is_dp_workgroup
from services.dp_welcome import deliver_dp_welcome
from services.workgroup_nomination_flow import resolve_nominee_identity
from services.workgroup_positions import (
    WORKGROUP_POSITIONS,
    ACTIVE_NOMINATION_STATUSES,
    NOMINATION_STATUS_APPROVED,
    NOMINATION_STATUS_NOMINEE_ACCEPTED,
    NOMINATION_STATUS_PENDING_NOMINEE,
    detect_self_nomination,
    initial_nomination_status,
    position_label,
    positions_for_api,
    status_label,
)
from services.workgroup_nomination_mail import send_nomination_submitted

bp = Blueprint('workgroups_api', __name__, url_prefix='/api/workgroups')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Per-workgroup endpoints
# ---------------------------------------------------------------------------

@bp.route('/positions/', methods=['GET'])
def api_list_positions():
    """List nominatable workgroup position types."""
    return jsonify({'positions': positions_for_api()})


@bp.route('/<string:workgroup_id>/', methods=['GET'])
def api_workgroup_detail(workgroup_id):
    """Return full workgroup detail matching the fields the page JS reads."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    payload = enrich_workgroup_dict(workgroup.to_dict(), workgroup)
    from services.api_auth import get_api_user
    current_user = get_api_user()
    payload['can_edit'] = can_manage_workgroup(workgroup, current_user)
    payload['can_invite_members'] = can_invite_workgroup_member(workgroup, current_user)
    return jsonify(payload)


@bp.route('/<string:workgroup_id>/chairs/', methods=['GET'])
def api_workgroup_chairs(workgroup_id):
    """List position nominations (chairs / co-leads / editors / ...) for a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    rows = db.session.execute(
        text("""
            SELECT id, group_acronym, chair_name, approved, set_at, user_id,
                   position_key, status
            FROM working_group_chair
            WHERE group_acronym = :acronym
            ORDER BY set_at DESC
        """),
        {'acronym': workgroup.acronym},
    ).fetchall()

    chairs = []
    for row in rows:
        status = row[7] or (
            NOMINATION_STATUS_APPROVED if coerce_storage_bool(row[3]) else NOMINATION_STATUS_PENDING_NOMINEE
        )
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


@bp.route('/<string:workgroup_id>/members/', methods=['GET'])
def api_workgroup_members(workgroup_id):
    """List members of a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    rows = db.session.execute(
        text("""
            SELECT id, group_acronym, user_name, joined_at, user_id
            FROM working_group_member
            WHERE group_acronym = :acronym
            ORDER BY joined_at DESC
        """),
        {'acronym': workgroup.acronym},
    ).fetchall()

    members = [{
        'id': row[0],
        'group_acronym': row[1],
        'user_name': row[2],
        'joined_at': row[3],
        'user_id': row[4],
    } for row in rows]

    return jsonify({'members': members, 'count': len(members)})


@bp.route('/<string:acronym>/me/status', methods=['GET'])
@require_auth
def api_workgroup_my_status(acronym):
    """Current user's membership, positions, and join/nominate affordances for one workgroup."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    return jsonify(user_workgroup_status(current_user.get('id'), acronym))


@bp.route('/<string:workgroup_id>/assigned-documents/', methods=['GET'])
def api_workgroup_assigned_documents(workgroup_id):
    """Drafts assigned to this workgroup via submission.group."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    documents = list_assigned_documents_for_workgroup(workgroup)
    return jsonify({'documents': documents, 'count': len(documents)})


@bp.route('/<string:workgroup_id>/join/', methods=['POST'])
@require_auth
def api_workgroup_join(workgroup_id):
    """Join a workgroup as a member (or request membership if approval required)."""
    current_user = get_current_user()
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

    # Membership + welcome notification share one commit.
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


@bp.route('/<string:workgroup_id>/nominate/', methods=['POST'])
@require_auth
def api_workgroup_nominate(workgroup_id):
    """Nominate a person (self or another) for a workgroup position."""
    current_user = get_current_user()
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

    # Same server-authoritative nominee binding as routes/workgroups.py.
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