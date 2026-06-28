# Scoped Referral Attribution (Gov Hub + Canopi)

Shared contract and implementation artifacts for partial unification of referral systems.

| Document | Purpose |
|----------|---------|
| [contract.json](./contract.json) | Machine-readable schema (token payload v1/v2, events, conversions) |
| [FLOW_MAP.md](./FLOW_MAP.md) | Product flow → attribution model mapping |
| [SCHEMA.md](./SCHEMA.md) | Additive DB changes (both products) |
| [ROLLOUT.md](./ROLLOUT.md) | Phased implementation plan |

## Implementations

| Product | Path |
|---------|------|
| Canopi (Node) | `canopi/utils/shareRefToken.js`, `canopi/services/referralAttributionService.js` |
| Gov Hub (Python) | `gov-hub-prod/services/referral_tokens.py`, `gov-hub-prod/services/referral_attribution.py` |

## Token versions

- **v1** — existing Canopi tokens: referrer + entity only (backward compatible).
- **v2** — scoped tokens: adds `product`, `scopeType`, `scopeId`, optional `campaign` and `channel`.

Both products verify v1 and v2 with the same HMAC secret (`SHARE_REF_HMAC_SECRET` / Gov Hub `REFERRAL_TOKEN_SECRET`).

## Query params

| Param | Meaning |
|-------|---------|
| `ref_token` | Signed scoped attribution token (preferred) |
| `ref` | Legacy Gov Hub 8-char user code or Canopi referrer UUID |

During rollout, Gov Hub accepts both; new links should use `ref_token`.
