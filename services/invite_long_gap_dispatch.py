"""Two-phase long-gap dispatch: classify DP fit then bulk draft reconnect emails."""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from flask import current_app, has_app_context

from services.assist import (
    LlmCallFailed,
    LlmTemporarilyBusy,
    call_llm,
    clean_draft,
    llm_configured,
    resolve_llm_config,
    strip_em_dashes,
)
from services.dp_admin_invite_store import (
    get_long_gap_dispatch_rows,
    list_selected_invite_emails,
    patch_long_gap_dispatch_row,
    save_long_gap_dispatch_rows,
)
from services.invite_message_strategy import _parse_last_contact_date
from services.invite_research_pathways import build_zoho_contact_context
from services.platform_invitation_mail import (
    LONG_GAP_EMAIL_SUBJECT,
    LONG_GAP_PROGRESSION_IMAGE_URL,
    dp_workgroup_card_image_url,
    normalize_long_gap_greeting_in_body,
    sanitize_invite_email_body,
    send_long_gap_outreach_email,
)
from services.workgroup_invite_ai import (
    _DATE_FORMAT_RULE,
    _NO_EM_DASH_RULE,
    _all_dp_workgroup_catalog,
    _invitee_greeting_name,
    _strip_stray_name_punctuation,
    _parse_json_object,
    _zoho_contact_draft_guidance,
    draft_admin_invitation_email,
    ensure_invite_greeting,
    invite_draft_contains_planning_leak,
)
from services.workgroup_authority import is_dp_site_admin
from services.zoho_mail import (
    admin_contacts_snapshot_path,
    normalize_admin_email,
    outreach_selection_reasons,
)

_INTERN_KEYWORDS = frozenset({'intern', 'presence', 'bridgit', 'ved', 'aryan'})
_CLASSIFY_BATCH_SIZE = 8
_CLASSIFY_MAX_WORKERS = 5
_DRAFT_MAX_WORKERS = 3
_SEND_INTERVAL_SEC = 1.0
_LONG_GAP_PRODUCTION_SOURCE = 'long_gap_dispatch'
_CLASSIFICATION_UNAVAILABLE = 'classification unavailable'
_CLASSIFICATION_ERROR_MESSAGE = 'Classification unavailable'
_HEURISTIC_CLASSIFY_MARKER = 'heuristic-classify-fallback-v1'
_TERM_DP_SLUG_HINTS = {
    'meta-layer': 'governance',
    'metaweb': 'governance',
    'overweb': 'interoperability',
    'security': 'dp15',
    'provenance': 'dp15',
    'commerce': 'commerce',
    'governance': 'governance',
    'interoperability': 'interoperability',
}

_LONG_GAP_TEMPLATE_OPENING = (
    "It's been a long time. I hope you are well. Since we've been in touch, I've been cooking. "
    "After the Metaweb book was published in late 2023, we started the Meta-Layer Initiative. "
    "In the kickoff, a father of the Internet Vint Cerf challenged us to come up with the "
    "Desirable Properties of a layered web. We have done two calls for input and now have a "
    "solid version with plans to digitally launch the 1.0 version on Sept 16, 2026 the "
    "two year anniversary of the kickoff event."
)

_LONG_GAP_TEMPLATE_MIDDLE = (
    "As someone with an early view into the meta-layer conversation, we would love your input. "
    "We'd like to invite you to use our community AI assistant to make sure that the "
    "desirable properties enable what you think is important in the next level of the internet."
)

_LONG_GAP_TEMPLATE_CONTRIBUTION = (
    "You can contribute as an individual which could take from 5-10 minutes to a couple of "
    "hours depending on how thoroughly you want to review and how deep you want to go. "
    "You can also join or lead a workgroup which will work on the synthesis."
)

_LONG_GAP_TEMPLATE_NO_DP = 'Please visit https://desirableproperties.org to participate.'

_LONG_GAP_TEMPLATE_DP_PARAGRAPH = (
    "I would love your input on {dp_label}, a workgroup focused on {workgroup_short_desc}.\n\n"
    "Take a look here: {workgroup_link}"
)

_LONG_GAP_TEMPLATE_SIGNOFF = "Warmly,\nDaveed Benjamin"

_FALLBACK_DP_CATALOG = [
    {
        'id': 'dp15-security-provenance',
        'slug': 'dp15',
        'name': 'DP15 - Security and Provenance',
        'description': 'Security, provenance, trust, and verification on the layered web.',
    },
    {
        'id': 'dp-governance',
        'slug': 'governance',
        'name': 'Governance workgroup',
        'description': 'Governance patterns and civic participation in layered web systems.',
    },
    {
        'id': 'dp-interoperability',
        'slug': 'interoperability',
        'name': 'Interoperability workgroup',
        'description': 'Protocols, standards, and cross-layer interoperability.',
    },
]


_DEFAULT_DISPATCH_CUTOFF = date(2025, 1, 1)


def long_gap_dispatch_use_llm() -> bool:
    """When false (default), classify/draft use deterministic heuristics and form templates."""
    raw = (os.environ.get('LONG_GAP_DISPATCH_USE_LLM') or '').strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def get_long_gap_dispatch_cutoff() -> date:
    """Dispatch list cutoff — broader than META_LAYER_CUTOFF for outreach selection."""
    raw = (os.environ.get('LONG_GAP_DISPATCH_CUTOFF') or '').strip()
    if raw:
        try:
            return datetime.strptime(raw[:10], '%Y-%m-%d').date()
        except ValueError:
            pass
    return _DEFAULT_DISPATCH_CUTOFF


def long_gap_dispatch_cutoff_label(cutoff: Optional[date] = None) -> str:
    """Human-readable label for the active dispatch cutoff."""
    active = cutoff or get_long_gap_dispatch_cutoff()
    return active.strftime('%b %d, %Y')


def is_long_gap_last_contact(last_contact: str, *, cutoff: Optional[date] = None) -> bool:
    """True when last contact is before the dispatch cutoff (includes all of 2024)."""
    active = cutoff or get_long_gap_dispatch_cutoff()
    contact_date = _parse_last_contact_date(last_contact)
    if contact_date is None:
        return True
    return contact_date < active


