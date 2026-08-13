"""Zoho Mail API client and one-time export snapshot for admin invite pathways."""
from __future__ import annotations

import json
import os
import re
import time
from email.utils import parseaddr
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from config import INSTANCE_DIR

_TOKEN_CACHE: Dict[str, Any] = {'access_token': '', 'expires_at': 0.0}

_DEFAULT_META_LAYER_TERMS = (
    'meta-layer',
    'metalayer',
    'desirable properties',
    'desirableproperties',
    'gov hub',
    'govhub',
    'layered web',
    'workgroup',
)

_SNAPSHOT_FILENAME = 'invite_zoho_contacts_snapshot.json'
_SNAPSHOT_DIRNAME = 'invite_zoho_snapshots'


def normalize_admin_email(email: str) -> str:
    return (email or '').strip().lower()


def admin_snapshot_key(admin_email: str) -> str:
    normalized = normalize_admin_email(admin_email)
    if not normalized:
        raise ValueError('admin email is required')
    slug = normalized.replace('@', '_at_')
    slug = re.sub(r'[^a-z0-9._-]+', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('._-')
    return slug or 'admin'


def admin_snapshots_dir() -> str:
    return os.path.join(INSTANCE_DIR, _SNAPSHOT_DIRNAME)


def admin_contacts_snapshot_path(admin_email: str) -> str:
    return os.path.join(
        admin_snapshots_dir(),
        f'{admin_snapshot_key(admin_email)}.json',
    )


def zoho_mail_configured() -> bool:
    return bool(
        (os.environ.get('ZOHO_MAIL_REFRESH_TOKEN') or '').strip()
        and (os.environ.get('ZOHO_MAIL_CLIENT_ID') or '').strip()
        and (os.environ.get('ZOHO_MAIL_CLIENT_SECRET') or '').strip()
    )


def contacts_snapshot_path() -> str:
    configured = (os.environ.get('ZOHO_MAIL_CONTACTS_SNAPSHOT') or '').strip()
    if configured:
        return configured
    return os.path.join(INSTANCE_DIR, _SNAPSHOT_FILENAME)


def zoho_snapshot_configured() -> bool:
    path = contacts_snapshot_path()
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return False
    contacts = payload.get('contacts')
    return isinstance(contacts, list) and len(contacts) > 0


def zoho_mail_pathway_available() -> bool:
    return zoho_snapshot_configured() or zoho_mail_configured()


def _zoho_accounts_base() -> str:
    return (os.environ.get('ZOHO_ACCOUNTS_BASE') or 'https://accounts.zoho.com').rstrip('/')


def _zoho_mail_api_base() -> str:
    return (os.environ.get('ZOHO_MAIL_API_BASE') or 'https://mail.zoho.com/api').rstrip('/')


def meta_layer_terms() -> Tuple[str, ...]:
    raw = (os.environ.get('ZOHO_MAIL_META_LAYER_TERMS') or '').strip()
    if not raw:
        return _DEFAULT_META_LAYER_TERMS
    return tuple(term.strip() for term in raw.split(',') if term.strip())


def message_matches_meta_layer(subject: str, body: str) -> bool:
    haystack = f'{subject}\n{body}'.lower()
    return any(term in haystack for term in meta_layer_terms())


def _parse_address(value: str) -> Tuple[str, str]:
    name, email = parseaddr(value or '')
    return name.strip(), email.strip().lower()


def _owner_email() -> str:
    return (os.environ.get('ZOHO_MAIL_OWNER_EMAIL') or '').strip().lower()


def aggregate_external_contacts(
    messages: Iterable[dict],
    *,
    owner_email: str = '',
    max_contacts: int = 40,
) -> List[dict]:
    """Group message rows by external participant email."""
    owner = (owner_email or _owner_email()).strip().lower()
    contacts: Dict[str, dict] = {}

    for msg in messages:
        subject = (msg.get('subject') or '')[:200]
        summary = (msg.get('summary') or msg.get('snippet') or '')[:500]
        received = (msg.get('received') or msg.get('receivedTime') or msg.get('received_time') or '')[:40]
        participants: List[str] = []
        for key in ('participants', 'fromAddress', 'from', 'sender', 'toAddress', 'to', 'ccAddress', 'cc'):
            raw = msg.get(key)
            if isinstance(raw, str) and raw.strip():
                participants.append(raw)
            elif isinstance(raw, list):
                participants.extend(str(item) for item in raw if str(item).strip())

        for participant in participants:
            name, email = _parse_address(participant)
            if not email or (owner and email == owner):
                continue
            row = contacts.setdefault(
                email,
                {
                    'email': email,
                    'name': name or email.split('@', 1)[0],
                    'message_count': 0,
                    'subjects': [],
                    'snippets': [],
                    'last_contact': '',
                },
            )
            if name and (not row['name'] or row['name'] == row['email'].split('@', 1)[0]):
                row['name'] = name
            row['message_count'] += 1
            if subject and subject not in row['subjects']:
                row['subjects'].append(subject)
            if summary and len(row['snippets']) < 4:
                row['snippets'].append(summary)
            if received and (not row['last_contact'] or received > row['last_contact']):
                row['last_contact'] = received

    return sorted(
        contacts.values(),
        key=lambda row: (-int(row['message_count']), row.get('last_contact') or '', row['email']),
    )[:max_contacts]


def _snapshot_payload_from_file(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError('Zoho contacts snapshot must be a JSON object')
    contacts = payload.get('contacts')
    if not isinstance(contacts, list):
        raise RuntimeError('Zoho contacts snapshot is missing a contacts array')
    return {
        'configured': True,
        'source': 'snapshot',
        'snapshot_path': path,
        'owner_email': normalize_admin_email(payload.get('owner_email') or ''),
        'exported_at': payload.get('exported_at') or '',
        'message_count': int(payload.get('message_count') or 0),
        'contacts': contacts[:40],
    }


def _load_contacts_snapshot(*, admin_email: str = '') -> Optional[Dict[str, Any]]:
    owner = normalize_admin_email(admin_email)
    if owner:
        per_admin = _snapshot_payload_from_file(admin_contacts_snapshot_path(owner))
        if per_admin:
            snapshot_owner = per_admin.get('owner_email') or owner
            if snapshot_owner and snapshot_owner != owner:
                return None
            return per_admin

    legacy_path = contacts_snapshot_path()
    legacy = _snapshot_payload_from_file(legacy_path)
    if not legacy:
        return None
    snapshot_owner = legacy.get('owner_email') or ''
    if owner and snapshot_owner and snapshot_owner != owner:
        return None
    return legacy


def _not_configured_payload(*, admin_email: str = '') -> Dict[str, Any]:
    owner = normalize_admin_email(admin_email)
    snapshot_path = admin_contacts_snapshot_path(owner) if owner else contacts_snapshot_path()
    return {
        'configured': False,
        'snapshot_path': snapshot_path,
        'error': (
            'Zoho Mail is not configured. Export mail and upload the ZIP to Meta-Console agent drop, '
            'then use Ingest from agent drop in the admin invite panel, or run '
            'scripts/zoho_mail_ingest_export.py --owner YOUR_EMAIL --input PATH --output '
            f'{snapshot_path}. Alternatively set ZOHO_MAIL_CLIENT_ID, ZOHO_MAIL_CLIENT_SECRET, '
            'and ZOHO_MAIL_REFRESH_TOKEN for live API access.'
        ),
        'contacts': [],
    }


def _get_access_token() -> str:
    now = time.time()
    cached = (_TOKEN_CACHE.get('access_token') or '').strip()
    if cached and now < float(_TOKEN_CACHE.get('expires_at') or 0) - 30:
        return cached

    refresh_token = (os.environ.get('ZOHO_MAIL_REFRESH_TOKEN') or '').strip()
    client_id = (os.environ.get('ZOHO_MAIL_CLIENT_ID') or '').strip()
    client_secret = (os.environ.get('ZOHO_MAIL_CLIENT_SECRET') or '').strip()
    if not refresh_token or not client_id or not client_secret:
        raise RuntimeError('Zoho Mail OAuth is not configured')

    resp = requests.post(
        f'{_zoho_accounts_base()}/oauth/v2/token',
        params={
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token',
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f'Zoho token refresh failed ({resp.status_code})')
    data = resp.json()
    token = (data.get('access_token') or '').strip()
    if not token:
        raise RuntimeError('Zoho token refresh returned no access token')
    expires_in = int(data.get('expires_in') or 3600)
    _TOKEN_CACHE['access_token'] = token
    _TOKEN_CACHE['expires_at'] = now + expires_in
    return token


def _zoho_headers() -> Dict[str, str]:
    return {'Authorization': f'Zoho-oauthtoken {_get_access_token()}'}


def _resolve_account_id() -> str:
    configured = (os.environ.get('ZOHO_MAIL_ACCOUNT_ID') or '').strip()
    if configured:
        return configured
    resp = requests.get(f'{_zoho_mail_api_base()}/accounts', headers=_zoho_headers(), timeout=20)
    if resp.status_code >= 400:
        raise RuntimeError(f'Zoho accounts lookup failed ({resp.status_code})')
    data = resp.json()
    accounts = data.get('data') or []
    if not accounts:
        raise RuntimeError('No Zoho Mail accounts found for this token')
    primary = next((a for a in accounts if a.get('type') == 'ZOHO_ACCOUNT'), accounts[0])
    account_id = str(primary.get('accountId') or primary.get('account_id') or '').strip()
    if not account_id:
        raise RuntimeError('Could not resolve Zoho Mail account id')
    return account_id


def _search_messages(account_id: str, search_key: str, *, limit: int = 25) -> List[dict]:
    resp = requests.get(
        f'{_zoho_mail_api_base()}/accounts/{account_id}/messages/search',
        headers=_zoho_headers(),
        params={'searchKey': search_key, 'limit': min(limit, 50)},
        timeout=25,
    )
    if resp.status_code >= 400:
        return []
    payload = resp.json()
    return list(payload.get('data') or [])


def _search_live_meta_layer_contacts(*, limit_per_term: int = 20) -> Dict[str, Any]:
    account_id = _resolve_account_id()
    messages_by_id: Dict[str, dict] = {}
    for term in meta_layer_terms():
        for msg in _search_messages(account_id, f'entire:{term}', limit=limit_per_term):
            msg_id = str(msg.get('messageId') or msg.get('message_id') or '').strip()
            if msg_id:
                messages_by_id[msg_id] = msg

    contact_rows = aggregate_external_contacts(messages_by_id.values())
    return {
        'configured': True,
        'source': 'live',
        'account_id': account_id,
        'message_count': len(messages_by_id),
        'contacts': contact_rows,
    }


def search_meta_layer_contacts(
    *,
    admin_email: str = '',
    limit_per_term: int = 20,
) -> Dict[str, Any]:
    """Load meta-layer contacts from per-admin export snapshot or live Zoho Mail API."""
    owner = normalize_admin_email(admin_email)
    snapshot = _load_contacts_snapshot(admin_email=owner)
    if snapshot:
        return snapshot

    if not zoho_mail_configured():
        payload = _not_configured_payload(admin_email=owner)
        return payload

    live = _search_live_meta_layer_contacts(limit_per_term=limit_per_term)
    if owner:
        live['owner_email'] = owner
    return live
