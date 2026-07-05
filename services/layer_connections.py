"""Layer organizational connections – types, submissions, review (MVP)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from extensions import db
from models import (
    Guild,
    GuildMembership,
    Layer,
    LayerConnection,
    LayerConnectionType,
    LAYER_CONNECTION_CONNECTOR_KINDS,
    LAYER_CONNECTION_STATUSES,
    User,
)
from services.coordination import is_layer_admin
from services.events import emit_event
from services.guild_phase1 import is_guild_officer
from services.utils import create_slug


def resolve_layer(layer_ref: str) -> Optional[Layer]:
    if not layer_ref:
        return None
    row = Layer.query.get(layer_ref)
    if row:
        return row
    return Layer.query.filter_by(slug=layer_ref).first()


def _user_row(user_id: str) -> Optional[User]:
    return User.query.get(user_id) if user_id else None


def enrich_connection(conn: LayerConnection, include_admin: bool = False) -> Dict[str, Any]:
    d = conn.to_dict(include_admin=include_admin)
    ct = conn.connection_type
    if ct:
        d['connection_type'] = {
            'id': ct.id,
            'title': ct.title,
            'slug': ct.slug,
        }
    if conn.guild:
        d['guild'] = {'id': conn.guild.id, 'name': conn.guild.name, 'slug': conn.guild.slug, 'image_url': conn.guild.image_url}
    if conn.source_layer:
        d['source_layer'] = {
            'id': conn.source_layer.id,
            'name': conn.source_layer.name,
            'slug': conn.source_layer.slug,
            'image_url': conn.source_layer.image_url,
        }
    if conn.representative:
        d['representative'] = {
            'id': conn.representative.id,
            'username': conn.representative.username,
            'displayName': conn.representative.displayName or conn.representative.username,
        }
    d['display_name'] = connection_display_name(conn)
    d['display_url'] = connection_display_url(conn)
    return d


def connection_display_name(conn: LayerConnection) -> str:
    if conn.connector_kind == 'guild' and conn.guild:
        return conn.guild.name
    if conn.connector_kind == 'layer' and conn.source_layer:
        return conn.source_layer.name
    if conn.connector_kind == 'external':
        return conn.external_name or 'External organization'
    if conn.connector_kind == 'individual' and conn.representative:
        return conn.representative.displayName or conn.representative.username
    return 'Connection'


def connection_display_url(conn: LayerConnection) -> Optional[str]:
    if conn.connector_kind == 'guild' and conn.guild:
        return f'/guilds/{conn.guild.slug}/'
    if conn.connector_kind == 'layer' and conn.source_layer:
        return f'/layers/{conn.source_layer.slug}/'
    if conn.connector_kind == 'external':
        return conn.external_url
    if conn.connector_kind == 'individual' and conn.representative:
        return f'/profile/{conn.representative.username}/'
    return None


def list_connection_types(layer_id: str, active_only: bool = False) -> List[LayerConnectionType]:
    q = LayerConnectionType.query.filter_by(layer_id=layer_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.order_by(LayerConnectionType.sort_order.asc(), LayerConnectionType.title.asc()).all()


def create_connection_type(layer: Layer, user: Dict[str, Any], data: Dict[str, Any]) -> LayerConnectionType:
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('title is required')
    slug = (data.get('slug') or create_slug(title)).strip().lower()[:120]
    if LayerConnectionType.query.filter_by(layer_id=layer.id, slug=slug).first():
        raise ValueError('A connection type with this slug already exists')
    row = LayerConnectionType(
        id=str(uuid4()),
        layer_id=layer.id,
        title=title,
        slug=slug,
        description=(data.get('description') or '').strip() or None,
        agreement_text=(data.get('agreement_text') or '').strip() or None,
        requires_approval=bool(data.get('requires_approval', True)),
        is_open=bool(data.get('is_open', True)),
        sort_order=int(data.get('sort_order') or 0),
        is_active=bool(data.get('is_active', True)),
        terms_version=1,
    )
    db.session.add(row)
    db.session.flush()
    emit_event(
        'layer_connection_type_created',
        actor_type='user',
        actor_id=user['id'],
        subject_type='layer_connection_type',
        subject_id=row.id,
        layer_id=layer.id,
        payload={'title': row.title, 'slug': row.slug},
    )
    return row


def update_connection_type(row: LayerConnectionType, data: Dict[str, Any]) -> LayerConnectionType:
    if 'title' in data and data['title']:
        row.title = str(data['title']).strip()
    if 'description' in data:
        row.description = (data.get('description') or '').strip() or None
    if 'agreement_text' in data:
        new_text = (data.get('agreement_text') or '').strip() or None
        if new_text != (row.agreement_text or None):
            row.agreement_text = new_text
            row.terms_version = (row.terms_version or 1) + 1
    if 'requires_approval' in data:
        row.requires_approval = bool(data['requires_approval'])
    if 'is_open' in data:
        row.is_open = bool(data['is_open'])
    if 'sort_order' in data:
        row.sort_order = int(data['sort_order'] or 0)
    if 'is_active' in data:
        row.is_active = bool(data['is_active'])
    row.updated_at = datetime.utcnow()
    return row


def _can_submit_for_guild(user_id: str, guild_id: str) -> bool:
    return is_guild_officer(guild_id, user_id)


def _can_submit_for_layer(user_id: str, source_layer_id: str) -> bool:
    src = Layer.query.get(source_layer_id)
    if not src:
        return False
    return is_layer_admin(src, {'id': user_id})


def _duplicate_active(
    layer_id: str,
    type_id: str,
    connector_kind: str,
    *,
    guild_id=None,
    source_layer_id=None,
    external_url=None,
    representative_user_id=None,
) -> bool:
    q = LayerConnection.query.filter_by(
        layer_id=layer_id,
        connection_type_id=type_id,
        connector_kind=connector_kind,
        status='active',
    )
    if connector_kind == 'guild':
        q = q.filter_by(guild_id=guild_id)
    elif connector_kind == 'layer':
        q = q.filter_by(source_layer_id=source_layer_id)
    elif connector_kind == 'external':
        q = q.filter_by(external_url=(external_url or '').strip().lower())
    elif connector_kind == 'individual':
        q = q.filter_by(representative_user_id=representative_user_id)
    return q.first() is not None


def submit_connection(layer: Layer, user: Dict[str, Any], data: Dict[str, Any]) -> LayerConnection:
    type_id = data.get('connection_type_id')
    ct = LayerConnectionType.query.filter_by(id=type_id, layer_id=layer.id, is_active=True).first()
    if not ct:
        raise ValueError('Connection type not found or inactive')
    if not ct.is_open:
        raise ValueError('This connection type is not accepting applications')

    connector_kind = (data.get('connector_kind') or '').strip().lower()
    if connector_kind not in LAYER_CONNECTION_CONNECTOR_KINDS:
        raise ValueError('Invalid connector_kind')

    agreement_accepted = bool(data.get('agreement_accepted'))
    if ct.agreement_text and not agreement_accepted:
        raise ValueError('You must accept the agreement to apply')

    guild_id = source_layer_id = external_name = external_url = representative_user_id = None

    if connector_kind == 'guild':
        guild_id = data.get('guild_id')
        guild = Guild.query.get(guild_id)
        if not guild:
            raise ValueError('Guild not found')
        if not _can_submit_for_guild(user['id'], guild.id):
            raise ValueError('You must be a guild officer to submit on behalf of this guild')
    elif connector_kind == 'layer':
        source_layer_id = data.get('source_layer_id')
        src = Layer.query.get(source_layer_id)
        if not src:
            raise ValueError('Source layer not found')
        if src.id == layer.id:
            raise ValueError('A layer cannot connect to itself')
        if not _can_submit_for_layer(user['id'], src.id):
            raise ValueError('You must be an admin of the connecting layer')
    elif connector_kind == 'external':
        external_name = (data.get('external_name') or '').strip()
        external_url = (data.get('external_url') or '').strip()
        if not external_name:
            raise ValueError('external_name is required')
        if not external_url:
            raise ValueError('external_url is required')
    elif connector_kind == 'individual':
        representative_user_id = data.get('representative_user_id') or user['id']
        rep = _user_row(representative_user_id)
        if not rep:
            raise ValueError('Representative user not found')
        if representative_user_id != user['id']:
            raise ValueError('You can only apply as yourself for now')

    if _duplicate_active(
        layer.id,
        ct.id,
        connector_kind,
        guild_id=guild_id,
        source_layer_id=source_layer_id,
        external_url=external_url,
        representative_user_id=representative_user_id,
    ):
        raise ValueError('An active connection of this type already exists')

    force_pending = connector_kind == 'layer'
    auto_active = not force_pending and not ct.requires_approval
    status = 'active' if auto_active else 'pending'
    now = datetime.utcnow()

    conn = LayerConnection(
        id=str(uuid4()),
        layer_id=layer.id,
        connection_type_id=ct.id,
        connector_kind=connector_kind,
        guild_id=guild_id,
        source_layer_id=source_layer_id,
        external_name=external_name,
        external_url=external_url.lower().rstrip('/') if external_url else None,
        representative_user_id=representative_user_id,
        status=status,
        message=(data.get('message') or '').strip() or None,
        agreement_accepted_at=now if agreement_accepted or ct.agreement_text else None,
        agreement_version=ct.terms_version if agreement_accepted or ct.agreement_text else None,
        submitted_by_user_id=user['id'],
        reviewed_by_user_id=user['id'] if auto_active else None,
        reviewed_at=now if auto_active else None,
    )
    db.session.add(conn)
    db.session.flush()
    emit_event(
        'layer_connection_submitted',
        actor_type='user',
        actor_id=user['id'],
        subject_type='layer_connection',
        subject_id=conn.id,
        layer_id=layer.id,
        payload={
            'connector_kind': connector_kind,
            'connection_type': ct.title,
            'status': status,
            'display_name': connection_display_name(conn),
        },
    )
    return conn


def review_connection(
    conn: LayerConnection,
    reviewer: Dict[str, Any],
    *,
    approve: bool,
    notes: Optional[str] = None,
    rejected_reason: Optional[str] = None,
) -> LayerConnection:
    if conn.status != 'pending':
        raise ValueError('Only pending connections can be reviewed')
    now = datetime.utcnow()
    conn.reviewed_by_user_id = reviewer['id']
    conn.reviewed_at = now
    conn.review_notes = (notes or '').strip() or None
    if approve:
        conn.status = 'active'
        conn.rejected_reason = None
        event = 'layer_connection_approved'
    else:
        conn.status = 'rejected'
        conn.rejected_reason = (rejected_reason or notes or 'Rejected').strip()
        event = 'layer_connection_rejected'
    conn.updated_at = now
    emit_event(
        event,
        actor_type='user',
        actor_id=reviewer['id'],
        subject_type='layer_connection',
        subject_id=conn.id,
        layer_id=conn.layer_id,
        payload={'display_name': connection_display_name(conn)},
    )
    return conn


def withdraw_connection(conn: LayerConnection, user: Dict[str, Any]) -> LayerConnection:
    if conn.status not in ('pending', 'active'):
        raise ValueError('Cannot withdraw this connection')
    if conn.submitted_by_user_id != user['id']:
        layer = Layer.query.get(conn.layer_id)
        if not layer or not is_layer_admin(layer, user):
            raise ValueError('Forbidden')
    conn.status = 'withdrawn'
    conn.updated_at = datetime.utcnow()
    return conn


def revoke_connection(conn: LayerConnection, reviewer: Dict[str, Any], reason: Optional[str] = None) -> LayerConnection:
    if conn.status != 'active':
        raise ValueError('Only active connections can be revoked')
    conn.status = 'revoked'
    conn.review_notes = (reason or conn.review_notes or '').strip() or None
    conn.reviewed_by_user_id = reviewer['id']
    conn.reviewed_at = datetime.utcnow()
    conn.updated_at = datetime.utcnow()
    emit_event(
        'layer_connection_revoked',
        actor_type='user',
        actor_id=reviewer['id'],
        subject_type='layer_connection',
        subject_id=conn.id,
        layer_id=conn.layer_id,
        payload={'display_name': connection_display_name(conn)},
    )
    return conn
