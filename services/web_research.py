"""Fetch URLs and optional web search for external contact research."""
from __future__ import annotations

import os
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import requests

_FETCH_TIMEOUT = 12
_MAX_FETCH_CHARS = 12000
_MAX_SNIPPET = 600
_USER_AGENT = 'GovHubWorkgroupInvite/1.0 (+https://hub.themetalayer.org)'


def _strip_html(html: str) -> str:
    text = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def fetch_url_text(url: str) -> Dict[str, Any]:
    raw = (url or '').strip()
    if not raw:
        return {'url': '', 'ok': False, 'error': 'empty url', 'text': ''}
    if not raw.startswith(('http://', 'https://')):
        raw = 'https://' + raw
    try:
        resp = requests.get(
            raw,
            timeout=_FETCH_TIMEOUT,
            headers={'User-Agent': _USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'},
            allow_redirects=True,
        )
        if resp.status_code >= 400:
            return {'url': raw, 'ok': False, 'error': f'HTTP {resp.status_code}', 'text': ''}
        text = _strip_html(resp.text or '')[:_MAX_FETCH_CHARS]
        return {'url': raw, 'ok': True, 'error': '', 'text': text}
    except requests.RequestException as exc:
        return {'url': raw, 'ok': False, 'error': str(exc)[:200], 'text': ''}


def brave_web_search(query: str, *, limit: int = 5) -> List[Dict[str, str]]:
    api_key = (os.environ.get('BRAVE_SEARCH_API_KEY') or '').strip()
    if not api_key:
        return []
    try:
        resp = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            params={'q': query, 'count': min(limit, 10)},
            headers={'Accept': 'application/json', 'X-Subscription-Token': api_key},
            timeout=_FETCH_TIMEOUT,
        )
        if resp.status_code >= 400:
            return []
        data = resp.json()
        out = []
        for item in (data.get('web') or {}).get('results') or []:
            out.append({
                'title': (item.get('title') or '')[:200],
                'url': item.get('url') or '',
                'snippet': (item.get('description') or '')[:_MAX_SNIPPET],
            })
        return out
    except requests.RequestException:
        return []


def tavily_web_search(query: str, *, limit: int = 5) -> List[Dict[str, str]]:
    api_key = (os.environ.get('TAVILY_API_KEY') or '').strip()
    if not api_key:
        return []
    try:
        resp = requests.post(
            'https://api.tavily.com/search',
            json={'api_key': api_key, 'query': query, 'max_results': min(limit, 10)},
            timeout=_FETCH_TIMEOUT,
        )
        if resp.status_code >= 400:
            return []
        data = resp.json()
        out = []
        for item in data.get('results') or []:
            out.append({
                'title': (item.get('title') or '')[:200],
                'url': item.get('url') or '',
                'snippet': (item.get('content') or '')[:_MAX_SNIPPET],
            })
        return out
    except requests.RequestException:
        return []


def web_search(query: str, *, limit: int = 5) -> List[Dict[str, str]]:
    q = (query or '').strip()
    if not q:
        return []
    results = brave_web_search(q, limit=limit)
    if results:
        return results
    return tavily_web_search(q, limit=limit)


