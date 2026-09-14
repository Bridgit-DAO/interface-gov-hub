# Activate Claude Code as Gov Hub agent-rep

**Host:** run Claude Code on the **Mac Mini** (always-on). Laptop lid closed is fine. This VPS does not have the `claude` CLI (`which claude` failed). Do not install Claude Code on the VPS.

**What this is:** the existing BYOA + augmented pkai overlay (`gov-hub-agent-rep`). Not a new product.

**Firewall:** Nothing becomes canonical because it was fluent.

One-time Mini setup (GitHub clone, symlink, tmux, no scp): [BOOTSTRAP-MAC-MINI.md](BOOTSTRAP-MAC-MINI.md).

---

## 1. Skill on the Mini: git pull + symlink (not `cp` from the VPS)

GitHub is the file bus. After `~/src/gov-hub` is a clone of `Bridgit-DAO/interface-gov-hub`:

```bash
cd ~/src/gov-hub && git pull
mkdir -p ~/.claude/skills
ln -sfn "$HOME/src/gov-hub/docs/skills/gov-hub-agent-rep" "$HOME/.claude/skills/gov-hub-agent-rep"
```

Do **not** `scp` or `cp` this folder from `/home/ubuntu/gov-hub-dev`. Do not keep a second copy under `Documents/`. Open Claude / Cursor on the clone.

Until `docs/skills/` is pushed to `origin/development`, the Mini clone will not have this kit. See the honest gap in [BOOTSTRAP-MAC-MINI.md](BOOTSTRAP-MAC-MINI.md).

Optional local env (never commit a filled token; prefer Mini Keychain or `~/.config/gov-hub/agent-rep.env`):

```bash
cp .env.agent-rep.example ~/.config/gov-hub/agent-rep.env
# then export GOV_HUB_AGENT_TOKEN after mint on the Mini browser (step 3)
```

---

## 2. Sign in (human, browser)

Open `https://dev.interfacehub.net` and sign in as yourself.

The agent is **you**, not a second account. Token mint requires this browser (or Web3Auth) session. An existing `gha_` token cannot mint another.

---

## 3. Mint `GOV_HUB_AGENT_TOKEN` (shown once)

Still in that signed-in tab, DevTools console:

```javascript
const r = await fetch('/api/me/agent-tokens/', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ label: 'claude-code' }),
});
const j = await r.json();
console.log(r.status, j.token, j.hint);
```

Expect HTTP 201. Copy `token` (`gha_...`). Store it only in shell env or a gitignored local file.

```bash
export GOV_HUB_AGENT_TOKEN='gha_...'   # paste once, do not paste into chat or git
export GOV_HUB_BASE='https://dev.interfacehub.net'
```

On this VPS (same identity, after mint), local API is `http://127.0.0.1:8001`. From the Mini, use the public **dev** base. Mint on the Mini browser; never copy `gha_` from the VPS.

---

## 4. Headers on every mutating call

```
Authorization: Bearer $GOV_HUB_AGENT_TOKEN
X-Agent-Rep: claude-code
Content-Type: application/json
```

Read the live contract first (no auth):

```bash
curl -sS "${GOV_HUB_BASE:-https://dev.interfacehub.net}/api/agent-rep/"
```

More examples: [examples.sh](examples.sh). Set `GOV_HUB_DRAFT_REF` to an approved draft (`ml_number`, `draft_name`, or submission id).

---

## 5. Two modes (pick one per turn)

| Mode | When | What you do |
|------|------|-------------|
| **Participate** (BYOA) | DP / REQ / ADR / page thread | List and submit patches, reader comments, workgroup chat, REQ/ADR **candidates**. Wait. |
| **Run SDLC** | Canopi or Overweb workshop | Learning lookup, then `intent.md` → `spec.md` → `plan.md`. Those files are not canonical DP text. |

SDLC homes: `canopi/intent/` (brownfield) and `/home/ubuntu/overweb/intent/` (greenfield). Public catalogs: theoverweb.org `/reqs/` and `/adrs/sdk/`.

---

## 6. Forbidden

- Accept, ensure working revision, or publish.
- Send `human_confirmed: true` unless you are a chair **and** the human confirmed that chair action **in this turn**.
- Treat a fluent patch, comment, or `spec.md` as the official DP / ML-REQ / ML-ADR.
- Firehose. One thoughtful submit, then wait.

Blocked routes return **403** `agent_canonical_write_blocked`. Tell the human to accept in the browser.

---

## 7. Learning lookup first (both modes)

Before compose-touching work or SDLC / product code:

1. `memory_recall` (symptom or feature area). HTTP `127.0.0.1:8791/recall` if MCP fails. BRC333 family: `collections: ["brc333"]`.
2. Read that project's `docs/redlines/catalog.json` (Gov Hub: this repo; Canopi: `canopi/docs/redlines/catalog.json`).
3. Only then PATCH/POST or edit files.

On FIXED: `memory_remember` (no secrets) plus a catalog row with a real `detect`. Spec: `meta-console/docs/ESTATE-LEARNING-LOOP.md`.

---

## Still blocked (human)

- Browser login and token mint on the **Mini** (cannot be done by the VPS agent).
- Chair accept / publish.
- `claude` on this VPS (do not install).
- Promoting this kit to `gov-hub-prod`.
- Pushing `docs/skills/` and the rest of the dirty `development` tree (operator must say so).
