"""Civic Mason: placement validation, eligibility check."""
from datetime import datetime

from sqlalchemy import extract

from models import Brick, Badge, Role, User

# Flask session key – only honored when app is in development (IS_DEVELOPMENT)
CIVIC_MASON_SESSION_DEMO = 'civic_mason_demo_mode'


def civic_mason_demo_mode_active(session_dict, is_development):
    """True when dev server and session flag is set – unlimited placements, no badge."""
    if not is_development or not session_dict:
        return False
    return bool(session_dict.get(CIVIC_MASON_SESSION_DEMO))


def user_has_civic_mason_eligibility(user_id, is_development=False):
    """User can place bricks if they have an issued badge from a role with civic_mason_eligible=True."""
    user = User.query.get(user_id)
    if is_development and user and user.email == 'daveed@bridgit.io':
        return True  # Dev-only admin shortcut
    badges = Badge.query.filter_by(claimant_id=user_id, status='issued').all()
    for b in badges:
        if b.role and getattr(b.role, 'civic_mason_eligible', False):
            return True
    return False


def user_brick_count_calendar_year(user_id):
    """How many bricks this user placed in the current UTC calendar year."""
    y = datetime.utcnow().year
    return Brick.query.filter(
        Brick.user_id == user_id,
        extract('year', Brick.created_at) == y,
    ).count()


# Stable API / UI codes (client translates via i18n)
ERR_BADGE_REQUIRED = 'BADGE_REQUIRED'
ERR_ALREADY_PLACED_THIS_YEAR = 'ALREADY_PLACED_THIS_YEAR'
ERR_POSITION_OCCUPIED = 'POSITION_OCCUPIED'
ERR_NO_SUPPORT_BELOW = 'NO_SUPPORT_BELOW'
ERR_ROW_FULL = 'ROW_FULL'


def civic_mason_can_place_brick(user_id, session_dict, is_development):
    """
    Whether this user may place a brick right now.
    Returns (allowed: bool, error_code_or_none) – codes are SCREAMING_SNAKE for client i18n.
    """
    if civic_mason_demo_mode_active(session_dict, is_development):
        return True, None

    if not user_has_civic_mason_eligibility(user_id, is_development=is_development):
        return False, ERR_BADGE_REQUIRED

    if user_brick_count_calendar_year(user_id) >= 1:
        return False, ERR_ALREADY_PLACED_THIS_YEAR

    return True, None


def civic_mason_eligibility_payload(user_id, session_dict, is_development):
    """
    JSON-friendly dict for GET /api/civic-mason/eligible/
    """
    demo = civic_mason_demo_mode_active(session_dict, is_development)
    allowed, code = civic_mason_can_place_brick(user_id, session_dict, is_development)

    reason = None
    if not allowed and code:
        if code == ERR_BADGE_REQUIRED:
            reason = 'badge_required'
        elif code == ERR_ALREADY_PLACED_THIS_YEAR:
            reason = 'already_placed_this_year'
        else:
            reason = 'not_eligible'

    return {
        'eligible': allowed,
        'demo_mode': demo,
        'dev_tools': bool(is_development),
        'reason': reason,
        'reason_code': code,
    }


def _get_occupied_set(bricks):
    """Return set of (grid_x, grid_y) for occupied positions."""
    return {(float(b.grid_x), float(b.grid_y)) for b in bricks}


def _slots_in_row(y):
    """Number of valid slots in row y. Row 0: x=0,1,2,... Row 1: x=0.5,1.5,..."""
    return float('inf')  # Unbounded for now; can cap per row


def is_valid_placement(grid_x, grid_y, existing_bricks):
    """
    Check if (grid_x, grid_y) is a valid placement.
    Rules:
    - Not already occupied
    - Row 0: any x (no support needed)
    - Row > 0: at least one of (x-0.5, y-1) or (x+0.5, y-1) must be occupied
    - 50% rule: row has < 50% of slots filled (slots = count of possible positions in row)
    """
    occupied = _get_occupied_set(existing_bricks)
    pos = (float(grid_x), float(grid_y))

    if pos in occupied:
        return False, ERR_POSITION_OCCUPIED

    y = float(grid_y)
    x = float(grid_x)

    if y > 0:
        left = (x - 0.5, y - 1)
        right = (x + 0.5, y - 1)
        if left not in occupied and right not in occupied:
            return False, ERR_NO_SUPPORT_BELOW

    # 50% rule: at most 12 bricks per row (base row has 24 slots; 50% = 12)
    row_bricks = [b for b in existing_bricks if abs(float(b.grid_y) - y) < 0.01]
    max_per_row = 12
    if len(row_bricks) >= max_per_row:
        return False, ERR_ROW_FULL

    return True, None
