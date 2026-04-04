"""Unified Phase I guild ↔ layer / guild ↔ artifact links (separate from artifact ↔ artifact)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from models import Artifact, Guild, GuildMembership, Layer, LayerMember

GUILD_ARTIFACT_LINK_TYPES = frozenset({'sponsor', 'co_author', 'review'})


def is_guild_officer(guild_id: str, user_id: str) -> bool:
    m = GuildMembership.query.filter_by(guild_id=guild_id, user_id=user_id).first()
    if not m:
        return False
    if getattr(m, 'membership_state', 'active') != 'active':
        return False
    return m.role in ('initiator', 'admin')


def active_layer_member(layer_id: str, user_id: str) -> bool:
    return (
        LayerMember.query.filter_by(
            layer_id=layer_id, user_id=user_id, status='active'
        ).first()
        is not None
    )


def can_manage_guild_layer_link(user: Optional[Dict[str, Any]], guild: Guild, layer: Layer) -> bool:
    """Layer admin, or guild officer who is also an active member of the layer."""
    if not user:
        return False
    from services.coordination import is_layer_admin

    if is_layer_admin(layer, user):
        return True
    if is_guild_officer(guild.id, user['id']) and active_layer_member(layer.id, user['id']):
        return True
    return False


def can_manage_guild_artifact_link(
    user: Optional[Dict[str, Any]], guild: Guild, artifact: Artifact
) -> bool:
    """Guild officer plus layer admin or active layer member (artifact's layer)."""
    if not user or not artifact.layer_id:
        return False
    layer = Layer.query.get(artifact.layer_id)
    if not layer:
        return False
    if not is_guild_officer(guild.id, user['id']):
        return False
    from services.coordination import is_layer_admin

    if is_layer_admin(layer, user):
        return True
    if active_layer_member(layer.id, user['id']):
        return True
    return False
