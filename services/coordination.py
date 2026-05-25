"""Coordination services: is_layer_admin, activate_vote, close_vote, _election_candidates_ordered."""
import hashlib
import json
import random
from collections import Counter
from datetime import datetime

from extensions import db
from models import (
    LayerAdmin, User, Vote, Ballot, VoteCandidate, VoteEligibilitySnapshot, Claim,
)
from services.events import emit_event
from services.utils import generate_claim_id


def is_site_moderation_staff(user):
    """Site roles allowed to perform narrowly scoped moderation (e.g. knowledge_form only), not full layer admin."""
    if not user:
        return False
    return user.get('role') in ('admin', 'editor')


def is_layer_admin(layer, user):
    """True if user is layer owner (initiator), an assigned layer admin, or site admin."""
    if not user:
        return False
    if user.get('role') == 'admin':
        return True
    if not layer:
        return False
    initiator_id = layer.initiator_id if hasattr(layer, 'initiator_id') else layer.get('initiator_id')
    if initiator_id == user['id']:
        return True
    lid = layer.id if hasattr(layer, 'id') else layer.get('id')
    return LayerAdmin.query.filter_by(layer_id=lid, user_id=user['id']).first() is not None


def activate_vote(vote):
    """Activate a scheduled vote: set status, snapshot eligibility."""
    if vote.status != 'scheduled':
        return False, f"Cannot activate vote in status '{vote.status}'"

    # Snapshot eligible voters = active LayerMembers for vote.layer_id
    members = LayerMember.query.filter_by(
        layer_id=vote.layer_id,
        status='active'
    ).all()

    for member in members:
        snapshot = VoteEligibilitySnapshot(
            vote_id=vote.id,
            person_id=member.user_id,
            is_eligible=True,
            reason='active project member at vote activation'
        )
        db.session.add(snapshot)

    vote.status = 'active'
    emit_event('vote_started', actor_type='user', actor_id=vote.created_by_id,
               subject_type='vote', subject_id=vote.id, layer_id=vote.layer_id,
               payload={'title': vote.title, 'eligible_count': len(members)})
    db.session.commit()

    print(f"[VOTE] Activated vote {vote.id} ({vote.title}) — {len(members)} eligible voters")
    return True, f"Activated with {len(members)} eligible voters"


