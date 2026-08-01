"""Authorization and lifecycle rules for workgroup position nominations.

Three invariants live here so every entry point (session API, page API, admin
API) enforces the same rules:

1. **Identity binding.** A nomination is a claim about one person. Only that
   person may accept or decline it: the linked account when ``user_id`` is set,
   otherwise the account whose verified email equals ``nominee_email``.
2. **Server-authoritative nominee identity.** When a nominator selects an
   existing Gov Hub account, the stored ``nominee_email`` is the account's own
   email. A nominator can never pair a victim's account id with an email they
   control, which would otherwise let them hold the acceptance token for
   somebody else's account.
3. **No floating roles.** Approval requires a Gov Hub account, creates the
   membership, and is idempotent so a partially delivered approval can be
   safely replayed instead of leaving unrecoverable state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import func

from extensions import db
from models import Layer, LayerAdmin, User, Workgroup, WorkingGroupChair
from services.coordination import is_layer_admin
from services.dp_welcome import (
    deliver_dp_welcome,
    nomination_welcome_variant,
    require_nominee_email,
)
from services.workgroup_authority import is_site_moderation_staff
from services.workgroup_links import is_dp_workgroup
from services.workgroup_membership import ensure_workgroup_membership
from services.workgroup_positions import (
    NOMINATION_STATUS_APPROVED,
    NOMINATION_STATUS_NOMINEE_ACCEPTED,
    NOMINATION_STATUS_NOMINEE_DECLINED,
    NOMINATION_STATUS_PENDING_NOMINEE,
    NOMINATION_STATUS_REJECTED,
    position_label,
)

RESPONSE_FORBIDDEN_ERROR = (
    'This nomination can only be answered by the person it names. '
    'Sign in with the invited account, or use the link from the nomination email.'
)
NOMINEE_EMAIL_MISMATCH_ERROR = (
    'The nominee email must match the selected Gov Hub account. '
    'Leave the email blank to use the account email.'
)
NOMINEE_ACCOUNT_MISSING_EMAIL_ERROR = (
    'The selected Gov Hub account has no email address on file, so the nominee '
    'cannot be contacted. Ask them to add an email to their profile first.'
)
REVIEW_FORBIDDEN_ERROR = (
    'Only layer administrators for this workgroup (or Gov Hub staff) can review '
    'this nomination.'
)
APPROVED_CANNOT_BE_REJECTED_ERROR = (
    'This nomination is already approved. Rejecting an approved role is not '
    'allowed; remove the role holder instead so membership and history stay intact.'
)


def normalize_email(email: Optional[str]) -> str:
    return (email or '').strip().lower()


# ---------------------------------------------------------------------------
# Nominee identity at creation time
# ---------------------------------------------------------------------------

@dataclass
class NomineeIdentity:
    """Server-resolved nominee: account (optional) plus authoritative email."""

    user: Optional[User] = None
    email: str = ''
    error: Optional[str] = None

    @property
    def user_id(self) -> Optional[str]:
        return self.user.id if self.user else None


def resolve_nominee_identity(
    *,
    nominee_user_id: Optional[str],
    nominee_email: Optional[str],
) -> NomineeIdentity:
    """Bind the submitted nominee email to the selected account, server-side.

    With no account selected the submitted email is used as-is (email-only
    nomination). With an account selected the account's own email always wins,
    and a submitted email that names a different address is rejected rather
    than silently overwritten so the nominator sees what will happen.
    """
    submitted = normalize_email(nominee_email)
    if not nominee_user_id:
        return NomineeIdentity(user=None, email=submitted)

    nominee_user = User.query.get(nominee_user_id)
    if not nominee_user:
        return NomineeIdentity(error='Selected Gov Hub user was not found')

    account_email = normalize_email(nominee_user.email)
    if not account_email:
        return NomineeIdentity(error=NOMINEE_ACCOUNT_MISSING_EMAIL_ERROR)
    if submitted and submitted != account_email:
        return NomineeIdentity(error=NOMINEE_EMAIL_MISMATCH_ERROR)
    return NomineeIdentity(user=nominee_user, email=account_email)


# ---------------------------------------------------------------------------
# Identity binding for accept / decline
# ---------------------------------------------------------------------------

def caller_matches_nomination(
    nomination: Optional[WorkingGroupChair],
    user: Optional[dict],
) -> bool:
    """True when the signed-in caller is the person the nomination names."""
    if not nomination or not user:
        return False
    caller_id = user.get('id')
    if nomination.user_id:
        # Linked account is authoritative: an email match on a different
        # account must not grant control over this nomination.
        return bool(caller_id) and str(nomination.user_id) == str(caller_id)

    nominee_email = normalize_email(nomination.nominee_email)
    if not nominee_email:
        return False
    return nominee_email == normalize_email(user.get('email'))


def nomination_is_pending_nominee(nomination: WorkingGroupChair) -> bool:
    return (nomination.status or NOMINATION_STATUS_PENDING_NOMINEE) == (
        NOMINATION_STATUS_PENDING_NOMINEE
    )


def record_nominee_response(nomination: WorkingGroupChair, *, accept: bool) -> None:
    """Apply the nominee's accept/decline. Caller commits."""
    nomination.status = (
        NOMINATION_STATUS_NOMINEE_ACCEPTED if accept else NOMINATION_STATUS_NOMINEE_DECLINED
    )
    nomination.nominee_responded_at = datetime.utcnow()
    # Accepting states willingness only; the role is granted at admin approval.
    nomination.approved = False


