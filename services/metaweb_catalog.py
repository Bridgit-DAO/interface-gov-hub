"""Read-only catalog search for Metaweb Book admin Gov Hub blueberry pickers."""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import or_

from models import Layer, Waitlist, Workgroup

VALID_KINDS = frozenset({'workgroups', 'layers', 'waitlists'})


def _clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 30
    return min(max(n, 1), 100)


def _search_workgroups(q: str, limit: int) -> List[Dict[str, Any]]:
    query = Workgroup.query.filter(
        Workgroup.approval_status == 'approved',
        Workgroup.status == 'active',
    )
    if q:
        like = f'%{q}%'
        query = query.filter(
            or_(
                Workgroup.name.ilike(like),
                Workgroup.acronym.ilike(like),
                Workgroup.slug.ilike(like),
            )
        )
    rows = query.order_by(Workgroup.name.asc()).limit(limit).all()
    items: List[Dict[str, Any]] = []
    for wg in rows:
        items.append({
            'id': wg.id,
            'label': wg.name,
            'slug': wg.slug or wg.acronym,
            'acronym': wg.acronym,
            'layerId': wg.layer_id,
            'layerName': wg.layer.name if wg.layer else None,
        })
    return items


def _search_layers(q: str, limit: int) -> List[Dict[str, Any]]:
    query = Layer.query.filter(
        Layer.approval_status == 'approved',
        Layer.display_status == 'active',
    )
    if q:
        like = f'%{q}%'
        query = query.filter(
            or_(
                Layer.name.ilike(like),
                Layer.slug.ilike(like),
            )
        )
    rows = query.order_by(Layer.name.asc()).limit(limit).all()
    return [
        {
            'id': layer.id,
            'label': layer.name,
            'slug': layer.slug,
        }
        for layer in rows
    ]


def _search_waitlists(q: str, limit: int) -> List[Dict[str, Any]]:
    query = Waitlist.query.filter(Waitlist.archived.is_(False))
    if q:
        like = f'%{q}%'
        query = query.filter(
            or_(
                Waitlist.name.ilike(like),
                Waitlist.id.ilike(like),
            )
        )
    rows = query.order_by(Waitlist.name.asc()).limit(limit).all()
    items: List[Dict[str, Any]] = []
    for wl in rows:
        items.append({
            'id': wl.id,
            'label': wl.name,
            'layerId': wl.layer_id,
            'layerName': wl.layer.name if wl.layer else None,
        })
    return items


def search_metaweb_catalog(*, kind: str, q: str = '', limit: int = 30) -> List[Dict[str, Any]]:
    """Return catalog rows for Metaweb admin typeahead pickers."""
    normalized_kind = (kind or '').strip().lower()
    if normalized_kind not in VALID_KINDS:
        return []
    clamped = _clamp_limit(limit)
    needle = (q or '').strip()
    if normalized_kind == 'workgroups':
        return _search_workgroups(needle, clamped)
    if normalized_kind == 'layers':
        return _search_layers(needle, clamped)
    return _search_waitlists(needle, clamped)