def intern_alum_heuristic(
    *,
    snippets: Optional[List[str]] = None,
    subjects: Optional[List[str]] = None,
    matched_terms: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Keyword heuristic for Bridgit/Presence intern alumni."""
    parts: List[str] = []
    for collection in (snippets, subjects, matched_terms):
        parts.extend(str(item) for item in (collection or []))
    blob = ' '.join(parts).lower()
    if not blob.strip():
        return False, ''
    hits = [kw for kw in _INTERN_KEYWORDS if kw in blob]
    if 'intern' in blob and ('bridgit' in blob or 'presence' in blob):
        return True, 'intern keyword with Bridgit/Presence context'
    if len(hits) >= 2:
        return True, f'matched intern heuristics: {", ".join(hits[:4])}'
    return False, ''


def _subjects_snippet_summary(contact: dict) -> str:
    subjects = list(contact.get('sample_subjects') or contact.get('subjects') or [])[:4]
    snippets = list(contact.get('snippets') or [])[:2]
    parts: List[str] = []
    if subjects:
        parts.append('Subjects: ' + '; '.join(subjects))
    if snippets:
        parts.append('Snippets: ' + ' | '.join(str(snippet)[:180] for snippet in snippets))
    return ' '.join(parts)[:600]


def _load_snapshot_contacts(admin_email: str) -> List[dict]:
    path = Path(admin_contacts_snapshot_path(admin_email))
    if not path.is_file():
        return []
    try:
        with path.open(encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    contacts = payload.get('contacts')
    return contacts if isinstance(contacts, list) else []


def _dispatch_catalog() -> List[dict]:
    catalog = _all_dp_workgroup_catalog()
    if catalog:
        return catalog
    return list(_FALLBACK_DP_CATALOG)


def _sanitize_person_display_name(name: str) -> str:
    """Strip stray quotes and punctuation from Zoho contact display names."""
    cleaned = re.sub(r'\s+', ' ', (name or '').strip())
    return _strip_stray_name_punctuation(cleaned)


def _first_name_for_row(row: dict, contact: dict) -> str:
    """First name from contact name, else email local part."""
    invitee_display = _sanitize_person_display_name(row.get('name') or contact.get('name') or '')
    if invitee_display and '@' not in invitee_display:
        return _invitee_greeting_name(invitee_display)
    email = normalize_admin_email(row.get('email') or contact.get('email') or '')
    local = email.split('@', 1)[0] if '@' in email else email
    local_name = local.replace('.', ' ').replace('_', ' ').strip()
    return _invitee_greeting_name(local_name or invitee_display or 'there')


def _charter_description(catalog_entry: Optional[dict], dp_label: str = '') -> str:
    """Full charter/description from workgroup catalog."""
    if catalog_entry:
        charter = (
            catalog_entry.get('description')
            or catalog_entry.get('charter')
            or ''
        ).strip()
        if charter:
            return charter
    return (dp_label or 'this workgroup').strip()


def _workgroup_public_url(catalog_entry: Optional[dict]) -> str:
    """Public DP workgroup page URL (no invite token)."""
    from services.dp_public_urls import dp_challenge_site_base, workgroup_post_accept_path

    slug = ''
    if catalog_entry:
        slug = (catalog_entry.get('slug') or '').strip()
    base = dp_challenge_site_base()
    if not slug:
        return base
    return base + workgroup_post_accept_path(slug)


def get_long_gap_template_structure() -> dict:
    """Read-only template blocks for admin UI preview."""
    return {
        'greeting': 'Hi {first_name},',
        'opening': _LONG_GAP_TEMPLATE_OPENING,
        'middle': _LONG_GAP_TEMPLATE_MIDDLE,
        'contribution': _LONG_GAP_TEMPLATE_CONTRIBUTION,
        'no_dp': _LONG_GAP_TEMPLATE_NO_DP,
        'with_dp': _LONG_GAP_TEMPLATE_DP_PARAGRAPH,
        'signoff': _LONG_GAP_TEMPLATE_SIGNOFF,
        'progression_image_url': LONG_GAP_PROGRESSION_IMAGE_URL,
    }


def render_long_gap_template_email(
    row: dict,
    contact: dict,
    *,
    catalog_entry: Optional[dict] = None,
) -> str:
    """Deterministic long-gap form letter with public workgroup URLs in body."""
    first_name = _first_name_for_row(row, contact)
    dp_id = (row.get('dp_suggestion') or '').strip()
    dp_label = (row.get('dp_label') or '').strip()
    if not dp_label and catalog_entry:
        dp_label = (
            catalog_entry.get('name')
            or catalog_entry.get('slug')
            or ''
        ).strip()

    parts = [
        f'Hi {first_name},',
        '',
        _LONG_GAP_TEMPLATE_OPENING,
        '',
        _LONG_GAP_TEMPLATE_MIDDLE,
        '',
        _LONG_GAP_TEMPLATE_CONTRIBUTION,
    ]
    if dp_id and dp_label:
        workgroup_short_desc = _charter_description(catalog_entry, dp_label).rstrip('.')
        parts.append(
            _LONG_GAP_TEMPLATE_DP_PARAGRAPH.format(
                dp_label=dp_label,
                workgroup_short_desc=workgroup_short_desc,
                workgroup_link=_workgroup_public_url(catalog_entry),
            )
        )
    else:
        parts.append(_LONG_GAP_TEMPLATE_NO_DP)
    parts.append(_LONG_GAP_TEMPLATE_SIGNOFF)
    return '\n\n'.join(part for part in parts if part)


def _catalog_lookup(catalog: List[dict]) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    by_id: Dict[str, dict] = {}
    by_slug: Dict[str, dict] = {}
    for entry in catalog:
        wg_id = (entry.get('id') or '').strip()
        slug = (entry.get('slug') or '').strip().lower()
        if wg_id:
            by_id[wg_id] = entry
        if slug:
            by_slug[slug] = entry
            by_slug[slug.lower()] = entry
    return by_id, by_slug


def _resolve_dp_entry(
    raw_dp: Any,
    by_id: Dict[str, dict],
    by_slug: Dict[str, dict],
) -> Tuple[Optional[str], str]:
    if raw_dp is None:
        return None, ''
    cleaned = str(raw_dp).strip()
    if not cleaned or cleaned.lower() in {'null', 'none', 'skip'}:
        return None, ''
    lowered = cleaned.lower()
    if cleaned in by_id:
        entry = by_id[cleaned]
        return entry['id'], entry.get('name') or entry.get('slug') or cleaned
    if lowered in by_slug:
        entry = by_slug[lowered]
        return entry['id'], entry.get('name') or entry.get('slug') or cleaned
    # slug partial match (e.g. dp15)
    for slug_key, entry in by_slug.items():
        if slug_key and (lowered == slug_key or lowered.endswith(slug_key) or slug_key in lowered):
            return entry['id'], entry.get('name') or entry.get('slug') or slug_key
    return None, ''


def _normalize_confidence(value: Any) -> str:
    raw = str(value or '').strip().lower()
    if raw in ('high', 'strong'):
        return 'high'
    if raw in ('medium', 'moderate', 'fair'):
        return 'medium'
    return 'low'


def _empty_dispatch_row(contact: dict) -> dict:
    email = normalize_admin_email(contact.get('email') or '')
    last_contact = (contact.get('last_contact') or '').strip()
    selection = outreach_selection_reasons(contact)
    heuristic_intern, heuristic_note = intern_alum_heuristic(
        snippets=contact.get('snippets'),
        subjects=contact.get('sample_subjects') or contact.get('subjects'),
        matched_terms=selection.get('matched_terms'),
    )
    return {
        'email': email,
        'name': _sanitize_person_display_name(contact.get('name') or email),
        'last_contact': last_contact,
        'strategy': 'long_gap_reconnect',
        'subjects_snippet_summary': _subjects_snippet_summary(contact),
        'dp_suggestion': None,
        'dp_label': '',
        'confidence': 'low',
        'skip': False,
        'skip_reason': '',
        'intern_alum': heuristic_intern,
        'intern_alum_overridden': False,
        'dp_overridden': False,
        'skip_overridden': False,
        'intern_notes': heuristic_note,
        'why': '',
        'classification_status': 'pending',
        'classification_error': '',
        'draft_status': 'pending',
        'draft_body': '',
        'draft_error': '',
        'approved': False,
        'sample_subjects': list(contact.get('sample_subjects') or contact.get('subjects') or [])[:6],
        'snippets': [str(snippet)[:400] for snippet in (contact.get('snippets') or [])[:4]],
        'matched_terms': list(selection.get('matched_terms') or []),
    }


def build_long_gap_contact_list(admin: dict) -> List[dict]:
    """Intersect server selection with snapshot contacts in long-gap window."""
    owner = normalize_admin_email(admin.get('email') or '')
    selected = set(list_selected_invite_emails(owner))
    if not selected:
        return []
    contacts_by_email: Dict[str, dict] = {}
    for row in _load_snapshot_contacts(owner):
        email = normalize_admin_email(row.get('email') or '')
        if email and email in selected:
            contacts_by_email[email] = row
    long_gap_rows: List[dict] = []
    for email in sorted(selected):
        contact = contacts_by_email.get(email)
        if not contact:
            continue
        last_contact = (contact.get('last_contact') or '').strip()
        if not is_long_gap_last_contact(last_contact):
            continue
        long_gap_rows.append(contact)
    return long_gap_rows


def _sync_dispatch_rows(admin: dict, contacts: List[dict]) -> dict:
    owner = normalize_admin_email(admin.get('email') or '')
    existing = get_long_gap_dispatch_rows(owner).get('rows') or {}
    merged: Dict[str, dict] = {}
    for contact in contacts:
        email = normalize_admin_email(contact.get('email') or '')
        if not email:
            continue
        base = _empty_dispatch_row(contact)
        prior = existing.get(email)
        if isinstance(prior, dict):
            for key in (
                'dp_suggestion', 'dp_label', 'confidence', 'skip', 'skip_reason',
                'intern_alum', 'intern_alum_overridden', 'dp_overridden', 'skip_overridden',
                'intern_notes', 'why', 'classification_status', 'classification_error',
                'draft_status', 'draft_body', 'draft_error', 'approved',
            ):
                if key in prior:
                    base[key] = prior[key]
        merged[email] = base
    return save_long_gap_dispatch_rows(owner, merged)


def _classify_batch_payload(contacts: List[dict], catalog: List[dict]) -> dict:
    batch: List[dict] = []
    for contact in contacts:
        selection = outreach_selection_reasons(contact)
        heuristic_intern, heuristic_note = intern_alum_heuristic(
            snippets=contact.get('snippets'),
            subjects=contact.get('sample_subjects') or contact.get('subjects'),
            matched_terms=selection.get('matched_terms'),
        )
        batch.append({
            'email': normalize_admin_email(contact.get('email') or ''),
            'name': (contact.get('name') or '').strip(),
            'last_contact': (contact.get('last_contact') or '').strip(),
            'subjects': list(contact.get('sample_subjects') or contact.get('subjects') or [])[:6],
            'snippets': [str(snippet)[:300] for snippet in (contact.get('snippets') or [])[:3]],
            'matched_terms': list(selection.get('matched_terms') or []),
            'intern_heuristic': heuristic_intern,
            'intern_heuristic_note': heuristic_note,
        })
    return {'contacts': batch, 'workgroups_catalog': catalog}


def _flask_app():
    if has_app_context():
        return current_app._get_current_object()
    from app import app as flask_app
    return flask_app


def _classification_error_result() -> dict:
    return {
        'dp_suggestion': None,
        'dp_label': '',
        'confidence': 'low',
        'skip': False,
        'skip_reason': '',
        'intern_alum': False,
        'intern_notes': '',
        'why': _CLASSIFICATION_UNAVAILABLE,
        'classification_status': 'error',
        'classification_error': _CLASSIFICATION_ERROR_MESSAGE,
    }


def _parse_classify_response(raw: str, by_id: Dict[str, dict], by_slug: Dict[str, dict]) -> Dict[str, dict]:
    if not (raw or '').strip():
        raise ValueError('empty LLM classification response')

    parsed = _parse_json_object(raw)
    results = parsed.get('results')
    if not isinstance(results, list):
        results = parsed.get('contacts')
    if not isinstance(results, list):
        raise ValueError('classification response missing results array')

    out: Dict[str, dict] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        email = normalize_admin_email(item.get('email') or '')
        if not email:
            continue
        dp_id, dp_label = _resolve_dp_entry(
            item.get('dp_slug') or item.get('workgroup_id') or item.get('dp_suggestion'),
            by_id,
            by_slug,
        )
        skip = bool(item.get('skip'))
        skip_reason = (item.get('skip_reason') or '').strip()[:300]
        intern_alum = bool(item.get('intern_alum'))
        intern_notes = (item.get('intern_notes') or '').strip()[:300]
        why = (item.get('why') or item.get('rationale') or '').strip()[:400]
        out[email] = {
            'dp_suggestion': dp_id,
            'dp_label': dp_label or (item.get('dp_label') or '').strip()[:200],
            'confidence': _normalize_confidence(item.get('confidence')),
            'skip': skip,
            'skip_reason': skip_reason,
            'intern_alum': intern_alum,
            'intern_notes': intern_notes,
            'why': why,
            'classification_status': 'done',
            'classification_error': '',
        }
    return out


def _heuristic_why_from_contact(contact: dict, matched_terms: List[str]) -> str:
    subjects = list(contact.get('sample_subjects') or contact.get('subjects') or [])[:3]
    if subjects:
        joined = '; '.join(str(subject).strip() for subject in subjects if str(subject).strip())
        if joined:
            return f'Prior threads: {joined[:380]}'
    if matched_terms:
        return f'Matched outreach terms: {", ".join(matched_terms[:6])}'
    return 'Long-gap reconnect candidate (heuristic classify)'


def _heuristic_dp_from_terms(
    matched_terms: List[str],
    by_id: Dict[str, dict],
    by_slug: Dict[str, dict],
) -> Tuple[Optional[str], str]:
    for term in matched_terms:
        hint = _TERM_DP_SLUG_HINTS.get(str(term).strip().lower())
        if not hint:
            continue
        dp_id, dp_label = _resolve_dp_entry(hint, by_id, by_slug)
        if dp_id:
            return dp_id, dp_label
    return None, ''


def _heuristic_classify_contact(
    contact: dict,
    by_id: Dict[str, dict],
    by_slug: Dict[str, dict],
) -> dict:
    """Keyword-only classify when LLM JSON is empty or invalid."""
    selection = outreach_selection_reasons(contact)
    matched_terms = list(selection.get('matched_terms') or [])
    heuristic_intern, heuristic_note = intern_alum_heuristic(
        snippets=contact.get('snippets'),
        subjects=contact.get('sample_subjects') or contact.get('subjects'),
        matched_terms=matched_terms,
    )
    dp_id, dp_label = _heuristic_dp_from_terms(matched_terms, by_id, by_slug)
    why = _heuristic_why_from_contact(contact, matched_terms)
    return {
        'dp_suggestion': dp_id,
        'dp_label': dp_label,
        'confidence': 'low',
        'skip': False,
        'skip_reason': '',
        'intern_alum': heuristic_intern,
        'intern_notes': heuristic_note,
        'why': why,
        'classification_status': 'done',
        'classification_error': '',
        'classification_source': _HEURISTIC_CLASSIFY_MARKER,
    }


def _reset_draft_after_reclassify(row: dict) -> None:
    """Clear stale draft errors so approved rows can be drafted again."""
    if row.get('draft_status') in {'error', 'pending'} or row.get('draft_error'):
        row['draft_status'] = 'pending'
        row['draft_body'] = ''
        row['draft_error'] = ''


def merge_classify_result_into_row(row: dict, result: dict, contact: dict) -> None:
    """Apply LLM/heuristic classification; preserve user manual review overrides."""
    intern_overridden = bool(row.get('intern_alum_overridden'))
    dp_overridden = bool(row.get('dp_overridden'))
    skip_overridden = bool(row.get('skip_overridden'))

    preserved_intern = row.get('intern_alum') if intern_overridden else None
    preserved_notes = row.get('intern_notes') if intern_overridden else None
    preserved_dp = row.get('dp_suggestion') if dp_overridden else None
    preserved_dp_label = row.get('dp_label') if dp_overridden else None
    preserved_confidence = row.get('confidence') if dp_overridden else None
    preserved_skip = row.get('skip') if skip_overridden else None
    preserved_skip_reason = row.get('skip_reason') if skip_overridden else None
    preserved_approved = row.get('approved')

    row.update(result)
    _reset_draft_after_reclassify(row)

    row['approved'] = preserved_approved

    if intern_overridden:
        row['intern_alum'] = preserved_intern
        row['intern_notes'] = preserved_notes
    else:
        heuristic_intern, heuristic_note = intern_alum_heuristic(
            snippets=contact.get('snippets'),
            subjects=contact.get('sample_subjects') or contact.get('subjects'),
            matched_terms=row.get('matched_terms'),
        )
        if heuristic_intern and not row.get('intern_alum'):
            row['intern_alum'] = True
            if heuristic_note:
                row['intern_notes'] = heuristic_note

    if dp_overridden:
        row['dp_suggestion'] = preserved_dp
        row['dp_label'] = preserved_dp_label
        row['confidence'] = preserved_confidence

    if skip_overridden:
        row['skip'] = preserved_skip
        row['skip_reason'] = preserved_skip_reason


def _classify_one_batch(
    contacts: List[dict],
    catalog: List[dict],
    by_id: Dict[str, dict],
    by_slug: Dict[str, dict],
) -> Dict[str, dict]:
    if not llm_configured():
        raise RuntimeError('No LLM API key configured')
    cfg = resolve_llm_config()
    if not cfg:
        raise RuntimeError('No LLM API key configured')

    system = (
        'You classify Zoho email contacts for Desirable Properties long-gap outreach. '
        'For each contact, suggest ONE primary workgroup fit, set dp_slug to null when unsure, or mark skip. '
        'CRITICAL: Respond with a single JSON object only. No markdown fences, no commentary, no prose. '
        'Start your reply with { and end with }. Schema: {"results": ['
        '{email, dp_slug (slug from catalog or null), confidence (high|medium|low), '
        'skip (boolean), skip_reason, intern_alum (boolean), intern_notes, why (one line)}]}. '
        'Skip vendors, newsletters, no real relationship, or wrong audience. '
        'Use intern_alum=true when they interned with Bridgit or Presence (confirm intern_heuristic when present). '
        'Only use dp_slug values from the catalog when not skipping. '
        f'{_NO_EM_DASH_RULE}'
    )
    user_payload = _classify_batch_payload(contacts, catalog)
    raw = call_llm(
        [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(user_payload)},
        ],
        cfg,
        max_tokens=2400,
    )
    return _parse_classify_response(raw, by_id, by_slug)


def classify_long_gap_dispatch(
    admin: dict,
    *,
    emails: Optional[List[str]] = None,
    force: bool = False,
) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    contacts = build_long_gap_contact_list(admin)
    if emails:
        wanted = {normalize_admin_email(email) for email in emails if normalize_admin_email(email)}
        contacts = [row for row in contacts if normalize_admin_email(row.get('email') or '') in wanted]

    owner = normalize_admin_email(admin.get('email') or '')
    store = _sync_dispatch_rows(admin, build_long_gap_contact_list(admin))
    rows = store.get('rows') or {}

    to_classify: List[dict] = []
    for contact in contacts:
        email = normalize_admin_email(contact.get('email') or '')
        row = rows.get(email)
        if not row:
            continue
        if not force and row.get('classification_status') == 'done':
            continue
        to_classify.append(contact)

    catalog = _dispatch_catalog()
    by_id, by_slug = _catalog_lookup(catalog)

    if not to_classify:
        return {
            'success': True,
            'classified': 0,
            'total_long_gap': len(contacts),
            'rows': rows,
            'updated_at': store.get('updated_at') or '',
            'use_template_drafts': not long_gap_dispatch_use_llm(),
        }, 200

    if not long_gap_dispatch_use_llm():
        classified = 0
        for contact in to_classify:
            email = normalize_admin_email(contact.get('email') or '')
            if email not in rows:
                continue
            result = _heuristic_classify_contact(contact, by_id, by_slug)
            merge_classify_result_into_row(rows[email], result, contact)
            classified += 1
        saved = save_long_gap_dispatch_rows(owner, rows)
        return {
            'success': True,
            'classified': classified,
            'total_long_gap': len(build_long_gap_contact_list(admin)),
            'errors': [_HEURISTIC_CLASSIFY_MARKER],
            'rows': saved.get('rows') or rows,
            'updated_at': saved.get('updated_at') or '',
            'workgroup_catalog': catalog,
            'use_template_drafts': True,
        }, 200

    if not llm_configured():
        return {'error': 'No LLM API key configured for classification'}, 503

    batches: List[List[dict]] = []
    for index in range(0, len(to_classify), _CLASSIFY_BATCH_SIZE):
        batches.append(to_classify[index : index + _CLASSIFY_BATCH_SIZE])

    classified = 0
    errors: List[str] = []
    flask_app = _flask_app()

    def run_batch(batch: List[dict]) -> Tuple[List[dict], Dict[str, dict], List[str]]:
        with flask_app.app_context():
            try:
                parsed = _classify_one_batch(batch, catalog, by_id, by_slug)
                return batch, parsed, []
            except (json.JSONDecodeError, LlmCallFailed, LlmTemporarilyBusy, ValueError, RuntimeError):
                heuristic: Dict[str, dict] = {}
                for contact in batch:
                    email = normalize_admin_email(contact.get('email') or '')
                    if email:
                        heuristic[email] = _heuristic_classify_contact(contact, by_id, by_slug)
                return batch, heuristic, [_HEURISTIC_CLASSIFY_MARKER]

    with ThreadPoolExecutor(max_workers=_CLASSIFY_MAX_WORKERS) as pool:
        futures = [pool.submit(run_batch, batch) for batch in batches]
        for future in as_completed(futures):
            batch, parsed, batch_errors = future.result()
            for err in batch_errors:
                if err not in errors:
                    errors.append(err)
            for contact in batch:
                email = normalize_admin_email(contact.get('email') or '')
                if email not in rows:
                    continue
                result = parsed.get(email)
                if not result:
                    result = _heuristic_classify_contact(contact, by_id, by_slug)
                    if _HEURISTIC_CLASSIFY_MARKER not in errors:
                        errors.append(_HEURISTIC_CLASSIFY_MARKER)
                merge_classify_result_into_row(rows[email], result, contact)
                classified += 1

    saved = save_long_gap_dispatch_rows(owner, rows)
    return {
        'success': True,
        'classified': classified,
        'total_long_gap': len(build_long_gap_contact_list(admin)),
        'errors': errors[:5],
        'rows': saved.get('rows') or rows,
        'updated_at': saved.get('updated_at') or '',
        'workgroup_catalog': catalog,
        'use_template_drafts': not long_gap_dispatch_use_llm(),
    }, 200


def get_long_gap_dispatch_review(admin: dict) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403
    contacts = build_long_gap_contact_list(admin)
    store = _sync_dispatch_rows(admin, contacts)
    rows = store.get('rows') or {}
    ordered = [
        _sanitize_row_draft_body(rows[normalize_admin_email(contact.get('email') or '')])
        for contact in contacts
        if normalize_admin_email(contact.get('email') or '') in rows
    ]
    cutoff = get_long_gap_dispatch_cutoff()
    return {
        'success': True,
        'total_long_gap': len(contacts),
        'dispatch_cutoff': cutoff.isoformat(),
        'dispatch_cutoff_label': long_gap_dispatch_cutoff_label(cutoff),
        'rows': ordered,
        'updated_at': store.get('updated_at') or '',
        'workgroup_catalog': _dispatch_catalog(),
        'use_template_drafts': not long_gap_dispatch_use_llm(),
        'template_mode_notice': (
            'Using template emails (no AI draft)'
            if not long_gap_dispatch_use_llm()
            else ''
        ),
    }, 200


def patch_long_gap_dispatch_review(
    admin: dict,
    *,
    email: str,
    patch: dict,
) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'success': False, 'error': 'DP site admin required'}, 403
    owner = normalize_admin_email(admin.get('email') or '')
    allowed = {
        'dp_suggestion', 'dp_label', 'skip', 'skip_reason', 'approved', 'intern_alum', 'intern_notes',
    }
    clean_patch = {key: patch[key] for key in allowed if key in patch}
    if 'intern_alum' in clean_patch:
        clean_patch['intern_alum'] = bool(clean_patch['intern_alum'])
        clean_patch['intern_alum_overridden'] = True
    if 'dp_suggestion' in clean_patch:
        try:
            catalog = _dispatch_catalog()
            by_id, by_slug = _catalog_lookup(catalog)
            dp_id, dp_label = _resolve_dp_entry(clean_patch['dp_suggestion'], by_id, by_slug)
        except Exception:
            catalog = list(_FALLBACK_DP_CATALOG)
            by_id, by_slug = _catalog_lookup(catalog)
            dp_id, dp_label = _resolve_dp_entry(clean_patch['dp_suggestion'], by_id, by_slug)
        clean_patch['dp_suggestion'] = dp_id
        if dp_label and 'dp_label' not in clean_patch:
            clean_patch['dp_label'] = dp_label
        elif not dp_label and isinstance(clean_patch.get('dp_label'), str):
            clean_patch['dp_label'] = clean_patch['dp_label'].strip()
        clean_patch['dp_overridden'] = True
    if 'skip' in clean_patch:
        clean_patch['skip'] = bool(clean_patch['skip'])
        clean_patch['skip_overridden'] = True
    if 'dp_suggestion' in clean_patch:
        prior_payload = _load_dispatch_payload(owner)
        prior_rows = prior_payload.get('rows') or {}
        prior_row = prior_rows.get(normalize_admin_email(email))
        if isinstance(prior_row, dict):
            old_dp = str(prior_row.get('dp_suggestion') or '').strip()
            new_dp = str(clean_patch.get('dp_suggestion') or '').strip()
            if old_dp != new_dp:
                clean_patch['draft_status'] = 'pending'
                clean_patch['draft_body'] = ''
                clean_patch['draft_error'] = ''
    try:
        row = patch_long_gap_dispatch_row(owner, email, clean_patch)
    except (OSError, ValueError, TypeError) as exc:
        return {
            'success': False,
            'error': f'Failed to save dispatch row: {exc}',
            'code': 'dispatch_save_failed',
        }, 500
    if not row:
        return {'success': False, 'error': 'dispatch row not found'}, 404
    return {'success': True, 'row': row}, 200


def _intern_draft_guidance(row: dict) -> str:
    if not row.get('intern_alum'):
        return ''
    notes = (row.get('intern_notes') or '').strip()
    base = (
        'INTERN ALUM: Open by thanking them for interning with Bridgit and/or Presence. '
        'Acknowledge their contribution to those projects before the Meta-Layer reconnection arc.'
    )
    if notes:
        return f'{base} Context: {notes}'
    return base


def _workgroup_dp_draft_guidance(
    row: dict,
    catalog_entry: Optional[dict],
    contact: dict,
) -> str:
    """Mandatory LLM guidance when admin selected a suggested DP workgroup."""
    dp_label = (row.get('dp_label') or '').strip()
    name = dp_label
    charter = ''
    if catalog_entry:
        name = (
            catalog_entry.get('name')
            or dp_label
            or catalog_entry.get('slug')
            or ''
        ).strip()
        charter = (
            catalog_entry.get('description')
            or catalog_entry.get('charter')
            or ''
        ).strip()[:600]
    subjects = list(
        row.get('sample_subjects')
        or contact.get('sample_subjects')
        or contact.get('subjects')
        or []
    )[:4]
    subject_line = '; '.join(
        str(subject).strip() for subject in subjects if str(subject).strip()
    )[:400]
    snippet_bits = [
        str(snippet)[:200]
        for snippet in (row.get('snippets') or contact.get('snippets') or [])[:2]
    ]
    lines = [
        'PRIMARY WORKGROUP INVITATION (mandatory for this draft):',
        (
            f'After the long-gap Meta-Layer reconnection arc, you MUST explicitly invite the '
            f'recipient to the "{name}" workgroup by its full name (include DP number/acronym '
            f'when part of the title, e.g. DP6 Commerce).'
        ),
        (
            'Include 1-2 sentences on why THIS workgroup fits them based on their Zoho subjects '
            'and snippets — tie their history to the workgroup focus; do not stay generic.'
        ),
    ]
    if charter:
        lines.append(f'Workgroup charter/summary: {charter}')
    if subject_line:
        lines.append(f'Their email subjects: {subject_line}')
    if snippet_bits:
        lines.append('Snippet context: ' + ' | '.join(snippet_bits))
    lines.append(
        'Sign off as Daveed or Daveed Benjamin. No em dashes. Output ONLY the finished email body.'
    )
    return '\n'.join(lines)


_LONG_GAP_GENERIC_GUIDANCE = (
    'LONG-GAP RECONNECT (warm and personal – avoid form-letter tone):\n'
    'Open naturally: it has been a long time, hope they are well, and since you last spoke a lot has been cooking.\n'
    'Brief Meta-Layer arc in prose: Metaweb book (late 2023), Meta-Layer Initiative kickoff (September 2024), '
    'Vint Cerf on Desirable Properties of a layered web, community input rounds, 0.77 draft, '
    'digital 1.0 launch September 16, 2026.\n'
    'Weave in this contact\'s Zoho subjects and snippet details (e.g. GFC intro, Bridgit advisor calls, catch-ups).\n'
    'Do NOT name a specific workgroup or charter. Invite them to explore workgroups, use the community AI assistant '
    '(Hermes), or have a short conversation with Daveed.\n'
    'Mirror their communication style from snippets. Verbose contacts should get a longer, warmer draft.\n'
    'Sign off as Daveed or Daveed Benjamin with a complete closing sentence.'
)


def _long_gap_length_key(zoho_ctx: Optional[dict]) -> str:
    """Pick draft length from inferred Zoho communication style."""
    style = (zoho_ctx or {}).get('communication_style') or {}
    labels = style.get('labels') or []
    verbosity = (style.get('verbosity') or 'medium').strip().lower()
    if 'verbose' in labels or verbosity == 'verbose':
        return 'long'
    if 'terse' in labels or verbosity == 'terse':
        return 'short'
    return 'medium'


def _finalize_long_gap_draft(
    raw: str,
    *,
    length_key: str,
    invitee_display: str,
    greet_name: str,
) -> str:
    """Clean LLM output: strip reasoning leaks, ensure greeting, sanitize markers."""
    draft = clean_draft(raw, length_preference=length_key, invitee_name=greet_name)
    draft = ensure_invite_greeting(draft, invitee_display)
    draft = strip_em_dashes(draft)
    return sanitize_invite_email_body(draft)


def _sanitize_stored_invite_draft(body: str, *, invitee_name: str = '') -> str:
    """Strip LLM planning leaks from a stored or loaded draft body."""
    text = (body or '').strip()
    if not text:
        return text
    greet_name = _invitee_greeting_name(invitee_name) if invitee_name else ''
    draft = clean_draft(text, invitee_name=greet_name or None)
    draft = strip_em_dashes(draft)
    return sanitize_invite_email_body(draft)


def _sanitize_row_draft_body(row: dict) -> dict:
    """Return row with sanitized draft_body for API responses (does not persist)."""
    updated = dict(row)
    original_name = (row.get('name') or '').strip()
    clean_name = _sanitize_person_display_name(original_name)
    if clean_name and clean_name != original_name:
        updated['name'] = clean_name
    body = (updated.get('draft_body') or '').strip()
    if not body:
        return updated if updated != row else row
    invitee_name = clean_name or original_name
    cleaned = _sanitize_stored_invite_draft(body, invitee_name=invitee_name)
    cleaned = normalize_long_gap_greeting_in_body(cleaned, invitee_name)
    if cleaned == body and updated.get('name') == row.get('name'):
        return row
    updated['draft_body'] = cleaned
    return updated


def _draft_generic_long_gap_reconnect(
    admin: dict,
    row: dict,
    contact: dict,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Draft a long-gap Meta-Layer reconnect email without a specific workgroup."""
    if not llm_configured():
        return row['email'], None, 'No LLM API key configured for drafting'
    cfg = resolve_llm_config()
    if not cfg:
        return row['email'], None, 'No LLM API key configured for drafting'

    from models import User

    inviter_user = User.query.get(admin.get('id'))
    inviter_name = (
        (inviter_user.displayName or inviter_user.username or 'A member')
        if inviter_user
        else 'A member'
    )
    invitee_display = (row.get('name') or contact.get('name') or '').strip()
    greet_name = _invitee_greeting_name(invitee_display)
    zoho_ctx = build_zoho_contact_context({
        'email': contact.get('email'),
        'name': contact.get('name'),
        'last_contact': contact.get('last_contact'),
        'message_count': contact.get('message_count'),
        'snippets': contact.get('snippets'),
        'sample_subjects': contact.get('sample_subjects') or contact.get('subjects'),
        'summary': row.get('subjects_snippet_summary'),
    })
    zoho_guidance = _zoho_contact_draft_guidance(zoho_ctx)
    extra = _intern_draft_guidance(row)
    if row.get('why') and row['why'] != _CLASSIFICATION_UNAVAILABLE:
        extra = (extra + '\n' + f'Classification note: {row["why"]}').strip()
    combined_guidance = '\n\n'.join(
        part for part in (_LONG_GAP_GENERIC_GUIDANCE, zoho_guidance, extra) if part
    )
    length_key = _long_gap_length_key(zoho_ctx)
    length_note = (
        'About 380–480 words: substantive middle paragraphs, not padding.'
        if length_key == 'long'
        else 'About 120–180 words: crisp and warm.'
        if length_key == 'short'
        else 'About 220–320 words.'
    )
    system = (
        'Write a warm personal long-gap reconnection email (plain text, no subject line). '
        'Output ONLY the finished email body. '
        'Never output analysis, requirement checklists, word counts, or lines like '
        '"Let me check", "Let me finalize", or "Let me reconsider". '
        'Do NOT invite the recipient to a specific workgroup by name or charter. '
        'Mention Desirable Properties and the Meta-Layer arc naturally in prose. '
        'Invite them to explore workgroups, use the community AI assistant (Hermes), '
        'or have a short conversation with Daveed. '
        f'The FIRST line MUST be a greeting using the invitee\'s first name, e.g. "Hi {greet_name},". '
        f'{_NO_EM_DASH_RULE}'
        f'{_DATE_FORMAT_RULE} '
        f'LENGTH ({length_key}): {length_note} '
        'End with a complete closing sentence and sign-off as Daveed or Daveed Benjamin. '
        'Do not output join links or workgroup invitation URLs.'
    )
    user_payload = {
        'inviter_name': inviter_name,
        'invitee_name': invitee_display or row['email'],
        'invitee_email': row['email'],
        'tone': 'warm',
        'length': length_key,
        'previous_interaction': row.get('subjects_snippet_summary') or '',
        'extra_guidance': combined_guidance,
        'zoho_contact_context': zoho_ctx,
    }
    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': json.dumps(user_payload)},
    ]
    max_tokens = 900 if length_key == 'short' else 2400 if length_key == 'long' else 1600
    raw = call_llm(messages, cfg, max_tokens=max_tokens)
    draft_body = _finalize_long_gap_draft(
        raw,
        length_key=length_key,
        invitee_display=invitee_display,
        greet_name=greet_name,
    )
    if invite_draft_contains_planning_leak(draft_body):
        retry_user = json.dumps({
            **user_payload,
            'retry_note': (
                'The previous output included internal reasoning or requirement checklists. '
                'Output ONLY the final email text – no "Let me check", checklists, or revision notes.'
            ),
            'previous_attempt': draft_body[:1200],
        })
        raw = call_llm(
            [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': retry_user},
            ],
            cfg,
            max_tokens=max_tokens,
            temperature=0.5,
        )
        draft_body = _finalize_long_gap_draft(
            raw,
            length_key=length_key,
            invitee_display=invitee_display,
            greet_name=greet_name,
        )
    if not draft_body:
        return row['email'], None, 'empty draft returned'
    return row['email'], draft_body, None


