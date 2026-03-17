"""Civic Mason: placement validation, eligibility check."""
from models import Brick, Badge, Role


def user_has_civic_mason_eligibility(user_id):
    """User can place bricks if they have an issued badge from a role with civic_mason_eligible=True."""
    badges = Badge.query.filter_by(claimant_id=user_id, status='issued').all()
    for b in badges:
        if b.role and getattr(b.role, 'civic_mason_eligible', False):
            return True
    return False


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
        return False, "Position already occupied"

    y = float(grid_y)
    x = float(grid_x)

    if y > 0:
        left = (x - 0.5, y - 1)
        right = (x + 0.5, y - 1)
        if left not in occupied and right not in occupied:
            return False, "Must rest on at least one brick below"

    # 50% rule: on each row, at most half the slots can be filled
    # Slots in row y: derived from row extent (row below or row itself)
    row_bricks = [b for b in existing_bricks if abs(float(b.grid_y) - y) < 0.01]
    if row_bricks:
        xs = [float(b.grid_x) for b in row_bricks]
        x_min, x_max = min(xs), max(xs)
        # Half-offset: row 0 has int slots; row 1 has .5 slots. Slots = 2 * span for half-units
        span = x_max - x_min + 0.5
        slots = max(2, int(span * 2))
        if len(row_bricks) >= slots // 2:
            return False, "Row is full (50% limit)"

    return True, None
