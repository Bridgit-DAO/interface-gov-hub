"""Per-layer two-letter draft prefix CRUD."""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import LayerPrefix

LAYER_PREFIX_FORMAT_RE = re.compile(r'^[A-Z]{2}$')


def _normalize_prefix(raw: object) -> str:
    if not isinstance(raw, str):
        return ''
    return raw.strip().upper()


def is_valid_prefix_format(value: object) -> bool:
    """Two uppercase ASCII letters, e.g. 'ML', 'CL'."""
    return bool(LAYER_PREFIX_FORMAT_RE.match(_normalize_prefix(value)))


def get_default_prefix(layer_id: str) -> Optional[LayerPrefix]:
    return LayerPrefix.query.filter_by(
        layer_id=layer_id, is_default=True,
    ).order_by(LayerPrefix.created_at.asc()).first()


def effective_prefix_for_document(
    *,
    prefix_code: object = None,
    layer_id: object = None,
    primary_layer_id: object = None,
) -> str:
    """Resolve the 2-letter draft prefix for a submission or catalog row.

    Mirrors ``routes.submissions._layer_prefix_for_submission``: honour an
    explicit per-draft ``prefix_code``, then the layer's default
    ``LayerPrefix`` row, then ``ML``.
    """
    override = _normalize_prefix(prefix_code)
    if override and is_valid_prefix_format(override):
        return override
    lid = primary_layer_id or layer_id
    if not lid:
        return 'ML'
    try:
        row = get_default_prefix(str(lid))
        if row is None:
            return 'ML'
        prefix = _normalize_prefix(getattr(row, 'prefix', None) or '')
        return prefix or 'ML'
    except Exception:
        return 'ML'


def effective_prefix_for_submission(submission) -> str:
    """Return the effective prefix for a ``Submission`` ORM row."""
    if submission is None:
        return 'ML'
    return effective_prefix_for_document(
        prefix_code=getattr(submission, 'prefix_code', None),
        layer_id=getattr(submission, 'layer_id', None),
        primary_layer_id=getattr(submission, 'primary_layer_id', None),
    )


def effective_prefix_for_draft(draft: dict) -> str:
    """Return the effective prefix for a draft dict in the document catalog."""
    return effective_prefix_for_document(
        prefix_code=draft.get('prefix_code') or draft.get('prefix'),
        layer_id=draft.get('layer_id'),
        primary_layer_id=draft.get('primary_layer_id'),
    )


def catalog_prefix_badge_value(effective_prefix: str, ml_number: object = None) -> Optional[str]:
    """Return prefix text for /doc/all/ badge, or None when redundant with ml_number."""
    prefix = _normalize_prefix(effective_prefix)
    if not prefix:
        return None
    ml = (str(ml_number) if ml_number is not None else '').strip()
    if ml and ml.upper().startswith(f'{prefix}-'):
        return None
    return prefix


def list_prefixes(layer_id: str) -> list[LayerPrefix]:
    return (
        LayerPrefix.query
        .filter_by(layer_id=layer_id)
        .order_by(LayerPrefix.is_default.desc(), LayerPrefix.created_at.asc())
        .all()
    )


def add_prefix(layer_id: str, raw_prefix: str, created_by: Optional[str]) -> tuple[dict, int]:
    """Add a prefix to a layer.

    Returns (body, status_code). 400 on format errors, 409 on global uniqueness
    conflict, 201 on success.
    """
    prefix = _normalize_prefix(raw_prefix)
    if not is_valid_prefix_format(prefix):
        return {
            'error': 'Prefix must be exactly two uppercase ASCII letters (e.g. "ML").',
            'code': 'invalid_format',
        }, 400

    existing = LayerPrefix.query.filter_by(prefix=prefix).first()
    if existing:
        return {
            'error': f'Prefix "{prefix}" is already taken by another layer.',
            'code': 'prefix_taken',
        }, 409

    row = LayerPrefix(
        layer_id=layer_id,
        prefix=prefix,
        is_default=False,
        created_by=created_by,
    )
    try:
        db.session.add(row)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            'error': f'Prefix "{prefix}" is already taken by another layer.',
            'code': 'prefix_taken',
        }, 409
    return {'prefix': row.to_dict()}, 201


def update_prefix(layer_id: str, prefix_id: str, raw_prefix: str) -> tuple[dict, int]:
    """Rename a prefix (must still be 2 uppercase letters and globally unique)."""
    prefix = _normalize_prefix(raw_prefix)
    if not is_valid_prefix_format(prefix):
        return {
            'error': 'Prefix must be exactly two uppercase ASCII letters (e.g. "ML").',
            'code': 'invalid_format',
        }, 400

    row = LayerPrefix.query.filter_by(id=prefix_id, layer_id=layer_id).first()
    if not row:
        return {'error': 'Prefix not found'}, 404

    conflict = LayerPrefix.query.filter(
        LayerPrefix.prefix == prefix,
        LayerPrefix.id != prefix_id,
    ).first()
    if conflict:
        return {
            'error': f'Prefix "{prefix}" is already taken by another layer.',
            'code': 'prefix_taken',
        }, 409

    row.prefix = prefix
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            'error': f'Prefix "{prefix}" is already taken by another layer.',
            'code': 'prefix_taken',
        }, 409
    return {'prefix': row.to_dict()}, 200


