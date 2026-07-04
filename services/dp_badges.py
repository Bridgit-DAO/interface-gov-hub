"""DP Challenge badge readiness scaffolding.

Contributor badges are intentionally off-chain for recruitment. Workgroup
leadership can enable the existing workgroup badge settings, then award/review
through current Badge/Claim/OneTimeBadge primitives. Ordinal inscription
preservation is a future operations step, not automated here.
"""
from __future__ import annotations

DP_CONTRIBUTOR_BADGE_SLUG = 'dp-contributor'
DP_CONTRIBUTOR_BADGE_LABEL = 'DP Contributor'
DP_BADGE_AUTHORITY = 'workgroup_leadership'
DP_BADGE_ISSUANCE_MODE = 'off_chain'
DP_BADGE_INSCRIPTION_STATUS = 'future_queued'


def dp_contributor_badge_status(workgroup) -> dict:
    enabled = bool(getattr(workgroup, 'badge_enabled', False))
    has_timing = any(
        getattr(workgroup, field, None) is not None
        for field in ('badge_submission_days', 'badge_voting_days', 'badge_delay_days')
    )
    ready = enabled
    if not enabled:
        note = 'Enable workgroup badges before recruitment close.'
    elif has_timing:
        note = 'Off-chain contributor badge settings are configured.'
    else:
        note = 'Off-chain badges are enabled; review timing defaults before awards.'
    return {
        'slug': DP_CONTRIBUTOR_BADGE_SLUG,
        'label': DP_CONTRIBUTOR_BADGE_LABEL,
        'authority': DP_BADGE_AUTHORITY,
        'issuance_mode': DP_BADGE_ISSUANCE_MODE,
        'inscription_status': DP_BADGE_INSCRIPTION_STATUS,
        'enabled': enabled,
        'ready': ready,
        'note': note,
    }
