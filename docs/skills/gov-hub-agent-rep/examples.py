#!/usr/bin/env python3
"""Minimal agent-rep client. Token from GOV_HUB_AGENT_TOKEN only."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get('GOV_HUB_BASE', 'https://dev.interfacehub.net').rstrip('/')
TOKEN = os.environ.get('GOV_HUB_AGENT_TOKEN', '')
REF = os.environ.get('GOV_HUB_DRAFT_REF', '')


def call(method: str, path: str, body=None):
    if not TOKEN:
        sys.exit('Set GOV_HUB_AGENT_TOKEN')
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'X-Agent-Rep': 'claude-code',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            print(raw[:800])
    except urllib.error.HTTPError as exc:
        print(exc.read().decode('utf-8')[:800], file=sys.stderr)
        raise


if __name__ == '__main__':
    if not REF:
        sys.exit('Set GOV_HUB_DRAFT_REF')
    call('GET', '/api/agent-rep/')
    if len(sys.argv) > 1 and sys.argv[1] == 'comment':
        call('POST', f'/api/doc/draft/{REF}/reader-comments/', {
            'text': 'Agent-rep note for discussion. Not canonical.',
            'comment_scope': 'document',
        })
