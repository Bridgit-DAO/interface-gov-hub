"""Build per-admin Zoho Mail contact snapshots from exported EML/ZIP files."""
from __future__ import annotations

import getpass
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

from services.zoho_mail import aggregate_external_contacts, message_matches_meta_layer, meta_layer_terms

_DEFAULT_ALLOWLIST_DOMAINS = (
    'bridgit.io',
    'metalayer.world',
    'metalayer.io',
    'govhub.io',
    'gov-hub.io',
    'desirableproperties.org',
    'desirableproperties.com',
    'contextcoding.com',
    'overweb.io',
    'canopi.live',
    'daveedbenjamin.com',
)

_DEFAULT_INCLUDE_FOLDERS = (
    'Inbox',
    'Sent',
    'Drafts',
    'Submissions',
    'Non-submissions',
    'SIG',
    'Interns',
    'Templates',
)


def allowlist_domains() -> Tuple[str, ...]:
    raw = (os.environ.get('ZOHO_MAIL_ALLOWLIST_DOMAINS') or '').strip()
    if not raw:
        return _DEFAULT_ALLOWLIST_DOMAINS
    return tuple(domain.strip().lower() for domain in raw.split(',') if domain.strip())


def export_password() -> str:
    value = (os.environ.get('ZOHO_MAIL_EXPORT_PASSWORD') or '').strip()
    if value:
        return value
    # config.load_dotenv may not run when this module is imported alone
    try:
        from dotenv import dotenv_values

        env_path = Path(__file__).resolve().parents[1] / '.env'
        if env_path.is_file():
            return (dotenv_values(env_path).get('ZOHO_MAIL_EXPORT_PASSWORD') or '').strip()
    except Exception:
        pass
    return ''


def resolve_export_password(cli_password: str = '') -> str:
    return (cli_password or export_password()).strip()


def prompt_export_password_if_needed(
    input_paths: Sequence[Path],
    password: str,
    *,
    prompt: str = 'Zoho export ZIP password: ',
) -> str:
    if password:
        return password
    zip_paths = [path for path in input_paths if path.suffix.lower() == '.zip']
    if not zip_paths:
        return ''
    metadata = inspect_export_metadata(zip_paths)
    if int(metadata.get('encrypted_eml_entries') or 0) <= 0:
        return ''
    if sys.stdin.isatty():
        entered = getpass.getpass(prompt).strip()
        if entered:
            return entered
    return ''


def _zip_decrypt_runtime_error(
    exc: BaseException,
    archive_name: str,
    *,
    password_provided: bool,
) -> RuntimeError:
    message = str(exc).lower()
    if 'bad password' in message:
        return RuntimeError(
            f'Wrong export password for {archive_name}. '
            'Use the password set in Zoho Mail → Settings → Mail Accounts → Export. '
            'If passing via shell, quote special characters (e.g. --password \'your pass\').',
        )
    if password_provided:
        return RuntimeError(f'Could not decrypt {archive_name}: {exc}')
    return RuntimeError(
        f'Encrypted export requires --password, ZOHO_MAIL_EXPORT_PASSWORD, '
        f'or an interactive prompt ({archive_name})',
    )


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


def _participant_emails(participants: Sequence[str]) -> List[str]:
    emails: List[str] = []
    for participant in participants:
        _, email = parseaddr(participant or '')
        cleaned = email.strip().lower()
        if cleaned:
            emails.append(cleaned)
    return emails


def participant_matches_allowlist(
    participants: Sequence[str],
    *,
    domains: Optional[Sequence[str]] = None,
) -> bool:
    allowed = tuple(domain.lower() for domain in (domains or allowlist_domains()))
    for email in _participant_emails(participants):
        domain = email.split('@', 1)[-1]
        if any(domain == allowed_domain or domain.endswith(f'.{allowed_domain}') for allowed_domain in allowed):
            return True
    return False


