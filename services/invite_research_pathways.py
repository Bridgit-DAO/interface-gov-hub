"""Admin invite research pathways: Zoho mail, web search, URL author extraction."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from services.assist import LlmCallFailed, LlmTemporarilyBusy, call_llm, llm_configured, resolve_llm_config
from services.web_research import extract_linkedin_vanity, fetch_url_text, web_search
from services.workgroup_invite_ai import _NO_EM_DASH_RULE, _parse_json_object
from services.zoho_mail import search_meta_layer_contacts, zoho_mail_pathway_available

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


def _rank_zoho_contacts(contacts: List[dict]) -> List[dict]:
    if not contacts:
        return []
    if not llm_configured():
        return [
            {
                'id': row['email'],
                'name': row.get('name') or row['email'],
                'email': row['email'],
                'confidence': 'medium',
                'score': 55,
                'summary': '; '.join((row.get('subjects') or [])[:2])[:400],
                'message_count': row.get('message_count') or 0,
                'last_contact': row.get('last_contact') or '',
                'sample_subjects': (row.get('subjects') or [])[:4],
            }
            for row in contacts[:20]
        ]

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
    out: List[dict] = []
    for row in contacts:
        email = row['email']
        ranked = ranked_by_email.get(email.lower(), {})
        try:
            score = int(ranked.get('score'))
        except (TypeError, ValueError):
            score = min(95, 40 + int(row.get('message_count') or 0) * 8)
        score = max(0, min(100, score))
        out.append({
            'id': email,
            'name': row.get('name') or email,
            'email': email,
            'confidence': _confidence_from_score(score),
            'score': score,
            'summary': (ranked.get('summary') or '; '.join((row.get('subjects') or [])[:2]))[:500],
            'message_count': row.get('message_count') or 0,
            'last_contact': row.get('last_contact') or '',
            'sample_subjects': (row.get('subjects') or [])[:4],
            'snippets': (row.get('snippets') or [])[:3],
        })
    out.sort(key=lambda item: (-item['score'], -item['message_count'], item['email']))
    return out[:25]


def pathway_zoho_mail_contacts() -> Tuple[dict, int]:
    try:
        raw = search_meta_layer_contacts()
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
            'contacts': [],
        }, 200

    contacts = _rank_zoho_contacts(raw.get('contacts') or [])
    return {
        'success': True,
        'configured': True,
        'source': raw.get('source') or 'live',
        'exported_at': raw.get('exported_at') or '',
        'message_count': raw.get('message_count') or 0,
        'contacts': contacts,
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

    if zoho_contact:
        name = (zoho_contact.get('name') or '').strip()
        email = (zoho_contact.get('email') or '').strip()
        if zoho_contact.get('summary'):
            previous_parts.append(str(zoho_contact['summary']))
        subjects = zoho_contact.get('sample_subjects') or []
        if subjects:
            previous_parts.append('Recent email subjects: ' + '; '.join(subjects[:4]))
        snippets = zoho_contact.get('snippets') or []
        if snippets:
            previous_parts.append('Email context: ' + ' '.join(snippets[:2])[:800])

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
    }
