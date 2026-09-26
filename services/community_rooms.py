"""Evidence-scoped coordination with fixed audiences and human-owned commitments.

The baseline facilitator is deterministic. A future Hermes adapter must accept only
this prefiltered context, have no side-effect tools, and pass delivery revalidation.
"""
import re
from flask import abort, g, has_request_context
from extensions import db
from models import User, LayerMember
from models.community_intelligence import CIRoom, CIRoomMessage, CIAction
from services import community_intelligence as ci


def key(data):
    value = ci.text_field(data, 'request_key', 64)
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', value):
        abort(400, description='request_key must be 8-64 letters, digits, underscores or hyphens.')
    return value


def room_for(layer_id, user_id, room_id):
    room = CIRoom.query.filter_by(id=room_id, layer_id=layer_id).first_or_404()
    if user_id not in room.members:
        abort(404)
    return room


def evidence_for(room, user_id):
    """Require layer publication, not the asker's personal organization permissions."""
    expected = {e['claim_id']: e for e in room.evidence}
    rows = ci.evidence_query(room.layer_id, user_id, shared_only=True).filter(
        ci.CIClaim.id.in_(expected)).all()
    if len(rows) != len(expected):
        return None
    for claim, source, program in rows:
        e = expected[claim.id]
        if (source.id != e['source_id'] or source.revision != e['source_revision']
                or program.id != e['program_id'] or program.revision != e['program_revision']):
            return None
    return rows


def require_current(room, user_id):
    rows = evidence_for(room, user_id)
    if rows is None:
        abort(409, description='Discussion evidence changed or was withdrawn. Start a new room with current evidence; history is restricted.')
    if has_request_context():
        g.ci_read_rooms = getattr(g, 'ci_read_rooms', set()) | {room.id}
    for _, source, program in rows:
        ci.track_evidence(source, program)
    return rows


def lock_evidence(rows):
    """Serialize writes with withdrawal/retirement on the authoritative SQL rows.

    Conditional no-op updates take write locks without changing content revisions.
    A write starting after revocation fails; withdrawal starting after a message
    waits for that commit and then removes the persisted dependent copies.
    """
    if has_request_context() and getattr(g, 'ci_user', None):
        active_member = LayerMember.query.filter_by(
            layer_id=rows[0][1].layer_id, user_id=g.ci_user['id'], status='active'
        ).update({'status': 'active'}, synchronize_session=False)
        if active_member != 1:
            abort(404)
    for _, source, program in sorted(rows, key=lambda row: row[1].id):
        count = ci.CISource.query.filter_by(id=source.id, revision=source.revision, visibility='layer').filter(
            ci.CISource.state.in_(['ready', 'needs_review'])).update(
                {'revision': source.revision}, synchronize_session=False)
        active = ci.CIProgram.query.filter_by(id=program.id, revision=program.revision, lifecycle='active').update(
            {'revision': program.revision}, synchronize_session=False)
        if count != 1 or active != 1:
            abort(409, description='Evidence changed. Refresh before continuing.')


def create_room(layer_id, user_id, data):
    request_key = key(data)
    previous = CIRoom.query.filter_by(layer_id=layer_id, created_by=user_id, request_key=request_key).first()
    if previous:
        require_current(previous, user_id)
        return previous
    ids = data.get('claim_ids')
    usernames = data.get('members')
    if not isinstance(ids, list) or len(ids) != 2 or not all(isinstance(x, str) for x in ids) or len(set(ids)) != 2:
        abort(400, description='Select exactly one reviewed need and one reviewed offer.')
    if not isinstance(usernames, list) or len(usernames) > 20 or not all(isinstance(x, str) and len(x) <= 100 for x in usernames):
        abort(400, description='Supply up to 20 exact member usernames.')
    rows = ci.evidence_query(layer_id, user_id, shared_only=True).filter(ci.CIClaim.id.in_(ids)).all()
    if len(rows) != 2:
        abort(404)
    first, second = rows
    if ({first[0].kind, second[0].kind} != {'need', 'offer'} or not first[0].topic
            or first[0].topic.casefold() != (second[0].topic or '').casefold()
            or first[1].organization_id == second[1].organization_id):
        abort(400, description='Evidence must be complementary reviewed needs/offers from different organizations with the same topic.')
    members = {user_id}
    for username in set(usernames):
        user = User.query.filter_by(username=username).first()
        if not user or not LayerMember.query.filter_by(layer_id=layer_id, user_id=user.id, status='active').first():
            abort(404, description='A selected participant is not available in this layer.')
        members.add(user.id)
    lock_evidence(rows)
    snapshots = [dict(claim_id=c.id, source_id=s.id, source_revision=s.revision,
                      program_id=p.id, program_revision=p.revision) for c, s, p in rows]
    room = CIRoom(layer_id=layer_id, created_by=user_id, title=ci.text_field(data, 'title'),
                  members=sorted(members), evidence=snapshots, request_key=request_key)
    db.session.add(room); db.session.flush()
    return room


