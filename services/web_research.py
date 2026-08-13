"""Fetch URLs and optional web search for external contact research."""
from __future__ import annotations

import os
import re
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

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


def build_search_query(name: str, linkedin_url: str = '', extra: Optional[List[str]] = None) -> str:
    parts = [name.strip()]
    if linkedin_url.strip():
        parts.append(linkedin_url.strip())
    return ' '.join(parts)


def normalize_linkedin_url(url: str) -> str:
    """Normalize user-entered LinkedIn URLs for fetch and research."""
    raw = (url or '').strip()
    if not raw:
        return ''
    if not raw.startswith(('http://', 'https://')):
        raw = f'https://{raw.lstrip("/")}'
    return raw


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
    search_results = web_search(build_search_query(name, linkedin_url), limit=6)

    combined_text_parts = []
    for item in url_corpus:
        if item.get('ok') and item.get('text'):
            combined_text_parts.append(f"URL {item['url']}: {item['text'][:3000]}")
    for hit in search_results:
        combined_text_parts.append(
            f"Search hit {hit.get('title', '')} ({hit.get('url', '')}): {hit.get('snippet', '')}",
        )

    return {
        'name': name.strip(),
        'url_corpus': url_corpus,
        'search_results': search_results,
        'combined_text': '\n\n'.join(combined_text_parts)[:_MAX_FETCH_CHARS],
        'search_available': bool(
            (os.environ.get('BRAVE_SEARCH_API_KEY') or '').strip()
            or (os.environ.get('TAVILY_API_KEY') or '').strip()
        ),
    }