def close_vote(vote):
    """Close an active vote: tally ballots, determine result."""
    if vote.status != 'active':
        return False, f"Cannot close vote in status '{vote.status}'"

    ballots = Ballot.query.filter_by(vote_id=vote.id).all()
    eligible_count = VoteEligibilitySnapshot.query.filter_by(
        vote_id=vote.id, is_eligible=True
    ).count()

    vote_type = getattr(vote, 'vote_type', None) or 'approval'
    if vote_type == 'election':
        candidate_votes = Counter(b.choice for b in ballots if b.choice and b.choice not in ('yes', 'no', 'abstain'))
        votes_cast = len(ballots)
        quorum_met = votes_cast >= vote.quorum_count
        seats = getattr(vote, 'seats', 1) or 1
        approved_ids = {str(c.id) for c in vote.candidates.filter(VoteCandidate.status == 'approved').all()}
        ranked = [(cid, cnt) for cid, cnt in candidate_votes.most_common() if cid in approved_ids]
        winners = [cid for cid, _ in ranked[:int(seats)]]
        vote.result = 'elected' if winners else 'no_quorum' if not quorum_met else 'no_winners'
        vote.status = 'closed'
        vote.closed_at = datetime.utcnow()
        emit_event('vote_closed', actor_type='system', subject_type='vote', subject_id=vote.id,
                   layer_id=vote.layer_id, payload={'result': vote.result, 'votes_cast': votes_cast, 'winners': winners})
        by_candidate = []
        for c in vote.candidates.filter(VoteCandidate.status == 'approved').order_by(VoteCandidate.display_order, VoteCandidate.id):
            u = User.query.get(c.user_id)
            name = (u.displayName or u.username or u.oauthName or f'User {c.user_id}') if u else f'Candidate {c.id}'
            by_candidate.append({'candidate_id': str(c.id), 'name': name, 'votes': candidate_votes.get(str(c.id), 0)})
        winner_names = []
        for cid in winners:
            vc = VoteCandidate.query.get(str(cid)) if cid else None
            if vc:
                u = User.query.get(vc.user_id)
                winner_names.append((u.displayName or u.username or u.oauthName or f'User {vc.user_id}') if u else f'Candidate {cid}')
            else:
                winner_names.append(str(cid))
        vote.result_summary = json.dumps({
            'eligible': eligible_count,
            'votes_cast': votes_cast,
            'candidate_totals': dict(candidate_votes),
            'by_candidate': by_candidate,
            'winners': winners,
            'winner_names': winner_names,
            'seats': seats,
            'quorum_required': vote.quorum_count,
            'quorum_met': quorum_met,
            'result': vote.result
        })
        db.session.flush()
        if vote.role_id and winners:
            for cid in winners:
                vc = VoteCandidate.query.get(str(cid)) if cid else None
                if vc:
                    claim_id = generate_claim_id()
                    claim = Claim(
                        id=claim_id,
                        layer_id=vote.layer_id,
                        role_id=vote.role_id,
                        claimant_id=vc.user_id,
                        intent='Elected via vote',
                        status='active',
                        approval_required=False
                    )
                    db.session.add(claim)
                    emit_event('role_claimed', actor_type='system', subject_type='claim', subject_id=claim_id,
                               layer_id=vote.layer_id, payload={'role_id': vote.role_id, 'claimant_id': vc.user_id, 'election_vote_id': vote.id})
    else:
        yes_count = sum(1 for b in ballots if b.choice == 'yes')
        no_count = sum(1 for b in ballots if b.choice == 'no')
        abstain_count = sum(1 for b in ballots if b.choice == 'abstain')
        votes_cast = yes_count + no_count + abstain_count
        quorum_met = votes_cast >= vote.quorum_count
        if yes_count + no_count > 0:
            yes_ratio = yes_count / (yes_count + no_count)
        else:
            yes_ratio = 0.0
        if not quorum_met:
            vote.result = 'no_quorum'
        elif yes_ratio >= vote.win_threshold:
            vote.result = 'passed'
        else:
            vote.result = 'failed'
        vote.status = 'closed'
        vote.closed_at = datetime.utcnow()
        emit_event('vote_closed', actor_type='system', subject_type='vote', subject_id=vote.id,
                   layer_id=vote.layer_id, payload={'result': vote.result, 'votes_cast': votes_cast})
        vote.result_summary = json.dumps({
            'eligible': eligible_count,
            'votes_cast': votes_cast,
            'yes': yes_count,
            'no': no_count,
            'abstain': abstain_count,
            'quorum_required': vote.quorum_count,
            'quorum_met': quorum_met,
            'yes_ratio': round(yes_ratio, 4),
            'win_threshold': vote.win_threshold,
            'result': vote.result
        })

    db.session.commit()
    return True, vote.result


def _election_candidates_ordered(vote):
    """Return approved candidates for an election vote in ballot order (randomized when active)."""
    candidates = list(vote.candidates.filter(VoteCandidate.status == 'approved').order_by(VoteCandidate.display_order, VoteCandidate.id))
    if not candidates:
        return []
    if vote.status in ('scheduled', 'active') and getattr(vote, 'ballot_order_seed', None) is None:
        vote.ballot_order_seed = random.randint(1, 2**31 - 1)
        db.session.commit()
    seed = getattr(vote, 'ballot_order_seed', None) or 0
    if seed:
        def order_key(c):
            h = hashlib.sha256(f"{seed}_{c.id}".encode()).hexdigest()
            return int(h[:16], 16)
        candidates = sorted(candidates, key=order_key)
    return candidates
