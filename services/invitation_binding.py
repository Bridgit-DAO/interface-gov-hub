"""Shareable vs private invitation policy (layers, platform invites)."""
from __future__ import annotations

from typing import Optional, Tuple

from models import Layer, PlatformInvitation, Workgroup

# Platform types that are always shareable (open campaign links).
PLATFORM_SHAREABLE_TYPES = frozenset({
    'participate_dp',
    'edit_document',
    'edit_document_passage',
})

# Platform types that stay private (email-bound) unless layer is public for workgroup.
PLATFORM_PRIVATE_TYPES = frozenset({
    'review_document',
    'join_workgroup',
})

BINDING_SHAREABLE = 'shareable'
BINDING_PRIVATE = 'private'


def layer_listing_is_public(layer: Optional[Layer]) -> bool:
    if not layer:
        return False
    return (getattr(layer, 'listing_visibility', None) or 'public') == 'public'


def platform_invite_is_shareable(invite_type: str, target: Optional[dict] = None) -> bool:
    """Whether this platform invitation should use a multi-use shareable link."""
    invite_type = (invite_type or '').strip()
    if invite_type in PLATFORM_SHAREABLE_TYPES:
        return True
    if invite_type == 'join_workgroup':
        target = target if isinstance(target, dict) else {}
        wg_id = (target.get('workgroup_id') or '').strip()
        if not wg_id:
            return False
        wg = Workgroup.query.get(wg_id)
        if not wg:
            return False
        return layer_listing_is_public(wg.layer)
    if invite_type == 'review_document':
        return False
    return False


def layer_invite_is_shareable(layer: Optional[Layer]) -> bool:
    """Public layers use one shareable join link; private layers use private invites."""
    return layer_listing_is_public(layer)


def invitation_is_shareable(
    binding_mode: Optional[str],
    *,
    invite_type: Optional[str] = None,
    target: Optional[dict] = None,
    layer: Optional[Layer] = None,
) -> bool:
    mode = (binding_mode or '').strip().lower()
    if mode == BINDING_SHAREABLE:
        return True
    if mode == BINDING_PRIVATE:
        return False
    if layer is not None:
        return layer_invite_is_shareable(layer)
    if invite_type:
        return platform_invite_is_shareable(invite_type, target)
    return False


def platform_invitation_is_shareable(inv: PlatformInvitation) -> bool:
    return invitation_is_shareable(
        getattr(inv, 'binding_mode', None),
        invite_type=inv.invite_type,
        target=_load_target_safe(inv),
    )


def layer_invitation_is_shareable(inv, layer: Optional[Layer] = None) -> bool:
    if layer is None and getattr(inv, 'layer_id', None):
        layer = Layer.query.get(inv.layer_id)
    return invitation_is_shareable(
        getattr(inv, 'binding_mode', None),
        layer=layer,
    )


def _load_target_safe(inv: PlatformInvitation) -> dict:
    import json
    try:
        data = json.loads(inv.target_json or '{}')
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def resolve_platform_binding_mode(invite_type: str, target: Optional[dict]) -> str:
    return BINDING_SHAREABLE if platform_invite_is_shareable(invite_type, target) else BINDING_PRIVATE


def resolve_layer_binding_mode(layer: Layer) -> str:
    return BINDING_SHAREABLE if layer_invite_is_shareable(layer) else BINDING_PRIVATE
