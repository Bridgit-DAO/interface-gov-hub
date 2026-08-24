"""Promote CFI proposed patches to Canopi Discuss (server-to-server)."""
from __future__ import annotations

import os
import re
from typing import Any, Optional, Tuple

import requests

from config import CANOPI_API_URL

BLOCKED_AUTHOR_USER_IDS = frozenset({
    '123e4567-e89b-12d3-a456-426614174000',
})

_FIRST_PERSON_RE = re.compile(
    r"\b(I|I'm|I've|I have|my |mine\b|me\b|we've|we have|we stopped)\b",
    re.IGNORECASE,
)
_NORMATIVE_RE = re.compile(r'\b(SHOULD|MUST|SHALL)\b')
_META_HEADER_RE = re.compile(r'^###\s*(CFI Round|Community signal)', re.IGNORECASE)


def _patch_passes_quality_gates(proposed_text: str) -> tuple[bool, Optional[str]]:
    text = (proposed_text or '').strip()
    if len(text) < 40:
        return False, 'too_short'
    if _META_HEADER_RE.search(text):
        return False, 'meta_header_wrapper'
    if _FIRST_PERSON_RE.search(text):
        return False, 'personal_anecdote'
    if not _NORMATIVE_RE.search(text):
        return False, 'not_normative'
    return True, None


def _ops_secret() -> str:
    return (
        os.environ.get('METAWEB_OPS_SECRET', '').strip()
        or os.environ.get('CANOPI_DP_INTERNAL_SECRET', '').strip()
    )


def _canopi_internal_base() -> str:
    return os.environ.get('CANOPI_INTERNAL_API_URL', CANOPI_API_URL).rstrip('/')


def _auth_headers() -> dict[str, str]:
    secret = _ops_secret()
    if not secret:
        return {}
    return {
        'Authorization': f'Bearer {secret}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }


def promote_cfi_patch_to_canopi(patch: dict, *, submission: Optional[dict] = None) -> Tuple[dict, int]:
    """Publish one CFI patch to Canopi Discuss."""
    headers = _auth_headers()
    if not headers:
        return {'ok': False, 'error': 'METAWEB_OPS_SECRET not configured'}, 503

    if not isinstance(patch, dict):
        return {'ok': False, 'error': 'patch object required'}, 400

    if patch.get('canopi_message_id'):
        return {
            'ok': True,
            'idempotent': True,
            'messageId': patch.get('canopi_message_id'),
            'discussHref': patch.get('canopi_discuss_href'),
        }, 200

    sub = submission or {}
    proposed = patch.get('proposed_text') or ''
    ok, reason = _patch_passes_quality_gates(proposed)
    if not ok:
        return {'ok': False, 'error': f'patch failed quality gate: {reason}'}, 422

    author_user_id = (
        sub.get('canopi_user_id')
        or sub.get('canopiUserId')
        or patch.get('canopi_user_id')
        or patch.get('canopiUserId')
    )
    if author_user_id in BLOCKED_AUTHOR_USER_IDS:
        return {'ok': False, 'error': 'blocked placeholder author user id'}, 422

    contributor_email = (
        sub.get('contributor_email')
        or sub.get('contributorEmail')
        or patch.get('contributor_email')
        or patch.get('contributorEmail')
    )
    attributed = sub.get('attributed_to') or sub.get('attributedTo')
    if contributor_email and '@' in str(contributor_email):
        author_email = contributor_email
    else:
        author_email = None

    if not author_user_id and not author_email and not attributed:
        return {
            'ok': False,
            'error': 'no resolved contributor author (register contributor before promote)',
        }, 422

    body = {
        'cfiPatchId': patch.get('id'),
        'submissionId': sub.get('submission_id') or patch.get('submission_id'),
        'targetDp': patch.get('target_dp'),
        'draftRef': patch.get('target_dp'),
        'patchMode': patch.get('patch_mode'),
        'originalText': patch.get('original_text'),
        'proposedText': proposed,
        'rationale': patch.get('rationale'),
        'authorUserId': author_user_id,
        'authorEmail': author_email,
        'authorName': attributed or sub.get('submitted_by') or sub.get('submittedBy'),
    }

    try:
        res = requests.post(
            f'{_canopi_internal_base()}/v1/internal/metaweb/publish-cfi-patch',
            json=body,
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as exc:
        return {'ok': False, 'error': f'Canopi request failed: {exc}'}, 502

    try:
        data = res.json()
    except ValueError:
        data = {'ok': False, 'error': res.text[:500] or f'HTTP {res.status_code}'}

    if not res.ok:
        return {
            'ok': False,
            'error': data.get('error') or f'Canopi HTTP {res.status_code}',
            'details': data,
        }, res.status_code if res.status_code >= 400 else 502

    return data, 200 if data.get('idempotent') else 201


def promote_cfi_submission_to_canopi(group: dict) -> Tuple[dict, int]:
    """Publish all patches in a CFI submission group to Canopi."""
    headers = _auth_headers()
    if not headers:
        return {'ok': False, 'error': 'METAWEB_OPS_SECRET not configured'}, 503

    patches = group.get('patches') or []
    if not patches:
        return {'ok': False, 'error': 'no patches in group'}, 400

    body = {
        'submissionId': group.get('submission_id'),
        'attributedTo': group.get('attributed_to'),
        'submittedBy': group.get('submitted_by'),
        'authorUserId': group.get('canopi_user_id') or group.get('canopiUserId'),
        'authorEmail': group.get('contributor_email') or group.get('contributorEmail'),
        'patches': patches,
    }

    try:
        res = requests.post(
            f'{_canopi_internal_base()}/v1/internal/metaweb/publish-cfi-submission',
            json=body,
            headers=headers,
            timeout=120,
        )
    except requests.RequestException as exc:
        return {'ok': False, 'error': f'Canopi request failed: {exc}'}, 502

    try:
        data = res.json()
    except ValueError:
        data = {'ok': False, 'error': res.text[:500] or f'HTTP {res.status_code}'}

    if not res.ok:
        return {
            'ok': False,
            'error': data.get('error') or f'Canopi HTTP {res.status_code}',
            'details': data,
        }, res.status_code if res.status_code >= 400 else 502

    return data, 200


def mark_cfi_patch_promoted_in_graph(
    patch_id: str,
    *,
    canopi_message_id: str,
    canopi_discuss_href: Optional[str] = None,
) -> dict[str, Any]:
    """Record Canopi message id on CfiProposedPatch in Neo4j."""
    import subprocess
    import json

    script = os.path.join(
        os.environ.get('DP_MEMORY_GRAPH_ROOT', '/home/ubuntu/dp-memory-graph'),
        'scripts',
        'cfi-mark-canopi-promoted.mjs',
    )
    if not os.path.isfile(script):
        return {'ok': False, 'error': f'missing script: {script}'}

    cmd = [
        'node',
        script,
        '--patch-id',
        patch_id,
        '--message-id',
        canopi_message_id,
    ]
    if canopi_discuss_href:
        cmd.extend(['--discuss-href', canopi_discuss_href])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError as exc:
        return {'ok': False, 'error': str(exc)}

    raw = (proc.stdout or '').strip()
    if not raw:
        return {'ok': False, 'error': proc.stderr or f'exit {proc.returncode}'}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {'ok': False, 'error': 'invalid mark script output'}
