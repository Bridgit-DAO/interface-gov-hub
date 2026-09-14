#!/usr/bin/env bash
# Agent-rep examples for Claude Code. Requires GOV_HUB_AGENT_TOKEN.
# Do not echo the token. Do not run accept/publish from this script.
set -euo pipefail

BASE="${GOV_HUB_BASE:-https://dev.interfacehub.net}"
REF="${GOV_HUB_DRAFT_REF:?set GOV_HUB_DRAFT_REF to an approved draft ref}"

if [ -z "${GOV_HUB_AGENT_TOKEN:-}" ]; then
  echo "Set GOV_HUB_AGENT_TOKEN (gha_...) minted via POST /api/me/agent-tokens/" >&2
  exit 1
fi

auth=(-H "Authorization: Bearer ${GOV_HUB_AGENT_TOKEN}" -H "X-Agent-Rep: claude-code" -H "Content-Type: application/json")

curl -sS "${BASE}/api/agent-rep/" | head -c 400
echo

curl -sS "${BASE}/api/doc/draft/${REF}/proposals/" | head -c 400
echo

# Page comment (document scope)
curl -sS -X POST "${BASE}/api/doc/draft/${REF}/reader-comments/" \
  "${auth[@]}" \
  -d '{"text":"Agent-rep note: proposing this for discussion, not as canonical text.","comment_scope":"document"}'
echo

# REQ candidate competing for recommended / write-in
curl -sS -X POST "${BASE}/api/doc/draft/${REF}/req-packages/" \
  "${auth[@]}" \
  -d '{
    "kind": "req",
    "choice_key": "default",
    "tier": "recommended",
    "title": "Example recommended package",
    "body": "Cite DPs. List acceptance criteria. This stays a candidate until a human picks.",
    "dp_refs": ["DP8"]
  }'
echo