def delete_prefix(layer_id: str, prefix_id: str) -> tuple[dict, int]:
    """Delete a prefix. Refuses to delete the current default; the layer
    must mark another prefix as default first.
    """
    row = LayerPrefix.query.filter_by(id=prefix_id, layer_id=layer_id).first()
    if not row:
        return {'error': 'Prefix not found'}, 404
    if bool(row.is_default):
        return {
            'error': (
                'This is the default prefix for the layer. Mark another prefix '
                'as default first, then delete this one.'
            ),
            'code': 'cannot_delete_default',
        }, 400
    # Refuse to delete the last remaining prefix (a layer should always
    # have at least one prefix available).
    remaining = LayerPrefix.query.filter_by(layer_id=layer_id).count()
    if remaining <= 1:
        return {
            'error': 'A layer must always have at least one prefix. Add another one first.',
            'code': 'last_prefix',
        }, 400

    db.session.delete(row)
    db.session.commit()
    return {'success': True}, 200


def set_default_prefix(layer_id: str, prefix_id: str) -> tuple[dict, int]:
    """Mark `prefix_id` as the active default for the layer (clear all others)."""
    row = LayerPrefix.query.filter_by(id=prefix_id, layer_id=layer_id).first()
    if not row:
        return {'error': 'Prefix not found'}, 404

    LayerPrefix.query.filter_by(layer_id=layer_id).update({'is_default': False})
    row.is_default = True
    db.session.commit()
    return {'prefix': row.to_dict()}, 200


def prefixes_for_user(user_id: str) -> list[dict]:
    """All prefixes for layers the user can access (admin or active member).

    Returns a flat list of dicts enriched with the owning layer's name/slug.
    Used by the header dropdown.
    """
    if not user_id:
        return []
    from models import Layer, LayerAdmin, LayerMember

    admin_layer_ids = [
        la.layer_id for la in
        LayerAdmin.query.filter_by(user_id=user_id).all()
    ]
    member_layer_ids = [
        lm.layer_id for lm in
        LayerMember.query.filter_by(user_id=user_id, status='active').all()
    ]
    owner_layer_ids = [
        l.id for l in
        Layer.query.filter_by(initiator_id=user_id).all()
    ]
    all_layer_ids = set(admin_layer_ids) | set(member_layer_ids) | set(owner_layer_ids)
    if not all_layer_ids:
        return []

    prefixes = (
        LayerPrefix.query
        .filter(LayerPrefix.layer_id.in_(all_layer_ids))
        .order_by(LayerPrefix.layer_id, LayerPrefix.is_default.desc(), LayerPrefix.created_at.asc())
        .all()
    )
    layers = {
        l.id: l for l in
        Layer.query.filter(Layer.id.in_(all_layer_ids)).all()
    }
    out = []
    for p in prefixes:
        layer = layers.get(p.layer_id)
        if not layer:
            continue
        out.append({
            **p.to_dict(),
            'layer_name': layer.name,
            'layer_slug': layer.slug,
        })
    return out


# ---------------------------------------------------------------------------
# Public layer listing helper
# ---------------------------------------------------------------------------
# Centralises the ``approval_status='approved' AND display_status='active'``
# filter used by the home directory, the submit-form layer dropdown, and the
# layer connections page. Layer admins still see their own pending layers so
# they can flip them to active from the Edit Layer modal.

DISPLAY_STATUS_VALUES = ('pending', 'active')
PUBLIC_LAYER_ADMIN_ALLOWED_STATUSES = ('pending', 'active')


def normalize_display_status(raw, default: str = 'pending') -> str:
    """Whitelist-validate a `display_status` value from the API.

    Anything not in ``DISPLAY_STATUS_VALUES`` falls back to ``default``.
    Unknown future values are deliberately rejected so the column stays
    predictable in the UI.
    """
    v = (str(raw) if raw is not None else '').strip().lower()
    return v if v in DISPLAY_STATUS_VALUES else default


def _layer_admin_layer_ids(user_id: Optional[str]) -> list[str]:
    """Layer IDs where ``user_id`` is a ``LayerAdmin`` (initiator counts too)."""
    if not user_id:
        return []
    from models import Layer, LayerAdmin

    admin_ids = [
        la.layer_id for la in
        LayerAdmin.query.filter_by(user_id=user_id).all()
    ]
    owner_ids = [
        l.id for l in
        Layer.query.filter_by(initiator_id=user_id).all()
    ]
    return list(set(admin_ids) | set(owner_ids))


def visible_layers_for_user(user_id: Optional[str] = None, *, active_only: bool = False):
    """Approved layers visible to ``user_id`` (or anonymous when ``None``).

    Always limited to ``approval_status='approved'``. Plus:
      * ``display_status='active'`` layers are visible to everyone.
      * A layer's admin / owner also sees their own layers regardless of
        ``display_status`` (so they can finish setup before flipping active).

    Set ``active_only=True`` to ignore the admin-owner exception and return
    ONLY ``display_status='active'`` layers — used by user-facing surfaces
    like the ``/docs/`` directory filter where pending layers must never
    leak even for the layer's own admins.

    Returns the Layer rows ordered alphabetically by name and deduped by
    name (mirrors the ``group_by(Layer.name)`` pattern used elsewhere).
    """
    from models import Layer, LayerAdmin

    base = Layer.query.filter(Layer.approval_status == 'approved')

    if active_only:
        # Public user-facing surfaces: strict active-only, no exceptions.
        q = base.filter(Layer.display_status == 'active')
    else:
        admin_ids = _layer_admin_layer_ids(user_id)
        if admin_ids:
            from sqlalchemy import or_

            q = base.filter(or_(
                Layer.display_status == 'active',
                Layer.id.in_(admin_ids),
            ))
        else:
            q = base.filter(Layer.display_status == 'active')

    rows = q.group_by(Layer.name).order_by(Layer.name).all()

    # Touch LayerAdmin so static analysers don't flag the import as unused
    # when the helper is called via anonymous traffic; the import is needed
    # for ``_layer_admin_layer_ids`` and the IN clause above.
    _ = LayerAdmin

    return rows