# ---------------------------------------------------------------------------
# Object-scoped review authorization
# ---------------------------------------------------------------------------

def nomination_layer(nomination: Optional[WorkingGroupChair]) -> Optional[Layer]:
    if not nomination or not nomination.group_acronym:
        return None
    workgroup = Workgroup.query.filter_by(acronym=nomination.group_acronym).first()
    if not workgroup or not workgroup.layer_id:
        return None
    return Layer.query.get(workgroup.layer_id)


def can_review_nomination(
    nomination: Optional[WorkingGroupChair],
    user: Optional[dict],
) -> bool:
    """Gov Hub staff, or a layer admin/owner of the nomination's own layer.

    Mirrors the recipients of the "nominee accepted" notification, so everyone
    who is asked to review a nomination can actually act on it — and nobody can
    act on another layer's nominations.
    """
    if not user:
        return False
    if is_site_moderation_staff(user):
        return True
    layer = nomination_layer(nomination)
    if not layer:
        return False
    return bool(is_layer_admin(layer, user))


def administered_layer_ids(user: Optional[dict]) -> set:
    """Layer ids the user owns or is an assigned admin for."""
    if not user or not user.get('id'):
        return set()
    uid = user['id']
    owned = {row.id for row in Layer.query.filter_by(initiator_id=uid).all()}
    assigned = {row.layer_id for row in LayerAdmin.query.filter_by(user_id=uid).all()}
    return owned | assigned


def can_review_any_nomination(user: Optional[dict]) -> bool:
    """Whether the review queue should be reachable at all for this user."""
    if not user:
        return False
    return is_site_moderation_staff(user) or bool(administered_layer_ids(user))


# ---------------------------------------------------------------------------
# Approval / rejection
# ---------------------------------------------------------------------------

@dataclass
class ApprovalResult:
    ok: bool = False
    error: Optional[str] = None
    status_code: int = 200
    already_approved: bool = False
    welcome_url: Optional[str] = None
    membership_created: bool = False
    linked_user_id: Optional[str] = None
    notifications: dict = field(default_factory=dict)


def _accounts_for_email(email: str) -> list:
    if not email:
        return []
    return User.query.filter(func.lower(User.email) == email).all()


