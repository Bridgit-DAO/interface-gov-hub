"""Canopi synthesis workgroup export – Gov Hub revision picker backend."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from models import DpProposal, Submission
from services.canopi_community_sync import _api_base, _headers
from services.dp_proposals import is_dp_submission, workgroup_for_submission
from services.workgroup_links import extract_dp_number_from_title

log = logging.getLogger(__name__)

_BOOK_ORIGIN = os.environ.get(
    'DP_CANOPI_BOOK_ORIGIN',
    'https://book.desirableproperties.org',
).rstrip('/')


def book_page_id_for_dp_number(dp_num: int) -> str:
    """Mirror Canopi canopiPageIdFromUrl for DP book viewer paths."""
    slug = f'dp{int(dp_num):02d}'
    if 'desirableproperties.org' not in _BOOK_ORIGIN:
        from urllib.parse import urlparse

        host = urlparse(_BOOK_ORIGIN).hostname or 'book.desirableproperties.org'
        host = host.replace('www.', '')
        raw = f'{host}/viewer/{slug}'
    else:
        raw = f'book.desirableproperties.org/viewer/{slug}'
    return re.sub(r'[^a-zA-Z0-9]', '_', raw).lower()[:100]


def anchor_identity_hash_from_context(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    obj: Any = raw
    if isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return None
        try:
            obj = json.loads(trimmed)
        except json.JSONDecodeError:
            return None
    if not isinstance(obj, dict):
        return None
    for key in ('anchorIdentityHash', 'anchor_hash', 'anchorHash'):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def compute_anchor_union_hash(anchor_hashes: List[str]) -> str:
    """Same algorithm as Canopi synthesisJudgmentService.computeAnchorUnionHash."""
    seen: set[str] = set()
    normalized: List[str] = []
    for item in anchor_hashes:
        h = str(item or '').strip()
        if not h or h in seen:
            continue
        seen.add(h)
        normalized.append(h)
    normalized.sort()
    if not normalized:
        return ''
    return hashlib.sha256('|'.join(normalized).encode('utf-8')).hexdigest()


def _list_canopi_patches(page_id: str, anchor_hash: str) -> List[dict]:
    base = _api_base()
    url = f'{base}/v1/patches'
    params = {'pageId': page_id, 'anchorHash': anchor_hash}
    try:
        res = requests.get(url, params=params, headers=_headers(), timeout=30)
    except requests.RequestException as exc:
        log.warning('Canopi patches list failed: %s', exc)
        raise RuntimeError('Canopi patches API unavailable') from exc
    if res.status_code >= 400:
        log.warning('Canopi patches list %s: %s', res.status_code, res.text[:300])
        raise RuntimeError(f'Canopi patches API error ({res.status_code})')
    data = res.json() if res.content else {}
    patches = data.get('patches') if isinstance(data, dict) else None
    return patches if isinstance(patches, list) else []


def collect_anchor_hashes_for_scope(page_id: str, primary_anchor_hash: str) -> List[str]:
    hashes: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        h = str(raw or '').strip()
        if not h or h in seen:
            return
        seen.add(h)
        hashes.append(h)

    add(primary_anchor_hash)
    for patch in _list_canopi_patches(page_id, primary_anchor_hash):
        if not isinstance(patch, dict):
            continue
        add(patch.get('anchorContentHash'))
        ctx = patch.get('contextAnchor')
        if isinstance(ctx, str):
            add(anchor_identity_hash_from_context(ctx))
        elif isinstance(ctx, dict):
            add(anchor_identity_hash_from_context(ctx))

    return sorted(hashes)


def fetch_workgroup_export(
    page_id: str,
    anchor_union_hash: str,
    *,
    workgroup_id: Optional[str] = None,
) -> Dict[str, Any]:
    base = _api_base()
    url = f'{base}/v1/synthesis-judgments/workgroup-export'
    params: Dict[str, str] = {
        'pageId': page_id,
        'anchorUnionHash': anchor_union_hash,
    }
    if workgroup_id:
        params['workgroupId'] = workgroup_id
    try:
        res = requests.get(url, params=params, headers=_headers(), timeout=45)
    except requests.RequestException as exc:
        log.warning('Canopi synthesis export failed: %s', exc)
        raise RuntimeError('Canopi synthesis export unavailable') from exc
    try:
        payload = res.json() if res.content else {}
    except ValueError:
        payload = {'error': res.text[:500]}
    if res.status_code >= 400:
        message = payload.get('error') if isinstance(payload, dict) else res.text
        raise RuntimeError(str(message or f'Canopi export error ({res.status_code})'))
    return payload if isinstance(payload, dict) else {'export': payload}


def resolve_synthesis_scope_for_proposal(
    proposal: DpProposal,
    submission: Submission,
) -> Tuple[str, str, str]:
    """
    Resolve Canopi pageId and anchorUnionHash for one passage proposal.

    Returns (page_id, anchor_union_hash, primary_anchor_hash).
    """
    if not is_dp_submission(submission):
        raise ValueError('Synthesis export is only available for Desirable Properties chapters')

    dp_num = extract_dp_number_from_title(submission.title or '')
    if dp_num is None:
        raise ValueError('Could not determine DP chapter number for this document')

    primary_hash = anchor_identity_hash_from_context(proposal.context_anchor)
    if not primary_hash:
        raise ValueError(
            'This patch has no Canopi anchor identity. Open the passage in the DP book embed '
            'and re-propose from a highlighted selection.'
        )

    page_id = book_page_id_for_dp_number(dp_num)
    anchor_hashes = collect_anchor_hashes_for_scope(page_id, primary_hash)
    union_hash = compute_anchor_union_hash(anchor_hashes)
    if not union_hash:
        raise ValueError('Could not compute anchor union hash for this passage')
    return page_id, union_hash, primary_hash


def passage_synthesis_export_for_proposal(proposal: DpProposal, submission: Submission) -> Dict[str, Any]:
    page_id, union_hash, primary_hash = resolve_synthesis_scope_for_proposal(proposal, submission)
    wg = workgroup_for_submission(submission)
    workgroup_id = wg.id if wg else None
    export = fetch_workgroup_export(page_id, union_hash, workgroup_id=workgroup_id)
    export['scope'] = {
        'pageId': page_id,
        'anchorUnionHash': union_hash,
        'primaryAnchorHash': primary_hash,
        'proposalId': proposal.id,
        'submissionId': submission.id,
    }
    return export
