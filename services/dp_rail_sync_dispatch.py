"""Trigger desirable-properties rail sync when a DP book revision is approved."""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: str = 'false') -> bool:
    return os.environ.get(key, default).strip().lower() in ('1', 'true', 'yes', 'on')


DP_RAIL_SYNC_DISPATCH_ENABLED = _env_bool('GOVHUB_DP_RAIL_SYNC_DISPATCH', 'false')
GH_DISPATCH_TOKEN = os.environ.get('GH_DISPATCH_TOKEN', '').strip()
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'shiftshapr/desirable-properties').strip()
DISPATCH_EVENT = 'govhub-rail-sync'
DP_RAIL_SYNC_ENV = os.environ.get('DP_RAIL_SYNC_ENV', 'main').strip() or 'main'


def _dp_rail_sync_ml_numbers() -> frozenset[str]:
    raw = os.environ.get('DP_RAIL_SYNC_ML_NUMBERS', 'ML-Draft-026').strip()
    return frozenset(m.strip() for m in raw.split(',') if m.strip())


def is_dp_book_rail_submission(submission: Any) -> bool:
    """True when an approved revision should sync to desirable-properties book rails."""
    if not getattr(submission, 'is_revision', False):
        return False

    ml = (getattr(submission, 'ml_number', None) or '').strip()
    if not ml.startswith('ML-Draft-'):
        return False

    if ml in _dp_rail_sync_ml_numbers():
        return True

    from services.documents import is_desirable_properties_collection_document

    title = (getattr(submission, 'title', None) or '').strip()
    if is_desirable_properties_collection_document(title):
        return True

    parent_name = (getattr(submission, 'parent_draft_name', None) or '').strip()
    if parent_name:
        from services.submissions import get_submission_by_ref

        parent = get_submission_by_ref(parent_name)
        if parent and is_desirable_properties_collection_document(
            (getattr(parent, 'title', None) or '').strip()
        ):
            return True

    return False


def dispatch_dp_rail_sync(submission: Any, *, env: str | None = None) -> bool:
    """POST repository_dispatch to GitHub. Returns True when dispatched."""
    if not DP_RAIL_SYNC_DISPATCH_ENABLED:
        return False
    if not GH_DISPATCH_TOKEN:
        logger.warning('DP rail sync dispatch skipped: GH_DISPATCH_TOKEN not set')
        return False
    if not is_dp_book_rail_submission(submission):
        return False

    sync_env = (env or DP_RAIL_SYNC_ENV).strip() or 'main'
    url = f'https://api.github.com/repos/{GITHUB_REPO}/dispatches'
    payload = {
        'event_type': DISPATCH_EVENT,
        'client_payload': {
            'env': sync_env,
            'ml_number': getattr(submission, 'ml_number', None) or '',
            'revision_number': getattr(submission, 'revision_number', None) or '',
            'submission_id': getattr(submission, 'id', None) or '',
        },
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                'Authorization': f'Bearer {GH_DISPATCH_TOKEN}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
            },
            timeout=15,
        )
        if resp.status_code == 204:
            logger.info(
                'DP rail sync dispatched for %s rev %s',
                submission.ml_number,
                getattr(submission, 'revision_number', None) or '',
            )
            return True
        logger.warning(
            'DP rail sync dispatch failed: HTTP %s %s',
            resp.status_code,
            (resp.text or '')[:200],
        )
        return False
    except requests.RequestException as exc:
        logger.warning('DP rail sync dispatch error: %s', exc)
        return False