def gather_url_corpus(urls: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    corpus = []
    for url in urls:
        u = (url or '').strip()
        if not u or u in seen:
            continue
        seen.add(u)
        corpus.append(fetch_url_text(u))
    return corpus


_LINKEDIN_VANITY_RE = re.compile(r'linkedin\.com/in/([^/?#]+)', re.I)


def extract_linkedin_vanity(url: str) -> str:
    match = _LINKEDIN_VANITY_RE.search(url or '')
    if not match:
        return ''
    return unquote(match.group(1).strip('/'))


def is_linkedin_profile_url(url: str) -> bool:
    return bool(extract_linkedin_vanity(url))


def build_search_query(name: str, linkedin_url: str = '', extra: Optional[List[str]] = None) -> str:
    vanity = extract_linkedin_vanity(linkedin_url)
    clean_name = name.strip()
    if clean_name and vanity:
        return f'"{clean_name}" site:linkedin.com/in/{vanity}'
    parts = [clean_name]
    if linkedin_url.strip():
        parts.append(linkedin_url.strip())
    return ' '.join(part for part in parts if part)


def build_person_search_queries(name: str, linkedin_url: str = '') -> List[str]:
    """Build targeted queries for profile discovery when LinkedIn blocks direct fetch."""
    clean_name = name.strip()
    vanity = extract_linkedin_vanity(linkedin_url)
    queries: List[str] = []
    if clean_name and vanity:
        queries.append(f'site:linkedin.com/in/{vanity} {clean_name}')
        queries.append(f'"{clean_name}" {vanity} linkedin')
        queries.append(f'{clean_name} linkedin profile {vanity}')
    elif clean_name:
        queries.append(f'"{clean_name}" linkedin profile')
    if linkedin_url.strip() and linkedin_url.strip() not in queries:
        queries.append(linkedin_url.strip())
    deduped: List[str] = []
    seen = set()
    for query in queries:
        key = query.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(query)
    return deduped[:4]


def _dedupe_search_results(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for item in results:
        url = (item.get('url') or '').strip()
        key = url.casefold() if url else (item.get('title') or '').casefold()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(item)
    return out


def collect_person_search_results(
    name: str,
    linkedin_url: str = '',
    *,
    limit_per_query: int = 4,
    max_total: int = 8,
) -> List[Dict[str, str]]:
    queries = build_person_search_queries(name, linkedin_url)
    if not queries and name.strip():
        queries = [name.strip()]
    results: List[Dict[str, str]] = []
    for query in queries:
        results.extend(web_search(query, limit=limit_per_query))
        results = _dedupe_search_results(results)
        if len(results) >= max_total:
            break
    return results[:max_total]


def normalize_linkedin_url(url: str) -> str:
    """Normalize user-entered LinkedIn URLs for fetch and research."""
    raw = (url or '').strip()
    if not raw:
        return ''
    if not raw.startswith(('http://', 'https://')):
        raw = f'https://{raw.lstrip("/")}'
    return raw


def _linkedin_fetch_ok(url_corpus: List[Dict[str, Any]], linkedin_url: str) -> bool:
    if not linkedin_url:
        return False
    target = linkedin_url.casefold().rstrip('/')
    for item in url_corpus:
        item_url = (item.get('url') or '').casefold().rstrip('/')
        if item_url != target:
            continue
        text = (item.get('text') or '').strip()
        return bool(item.get('ok') and len(text) >= 120)
    return False


def build_research_warnings(
    *,
    linkedin_url: str,
    linkedin_fetch_ok: bool,
    search_results: List[Dict[str, str]],
    search_available: bool,
    combined_text: str,
) -> List[str]:
    warnings: List[str] = []
    vanity = extract_linkedin_vanity(linkedin_url)
    if linkedin_url and not linkedin_fetch_ok:
        warnings.append(
            'LinkedIn blocked direct profile fetch. Workgroup matching relies on web search snippets.',
        )
    if not search_available:
        warnings.append(
            'Web search is not configured on Gov Hub (set BRAVE_SEARCH_API_KEY or TAVILY_API_KEY).',
        )
    elif linkedin_url and not search_results:
        warnings.append(
            'No web search hits were returned for this LinkedIn profile. '
            'Try adding role keywords or paste a short LinkedIn summary under Previous interaction.',
        )
    if linkedin_url and not combined_text.strip():
        warnings.append(
            'No public profile text was gathered. Matches may be weak until search is configured '
            'or you add professional background in Previous interaction.',
        )
    elif vanity and linkedin_url and not linkedin_fetch_ok and search_results:
        warnings.append(
            f'Using search snippets for linkedin.com/in/{vanity}; verify matches against the profile.',
        )
    return warnings


def research_person_corpus(
    *,
    name: str,
    linkedin_url: str = '',
    extra_links: Optional[List[str]] = None,
) -> Dict[str, Any]:
    linkedin_url = normalize_linkedin_url(linkedin_url)
    urls = []
    if linkedin_url:
        urls.append(linkedin_url)
    for link in extra_links or []:
        if link and link.strip():
            urls.append(link.strip())

    url_corpus = gather_url_corpus(urls)
    search_available = bool(
        (os.environ.get('BRAVE_SEARCH_API_KEY') or '').strip()
        or (os.environ.get('TAVILY_API_KEY') or '').strip()
    )
    search_results = collect_person_search_results(name, linkedin_url, max_total=8)
    linkedin_fetch_ok = _linkedin_fetch_ok(url_corpus, linkedin_url)

    combined_text_parts = []
    if linkedin_url and not linkedin_fetch_ok:
        vanity = extract_linkedin_vanity(linkedin_url)
        combined_text_parts.append(
            'LinkedIn profile anchor: '
            f'{linkedin_url}'
            + (f' (vanity slug: {vanity})' if vanity else '')
            + '. Direct fetch was blocked; use search hits for role and expertise.',
        )
    for item in url_corpus:
        if item.get('ok') and item.get('text'):
            combined_text_parts.append(f"URL {item['url']}: {item['text'][:3000]}")
    for hit in search_results:
        combined_text_parts.append(
            f"Search hit {hit.get('title', '')} ({hit.get('url', '')}): {hit.get('snippet', '')}",
        )

    combined_text = '\n\n'.join(combined_text_parts)[:_MAX_FETCH_CHARS]
    research_warnings = build_research_warnings(
        linkedin_url=linkedin_url,
        linkedin_fetch_ok=linkedin_fetch_ok,
        search_results=search_results,
        search_available=search_available,
        combined_text=combined_text,
    )

    return {
        'name': name.strip(),
        'url_corpus': url_corpus,
        'search_results': search_results,
        'combined_text': combined_text,
        'search_available': search_available,
        'linkedin_vanity': extract_linkedin_vanity(linkedin_url),
        'linkedin_fetch_ok': linkedin_fetch_ok,
        'research_warnings': research_warnings,
    }