def _draft_one_row_template(
    row: dict,
    contact: dict,
) -> Tuple[str, Optional[str], Optional[str]]:
    catalog = _dispatch_catalog()
    by_id, _ = _catalog_lookup(catalog)
    dp_id = (row.get('dp_suggestion') or '').strip()
    catalog_entry = by_id.get(dp_id) if dp_id else None
    draft_body = render_long_gap_template_email(row, contact, catalog_entry=catalog_entry)
    if not draft_body:
        return row['email'], None, 'empty template draft'
    return row['email'], draft_body, None


def _draft_one_row(admin: dict, row: dict, contact: dict) -> Tuple[str, Optional[str], Optional[str]]:
    if not long_gap_dispatch_use_llm():
        return _draft_one_row_template(row, contact)
    dp_id = (row.get('dp_suggestion') or '').strip()
    if not dp_id:
        return _draft_generic_long_gap_reconnect(admin, row, contact)
    zoho_ctx = build_zoho_contact_context({
        'email': contact.get('email'),
        'name': contact.get('name'),
        'last_contact': contact.get('last_contact'),
        'message_count': contact.get('message_count'),
        'snippets': contact.get('snippets'),
        'sample_subjects': contact.get('sample_subjects') or contact.get('subjects'),
        'summary': row.get('subjects_snippet_summary'),
    })
    catalog = _dispatch_catalog()
    by_id, _ = _catalog_lookup(catalog)
    catalog_entry = by_id.get(dp_id)
    extra_parts: List[str] = [
        _workgroup_dp_draft_guidance(row, catalog_entry, contact),
        _intern_draft_guidance(row),
    ]
    if row.get('why') and row['why'] != _CLASSIFICATION_UNAVAILABLE:
        extra_parts.append(f'Classification note: {row["why"]}')
    extra = '\n\n'.join(part for part in extra_parts if part)
    length_key = _long_gap_length_key(zoho_ctx)
    payload, status = draft_admin_invitation_email(
        primary_workgroup_id=dp_id,
        inviter=admin,
        name=(row.get('name') or contact.get('name') or '').strip(),
        email=row['email'],
        tone='warm',
        length=length_key,
        previous_interaction=row.get('subjects_snippet_summary') or '',
        extra_guidance=extra,
        zoho_contact_context=zoho_ctx,
        message_strategy='long_gap_reconnect',
        strategy_confirmed=True,
    )
    if status >= 400 or payload.get('error') or payload.get('blocked'):
        return row['email'], None, (payload.get('error') or 'draft failed')[:300]
    draft_body = (payload.get('draft') or '').strip()
    if not draft_body:
        return row['email'], None, 'empty draft returned'
    invitee_display = (row.get('name') or contact.get('name') or '').strip()
    greet_name = _invitee_greeting_name(invitee_display)
    draft_body = _finalize_long_gap_draft(
        draft_body,
        length_key=length_key,
        invitee_display=invitee_display,
        greet_name=greet_name,
    )
    if invite_draft_contains_planning_leak(draft_body):
        return row['email'], None, 'draft still contains planning leak after sanitize'
    return row['email'], draft_body, None


