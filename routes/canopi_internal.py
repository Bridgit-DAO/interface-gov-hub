"""Canopi server-to-server internal routes (workgroup membership, etc.)."""
from __future__ import annotations

import os
import secrets

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from extensions import db
from models import User, Workgroup

bp = Blueprint('canopi_internal', __name__)


def _canopi_internal_allowed() -> bool:
    secret = (os.environ.get('GOV_HUB_API_KEY') or '').strip()
    if not secret:
        return False
    supplied = (
        request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
        or ''
    ).strip()
    return bool(supplied) and secrets.compare_digest(supplied, secret)


def _normalize_email(raw: str | None) -> str:
    return (raw or '').strip().lower()


def _resolve_workgroup(workgroup_ref: str | None):
    ref = (workgroup_ref or '').strip()
    if not ref:
        return None
    wg = Workgroup.query.get(ref)
    if wg:
        return wg
    return Workgroup.query.filter(
        (Workgroup.slug == ref) | (Workgroup.acronym == ref)
    ).first()


@bp.route('/api/internal/canopi/workgroup-membership', methods=['GET'])
def workgroup_membership():
    """
    Check whether an email belongs to a GovHub workgroup.

    Auth: GOV_HUB_API_KEY via Authorization: Bearer.
    Query: workgroup_id (uuid, slug, or acronym), email
    """
    if not _canopi_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    workgroup_ref = request.args.get('workgroup_id') or request.args.get('workgroupId')
    email = _normalize_email(request.args.get('email'))
    if not workgroup_ref or not email:
        return jsonify({'error': 'workgroup_id and email are required'}), 400

    workgroup = _resolve_workgroup(workgroup_ref)
    if not workgroup or not workgroup.acronym:
        return jsonify({'isMember': False, 'reason': 'workgroup_not_found'})

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return jsonify({'isMember': False, 'reason': 'user_not_found'})

    row = db.session.execute(
        text(
            """
            SELECT id FROM working_group_member
            WHERE group_acronym = :acronym AND user_id = :user_id
            LIMIT 1
            """
        ),
        {'acronym': workgroup.acronym, 'user_id': user.id},
    ).fetchone()

    return jsonify({
        'isMember': bool(row),
        'workgroupId': workgroup.id,
        'workgroupAcronym': workgroup.acronym,
        'email': email,
    })
