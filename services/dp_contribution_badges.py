"""Badge eligibility hooks when DP contributions are accepted or considered."""
from __future__ import annotations

from typing import TYPE_CHECKING

from services.dp_badges import DP_CONTRIBUTOR_BADGE_LABEL, DP_CONTRIBUTOR_BADGE_SLUG

if TYPE_CHECKING:
    from models.dp_proposal import DpProposal


def on_dp_contribution_outcome(proposal: 'DpProposal', outcome: str) -> None:
    """
    Emit badge-eligibility signal when a Gov Hub contribution reaches
    accepted or considered. Workgroup leads award via existing badge flows.
    """
    if outcome not in ('accepted', 'considered'):
        return
    if not proposal or not proposal.author_user_id:
        return

    from services.dp_proposals import workgroup_for_submission, submission_draft_ref
    from services.events import emit_event
    from models import Submission

    sub = Submission.query.get(proposal.submission_id)
    wg = workgroup_for_submission(sub) if sub else None
    badge_status = None
    if wg:
        from services.dp_badges import dp_contributor_badge_status

        badge_status = dp_contributor_badge_status(wg)

    emit_event(
        'dp_contribution_badge_eligible',
        actor_type='system',
        actor_id='govhub',
        subject_type='dp_proposal',
        subject_id=proposal.id,
        layer_id=sub.layer_id if sub else None,
        payload={
            'outcome': outcome,
            'author_user_id': proposal.author_user_id,
            'proposal_id': proposal.id,
            'submission_id': proposal.submission_id,
            'draft_ref': submission_draft_ref(sub),
            'badge_slug': DP_CONTRIBUTOR_BADGE_SLUG,
            'badge_label': DP_CONTRIBUTOR_BADGE_LABEL,
            'workgroup_id': wg.id if wg else None,
            'badge_ready': bool(badge_status and badge_status.get('ready')),
        },
    )
