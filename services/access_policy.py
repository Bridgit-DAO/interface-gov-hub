"""Listing visibility and join-policy helpers (layers, guilds, quests).

See docs/GOV_HUB_ACCESS_SSOT_AND_OPENAPI.md for semantics.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

LISTING_VISIBILITY = frozenset({'public', 'private'})
JOIN_POLICY_LAYER_GUILD = frozenset({'open', 'by_invitation', 'nft_gated'})
JOIN_POLICY_QUEST = frozenset({'open', 'open_to_layer', 'open_to_guild', 'by_invitation'})


def normalize_listing_visibility(raw: Optional[str], default: str = 'public') -> str:
    v = (raw or default or 'public').strip().lower()
    return v if v in LISTING_VISIBILITY else default


def normalize_join_policy_layer_guild(raw: Optional[str], default: str = 'open') -> str:
    v = (raw or default or 'open').strip().lower()
    return v if v in JOIN_POLICY_LAYER_GUILD else default


def normalize_join_policy_quest(raw: Optional[str], default: str = 'open') -> str:
    v = (raw or default or 'open').strip().lower()
    return v if v in JOIN_POLICY_QUEST else default


def active_layer_member(layer_id: str, user_id: str) -> bool:
    from models import LayerMember

    return (
        LayerMember.query.filter_by(
            layer_id=layer_id, user_id=user_id, status='active'
        ).first()
        is not None
    )


def layer_listing_visible(layer, user: Optional[Dict[str, Any]]) -> bool:
    from services.coordination import is_layer_admin

    vis = getattr(layer, 'listing_visibility', None) or 'public'
    if vis != 'private':
        return True
    if not user:
        return False
    if is_layer_admin(layer, user):
        return True
    return active_layer_member(layer.id, user['id'])


def guild_listing_visible(guild, user: Optional[Dict[str, Any]]) -> bool:
    from models import GuildMembership

    vis = getattr(guild, 'listing_visibility', None) or 'public'
    if vis != 'private':
        return True
    if not user:
        return False
    m = GuildMembership.query.filter_by(
        guild_id=guild.id, user_id=user['id'], membership_state='active'
    ).first()
    return m is not None


def quest_listing_visible(quest, user: Optional[Dict[str, Any]]) -> bool:
    from models import Layer
    from services.coordination import is_layer_admin

    vis = getattr(quest, 'listing_visibility', None) or 'public'
    if vis != 'private':
        return True
    if not user:
        return False
    layer = Layer.query.get(quest.layer_id)
    if not layer:
        return False
    if is_layer_admin(layer, user):
        return True
    if quest.creator_user_id and quest.creator_user_id == user['id']:
        return True
    return active_layer_member(quest.layer_id, user['id'])


def user_in_linked_guild_for_quest(quest_id: str, user_id: str) -> bool:
    from models import GuildMembership, GuildQuestLink

    links = GuildQuestLink.query.filter_by(quest_id=quest_id).all()
    for ln in links:
        m = GuildMembership.query.filter_by(
            guild_id=ln.guild_id, user_id=user_id, membership_state='active'
        ).first()
        if m:
            return True
    return False


def can_user_submit_quest(quest, user: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Return (allowed, error_message)."""
    from models import Layer
    from services.coordination import is_layer_admin

    jp = getattr(quest, 'join_policy', None) or 'open'
    uid = user['id']

    if jp == 'open':
        return True, None
    if jp == 'open_to_layer':
        if active_layer_member(quest.layer_id, uid):
            return True, None
        return False, 'This quest is limited to members of its layer.'
    if jp == 'open_to_guild':
        if user_in_linked_guild_for_quest(quest.id, uid):
            return True, None
        return False, 'This quest is limited to members of guilds linked to the quest.'
    if jp == 'by_invitation':
        if quest.creator_user_id == uid:
            return True, None
        layer = Layer.query.get(quest.layer_id)
        if layer and is_layer_admin(layer, user):
            return True, None
        return False, 'This quest requires an invitation to participate.'
    return True, None