def message_matches_filters(
    subject: str,
    body: str,
    participants: Sequence[str],
    *,
    domains: Optional[Sequence[str]] = None,
) -> bool:
    if message_matches_meta_layer(subject, body):
        return True
    allow_allowlist = (os.environ.get('ZOHO_MAIL_ALLOW_ALLOWLIST_MESSAGES') or '').strip().lower() in {
        '1',
        'true',
        'yes',
    }
    if allow_allowlist:
        return participant_matches_allowlist(participants, domains=domains)
    return False


def _zip_folder_name(entry_name: str) -> str:
    parts = entry_name.split('/')
    return parts[0] if len(parts) > 1 else ''


def _folder_allowed(entry_name: str, include_folders: Optional[Sequence[str]]) -> bool:
    if not include_folders:
        return True
    folder = _zip_folder_name(entry_name)
    if not folder:
        return True
    allowed = {name.strip() for name in include_folders if name.strip()}
    return folder in allowed


def parse_eml_bytes(data: bytes, *, domains: Optional[Sequence[str]] = None) -> dict | None:
    message = BytesParser(policy=policy.default).parsebytes(data)
    subject = _decode_header_value(message.get('subject', ''))
    body = _message_body_text(message)[:8000]
    participants = _address_headers(message, 'from', 'to', 'cc', 'bcc')
    if not message_matches_filters(subject, body, participants, domains=domains):
        return None

    received = ''
    date_header = message.get('date')
    if date_header:
        try:
            received = parsedate_to_datetime(date_header).isoformat()
        except (TypeError, ValueError, OverflowError):
            received = _decode_header_value(date_header)

    summary = body.strip().replace('\n', ' ')[:500]
    keyword_hits = sum(1 for term in meta_layer_terms() if term in f'{subject}\n{body}'.lower())
    return {
        'subject': subject,
        'summary': summary,
        'received': received,
        'participants': participants,
        'keyword_hits': keyword_hits,
    }


def _parse_eml(path: Path, *, domains: Optional[Sequence[str]] = None) -> dict | None:
    return parse_eml_bytes(path.read_bytes(), domains=domains)


def resolve_export_inputs(raw_inputs: Sequence[str]) -> List[Path]:
    paths: List[Path] = []
    for raw in raw_inputs:
        candidate = Path(raw).expanduser()
        if any(ch in raw for ch in ('*', '?', '[')):
            glob_root = candidate.parent if candidate.parent != Path('.') else Path('/home/ubuntu')
            pattern = candidate.name if candidate.name else raw
            paths.extend(sorted(glob_root.glob(pattern)))
            continue
        resolved = candidate.resolve()
        if resolved.is_dir():
            paths.extend(sorted(resolved.rglob('*.zip')))
            paths.extend(sorted(resolved.rglob('*.eml')))
            continue
        if resolved.exists():
            paths.append(resolved)
    deduped: List[Path] = []
    seen = set()
    for path in paths:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path.resolve())
    return deduped


def inspect_export_metadata(input_paths: Sequence[Path]) -> dict:
    zip_rows = []
    corrupt = []
    folder_counts: Counter[str] = Counter()
    total_eml = 0
    encrypted_eml = 0

    for path in input_paths:
        if path.suffix.lower() != '.zip':
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                infos = [info for info in archive.infolist() if info.filename.lower().endswith('.eml')]
                encrypted = sum(1 for info in infos if info.flag_bits & 0x1)
                folders = Counter(_zip_folder_name(info.filename) or '(root)' for info in infos)
                row = {
                    'path': str(path),
                    'eml_count': len(infos),
                    'encrypted_eml_count': encrypted,
                    'compressed_bytes': path.stat().st_size,
                    'folders': dict(folders),
                }
                zip_rows.append(row)
                total_eml += len(infos)
                encrypted_eml += encrypted
                folder_counts.update(folders)
        except zipfile.BadZipFile as exc:
            corrupt.append({'path': str(path), 'error': str(exc)})

    return {
        'zip_count': len(zip_rows),
        'corrupt_zips': corrupt,
        'total_eml_entries': total_eml,
        'encrypted_eml_entries': encrypted_eml,
        'folder_counts': dict(folder_counts.most_common()),
        'zips': zip_rows,
        'meta_layer_terms': list(meta_layer_terms()),
        'allowlist_domains': list(allowlist_domains()),
    }