def link_nominee_account(nomination: WorkingGroupChair) -> Optional[str]:
    """Resolve an email-only nomination to a Gov Hub account.

    Returns an error message when the email cannot be resolved to exactly one
    account; sets ``nomination.user_id`` on success. Caller commits.
    """
    if nomination.user_id:
        return None

    email = normalize_email(nomination.nominee_email)
    if not email:
        return require_nominee_email(nomination)

    matches = _accounts_for_email(email)
    if not matches:
        return (
            f'{email} does not have a Gov Hub account yet, so this role cannot be '
            'assigned. Ask the nominee to sign in to Gov Hub with that email '
            'address, then approve this nomination again.'
        )
    if len(matches) > 1:
        return (
            f'{email} matches more than one Gov Hub account. Resolve the duplicate '
            'accounts before approving this nomination.'
        )
    nomination.user_id = matches[0].id
    return None


def approve_nomination(
    nomination: WorkingGroupChair,
    *,
    actor: Optional[dict] = None,
) -> ApprovalResult:
    """Approve a nomination: grant the role, create membership, queue welcome.

    All database effects (status, membership, in-app welcome notification)
    commit together. Email is sent after the commit and its outcome is reported
    rather than rolled back, so a mail outage never discards the nominee's
    consent or the approval itself. Re-approving an already approved nomination
    repairs missing membership/welcome instead of failing, which is the recovery
    path for a partially delivered approval.
    """
    del actor  # reserved for future audit logging
    current_status = nomination.status or NOMINATION_STATUS_PENDING_NOMINEE
    already_approved = current_status == NOMINATION_STATUS_APPROVED

    if not already_approved and current_status != NOMINATION_STATUS_NOMINEE_ACCEPTED:
        return ApprovalResult(
            error='Nominee must accept before admin approval',
            status_code=400,
        )

    email_error = require_nominee_email(nomination)
    if email_error:
        return ApprovalResult(error=email_error, status_code=400)

    link_error = link_nominee_account(nomination)
    if link_error:
        return ApprovalResult(error=link_error, status_code=409)

    nomination.approved = True
    nomination.status = NOMINATION_STATUS_APPROVED

    display_name = nomination.chair_name or ''
    if not display_name:
        nominee_user = User.query.get(nomination.user_id)
        display_name = (
            (nominee_user.displayName or nominee_user.username) if nominee_user else ''
        )
    _member, membership_created = ensure_workgroup_membership(
        acronym=nomination.group_acronym,
        user_id=nomination.user_id,
        display_name=display_name,
    )

    workgroup = Workgroup.query.filter_by(acronym=nomination.group_acronym).first()
    welcome_url = None
    if workgroup and is_dp_workgroup(workgroup):
        welcome_url = deliver_dp_welcome(
            user_id=nomination.user_id,
            workgroup=workgroup,
            variant=nomination_welcome_variant(nomination.position_key),
            position_key=nomination.position_key,
        )

    # Single commit: role, membership and the in-app welcome are all-or-nothing.
    db.session.commit()

    return ApprovalResult(
        ok=True,
        already_approved=already_approved,
        welcome_url=welcome_url,
        membership_created=membership_created,
        linked_user_id=nomination.user_id,
    )


def reject_nomination(nomination: WorkingGroupChair) -> ApprovalResult:
    """Reject a nomination that has not been approved yet.

    Approved roles are terminal for this endpoint: removing a granted role is a
    revocation, which must not silently strip the person's workgroup membership.
    """
    current_status = nomination.status or NOMINATION_STATUS_PENDING_NOMINEE
    if current_status == NOMINATION_STATUS_APPROVED or nomination.approved:
        return ApprovalResult(error=APPROVED_CANNOT_BE_REJECTED_ERROR, status_code=409)
    if current_status == NOMINATION_STATUS_REJECTED:
        return ApprovalResult(ok=True, already_approved=False)

    nomination.approved = False
    nomination.status = NOMINATION_STATUS_REJECTED
    db.session.commit()
    return ApprovalResult(ok=True)


def nomination_position_label(nomination: WorkingGroupChair) -> str:
    return position_label(nomination.position_key or 'chair')