def _collect_draft_targets(
    rows: Dict[str, dict],
    *,
    emails: Optional[List[str]] = None,
    force: bool = False,
) -> Tuple[List[dict], List[Tuple[str, dict]]]:
    """Return approved rows needing draft plus skip rows that need status=skipped."""
    wanted = (
        {normalize_admin_email(email) for email in emails if normalize_admin_email(email)}
        if emails
        else None
    )
    targets: List[dict] = []
    skip_patches: List[Tuple[str, dict]] = []
    for email_key, row in rows.items():
        if not isinstance(row, dict):
            continue
        if wanted is not None and email_key not in wanted:
            continue
        if not row.get('approved'):
            continue
        if row.get('skip'):
            if row.get('draft_status') != 'skipped':
                skip_patches.append((email_key, {'draft_status': 'skipped'}))
            continue
        if row.get('draft_status') == 'done' and row.get('draft_body') and not force:
            continue
        if force and row.get('draft_body'):
            row['draft_status'] = 'pending'
            row['draft_body'] = ''
            row['draft_error'] = ''
        targets.append(row)
    return targets, skip_patches


def _load_dispatch_payload(owner: str) -> dict:
    from services.dp_admin_invite_store import _load_long_gap_dispatch_payload

    return _load_long_gap_dispatch_payload(owner)