def iter_export_messages(
    input_paths: Sequence[Path],
    *,
    password: str = '',
    domains: Optional[Sequence[str]] = None,
    include_folders: Optional[Sequence[str]] = None,
    sample_per_zip: int = 0,
    max_messages: int = 0,
    yield_scan_stats: bool = False,
    report_progress: bool = False,
) -> Iterator[dict]:
    emitted = 0
    zip_total = sum(1 for path in input_paths if path.suffix.lower() == '.zip')
    zip_index = 0
    for input_path in input_paths:
        if input_path.suffix.lower() == '.eml':
            stats = {'scanned_eml': 1, 'matched_eml': 0, 'source_entry': str(input_path)}
            parsed = _parse_eml(input_path, domains=domains)
            if parsed:
                stats['matched_eml'] = 1
                if yield_scan_stats:
                    yield {'_scan': stats}
                yield parsed
                emitted += 1
                if max_messages and emitted >= max_messages:
                    return
            elif yield_scan_stats:
                yield {'_scan': stats}
            continue

        if input_path.suffix.lower() != '.zip':
            continue

        zip_index += 1
        if report_progress:
            label = input_path.name
            if sample_per_zip:
                print(
                    f'[{zip_index}/{zip_total}] {label}: listing entries…',
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(f'[{zip_index}/{zip_total}] {label}: scanning…', file=sys.stderr, flush=True)

        with zipfile.ZipFile(input_path) as archive:
            if password:
                archive.setpassword(password.encode('utf-8'))
            names = sorted(
                info.filename
                for info in archive.infolist()
                if info.filename.lower().endswith('.eml') and _folder_allowed(info.filename, include_folders)
            )
            if sample_per_zip:
                names = names[:sample_per_zip]
            if report_progress:
                print(
                    f'[{zip_index}/{zip_total}] {label}: decrypting {len(names):,} EML…',
                    file=sys.stderr,
                    flush=True,
                )
            for entry_index, name in enumerate(names, start=1):
                stats = {'scanned_eml': 1, 'matched_eml': 0, 'source_entry': name}
                try:
                    parsed = parse_eml_bytes(archive.read(name), domains=domains)
                except RuntimeError as exc:
                    err_text = str(exc).lower()
                    if 'password' in err_text or 'encrypted' in err_text:
                        raise _zip_decrypt_runtime_error(
                            exc,
                            input_path.name,
                            password_provided=bool(password),
                        ) from exc
                    raise
                except zipfile.BadZipFile as exc:
                    err_text = str(exc).lower()
                    if password and ('password' in err_text or 'decrypt' in err_text):
                        raise _zip_decrypt_runtime_error(
                            exc,
                            input_path.name,
                            password_provided=True,
                        ) from exc
                    raise RuntimeError(f'Could not read encrypted entry in {input_path.name}: {exc}') from exc
                if parsed:
                    stats['matched_eml'] = 1
                    parsed['_source_entry'] = name
                    if yield_scan_stats:
                        yield {'_scan': stats}
                    yield parsed
                    emitted += 1
                    if max_messages and emitted >= max_messages:
                        return
                elif yield_scan_stats:
                    yield {'_scan': stats}
                if report_progress and entry_index % 10 == 0:
                    print(
                        f'[{zip_index}/{zip_total}] {label}: {entry_index}/{len(names)} EML',
                        file=sys.stderr,
                        flush=True,
                    )
            if report_progress:
                print(
                    f'[{zip_index}/{zip_total}] {label}: done ({len(names):,} EML)',
                    file=sys.stderr,
                    flush=True,
                )


def _iter_eml_paths(input_path: Path, *, password: str = ''):
    if input_path.is_dir():
        yield from sorted(input_path.rglob('*.eml'))
        return

    if input_path.suffix.lower() == '.zip':
        if password:
            with zipfile.ZipFile(input_path) as archive:
                archive.setpassword(password.encode('utf-8'))
                with tempfile.TemporaryDirectory(prefix='zoho-mail-export-') as tmpdir:
                    archive.extractall(tmpdir)
                for eml_path in sorted(Path(tmpdir).rglob('*.eml')):
                    yield eml_path
            return
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


def analyze_export(
    input_paths: Sequence[Path],
    *,
    password: str = '',
    owner_email: str = '',
    domains: Optional[Sequence[str]] = None,
    include_folders: Optional[Sequence[str]] = None,
    sample_per_zip: int = 0,
    max_messages: int = 0,
    report_progress: bool = False,
) -> dict:
    metadata = inspect_export_metadata([path for path in input_paths if path.suffix.lower() == '.zip'])
    stats = {
        'scanned_eml': 0,
        'matched_eml': 0,
        'decrypt_errors': 0,
        'matched_by_keyword': 0,
        'matched_by_allowlist_only': 0,
        'folder_hits': Counter(),
    }
    messages: List[dict] = []

    try:
        for item in iter_export_messages(
            input_paths,
            password=password,
            domains=domains,
            include_folders=include_folders,
            sample_per_zip=sample_per_zip,
            max_messages=max_messages,
            yield_scan_stats=True,
            report_progress=report_progress,
        ):
            if '_scan' in item:
                stats['scanned_eml'] += int(item['_scan'].get('scanned_eml') or 0)
                stats['matched_eml'] += int(item['_scan'].get('matched_eml') or 0)
                continue
            folder = _zip_folder_name(item.get('_source_entry', '')) or '(unknown)'
            stats['folder_hits'][folder] += 1
            if int(item.get('keyword_hits') or 0) > 0:
                stats['matched_by_keyword'] += 1
            else:
                stats['matched_by_allowlist_only'] += 1
            clean = dict(item)
            clean.pop('_source_entry', None)
            messages.append(clean)
    except RuntimeError as exc:
        err_text = str(exc).lower()
        if any(token in err_text for token in ('password', 'encrypted', 'decrypt')):
            stats['decrypt_errors'] += 1
            metadata['password_error'] = str(exc)
            metadata['password_required'] = 'wrong export password' not in err_text
            metadata['password_rejected'] = 'wrong export password' in err_text
        else:
            raise

    contacts = aggregate_external_contacts(messages, owner_email=owner_email)
    metadata.update(
        {
            'owner_email': owner_email,
            'include_folders': list(include_folders or []),
            'sample_per_zip': sample_per_zip,
            'scanned_eml': stats['scanned_eml'],
            'matched_eml': stats['matched_eml'],
            'matched_by_keyword': stats['matched_by_keyword'],
            'matched_by_allowlist_only': stats['matched_by_allowlist_only'],
            'decrypt_errors': stats['decrypt_errors'],
            'folder_hits': dict(stats['folder_hits']),
            'top_contacts': contacts[:15],
            'estimated_snapshot_contacts': len(contacts),
        },
    )
    return metadata


def prune_snapshot_payload(
    messages: Iterable[dict],
    *,
    owner_email: str,
    max_contacts: int = 0,
    max_snippets: int = 3,
    max_subjects: int = 6,
) -> dict:
    message_list = [
        message for message in messages
        if isinstance(message, dict) and '_scan' not in message
    ]
    contacts = aggregate_external_contacts(message_list, owner_email=owner_email, max_contacts=max_contacts)
    for row in contacts:
        row['subjects'] = (row.get('subjects') or [])[:max_subjects]
        row['snippets'] = (row.get('snippets') or [])[:max_snippets]
    return {
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'source': 'zoho_mail_export',
        'owner_email': owner_email,
        'message_count': len(message_list),
        'contacts': contacts,
    }


def build_snapshot(
    *,
    input_path: Path,
    owner_email: str,
    output_path: Path,
    password: str = '',
    domains: Optional[Sequence[str]] = None,
    include_folders: Optional[Sequence[str]] = None,
    max_contacts: int = 0,
) -> dict:
    messages = list(
        iter_export_messages(
            [input_path],
            password=password,
            domains=domains,
            include_folders=include_folders,
        ),
    )
    payload = prune_snapshot_payload(
        messages,
        owner_email=owner_email,
        max_contacts=max_contacts,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload
