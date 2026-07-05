# Soft launch – future Vue entry (optional)

Scaffold pages today live under Flask:

- `/soft-launch/` – homepage
- `/soft-launch/onboarding/` – five-step wizard
- `/soft-launch/artifact/` – demo contribution (`?scenario=…`)

JSON: `GET /api/soft-launch/fixtures/`, `GET /api/soft-launch/lifecycle/`

When you add a dedicated Vite entry (e.g. `client/soft-launch/main.js`), consider these **Vue** slices (minimal styling first):

| Component | Responsibility |
|-----------|----------------|
| `SoftLaunchHome.vue` | Hero, CTAs, how-it-works, activity cards, roles |
| `OnboardingWizard.vue` | Steps 1–5 + transition copy |
| `LifecycleStepper.vue` | Maps `ORDERED_STATUSES` → UI labels |
| `ArtifactSoftLaunch.vue` | Header, actions, readiness, voting blocks |
| `ReviewReadinessPanel.vue` | Checklist + transition callout |
| `VotingPanel.vue` | Support / Oppose / Abstain + tallies |
| `VoteContextPanel.vue` | Evidence / opposition / comment counts |

Wire `rollupOptions.input` in `vite.config.js` when ready; keep **fixtures** as the single source until APIs match.
