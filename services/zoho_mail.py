"""Zoho Mail API client for admin invite research pathways."""
from __future__ import annotations

import os
import time
from email.utils import parseaddr
from typing import Any, Dict, List, Optional, Tuple

import requests

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


def zoho_mail_configured() -> bool:
    return bool(
        (os.environ.get('ZOHO_MAIL_REFRESH_TOKEN') or '').strip()
        and (os.environ.get('ZOHO_MAIL_CLIENT_ID') or '').strip()
        and (os.environ.get('ZOHO_MAIL_CLIENT_SECRET') or '').strip()
    )


def _zoho_accounts_base() -> str:
    return (os.environ.get('ZOHO_ACCOUNTS_BASE') or 'https://accounts.zoho.com').rstrip('/')


def _zoho_mail_api_base() -> str:
    return (os.environ.get('ZOHO_MAIL_API_BASE') or 'https://mail.zoho.com/api').rstrip('/')


def _meta_layer_terms() -> Tuple[str, ...]:
    raw = (os.environ.get('ZOHO_MAIL_META_LAYER_TERMS') or '').strip()
    if not raw:
        return _DEFAULT_META_LAYER_TERMS
    return tuple(term.strip() for term in raw.split(',') if term.strip())


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


def _parse_address(value: str) -> Tuple[str, str]:
    name, email = parseaddr(value or '')
    return name.strip(), email.strip().lower()


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


def search_meta_layer_contacts(*, limit_per_term: int = 20) -> Dict[str, Any]:
    """Search Zoho Mail for meta-layer related threads and group by external contact."""
    if not zoho_mail_configured():
        return {
            'configured': False,
            'error': (
                'Zoho Mail is not configured. Set ZOHO_MAIL_CLIENT_ID, ZOHO_MAIL_CLIENT_SECRET, '
                'and ZOHO_MAIL_REFRESH_TOKEN on Gov Hub.'
            ),
            'contacts': [],
        }

    account_id = _resolve_account_id()
    owner_email = (os.environ.get('ZOHO_MAIL_OWNER_EMAIL') or '').strip().lower()

    messages_by_id: Dict[str, dict] = {}
    for term in _meta_layer_terms():
        for msg in _search_messages(account_id, f'entire:{term}', limit=limit_per_term):
            msg_id = str(msg.get('messageId') or msg.get('message_id') or '').strip()
            if msg_id:
                messages_by_id[msg_id] = msg

    contacts: Dict[str, dict] = {}
    for msg in messages_by_id.values():
        subject = (msg.get('subject') or '')[:200]
        summary = (msg.get('summary') or msg.get('snippet') or '')[:500]
        received = (msg.get('receivedTime') or msg.get('received_time') or '')[:40]
        participants = []
        for key in ('fromAddress', 'from', 'sender', 'toAddress', 'to', 'ccAddress', 'cc'):
            raw = msg.get(key)
            if isinstance(raw, str) and raw.strip():
                participants.append(raw)
            elif isinstance(raw, list):
                participants.extend(str(item) for item in raw if str(item).strip())

        for participant in participants:
            name, email = _parse_address(participant)
            if not email or (owner_email and email == owner_email):
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

    contact_rows = sorted(
        contacts.values(),
        key=lambda row: (-int(row['message_count']), row.get('last_contact') or '', row['email']),
    )
    return {
        'configured': True,
        'account_id': account_id,
        'message_count': len(messages_by_id),
        'contacts': contact_rows[:40],
    }