def _save_dispatch_payload(owner: str, payload: dict) -> str:
    from services.dp_admin_invite_store import _save_long_gap_dispatch_payload

    _save_long_gap_dispatch_payload(owner, payload)
    return payload.get('updated_at') or ''


def _get_draft_job(owner: str) -> Optional[dict]:
    payload = _load_dispatch_payload(owner)
    job = payload.get('draft_job')
    return job if isinstance(job, dict) else None


def _set_draft_job(owner: str, job: Optional[dict]) -> str:
    payload = _load_dispatch_payload(owner)
    if job is None:
        payload.pop('draft_job', None)
    else:
        payload['draft_job'] = job
    return _save_dispatch_payload(owner, payload)


def _patch_draft_job(owner: str, patch: dict) -> Optional[dict]:
    payload = _load_dispatch_payload(owner)
    job = payload.get('draft_job')
    if not isinstance(job, dict):
        return None
    job.update(patch)
    payload['draft_job'] = job
    _save_dispatch_payload(owner, payload)
    return job


def _execute_draft_targets(
    admin: dict,
    owner: str,
    targets: List[dict],
    contact_by_email: Dict[str, dict],
    *,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> Tuple[int, int]:
    """Draft targets with incremental per-row saves. Returns (drafted_count, error_count)."""
    if not targets:
        return 0, 0

    use_llm = long_gap_dispatch_use_llm()
    if use_llm and not llm_configured():
        raise RuntimeError('No LLM API key configured for drafting')

    drafted = 0
    errors = 0
    completed = 0
    flask_app = _flask_app()

    def apply_draft_result(
        row: dict,
        result_email: str,
        body: Optional[str],
        err: Optional[str],
    ) -> None:
        nonlocal drafted, errors, completed
        email_key = normalize_admin_email(result_email or row.get('email') or '')
        if body:
            invitee_name = (row.get('name') or '').strip()
            clean_body = _sanitize_stored_invite_draft(body, invitee_name=invitee_name)
            patch_long_gap_dispatch_row(
                owner,
                email_key,
                {
                    'draft_body': clean_body,
                    'draft_status': 'done',
                    'draft_error': '',
                },
            )
            drafted += 1
        else:
            patch_long_gap_dispatch_row(
                owner,
                email_key,
                {
                    'draft_status': 'error',
                    'draft_error': err or 'draft failed',
                },
            )
            errors += 1
        completed += 1
        if on_progress:
            on_progress({
                'current_email': email_key,
                'completed': completed,
                'drafted': drafted,
                'errors': errors,
            })

    if not use_llm:
        for row in targets:
            contact = contact_by_email.get(row['email']) or {}
            try:
                result_email, body, err = _draft_one_row_template(row, contact)
            except Exception as exc:  # noqa: BLE001
                result_email, body, err = row.get('email') or '', None, str(exc)[:300]
            apply_draft_result(row, result_email, body, err)
        return drafted, errors

    def run_draft(row: dict) -> Tuple[str, Optional[str], Optional[str]]:
        with flask_app.app_context():
            contact = contact_by_email.get(row['email']) or {}
            return _draft_one_row(admin, row, contact)

    with ThreadPoolExecutor(max_workers=_DRAFT_MAX_WORKERS) as pool:
        futures = {pool.submit(run_draft, row): row for row in targets}
        for future in as_completed(futures):
            row = futures[future]
            email_key = normalize_admin_email(row.get('email') or '')
            try:
                result_email, body, err = future.result()
                email_key = normalize_admin_email(result_email or email_key)
            except Exception as exc:  # noqa: BLE001
                body, err = None, str(exc)[:300]
            apply_draft_result(row, email_key, body, err)
    return drafted, errors


def _draft_job_runner(
    admin: dict,
    owner: str,
    targets: List[dict],
    contact_by_email: Dict[str, dict],
    job_id: str,
) -> None:
    flask_app = _flask_app()
    with flask_app.app_context():
        try:
            def on_progress(progress: dict) -> None:
                _patch_draft_job(owner, {
                    'status': 'running',
                    'current_email': progress.get('current_email') or '',
                    'completed': progress.get('completed') or 0,
                    'drafted': progress.get('drafted') or 0,
                    'errors': progress.get('errors') or 0,
                })

            drafted, errors = _execute_draft_targets(
                admin,
                owner,
                targets,
                contact_by_email,
                on_progress=on_progress,
            )
            _patch_draft_job(owner, {
                'status': 'done',
                'completed': len(targets),
                'drafted': drafted,
                'errors': errors,
                'current_email': '',
                'finished_at': datetime.utcnow().isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            _patch_draft_job(owner, {
                'status': 'error',
                'error': str(exc)[:400],
                'finished_at': datetime.utcnow().isoformat(),
            })


def _draft_job_response(owner: str, job: dict) -> dict:
    store = get_long_gap_dispatch_rows(owner)
    return {
        'success': True,
        'job_id': job.get('job_id') or '',
        'status': job.get('status') or 'unknown',
        'total': job.get('total') or 0,
        'completed': job.get('completed') or 0,
        'drafted': job.get('drafted') or 0,
        'errors': job.get('errors') or 0,
        'current_email': job.get('current_email') or '',
        'error': job.get('error') or '',
        'started_at': job.get('started_at') or '',
        'finished_at': job.get('finished_at') or '',
        'updated_at': store.get('updated_at') or '',
    }


def start_draft_long_gap_dispatch_job(
    admin: dict,
    *,
    emails: Optional[List[str]] = None,
    force: bool = False,
) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    owner = normalize_admin_email(admin.get('email') or '')
    existing_job = _get_draft_job(owner)
    if existing_job and existing_job.get('status') == 'running':
        return _draft_job_response(owner, existing_job), 200

    contacts = build_long_gap_contact_list(admin)
    contact_by_email = {
        normalize_admin_email(row.get('email') or ''): row for row in contacts
    }
    store = get_long_gap_dispatch_rows(owner)
    rows = store.get('rows') or {}
    targets, skip_patches = _collect_draft_targets(rows, emails=emails, force=force)

    if force:
        for row in targets:
            email_key = normalize_admin_email(row.get('email') or '')
            if email_key:
                patch_long_gap_dispatch_row(
                    owner,
                    email_key,
                    {
                        'draft_status': 'pending',
                        'draft_body': '',
                        'draft_error': '',
                    },
                )

    for email_key, patch in skip_patches:
        patch_long_gap_dispatch_row(owner, email_key, patch)

    if not targets:
        _set_draft_job(owner, None)
        saved = get_long_gap_dispatch_rows(owner)
        return {
            'success': True,
            'status': 'done',
            'job_id': '',
            'total': 0,
            'completed': 0,
            'drafted': 0,
            'errors': 0,
            'rows': saved.get('rows') or rows,
            'updated_at': saved.get('updated_at') or '',
            'use_template_drafts': not long_gap_dispatch_use_llm(),
        }, 200

    if not long_gap_dispatch_use_llm():
        try:
            drafted, errors = _execute_draft_targets(
                admin,
                owner,
                targets,
                contact_by_email,
            )
        except RuntimeError as exc:
            return {'error': str(exc)}, 503
        saved = get_long_gap_dispatch_rows(owner)
        return {
            'success': True,
            'status': 'done',
            'job_id': '',
            'total': len(targets),
            'completed': len(targets),
            'drafted': drafted,
            'errors': errors,
            'rows': saved.get('rows') or rows,
            'updated_at': saved.get('updated_at') or '',
            'use_template_drafts': True,
            'message': f'Applied templates to {drafted} approved contact(s)',
        }, 200

    if not llm_configured():
        return {'error': 'No LLM API key configured for drafting'}, 503

    job_id = uuid.uuid4().hex
    job = {
        'job_id': job_id,
        'status': 'running',
        'total': len(targets),
        'completed': 0,
        'drafted': 0,
        'errors': 0,
        'current_email': '',
        'error': '',
        'started_at': datetime.utcnow().isoformat(),
        'finished_at': '',
    }
    _set_draft_job(owner, job)

    thread = threading.Thread(
        target=_draft_job_runner,
        args=(admin, owner, targets, contact_by_email, job_id),
        name=f'long-gap-draft-{job_id[:8]}',
        daemon=True,
    )
    thread.start()

    response = _draft_job_response(owner, job)
    response['message'] = f'Drafting {len(targets)} approved contact(s) in background'
    return response, 202


def get_draft_long_gap_dispatch_job_status(admin: dict) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    owner = normalize_admin_email(admin.get('email') or '')
    job = _get_draft_job(owner)
    if not job:
        saved = get_long_gap_dispatch_rows(owner)
        return {
            'success': True,
            'status': 'idle',
            'job_id': '',
            'total': 0,
            'completed': 0,
            'drafted': 0,
            'errors': 0,
            'updated_at': saved.get('updated_at') or '',
        }, 200
    return _draft_job_response(owner, job), 200


def draft_long_gap_dispatch(
    admin: dict,
    *,
    emails: Optional[List[str]] = None,
    force: bool = False,
) -> Tuple[dict, int]:
    """Synchronous draft (tests / legacy). Prefer start_draft_long_gap_dispatch_job."""
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    contacts = build_long_gap_contact_list(admin)
    contact_by_email = {
        normalize_admin_email(row.get('email') or ''): row for row in contacts
    }
    owner = normalize_admin_email(admin.get('email') or '')
    store = get_long_gap_dispatch_rows(owner)
    rows = store.get('rows') or {}
    targets, skip_patches = _collect_draft_targets(rows, emails=emails, force=force)

    for email_key, patch in skip_patches:
        patch_long_gap_dispatch_row(owner, email_key, patch)

    if not targets:
        saved = get_long_gap_dispatch_rows(owner)
        return {
            'success': True,
            'drafted': 0,
            'rows': saved.get('rows') or rows,
            'updated_at': saved.get('updated_at') or '',
            'use_template_drafts': not long_gap_dispatch_use_llm(),
        }, 200

    try:
        drafted, _errors = _execute_draft_targets(
            admin,
            owner,
            targets,
            contact_by_email,
        )
    except RuntimeError as exc:
        return {'error': str(exc)}, 503

    saved = get_long_gap_dispatch_rows(owner)
    return {
        'success': True,
        'drafted': drafted,
        'rows': saved.get('rows') or rows,
        'updated_at': saved.get('updated_at') or '',
        'use_template_drafts': not long_gap_dispatch_use_llm(),
    }, 200


def _long_gap_dp_card_image_url(
    row: dict,
    catalog_entry: Optional[dict],
) -> Optional[str]:
    dp_label = (row.get('dp_label') or '').strip()
    if catalog_entry:
        dp_label = (
            catalog_entry.get('name')
            or dp_label
            or catalog_entry.get('slug')
            or ''
        ).strip()
    return dp_workgroup_card_image_url(dp_label=dp_label)


def _long_gap_send_body_for_row(
    owner: str,
    row: dict,
    contact: dict,
) -> str:
    body = (row.get('draft_body') or '').strip()
    invitee_name = _sanitize_person_display_name(row.get('name') or contact.get('name') or '')
    if body:
        body = _sanitize_stored_invite_draft(body, invitee_name=invitee_name)
    else:
        catalog = _dispatch_catalog()
        by_id, _ = _catalog_lookup(catalog)
        dp_id = (row.get('dp_suggestion') or '').strip()
        catalog_entry = by_id.get(dp_id) if dp_id else None
        body = render_long_gap_template_email(row, contact, catalog_entry=catalog_entry)
    return normalize_long_gap_greeting_in_body(body, invitee_name)


def _send_long_gap_plain_email(
    inviter,
    to_email: str,
    to_name: str,
    body: str,
    *,
    dp_card_image_url: Optional[str] = None,
) -> bool:
    """Send long-gap outreach without a workgroup invitation (no-DP path)."""
    from services.assist import strip_em_dashes
    from services.zoho_mail import normalize_admin_email

    clean_body = sanitize_invite_email_body(strip_em_dashes((body or '').strip()))
    if not clean_body:
        return False
    clean_name = _sanitize_person_display_name(to_name)
    return send_long_gap_outreach_email(
        inviter,
        normalize_admin_email(to_email),
        clean_name or to_name,
        clean_body,
        dp_card_image_url=dp_card_image_url,
    )


def send_long_gap_dispatch_email(
    admin: dict,
    *,
    email: str,
    test_mode: bool = False,
    test_recipient_email: str = '',
) -> Tuple[dict, int]:
    """Send one approved long-gap draft to the contact or a test inbox."""
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    from models import User, Workgroup
    from services.dp_admin_invite_store import list_admin_invite_sends, record_admin_invite_send
    from services.workgroup_invite_ai import send_admin_invitation_email

    owner = normalize_admin_email(admin.get('email') or '')
    source_email = normalize_admin_email(email)
    if not source_email:
        return {'error': 'email is required'}, 400

    contacts = build_long_gap_contact_list(admin)
    contact_by_email = {
        normalize_admin_email(row.get('email') or ''): row for row in contacts
    }
    store = get_long_gap_dispatch_rows(owner)
    rows = store.get('rows') or {}
    row = rows.get(source_email)
    if not isinstance(row, dict):
        return {'error': 'dispatch row not found'}, 404
    if not row.get('approved'):
        return {'error': 'Contact is not approved for send'}, 400
    if row.get('skip'):
        return {'error': 'Contact is marked skip'}, 400

    contact = contact_by_email.get(source_email) or {}
    body = _long_gap_send_body_for_row(owner, row, contact)
    if not body:
        return {'error': 'No draft body available. Draft approved contacts first.'}, 400

    catalog = _dispatch_catalog()
    by_id, _ = _catalog_lookup(catalog)
    dp_id = (row.get('dp_suggestion') or '').strip()
    catalog_entry = by_id.get(dp_id) if dp_id else None
    dp_card_image_url = _long_gap_dp_card_image_url(row, catalog_entry) if dp_id else None

    inviter = User.query.get(admin.get('id'))
    if not inviter:
        return {'error': 'Inviter not found'}, 404

    deliver_email = source_email
    deliver_name = _sanitize_person_display_name(
        row.get('name') or contact.get('name') or source_email
    )
    audit_source = 'long_gap_dispatch'
    audit_status = 'sent'

    if test_mode:
        test_to = normalize_admin_email(test_recipient_email or owner)
        if not test_to:
            return {'error': 'test_recipient_email is required in test mode'}, 400
        deliver_email = test_to
        # Greeting uses source contact name (deliver_name); only delivery address changes.
        audit_source = 'long_gap_dispatch|test'
        audit_status = 'client_prepared'

        # Preview-only: send rendered draft without membership checks or invitations.
        sent = _send_long_gap_plain_email(
            inviter,
            deliver_email,
            deliver_name,
            body,
            dp_card_image_url=dp_card_image_url,
        )
        if not sent:
            return {'error': 'Email send failed'}, 500
        record = record_admin_invite_send(
            admin=admin,
            recipient_email=deliver_email,
            recipient_name=deliver_name,
            workgroup_ids=[],
            body=body,
            status=audit_status,
            send_mode='platform',
            source=audit_source,
            message_strategy='long_gap_reconnect',
        )
        return {
            'success': True,
            'send_record_id': record.id,
            'test_mode': True,
            'test_for_email': source_email,
            'delivered_to': deliver_email,
        }, 200

    if dp_id:
        payload, status = send_admin_invitation_email(
            primary_workgroup_id=dp_id,
            inviter_id=admin['id'],
            name=deliver_name,
            email=deliver_email,
            body=body,
            send_mode='platform',
            audit_source=audit_source,
            audit_status=audit_status,
            message_strategy='long_gap_reconnect',
            force_inline_join_links=True,
            long_gap_outreach=True,
            long_gap_dp_image_url=dp_card_image_url,
        )
        if status >= 400 or payload.get('blocked') or payload.get('error'):
            return payload, status
        payload['send_records'] = list_admin_invite_sends(
            admin,
            recipient_email=source_email,
            limit=5,
        )
        return payload, status

    sent = _send_long_gap_plain_email(
        inviter,
        deliver_email,
        deliver_name,
        body,
        dp_card_image_url=None,
    )
    if not sent:
        return {'error': 'Email send failed'}, 500

    record = record_admin_invite_send(
        admin=admin,
        recipient_email=deliver_email,
        recipient_name=deliver_name,
        workgroup_ids=[],
        body=body,
        status=audit_status,
        send_mode='platform',
        source=audit_source,
        message_strategy='long_gap_reconnect',
    )
    payload = {
        'success': True,
        'send_record_id': record.id,
        'delivered_to': deliver_email,
        'send_records': list_admin_invite_sends(
            admin,
            recipient_email=source_email,
            limit=5,
        ),
    }
    return payload, 200


def _long_gap_production_already_sent(admin: dict, email: str) -> bool:
    """True when a production long-gap dispatch email was already sent to this contact."""
    from services.dp_admin_invite_store import list_admin_invite_sends

    rows = list_admin_invite_sends(admin, recipient_email=email, limit=20)
    for row in rows:
        if (row.get('status') or '').strip().lower() != 'sent':
            continue
        source = (row.get('source') or '').strip().lower()
        if _LONG_GAP_PRODUCTION_SOURCE in source and 'test' not in source:
            return True
    return False


def _collect_send_all_targets(admin: dict) -> Tuple[List[str], int]:
    """Return approved contacts ready to send and how many were already sent."""
    owner = normalize_admin_email(admin.get('email') or '')
    store = get_long_gap_dispatch_rows(owner)
    rows = store.get('rows') or {}
    to_send: List[str] = []
    already_sent = 0
    for contact in build_long_gap_contact_list(admin):
        email = normalize_admin_email(contact.get('email') or '')
        row = rows.get(email)
        if not isinstance(row, dict):
            continue
        if not row.get('approved') or row.get('skip'):
            continue
        if not (row.get('draft_body') or '').strip():
            continue
        if _long_gap_production_already_sent(admin, email):
            already_sent += 1
            continue
        to_send.append(email)
    return to_send, already_sent


def _get_send_job(owner: str) -> Optional[dict]:
    payload = _load_dispatch_payload(owner)
    job = payload.get('send_job')
    return job if isinstance(job, dict) else None


def _set_send_job(owner: str, job: Optional[dict]) -> str:
    payload = _load_dispatch_payload(owner)
    if job is None:
        payload.pop('send_job', None)
    else:
        payload['send_job'] = job
    return _save_dispatch_payload(owner, payload)


def _patch_send_job(owner: str, patch: dict) -> Optional[dict]:
    payload = _load_dispatch_payload(owner)
    job = payload.get('send_job')
    if not isinstance(job, dict):
        return None
    job.update(patch)
    payload['send_job'] = job
    _save_dispatch_payload(owner, payload)
    return job


def _send_job_response(owner: str, job: dict) -> dict:
    store = get_long_gap_dispatch_rows(owner)
    error_details = job.get('error_details')
    if not isinstance(error_details, list):
        error_details = []
    return {
        'success': True,
        'job_id': job.get('job_id') or '',
        'status': job.get('status') or 'unknown',
        'total': job.get('total') or 0,
        'already_sent': job.get('already_sent') or 0,
        'completed': job.get('completed') or 0,
        'sent': job.get('sent') or 0,
        'skipped': job.get('skipped') or 0,
        'errors': job.get('errors') or 0,
        'error_details': error_details[:50],
        'current_email': job.get('current_email') or '',
        'error': job.get('error') or '',
        'started_at': job.get('started_at') or '',
        'finished_at': job.get('finished_at') or '',
        'updated_at': store.get('updated_at') or '',
    }


def _send_job_runner(
    admin: dict,
    owner: str,
    emails: List[str],
    job_id: str,
) -> None:
    flask_app = _flask_app()
    with flask_app.app_context():
        sent = 0
        skipped = 0
        error_count = 0
        error_details: List[dict] = []
        completed = 0
        try:
            for index, email in enumerate(emails):
                if _long_gap_production_already_sent(admin, email):
                    skipped += 1
                    completed += 1
                    _patch_send_job(owner, {
                        'status': 'running',
                        'completed': completed,
                        'sent': sent,
                        'skipped': skipped,
                        'errors': error_count,
                        'error_details': error_details,
                        'current_email': email,
                    })
                    continue

                payload, status = send_long_gap_dispatch_email(
                    admin,
                    email=email,
                    test_mode=False,
                )
                if status >= 400 or payload.get('blocked') or payload.get('error'):
                    error_count += 1
                    error_details.append({
                        'email': email,
                        'error': (payload.get('error') or 'send failed')[:300],
                    })
                else:
                    sent += 1
                completed += 1
                _patch_send_job(owner, {
                    'status': 'running',
                    'completed': completed,
                    'sent': sent,
                    'skipped': skipped,
                    'errors': error_count,
                    'error_details': error_details,
                    'current_email': email,
                })
                if index < len(emails) - 1:
                    time.sleep(_SEND_INTERVAL_SEC)

            _patch_send_job(owner, {
                'status': 'done',
                'completed': len(emails),
                'sent': sent,
                'skipped': skipped,
                'errors': error_count,
                'error_details': error_details,
                'current_email': '',
                'finished_at': datetime.utcnow().isoformat(),
            })
        except Exception as exc:  # noqa: BLE001
            _patch_send_job(owner, {
                'status': 'error',
                'error': str(exc)[:400],
                'finished_at': datetime.utcnow().isoformat(),
            })


def start_send_all_long_gap_dispatch_job(admin: dict) -> Tuple[dict, int]:
    """Send all approved long-gap drafts in a background job (production only)."""
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    owner = normalize_admin_email(admin.get('email') or '')
    existing_job = _get_send_job(owner)
    if existing_job and existing_job.get('status') == 'running':
        return _send_job_response(owner, existing_job), 200

    emails, already_sent = _collect_send_all_targets(admin)
    if not emails:
        _set_send_job(owner, None)
        return {
            'success': True,
            'status': 'done',
            'job_id': '',
            'total': 0,
            'already_sent': already_sent,
            'completed': 0,
            'sent': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': [],
            'message': (
                f'No pending contacts to send ({already_sent} already sent).'
                if already_sent
                else 'No approved contacts with drafts are ready to send.'
            ),
        }, 200

    job_id = uuid.uuid4().hex
    job = {
        'job_id': job_id,
        'status': 'running',
        'total': len(emails),
        'already_sent': already_sent,
        'completed': 0,
        'sent': 0,
        'skipped': 0,
        'errors': 0,
        'error_details': [],
        'current_email': '',
        'error': '',
        'started_at': datetime.utcnow().isoformat(),
        'finished_at': '',
    }
    _set_send_job(owner, job)

    thread = threading.Thread(
        target=_send_job_runner,
        args=(admin, owner, emails, job_id),
        name=f'long-gap-send-{job_id[:8]}',
        daemon=True,
    )
    thread.start()

    response = _send_job_response(owner, job)
    response['message'] = f'Sending to {len(emails)} approved contact(s)'
    return response, 202


def get_send_all_long_gap_dispatch_job_status(admin: dict) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403

    owner = normalize_admin_email(admin.get('email') or '')
    job = _get_send_job(owner)
    if not job:
        saved = get_long_gap_dispatch_rows(owner)
        return {
            'success': True,
            'status': 'idle',
            'job_id': '',
            'total': 0,
            'already_sent': 0,
            'completed': 0,
            'sent': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': [],
            'updated_at': saved.get('updated_at') or '',
        }, 200
    return _send_job_response(owner, job), 200


def get_long_gap_dispatch_template(admin: dict) -> Tuple[dict, int]:
    if not is_dp_site_admin(admin):
        return {'error': 'DP site admin required'}, 403
    return {
        'success': True,
        'template': get_long_gap_template_structure(),
        'subject': LONG_GAP_EMAIL_SUBJECT,
        'use_template_drafts': not long_gap_dispatch_use_llm(),
    }, 200


def parse_classify_result_item(item: dict, catalog: List[dict]) -> dict:
    """Parse a single classification JSON object (for tests)."""
    by_id, by_slug = _catalog_lookup(catalog)
    email = normalize_admin_email(item.get('email') or '')
    dp_id, dp_label = _resolve_dp_entry(
        item.get('dp_slug') or item.get('workgroup_id'),
        by_id,
        by_slug,
    )
    return {
        'email': email,
        'dp_suggestion': dp_id,
        'dp_label': dp_label,
        'confidence': _normalize_confidence(item.get('confidence')),
        'skip': bool(item.get('skip')),
        'skip_reason': (item.get('skip_reason') or '').strip(),
        'intern_alum': bool(item.get('intern_alum')),
        'why': (item.get('why') or '').strip(),
    }
