"""Load CFI proposed patches from dp-memory-graph Neo4j export."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional

DP_MEMORY_GRAPH_ROOT = os.environ.get(
    'DP_MEMORY_GRAPH_ROOT',
    '/home/ubuntu/dp-memory-graph',
)
EXPORT_SCRIPT = os.path.join(DP_MEMORY_GRAPH_ROOT, 'scripts', 'cfi-patches-export.mjs')


def fetch_cfi_patch_export(
    *,
    submission_id: Optional[str] = None,
    timeout: int = 45,
) -> dict[str, Any]:
    """Run the Neo4j export script and return parsed JSON."""
    if not os.path.isfile(EXPORT_SCRIPT):
        return {
            'ok': False,
            'error': f'export script not found: {EXPORT_SCRIPT}',
            'groups': [],
            'summary': {},
        }

    cmd = ['node', EXPORT_SCRIPT]
    if submission_id:
        cmd.extend(['--submission', submission_id])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=DP_MEMORY_GRAPH_ROOT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            'ok': False,
            'error': 'CFI patch export timed out',
            'groups': [],
            'summary': {},
        }
    except OSError as exc:
        return {
            'ok': False,
            'error': f'failed to run export: {exc}',
            'groups': [],
            'summary': {},
        }

    raw = (proc.stdout or '').strip()
    if not raw:
        err = (proc.stderr or '').strip() or f'export exited {proc.returncode}'
        return {
            'ok': False,
            'error': err,
            'groups': [],
            'summary': {},
        }

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            'ok': False,
            'error': f'invalid export JSON: {exc}',
            'groups': [],
            'summary': {},
        }

    if not isinstance(data, dict):
        return {
            'ok': False,
            'error': 'export returned non-object JSON',
            'groups': [],
            'summary': {},
        }

    data.setdefault('groups', [])
    data.setdefault('summary', {})
    return data
