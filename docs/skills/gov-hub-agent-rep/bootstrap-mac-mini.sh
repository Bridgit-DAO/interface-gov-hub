#!/usr/bin/env bash
# Idempotent Mac Mini bootstrap: clone GitHub remotes, symlink the skill.
# Does not scp from the VPS. Does not print tokens. Does not install claude.
set -euo pipefail

ROOT="${METALAYER_SRC:-$HOME/src}"
SKILL_LINK="${HOME}/.claude/skills/gov-hub-agent-rep"
ENV_LOCAL="${HOME}/.config/gov-hub/agent-rep.env"

GOV_HUB_URL="${GOV_HUB_GIT_URL:-git@github.com:Bridgit-DAO/interface-gov-hub.git}"
CANOPI_URL="${CANOPI_GIT_URL:-git@github.com:Bridgit-DAO/canopi.git}"
CANOPI_SDK_URL="${CANOPI_SDK_GIT_URL:-git@github.com:Bridgit-DAO/canopi-sdk.git}"

GOV_HUB_DIR="${ROOT}/gov-hub"
CANOPI_DIR="${ROOT}/canopi"
CANOPI_SDK_DIR="${ROOT}/canopi-sdk"
SKILL_SRC="${GOV_HUB_DIR}/docs/skills/gov-hub-agent-rep"

log() { printf '%s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

clone_if_missing() {
  local url="$1" dest="$2" branch="${3:-}"
  if [ -d "${dest}/.git" ]; then
    log "already cloned: ${dest}"
    return 0
  fi
  if [ -e "${dest}" ]; then
    warn "exists but is not a git clone: ${dest}"
    return 1
  fi
  mkdir -p "$(dirname "${dest}")"
  if [ -n "${branch}" ]; then
    git clone --branch "${branch}" "${url}" "${dest}"
  else
    git clone "${url}" "${dest}"
  fi
}

if [ -d /home/ubuntu/canopi-prod ] && [ "$(uname -s)" = "Linux" ]; then
  # Running on the estate VPS: refuse to pretend this is the Mini.
  warn "this looks like the estate VPS; run this script on the Mac Mini"
fi

mkdir -p "${ROOT}"

clone_if_missing "${GOV_HUB_URL}" "${GOV_HUB_DIR}" "development"
clone_if_missing "${CANOPI_URL}" "${CANOPI_DIR}" "main"
clone_if_missing "${CANOPI_SDK_URL}" "${CANOPI_SDK_DIR}"

if [ -e "${CANOPI_DIR}-prod" ] || [ -e "${ROOT}/canopi-prod" ]; then
  warn "canopi-prod path present; do not use it as a Claude worktree"
fi

mkdir -p "${HOME}/.claude/skills"
if [ -d "${SKILL_SRC}" ]; then
  ln -sfn "${SKILL_SRC}" "${SKILL_LINK}"
  log "symlink: ${SKILL_LINK} -> ${SKILL_SRC}"
else
  warn "skill folder missing in clone: ${SKILL_SRC}"
  warn "docs/skills/ is not on origin yet; Mini cannot symlink until that tree is pushed"
fi

mkdir -p "${HOME}/.config/gov-hub"
if [ ! -f "${ENV_LOCAL}" ]; then
  cat > "${ENV_LOCAL}" <<'EOF'
# Mini-only. Fill GOV_HUB_AGENT_TOKEN after minting in the Mini browser.
# Never commit this file. Never copy a gha_ value from the VPS.
GOV_HUB_BASE=https://dev.interfacehub.net
GOV_HUB_AGENT_TOKEN=
X_AGENT_REP=claude-code
GOV_HUB_DRAFT_REF=
EOF
  chmod 600 "${ENV_LOCAL}"
  log "wrote empty env template: ${ENV_LOCAL}"
else
  log "env file already present (not printed): ${ENV_LOCAL}"
fi

log "theoverweb.org: no GitHub remote (Bridgit-DAO/theoverweb does not exist); skip"
log "overweb/intent: no git on the VPS; skip (local Astra tree only)"
log "done. Open Claude on the clone folders, not a Documents copy."
log "Mint token on the Mini at https://dev.interfacehub.net POST /api/me/agent-tokens/"