def describe(room, user_id, *, full=False):
    rows = evidence_for(room, user_id)
    if rows is None:
        # Titles, excerpts, authors, participants, action text and counts can all
        # contain derived information; never return these for stale dependencies.
        return dict(id=room.id, stale=True, title='Discussion needs refreshed evidence',
                    message='Evidence changed, retired or became restricted. Start a new discussion from a current suggestion.')
    require_current(room, user_id)
    out = dict(id=room.id, title=room.title, stale=False, revision=room.revision,
               created_at=room.created_at.isoformat(), audience='Fixed participants; no audience expansion',
               members=[dict(id=u.id, username=u.username) for u in User.query.filter(User.id.in_(room.members)).all()])
    if full:
        out['citations'] = [ci.evidence_dict(*row) for row in sorted(rows, key=lambda row: row[0].id)]
        messages = CIRoomMessage.query.filter_by(room_id=room.id).order_by(CIRoomMessage.created_at, CIRoomMessage.id).limit(200).all()
        out['messages'] = [dict(id=m.id, body=m.body, kind=m.kind, author_id=m.author_id,
                                created_at=m.created_at.isoformat()) for m in messages]
        actions = CIAction.query.filter_by(room_id=room.id).order_by(CIAction.created_at, CIAction.id).limit(100).all()
        out['actions'] = [dict(id=a.id, text=a.text, owner_id=a.owner_id, proposed_by=a.proposed_by,
                               status=a.status, revision=a.revision,
                               accepted_at=a.accepted_at.isoformat() if a.accepted_at else None) for a in actions]
    return out


def post_message(room, user_id, data):
    lock_evidence(require_current(room, user_id))
    request_key = key(data)
    previous = CIRoomMessage.query.filter_by(room_id=room.id, author_id=user_id, request_key=request_key).first()
    if previous:
        return previous
    if CIRoomMessage.query.filter_by(room_id=room.id).count() >= 200:
        abort(409, description='This pilot room reached its 200-message limit.')
    message = CIRoomMessage(room_id=room.id, author_id=user_id,
                            body=ci.text_field(data, 'message', 4000), request_key=request_key)
    db.session.add(message); db.session.flush()
    return message


def facilitate(room, user_id, data):
    """Deterministic agenda with citations; never invent consensus or accept actions."""
    rows = require_current(room, user_id)
    lock_evidence(rows)
    request_key = key(data)
    previous = CIRoomMessage.query.filter_by(room_id=room.id, author_id=user_id, request_key=request_key).first()
    if previous:
        return previous
    question = ci.text_field(data, 'question', 500)
    if CIRoomMessage.query.filter_by(room_id=room.id).count() >= 200:
        abort(409, description='This pilot room reached its 200-message limit.')
    evidence = '\n'.join(f'[{i}] {c.statement}' for i, (c, _, _) in enumerate(sorted(rows, key=lambda row: row[0].id), 1))
    text = (f'Question: {question}\n\nReviewed evidence:\n{evidence}\n\n'
            'Discussion guide (rule-based; no live model):\n'
            '1. Ask each organization to confirm current willingness, capacity, timing and conditions.\n'
            '2. Record differences and unresolved questions in each participant’s own words.\n'
            '3. Propose the smallest useful experiment and a volunteer owner.\n'
            '4. The proposed owner must accept the next action personally.\n\n'
            'No agreement or partnership is inferred from these matching topics.')
    message = CIRoomMessage(room_id=room.id, author_id=user_id, kind='facilitator',
                            body=text, request_key=request_key)
    db.session.add(message); db.session.flush()
    return message


def propose_action(room, user_id, data):
    lock_evidence(require_current(room, user_id))
    request_key = key(data)
    previous = CIAction.query.filter_by(room_id=room.id, proposed_by=user_id, request_key=request_key).first()
    if previous:
        return previous
    owner = ci.text_field(data, 'owner_id', 36)
    if owner not in room.members or not LayerMember.query.filter_by(layer_id=room.layer_id, user_id=owner, status='active').first():
        abort(404)
    if CIAction.query.filter_by(room_id=room.id).count() >= 100:
        abort(409, description='This pilot room reached its 100-action limit.')
    action = CIAction(room_id=room.id, text=ci.text_field(data, 'text', 2000),
                      owner_id=owner, proposed_by=user_id, request_key=request_key)
    db.session.add(action); db.session.flush()
    return action


def proposal_draft(room, user_id):
    """Private download for deliberate handoff to the normal submission workflow."""
    require_current(room, user_id)
    data = describe(room, user_id, full=True)
    users = {m['id']: m['username'] for m in data['members']}
    lines = ['# Discussion draft: ' + room.title, '',
             'DRAFT FOR REVIEW. Not organizational consent, a partnership, or an approved proposal.',
             'Audience: fixed discussion participants. Review permissions before sharing or submitting.',
             f'Source discussion: /layers/{room.layer_id}/community/?room={room.id}', '',
             '## Evidence']
    for i, c in enumerate(data['citations'], 1):
        lines += [f"[{i}] {c['statement']}", f"Source: {c['title']} / {c['locator']} / revision {c['source_revision']}", '']
    lines += ['## Attributed discussion (no inferred consensus)']
    for m in data['messages']:
        if m['kind'] == 'human':
            lines += [f"{users.get(m['author_id'], 'Participant')}: {m['body']}", '']
    lines += ['## Next actions']
    for a in data['actions']:
        lines += [f"- {a['status'].upper()}: {a['text']} Owner: {users.get(a['owner_id'], 'Participant')}. "
                  f"Owner acceptance: {a['accepted_at'] or 'not accepted'}."]
    lines += ['', '## Unresolved questions',
              '- Capacity, timing, resources and organizational authority require explicit confirmation.',
              '- Disagreement remains unresolved unless participants explicitly record otherwise.', '',
              'Submit a reviewed version through the existing Gov Hub submission workflow.']
    return '\n'.join(lines)
