"""DP Challenge server-to-server routes (Hermes / ops secret)."""
from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from models import DpProposal, Submission
from extensions import db
from services.support_auth import require_hermes

bp = Blueprint('dp_internal', __name__)

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


@bp.route('/api/internal/dp/broadcast-user-emails', methods=['POST'])
@require_hermes
def dp_broadcast_user_emails():
    """Resolve Gov Hub account emails for DP broadcast enrichment.

    Workgroup signup ``user_id`` values are Gov Hub ``User.id`` — not Canopi
    ``AppUser.id``. Challenge-site broadcast must call here instead of Canopi
    ``/v1/internal/metaweb/user-email``.
    """
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('userIds') or data.get('user_ids') or []
    if not isinstance(raw_ids, list):
        return jsonify({'ok': False, 'error': 'invalid_user_ids'}), 400

    user_ids = [
        uid for uid in {str(value or '').strip() for value in raw_ids}
        if _UUID_RE.match(uid)
    ]
    if not user_ids:
        return jsonify({'ok': True, 'emails': {}})

    rows = User.query.filter(User.id.in_(user_ids)).all()
    emails: dict[str, str] = {}
    for row in rows:
        email = (row.email or '').strip().lower()
        if _EMAIL_RE.match(email):
            emails[row.id] = email

    return jsonify({'ok': True, 'emails': emails, 'requested': len(user_ids), 'found': len(emails)})


@bp.route('/api/internal/dp/broadcast-patch-status', methods=['POST'])
@require_hermes
def dp_broadcast_patch_status():
    """Patch submission counts per Gov Hub author for DP broadcast audience filters."""
    rows = (
        db.session.query(DpProposal.author_user_id, Submission.ml_number)
        .join(Submission, DpProposal.submission_id == Submission.id)
        .filter(DpProposal.author_user_id.isnot(None))
        .all()
    )

    users: dict[str, dict[str, object]] = {}
    for author_user_id, ml_number in rows:
        uid = str(author_user_id or '').strip()
        if not _UUID_RE.match(uid):
            continue
        entry = users.setdefault(uid, {'patchCount': 0, 'mlNumbers': []})
        entry['patchCount'] = int(entry['patchCount']) + 1
        ml = str(ml_number or '').strip()
        if ml:
            ml_numbers = entry['mlNumbers']
            if isinstance(ml_numbers, list) and ml not in ml_numbers:
                ml_numbers.append(ml)

    return jsonify({'ok': True, 'users': users, 'authorCount': len(users)})
