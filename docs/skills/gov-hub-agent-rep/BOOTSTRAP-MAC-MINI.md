# Bootstrap Claude Code on the Mac Mini

Always-on host for Claude Code. The laptop lid can close. This Mini is **not** a peer of prod on the VPS.

**File bus is GitHub.** Clone repos on the Mini. Do not `scp` `SKILL.md`, do not rsync trees from the VPS, do not email tokens.

**Token is minted on the Mini** in a browser at `https://dev.interfacehub.net`. Store it only on the Mini (Keychain or direnv). Never copy a `gha_` value off the VPS.

This VPS must not get a `claude` install.

---

## Honest gap (read before you clone)

A Mini clone of GitHub is **not** a copy of `/home/ubuntu/gov-hub-dev` today.


| On the Mini after `git clone` / `git pull`                    | Still only on the VPS until you say push                                             |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `Bridgit-DAO/interface-gov-hub` `development` as on `origin`  | Entire `docs/skills/` tree (this skill, this file, the activate kit)                 |
| `Bridgit-DAO/canopi` `main` (`intent/intent.md` is on origin) | Uncommitted Gate 1 / agent-rep / Astra / redlines / ml-req work under `gov-hub-dev`  |
| `Bridgit-DAO/canopi-sdk` (`master` or `sdk/sidebar-tabs`)     | `gov-hub-dev` is **ahead 1** of `origin/development` (invite copy) plus a dirty tree |
|                                                               | `canopi/intent/{spec,plan,README}.md` (untracked)                                    |
|                                                               | `canopi-sdk` overlay conformance files (local dirty / untracked)                     |
|                                                               | `/home/ubuntu/theoverweb.org` (no `.git`, no `Bridgit-DAO/theoverweb` repo)          |
|                                                               | `/home/ubuntu/overweb/intent/` (no git; Astra JSON lives here)                       |


Run the script anyway. It clones what exists and **warns** if the skill folder is missing on origin.

---



## 1. One-time Mini setup

SSH into the Mini (or sit at it). Laptop closed afterward is fine; work stays in `tmux` on the Mini.

```bash
# Homebrew if missing
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install git gh direnv tmux

# Claude Code on the Mini only (never on the VPS)
curl -fsSL https://claude.ai/install.sh | bash
# or: brew install --cask claude-code   # if that cask is what you use
which claude
```

GitHub auth on the Mini (creates Mini credentials; do not paste a VPS token):

```bash
gh auth login
# GitHub.com -> HTTPS or SSH -> login in the Mini browser
gh auth setup-git
```

Optional: `direnv hook` in `~/.zshrc` (direnv prints the hook command).

---



## 2. Clone list (actual remotes)

Parent directory defaults to `~/src` (`METALAYER_SRC` overrides).


| Local folder       | Clone URL                                          | Branch                                               |
| ------------------ | -------------------------------------------------- | ---------------------------------------------------- |
| `~/src/gov-hub`    | `git@github.com:Bridgit-DAO/interface-gov-hub.git` | `development` (repo default)                         |
| `~/src/canopi`     | `git@github.com:Bridgit-DAO/canopi.git`            | `main`                                               |
| `~/src/canopi-sdk` | `git@github.com:Bridgit-DAO/canopi-sdk.git`        | default `master` (VPS often uses `sdk/sidebar-tabs`) |


HTTPS equivalents:

- `https://github.com/Bridgit-DAO/interface-gov-hub.git`
- `https://github.com/Bridgit-DAO/canopi.git`
- `https://github.com/Bridgit-DAO/canopi-sdk.git`

**Do not clone** a canopi **prod** worktree. One `~/src/canopi` on `main` (or `staging` if you switch on purpose). No `canopi-prod`.

**Cannot clone today** (no GitHub remote):

- `theoverweb.org` (OPEN_ITEMS still wants `Bridgit-DAO/theoverweb`)
- `overweb/intent` (intent-only tree on the VPS)

VPS SSH is for live ops (`journalctl`, `curl` to `:8001`), not for carrying files.

After the skill is on origin:

```bash
cd ~/src/gov-hub
git pull
# script also does this:
ln -sfn "$HOME/src/gov-hub/docs/skills/gov-hub-agent-rep" "$HOME/.claude/skills/gov-hub-agent-rep"
```

