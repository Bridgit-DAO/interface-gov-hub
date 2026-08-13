"""Build per-admin Zoho Mail contact snapshots from exported EML/ZIP files."""
from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from services.zoho_mail import aggregate_external_contacts, message_matches_meta_layer


def _decode_header_value(value: str) -> str:
    return ' '.join((value or '').split())


def _message_body_text(message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get_content_type() not in ('text/plain', 'text/html'):
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or 'utf-8'
            try:
                parts.append(payload.decode(charset, errors='replace'))
            except LookupError:
                parts.append(payload.decode('utf-8', errors='replace'))
        return '\n'.join(parts)
    payload = message.get_payload(decode=True)
    if not payload:
        return ''
    charset = message.get_content_charset() or 'utf-8'
    try:
        return payload.decode(charset, errors='replace')
    except LookupError:
        return payload.decode('utf-8', errors='replace')


def _address_headers(message, *names: str) -> list[str]:
    values: list[str] = []
    for name in names:
        raw = message.get(name)
        if not raw:
            continue
        if isinstance(raw, (list, tuple)):
            values.extend(str(item) for item in raw if str(item).strip())
        else:
            values.append(str(raw))
    return values


def _parse_eml(path: Path) -> dict | None:
    data = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(data)
    subject = _decode_header_value(message.get('subject', ''))
    body = _message_body_text(message)[:8000]
    if not message_matches_meta_layer(subject, body):
        return None

    received = ''
    date_header = message.get('date')
    if date_header:
        try:
            received = parsedate_to_datetime(date_header).isoformat()
        except (TypeError, ValueError, OverflowError):
            received = _decode_header_value(date_header)

    participants = _address_headers(message, 'from', 'to', 'cc', 'bcc')
    summary = body.strip().replace('\n', ' ')[:500]
    return {
        'subject': subject,
        'summary': summary,
        'received': received,
        'participants': participants,
    }


def _iter_eml_paths(input_path: Path):
    if input_path.is_dir():
        yield from sorted(input_path.rglob('*.eml'))
        return

    if input_path.suffix.lower() == '.zip':
        with tempfile.TemporaryDirectory(prefix='zoho-mail-export-') as tmpdir:
            with zipfile.ZipFile(input_path) as archive:
                archive.extractall(tmpdir)
            for eml_path in sorted(Path(tmpdir).rglob('*.eml')):
                yield eml_path
        return

    if input_path.suffix.lower() == '.eml':
        yield input_path
        return

    raise ValueError(f'Unsupported input path: {input_path}')


def build_snapshot(*, input_path: Path, owner_email: str, output_path: Path) -> dict:
    messages = []
    for eml_path in _iter_eml_paths(input_path):
        parsed = _parse_eml(eml_path)
        if parsed:
            messages.append(parsed)

    contacts = aggregate_external_contacts(messages, owner_email=owner_email)
    payload = {
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'source': 'zoho_mail_export',
        'owner_email': owner_email,
        'message_count': len(messages),
        'contacts': contacts,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload
