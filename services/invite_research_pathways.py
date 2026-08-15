"""Admin invite research pathways: Zoho mail, web search, URL author extraction."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.assist import LlmCallFailed, LlmTemporarilyBusy, call_llm, llm_configured, resolve_llm_config
from services.invite_message_strategy import suggest_message_strategy
from services.web_research import extract_linkedin_vanity, fetch_url_text, web_search
from services.workgroup_invite_ai import _NO_EM_DASH_RULE, _parse_json_object
from services.zoho_mail import (
    normalize_admin_email,
    outreach_selection_reasons,
    search_meta_layer_contacts,
    zoho_mail_pathway_available,
)

_PATHWAY_RESEARCH_MAX_TOKENS = 2400

_META_LAYER_HINT = (
    'Meta-layer, Desirable Properties, Gov Hub, layered web, workgroups, governance, '
    'interoperability, and related civic-tech topics.'
)


def _confidence_from_score(score: int) -> str:
    if score >= 75:
        return 'high'
    if score >= 45:
        return 'medium'
    return 'low'


def format_contact_recency(last_contact: str) -> str:
    """Turn last_contact ISO-ish timestamp into natural recency phrasing for drafts."""
    cleaned = (last_contact or '').strip()
    if not cleaned:
        return 'unknown recency'
    date_part = cleaned[:10]
    try:
        contact_dt = datetime.strptime(date_part, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return 'recently' if cleaned else 'unknown recency'
    now = datetime.now(timezone.utc)
    days = (now - contact_dt).days
    if days < 0:
        return 'recently'
    if days <= 7:
        return 'within the past week'
    if days <= 31:
        return 'within the past month'
    if days <= 90:
        return 'a few months ago'
    if days <= 365:
        return 'earlier this year' if days > 120 else 'several months ago'
    if days <= 730:
        return 'over a year ago'
    return 'quite a while ago'


def infer_communication_style(
    snippets: Optional[List[str]] = None,
    subjects: Optional[List[str]] = None,
) -> dict:
    """Lightweight style labels from prior email snippets (no LLM call)."""
    text = ' '.join(snippets or []).strip()
    subjects_text = ' '.join(subjects or [])
    combined = f'{text} {subjects_text}'.lower()
    if not combined.strip():
        return {
            'labels': [],
            'notes': 'No prior email content available.',
            'formality': 'neutral',
            'verbosity': 'medium',
        }

    labels: List[str] = []
    formal_signals = (
        'dear', 'regards', 'sincerely', 'respectfully', 'please find attached', 'kindly',
    )
    casual_signals = (
        'hey', 'hi there', 'thanks!', 'cheers', 'gonna', 'awesome', 'cool', 'lol',
    )
    formal_count = sum(1 for signal in formal_signals if signal in combined)
    casual_count = sum(1 for signal in casual_signals if signal in combined)
    if formal_count > casual_count + 1:
        formality = 'formal'
        labels.append('formal')
    elif casual_count > formal_count:
        formality = 'casual'
        labels.append('casual')
    else:
        formality = 'neutral'
        labels.append('professional')

    word_count = len(text.split())
    if word_count < 30:
        verbosity = 'terse'
        labels.append('terse')
    elif word_count > 120:
        verbosity = 'verbose'
        labels.append('verbose')
    else:
        verbosity = 'medium'

    tech_signals = (
        'api', 'schema', 'deploy', 'github', 'json', 'protocol', 'rfc',
        'implementation', 'architecture', 'interoperability',
    )
    if any(signal in combined for signal in tech_signals):
        labels.append('technical')

    warm_signals = (
        'great to', 'wonderful', 'appreciate', 'thank you so much',
        'looking forward', 'excited', 'hope you', 'lovely', 'grateful',
    )
    if any(signal in combined for signal in warm_signals):
        labels.append('warm')

    notes_parts: List[str] = []
    if formality == 'formal':
        notes_parts.append('Uses formal salutations and closing language.')
    elif formality == 'casual':
        notes_parts.append('Uses casual, conversational tone.')
    if verbosity == 'terse':
        notes_parts.append('Keeps messages brief.')
    elif verbosity == 'verbose':
        notes_parts.append('Writes longer, detailed messages.')
    if 'technical' in labels:
        notes_parts.append('Discusses technical or implementation details.')
    if 'warm' in labels:
        notes_parts.append('Expresses warmth and enthusiasm.')

    return {
        'labels': list(dict.fromkeys(labels))[:5],
        'notes': ' '.join(notes_parts) or 'Standard business email tone.',
        'formality': formality,
        'verbosity': verbosity,
    }


def build_zoho_contact_context(zoho_contact: dict) -> dict:
    """Structured Zoho mail history for invite research and draft prompts."""
    snippets = list(zoho_contact.get('snippets') or [])
    subjects = list(
        zoho_contact.get('sample_subjects') or zoho_contact.get('subjects') or [],
    )
    style = infer_communication_style(snippets, subjects)
    last_contact = (zoho_contact.get('last_contact') or '').strip()
    suggested_strategy = suggest_message_strategy(last_contact)
    return {
        'source': 'zoho_mail',
        'email': (zoho_contact.get('email') or '').strip(),
        'name': (zoho_contact.get('name') or '').strip(),
        'last_contact': last_contact,
        'last_contact_recency': format_contact_recency(last_contact),
        'message_count': int(zoho_contact.get('message_count') or 0),
        'subjects': subjects[:6],
        'snippets': [str(snippet)[:400] for snippet in snippets[:4]],
        'summary': (zoho_contact.get('summary') or '')[:500],
        'communication_style': style,
        'suggested_strategy': suggested_strategy,
        'message_strategy': suggested_strategy,
    }


def _llm_json(system: str, user_payload: dict) -> dict:
    if not llm_configured():
        raise RuntimeError('No LLM API key configured')
    cfg = resolve_llm_config()
    if not cfg:
        raise RuntimeError('No LLM API key configured')
    raw = call_llm(
        [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(user_payload)},
        ],
        cfg,
        max_tokens=_PATHWAY_RESEARCH_MAX_TOKENS,
    )
    return _parse_json_object(raw)


_MAX_LLM_ZOHO_RANK = 60


def _heuristic_zoho_score(row: dict) -> int:
    meta_msgs = int(row.get('meta_layer_message_count') or 0)
    msg_count = int(row.get('message_count') or 0)
    keyword_score = int(row.get('keyword_score') or 0)
    if meta_msgs > 0:
        return min(
            98,
            40 + meta_msgs * 14 + min(keyword_score * 4, 20) + min(msg_count, 12),
        )
    return min(72, 20 + min(msg_count, 15) * 4)


def _format_ranked_zoho_contact(row: dict, *, score: int, summary: str = '') -> dict:
    snippets = (row.get('snippets') or [])[:3]
    subjects = (row.get('subjects') or row.get('sample_subjects') or [])[:4]
    style = infer_communication_style(snippets, subjects)
    last_contact = (row.get('last_contact') or '').strip()
    suggested_strategy = suggest_message_strategy(last_contact)
    return {
        'id': row['email'],
        'name': row.get('name') or row['email'],
        'email': row['email'],
        'confidence': _confidence_from_score(score),
        'score': score,
        'summary': (summary or '; '.join(subjects[:2]))[:500],
        'message_count': row.get('message_count') or 0,
        'meta_layer_message_count': row.get('meta_layer_message_count') or 0,
        'last_contact': last_contact,
        'sample_subjects': subjects,
        'snippets': snippets,
        'communication_style': style,
        'suggested_strategy': suggested_strategy,
        'message_strategy': suggested_strategy,
        'selection_reason': outreach_selection_reasons(row),
    }


def _rank_zoho_contacts(contacts: List[dict]) -> List[dict]:
    if not contacts:
        return []
    if not llm_configured() or len(contacts) > _MAX_LLM_ZOHO_RANK:
        out: List[dict] = []
        for row in contacts:
            score = _heuristic_zoho_score(row)
            out.append(_format_ranked_zoho_contact(row, score=score))
        out.sort(key=lambda item: (-item['score'], -item['message_count'], item['email']))
        return out

    system = (
        'You rank email contacts for a Desirable Properties / meta-layer outreach workflow. '
        'Respond with JSON only. Required key: contacts (array of '
        '{email, confidence, score, summary}). confidence is high|medium|low. '
        'score is 0-100 for meta-layer relevance. summary is one sentence of useful invite context. '
        f'{_NO_EM_DASH_RULE}'
    )
    try:
        analysis = _llm_json(system, {'contacts': contacts, 'topic_hint': _META_LAYER_HINT})
    except (json.JSONDecodeError, LlmCallFailed, LlmTemporarilyBusy, RuntimeError):
        analysis = {'contacts': []}

    ranked_by_email = {
        (item.get('email') or '').strip().lower(): item
        for item in analysis.get('contacts') or []
        if isinstance(item, dict)
    }
    out = []
    for row in contacts:
        email = row['email']
        ranked = ranked_by_email.get(email.lower(), {})
        try:
            score = int(ranked.get('score'))
        except (TypeError, ValueError):
            score = _heuristic_zoho_score(row)
        score = max(0, min(100, score))
        out.append(
            _format_ranked_zoho_contact(
                row,
                score=score,
                summary=(ranked.get('summary') or '')[:500],
            ),
        )
    out.sort(key=lambda item: (-item['score'], -item['message_count'], item['email']))
    return out


def pathway_zoho_mail_contacts(
    *,
    admin_email: str = '',
    admin: Optional[dict] = None,
    show_hidden: bool = False,
) -> Tuple[dict, int]:
    try:
        raw = search_meta_layer_contacts(admin_email=admin_email)
    except Exception as exc:  # noqa: BLE001 - surface provider errors to admin UI
        return {
            'configured': zoho_mail_pathway_available(),
            'error': str(exc)[:300],
            'contacts': [],
        }, 502

    if not raw.get('configured'):
        return {
            'configured': False,
            'error': raw.get('error') or 'Zoho Mail is not configured',
            'snapshot_path': raw.get('snapshot_path') or '',
            'contacts': [],
        }, 200

    contacts = _rank_zoho_contacts(raw.get('contacts') or [])
    visibility_meta = {
        'hidden_count': 0,
        'visible_count': len(contacts),
        'show_hidden': show_hidden,
    }
    if admin:
        from services.dp_admin_invite_store import filter_visible_zoho_contacts

        contacts, visibility_meta = filter_visible_zoho_contacts(
            contacts,
            admin,
            show_hidden=show_hidden,
        )
    return {
        'success': True,
        'configured': True,
        'source': raw.get('source') or 'live',
        'exported_at': raw.get('exported_at') or '',
        'owner_email': raw.get('owner_email') or normalize_admin_email(admin_email),
        'snapshot_path': raw.get('snapshot_path') or '',
        'message_count': raw.get('message_count') or 0,
        'snapshot_contact_count': raw.get('snapshot_contact_count'),
        'outreach_contact_count': raw.get('outreach_contact_count'),
        'contacts': contacts,
        **visibility_meta,
    }, 200


def pathway_name_search(*, name: str, context: str = '') -> Tuple[dict, int]:
    clean_name = (name or '').strip()
    if not clean_name:
        return {'error': 'Name is required'}, 400

    query = ' '.join(part for part in [clean_name, (context or '').strip(), 'meta-layer desirable properties'] if part)
    hits = web_search(query, limit=10)
    if not hits:
        return {
            'success': True,
            'query': query,
            'results': [],
            'search_available': False,
            'message': 'No search API key configured (BRAVE_SEARCH_API_KEY or TAVILY_API_KEY).',
        }, 200

    if llm_configured():
        system = (
            'You score web search hits for recruiting someone to Desirable Properties workgroups. '
            'Respond with JSON only. Required key: results (array of '
            '{url, relevance_score, relevance, rationale}). relevance is high|medium|low. '
            'relevance_score is 0-100. Only include hits that plausibly refer to the target person/topic. '
            f'{_NO_EM_DASH_RULE}'
        )
        try:
            analysis = _llm_json(
                system,
                {'target_name': clean_name, 'context': (context or '').strip(), 'search_hits': hits},
            )
            ranked = {
                (item.get('url') or '').strip(): item
                for item in analysis.get('results') or []
                if isinstance(item, dict)
            }
        except (json.JSONDecodeError, LlmCallFailed, LlmTemporarilyBusy, RuntimeError):
            ranked = {}
    else:
        ranked = {}

    results: List[dict] = []
    for index, hit in enumerate(hits):
        url = (hit.get('url') or '').strip()
        item = ranked.get(url, {})
        try:
            score = int(item.get('relevance_score'))
        except (TypeError, ValueError):
            score = max(20, 88 - index * 8)
        score = max(0, min(100, score))
        results.append({
            'id': url or f'hit-{index}',
            'url': url,
            'title': hit.get('title') or '',
            'snippet': hit.get('snippet') or '',
            'relevance': _confidence_from_score(score),
            'relevance_score': score,
            'rationale': (item.get('rationale') or hit.get('snippet') or '')[:400],
        })
    results.sort(key=lambda row: -row['relevance_score'])
    return {
        'success': True,
        'query': query,
        'search_available': True,
        'results': results,
    }, 200


def _guess_emails_for_name(name: str, *, limit: int = 6) -> List[dict]:
    hits = web_search(f'"{name}" email contact', limit=limit)
    emails: List[dict] = []
    seen = set()
    email_re = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
    for hit in hits:
        for match in email_re.findall(' '.join([hit.get('title') or '', hit.get('snippet') or ''])):
            normalized = match.strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            emails.append({
                'email': normalized,
                'source_url': hit.get('url') or '',
                'source_title': hit.get('title') or '',
            })
    return emails[:5]


def pathway_url_authors(*, url: str) -> Tuple[dict, int]:
    raw_url = (url or '').strip()
    if not raw_url:
        return {'error': 'URL is required'}, 400
    if not raw_url.startswith(('http://', 'https://')):
        raw_url = f'https://{raw_url.lstrip("/")}'

    fetched = fetch_url_text(raw_url)
    if not fetched.get('ok'):
        return {'error': fetched.get('error') or 'Could not fetch URL', 'url': raw_url}, 400

    page_text = (fetched.get('text') or '')[:10000]
    title = ''
    if llm_configured():
        system = (
            'You extract people from a web page for outreach about Desirable Properties / meta-layer work. '
            'Respond with JSON only. Required keys: page_title, page_summary, authors (array of '
            '{name, role, context, confidence, score}). confidence is high|medium|low. '
            'score is 0-100 for how likely this person is a primary author or key subject. '
            f'{_NO_EM_DASH_RULE}'
        )
        try:
            analysis = _llm_json(system, {'url': raw_url, 'page_text': page_text})
        except (json.JSONDecodeError, LlmCallFailed, LlmTemporarilyBusy, RuntimeError) as exc:
            return {'error': f'Author extraction failed: {exc}'}, 502
    else:
        return {'error': 'No LLM API key configured for author extraction'}, 503

    title = (analysis.get('page_title') or '')[:200]
    page_summary = (analysis.get('page_summary') or '')[:1200]
    authors_out: List[dict] = []
    for index, author in enumerate(analysis.get('authors') or []):
        if not isinstance(author, dict):
            continue
        clean_name = (author.get('name') or '').strip()
        if not clean_name:
            continue
        try:
            score = int(author.get('score'))
        except (TypeError, ValueError):
            score = max(30, 90 - index * 12)
        score = max(0, min(100, score))
        email_candidates = _guess_emails_for_name(clean_name)
        authors_out.append({
            'id': f'{raw_url}::{clean_name}',
            'name': clean_name,
            'role': (author.get('role') or '')[:200],
            'context': (author.get('context') or page_summary)[:800],
            'confidence': _confidence_from_score(score),
            'score': score,
            'source_url': raw_url,
            'email_candidates': email_candidates,
            'suggested_email': (email_candidates[0]['email'] if email_candidates else ''),
        })

    authors_out.sort(key=lambda row: -row['score'])
    return {
        'success': True,
        'url': raw_url,
        'page_title': title,
        'page_summary': page_summary,
        'authors': authors_out,
    }, 200


def build_pathway_context_bundle(
    *,
    zoho_contact: Optional[dict] = None,
    search_results: Optional[List[dict]] = None,
    url_author: Optional[dict] = None,
    page_summary: str = '',
) -> dict:
    """Merge selected pathway items into invite research form fields."""
    name = ''
    email = ''
    previous_parts: List[str] = []
    extra_links: List[str] = []

    zoho_contact_context: Optional[dict] = None
    if zoho_contact:
        zoho_contact_context = build_zoho_contact_context(zoho_contact)
        name = (zoho_contact.get('name') or zoho_contact_context.get('name') or '').strip()
        email = (zoho_contact.get('email') or zoho_contact_context.get('email') or '').strip()
        if zoho_contact.get('summary'):
            previous_parts.append(str(zoho_contact['summary']))
        subjects = zoho_contact_context.get('subjects') or []
        if subjects:
            previous_parts.append('Recent email subjects: ' + '; '.join(subjects[:4]))
        snippets = zoho_contact_context.get('snippets') or []
        if snippets:
            previous_parts.append('Email context: ' + ' '.join(snippets[:2])[:800])
        message_count = int(zoho_contact_context.get('message_count') or 0)
        last_contact = (zoho_contact_context.get('last_contact') or '').strip()
        if message_count or last_contact:
            recency = zoho_contact_context.get('last_contact_recency') or ''
            volume_note = f'{message_count} prior email{"s" if message_count != 1 else ""}'
            if last_contact:
                previous_parts.append(
                    f'Email history: {volume_note}; last contact {last_contact[:10]} ({recency}).',
                )
            else:
                previous_parts.append(f'Email history: {volume_note}.')
        style = (zoho_contact_context.get('communication_style') or {})
        style_labels = style.get('labels') or []
        if style_labels:
            previous_parts.append('Their communication style: ' + ', '.join(style_labels) + '.')

    if url_author:
        if not name:
            name = (url_author.get('name') or '').strip()
        if not email:
            email = (url_author.get('suggested_email') or '').strip()
        role = (url_author.get('role') or '').strip()
        context = (url_author.get('context') or page_summary or '').strip()
        if role:
            previous_parts.append(f'Role/title: {role}')
        if context:
            previous_parts.append(context)
        source = (url_author.get('source_url') or '').strip()
        if source:
            extra_links.append(source)

    if search_results:
        for hit in search_results:
            link = (hit.get('url') or '').strip()
            if link:
                extra_links.append(link)
            rationale = (hit.get('rationale') or hit.get('snippet') or '').strip()
            title = (hit.get('title') or '').strip()
            if title or rationale:
                previous_parts.append(f'{title}: {rationale}'.strip(': '))

    linkedin_url = ''
    for link in extra_links:
        if extract_linkedin_vanity(link):
            linkedin_url = link
            break
    if not linkedin_url and url_author:
        source = (url_author.get('source_url') or '').strip()
        if extract_linkedin_vanity(source):
            linkedin_url = source

    return {
        'name': name,
        'email': email,
        'previous_interaction': '\n\n'.join(part for part in previous_parts if part).strip(),
        'extra_links': extra_links,
        'linkedin_url': linkedin_url,
        'zoho_contact_context': zoho_contact_context,
    }