Idempotent wrapper (from this folder once it exists on the Mini, or curl-less: copy the script via git after push):

```bash
# After docs/skills is on origin:
cd ~/src/gov-hub
./docs/skills/gov-hub-agent-rep/bootstrap-mac-mini.sh
```

Until that push, run the same script from a gist you maintain, or paste it once onto the Mini. Do **not** scp the skill tree from the VPS.

---



## 3. Symlink the skill (not `cp`)

```bash
mkdir -p ~/.claude/skills
ln -sfn "$HOME/src/gov-hub/docs/skills/gov-hub-agent-rep" "$HOME/.claude/skills/gov-hub-agent-rep"
ls -l ~/.claude/skills/gov-hub-agent-rep
```

`git pull` in `~/src/gov-hub` updates `SKILL.md`. Do not keep a second copy under `Documents/`.

**Cursor / Claude "open this folder"** = `~/src/gov-hub` (or `~/src/canopi`, `~/src/canopi-sdk`). Not a duplicate tree.

---



## 4. Env on the Mini only

Example checked into git: `[.env.agent-rep.example](.env.agent-rep.example)`

```bash
mkdir -p ~/.config/gov-hub
cp ~/src/gov-hub/docs/skills/gov-hub-agent-rep/.env.agent-rep.example ~/.config/gov-hub/agent-rep.env
chmod 600 ~/.config/gov-hub/agent-rep.env
# leave GOV_HUB_AGENT_TOKEN empty until step 5
```

direnv in the clone (do not commit a filled `.envrc`):

```bash
# ~/src/gov-hub/.envrc  (gitignored via .env / local habits; keep token out of git)
export GOV_HUB_BASE=https://dev.interfacehub.net
export X_AGENT_REP=claude-code
# after mint:
# export GOV_HUB_AGENT_TOKEN='gha_...'   # Mini only
direnv allow
```

Or Keychain (token never in a file the agent might cat):

```bash
security add-generic-password -U -a "$USER" -s gov-hub-agent-token -w
# paste the token when security prompts; do not echo it
# later:
# export GOV_HUB_AGENT_TOKEN="$(security find-generic-password -a "$USER" -s gov-hub-agent-token -w)"
```

`GOV_HUB_BASE` stays `https://dev.interfacehub.net`. Do not point Claude at prod.

---



## 5. Mint the token on the Mini browser

1. On the Mini, open `https://dev.interfacehub.net` and sign in as yourself.
2. DevTools console (same tab):

```javascript
const r = await fetch('/api/me/agent-tokens/', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ label: 'claude-code-mac-mini' }),
});
const j = await r.json();
console.log(r.status, j.token ? 'token-present' : 'no-token', j.hint);
```

1. Copy `j.token` (`gha_...`) into Keychain or the Mini env file. Shown once.
2. Do not paste it into chat, git, or Slack. Do not mint on the VPS and mail it over.

Existing `gha_` tokens cannot mint another. Session cookie (browser) can.

---



## 6. tmux so SSH disconnect is fine

```bash
tmux new -s claude
cd ~/src/gov-hub
claude
# detach: Ctrl-b then d
# reattach from laptop SSH: tmux attach -t claude
```

The Mini stays on. Closing the laptop does not stop that session.

---



## 7. Forbidden

- Accept, ensure working revision, or publish on Gov Hub.
- `human_confirmed: true` unless you are a chair **and** the human confirmed that chair action in this turn.
- Any canopi **prod** worktree or deploy from the Mini as if it were the VPS.
- `scp` / rsync of skill files or tokens from `/home/ubuntu`.
- Installing `claude` on the VPS.

Blocked canonical writes return **403** `agent_canonical_write_blocked`. The human accepts in the browser.

---



## 8. Daily loop

```bash
cd ~/src/gov-hub && git pull
cd ~/src/canopi && git pull
cd ~/src/canopi-sdk && git pull
tmux attach -t claude || tmux new -s claude
```

SSH to the VPS only when you need live process or nginx state.

When the operator says **push**, the skill and agent-rep work can land on `origin/development`. Until then the Mini has GitHub, not the VPS dirty tree.