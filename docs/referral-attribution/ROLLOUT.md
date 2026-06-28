# Referral Unification Rollout

Phased delivery for shared scoped attribution. Each phase is independently shippable.

## Phase 1 — Contract + token infrastructure ✅ (this implementation)

**Goal:** Shared v2 token format and verifier in both codebases.

| Deliverable | Location |
|-------------|----------|
| JSON contract | `shared/referral-attribution/contract.json` |
| Canopi token v2 | `canopi/utils/shareRefToken.js` |
| Canopi attribution service | `canopi/services/referralAttributionService.js` |
| Gov Hub token verify/create | `gov-hub-prod/services/referral_tokens.py` |
| Gov Hub attribution recorder | `gov-hub-prod/services/referral_attribution.py` |
| DB migrations | `canopi/migrations/007_*`, `migrate_referral_attribution_v1` |

**Ops:** Run `node canopi/scripts/run-migration-007-referral-attribution.js` on Canopi DB; restart Gov Hub to apply SQLite migration.

**Feature flag:** None required — v1 tokens still work.

---

## Phase 2 — Gov Hub scoped links + dual param support

**Goal:** All referral links use `ref_token` only (legacy `?ref=` removed).

| Task | Status |
|------|--------|
| `join_layer` / `join_waitlist` accept `ref_token` only | Done |
| Record `referral_attribution` on conversion | Done |
| Layer detail UI passes `ref_token` from query | Done |
| API: scoped referral link generation | Done |
| Remove legacy `?ref=CODE` paths | Done |

**Success metrics:** % joins with `ref_token` vs legacy `ref`; zero join regressions.

---

## Phase 3 — Landing capture + embed referrals

**Goal:** Full funnel analytics per org/layer.

| Task | Notes |
|------|-------|
| Gov Hub landing beacon | POST anonymous landing before auth (mirror `share_landings`) |
| Waitlist embed email join | Pass `ref_token` through embed widget |
| Cross-product reporting API | Filter by `scope_type` + `scope_id` |
| Canopi signup ↔ Gov Hub layer join | Link MetaCommunity scope ids |

---

## Phase 4 — Org-scoped codes + reporting UI

**Goal:** True multi-org isolation.

| Task | Notes |
|------|-------|
| Per-layer or per-org referral codes | Replace global `user.referral_code` where needed |
| Layer admin referral dashboard | Counts from `referral_attribution` scoped to layer |
| Campaign entities | Optional `scope_type=campaign` |
| Rewards / incentives | Out of scope until product spec (Canopi OVERWEB_REWARDS plan) |

---

## Rollback

- Rollback: re-enable legacy code lookup in `resolve_referrer_from_token` if needed (not recommended).
- DB: New tables/columns are additive; no rollback required for core joins.
- Remove `REFERRAL_TOKEN_SECRET` alignment only if disabling cross-verify (not recommended).

---

## Testing checklist

- [ ] Canopi v1 and v2 tokens verify in Node tests
- [ ] Gov Hub Python tokens interoperate with Node (same secret, same payload)
- [ ] Layer join with `ref_token` sets `referred_by_id` + `referral_attribution` row
- [ ] Waitlist join with legacy `ref` still works
- [ ] Self-referral blocked for both param types
- [ ] Expired token rejected; join proceeds without attribution
