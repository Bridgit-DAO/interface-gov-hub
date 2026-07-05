# Civic Mason Landing Page – Full Cursor Instructions

## Objective

Build a landing experience that feels like a **rite of entry**, not a traditional website.

The user should feel like they are:

- Crossing a threshold
- Entering an unfinished world
- Choosing how to begin building

This is not UI navigation. This is an **initiation sequence**.

---

## Implementation location (canonical scaffold)

The deployable site lives **outside** `gov-hub-dev`, at:

**`/home/ubuntu/civicmason-site/public/`**

| Area | Path |
|------|------|
| Entry | `public/index.html` |
| Styles | `public/css/cm-initiation.css` |
| Logic | `public/js/app.js` (orchestration) |
| Stages | `public/js/stage-controller.js`, `public/js/config.js` |
| WebGL | `public/js/three-scene.js` |
| Fallback / reduced motion | `public/js/fallback-ui.js` |
| Hero imagery | `public/assets/hero-desktop.png`, `hero-mobile.png`, `hero-mobile-branded.png` (optional swap) |
| nginx example | `civicmason-site/nginx/civicmason.conf` |
| Publish on server | `civicmason-site/deploy.sh` (from repo root; requires sudo) |

**GovHub handoff:** `<meta name="govhub-origin" content="https://govhub.live">` in `index.html`. Path buttons navigate to `/soft-launch/onboarding/?intent=community|internet|cell`.

---

## What is implemented (scaffold v1)

- **Stage machine** on `#cm-root` via `data-cm-stage`: `threshold` → `transition` → `valley` → `guided` → `walk` → `paths`.
- **Device-native art (fallback):** separate **mobile** vs **desktop** hero images in CSS (`cm-initiation.css` / `.cm-fallback-bg`), not one image cropped for both.
- **WebGL path:** Three.js (`0.160.0` via CDN import map) with placeholder geometry: stone/door, valley plane, distant point lights, scripted transition (door swing + camera dolly + torch dim + fog). Subtle **desktop parallax** on mouse move.
- **Fallback path:** `prefers-reduced-motion: reduce` **or** no WebGL → static layers + CSS crossfade into “valley” overlay; **no** long transition animation.
- **Threshold copy:** “You are early.” / “The door is open.” / primary control **Become a Civic Mason** / “Step through.”
- **Guided copy (matches spec):** two paragraphs about building communities + internet; then **Continue** (extra beat vs. spec’s single “tap to walk” prompt–acceptable for clarity).
- **Walk:** two discrete advances (“Tap to walk forward”); **Enter/Space** supported on walk zone; then paths.
- **Paths:** three options; **Strengthen your community** is visually primary (“Suggested” label); pulse then navigate with `intent` query.
- **Accessibility:** `aria-live` region `#cm-live`; reduced-motion branch; `noscript` link to onboarding.

---

## Core principle (creative)

“You are early in something that will never be done.”

Everything in the experience should reinforce:

- Openness
- Possibility
- Responsibility
- Forward movement

*(Optional: surface this line once in copy or VO–sparingly–not as repeated wallpaper.)*

---

## Device-native design (CRITICAL)

We are NOT using responsive cropping only. We use **different compositions per device**.

### Mobile (primary)

- Vertical door image (tight framing)–**`hero-mobile.png`** (or **`hero-mobile-branded.png`** if type is baked into art; adjust CSS URL in `cm-initiation.css`).
- User feels standing at the threshold; door dominates; valley suggested, not fully revealed.

### Desktop / tablet

- Wide composition–**`hero-desktop.png`**.
- More cinematic; parallax-lite on fallback + Three camera.

### DO NOT

- Do not reuse the same image across devices as the only layer.
- Do not crop the desktop asset as the sole mobile solution.
- Do not center everything identically on all breakpoints.

Each device = different emotional framing.

---

## Scene structure (spec)

### Stage 1: Threshold (hero)

Use door image.

Overlay text:

- YOU ARE EARLY.
- The door is open.
- **[ Become a Civic Mason ]** (single primary control)
- Small: Step through.

### Behavior

- Control triggers transition; no scroll required for the core loop.

---

## Transition (CRITICAL)

Sequence:

1. Door opens slightly wider
2. Camera moves forward
3. Light increases subtly
4. Torch glow fades

**Spec timing:** 1.5–2.2 seconds, ease-in, no abrupt cuts.

**Current scaffold:** ~**3.8s** in `three-scene.js` / `app.js`–tune to hit the spec band.

**Fallback:** image crossfade + valley overlay (`fallback-ui.js`); reduced motion = instant state advance.

---

## Stage 2: Valley entry

User enters an **open** valley (not an enclosed box).

### Visual requirements

- Warm light, horizon readable, subtle depth (fog / gradient).
- Subtle signs of other builders (distant lights)–**partially** met in Three (point field); fallback is gradient-only until art pass.

### Do NOT

- Fantasy MMO look, heavy HUD, gamey particles.

---

## Guided overlay (copy lock)

Display after entering valley:

> This is a place where people build what their communities and the internet will become.  
> You are not here to watch. You are here to build.

**Spec nuance:** optional fade, then bottom **“Tap to walk forward.”**  
**Current:** **Continue** button → dedicated **walk** stage with that prompt. Adjust if you want one combined screen.

---

## Walk interaction

**Spec**

- Mobile: tap once → small forward motion; tap twice → path reveal.
- Desktop: **click or scroll** triggers forward motion.

**Current**

- Two taps/clicks (or Enter/Space) on walk zone; **scroll-to-advance not implemented**–add if you want parity.

**Do NOT**

- Joystick, drag-to-walk, continuous locomotion. Symbolic steps only.

---

## Stage 3: Path reveal

**Spec:** paths **emerge from terrain** (not obvious card UI), subtle glow, one path brighter.

**Current:** three **button-style** path blocks in CSS–scaffold only. Replace with shader/terrain markers or canvas-aligned hotspots when art is ready.

### Path content (intent mapping)

| User-facing | `intent` |
|-------------|----------|
| Strengthen your community (primary / suggested) | `community` |
| Improve the internet | `internet` |
| Start a Civic Mason cell | `cell` |

*(Spec text “Start a Civic Mason group” → product chose **cell**; keep consistent with GovHub query handling.)*

**Navigation:** `/soft-launch/onboarding/?intent=…` on origin from `govhub-origin`.

---

## Path interaction

- Tap/click path → short pulse → `location.href` to onboarding with intent.

---

## Emotional design rules

1. **Not a game** – no quest UI, RPG chrome, or scoring.
2. **Not fantasy** – avoid secret-society mystique; stone/door = **metaphor**, not genre.
3. **Grounded, civic** – real, human, buildable.
4. **Ritual, not hype** – slow, minimal copy, intentional motion.
5. **Identity first** – user feels they are *becoming* something.

---

## Art direction

- Base scenes: provided PNGs under `public/assets/`.
- Do not replace with generic stock without intention; avoid over-stylized FX.

---

## Performance notes (spec vs current)

| Item | Spec | Current |
|------|------|---------|
| Defer Three.js until first interaction | Yes | **Not yet**–module loads with page |
| Fallback for low-end / no WebGL | Yes | **Yes** |
| Mobile frame budget | Smooth 60 where possible | **Profile** on mid-tier Android |

**Backlog:** dynamic import of `three-scene.js` after “Become” or after `requestIdleCallback`.

---

## Success criteria

Within **~10s**: curious, invited, not overwhelmed.  
Within **~20s**: this is about **building**, applies to **me**, **clear next step**.

---

## Final instruction

This should feel like: **stepping through a real doorway into an unfinished world**–not browsing a product site or playing a game.

---

## Summary for Cursor

- **Source of truth for code:** `civicmason-site/public/`.
- Preserve **device-specific** hero images and **emotional** pacing.
- **Tighten** transition duration toward 1.5–2.2s when polishing.
- Replace **card UI paths** with **terrain-integrated** reveals when art/WebGL allow.
- Consider **scroll-to-step** on desktop for walk parity.
- Keep **GovHub** as the only coordination exit; **no** duplicate contribution logic on this site.

This document is an **initiation experience** spec **plus** an **as-built scaffold** checklist; update this file when major behavior or paths change.
