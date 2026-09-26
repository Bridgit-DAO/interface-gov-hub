"""Feature-gated community intelligence endpoints using Gov Hub session identity."""
import io
from flask import Blueprint, abort, g, jsonify, render_template, request, send_file
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import User, LayerMember
from models.community_intelligence import CIOrganization, CIMembership, CIProgram, CISource, CIClaim
from services import community_intelligence as ci
from services.csrf import csrf_token_valid, get_or_create_csrf_token
from services.identity import get_current_user
from services.community_extraction import MAX_BYTES

bp = Blueprint('community_intelligence', __name__)
API = '/api/layers/<layer_id>/community'


@bp.before_request
def boundary():
    request.max_content_length = MAX_BYTES + 64 * 1024
    g.ci_user = get_current_user()
    g.ci_layer = ci.require_layer(request.view_args['layer_id'], g.ci_user)
    g.ci_memberships = {(m.organization_id, m.role) for m in
                        CIMembership.query.filter_by(user_id=g.ci_user['id']).all()}
    # Defense in depth: the shared middleware skips CSRF during tests.
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if not csrf_token_valid(request.headers.get('X-CSRFToken')):
            abort(403, description='Invalid CSRF token.')


@bp.after_request
def no_cache(response):
    # Discard a prepared read if its evidence or audience changed during work.
    # Responses are not streamed or persisted; all evidence is checked at delivery.
    if response.status_code < 400 and (request.method == 'GET' or request.endpoint == 'community_intelligence.answer' or getattr(g, 'ci_read_rooms', None) or getattr(g, 'ci_read_opportunities', None)):
        uid = g.ci_user['id']
        layer_id = request.view_args['layer_id']
        dependencies = getattr(g, 'ci_dependencies', {})
        db.session.rollback()  # end the old read transaction and discard identity-map state
        valid = ci.enabled(layer_id) and LayerMember.query.filter_by(
            layer_id=layer_id, user_id=uid, status='active').first() is not None
        memberships = {(m.organization_id, m.role) for m in CIMembership.query.filter_by(user_id=uid).all()}
        valid = valid and memberships == g.ci_memberships
        for source_id, (source_revision, program_id, program_revision) in dependencies.items():
            source = ci.visible_sources(layer_id, uid).filter_by(id=source_id).first()
            program = db.session.get(CIProgram, program_id)
            if not source or source.revision != source_revision or not program or program.revision != program_revision:
                valid = False
                break
        from services import community_rooms as rooms
        from models.community_intelligence import CIRoom
        for room_id in getattr(g, 'ci_read_rooms', ()):
            room = db.session.get(CIRoom, room_id)
            if not room or uid not in room.members or rooms.evidence_for(room, uid) is None:
                valid = False
        from models.community_intelligence import CIOpportunity
        for item_id in getattr(g, 'ci_read_opportunities', ()):
            item = db.session.get(CIOpportunity, item_id)
            if not item or item.user_id != uid or rooms.evidence_for(item, uid) is None:
                valid = False
        if not valid:
            response.close()
            response = jsonify(error='Knowledge or access changed during this request. Refresh and try again.')
            response.status_code = 409
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['Vary'] = 'Cookie'
    if response.status_code >= 400:
        db.session.rollback()
    return response


@bp.errorhandler(IntegrityError)
def conflict(_error):
    db.session.rollback()
    return jsonify(error='Concurrent change or duplicate record. Refresh and retry.'), 409


def body():
    value = request.get_json()
    if not isinstance(value, dict):
        abort(400, description='A JSON object is required.')
    return value


@bp.get('/layers/<layer_id>/community/')
def workspace(layer_id):
    from services.rendering import render_page
    content = render_template('community_intelligence.html', layer=g.ci_layer,
                              csrf=get_or_create_csrf_token())
    return render_page('Community Intelligence', content)


@bp.get(API + '/')
def overview(layer_id):
    uid = g.ci_user['id']
    sources = ci.visible_sources(layer_id, uid).order_by(CISource.created_at.desc()).limit(100).all()
    memberships = CIMembership.query.filter_by(user_id=uid).all()
    organizations = [dict(id=m.organization_id, name=db.session.get(CIOrganization, m.organization_id).name,
                          role=m.role) for m in memberships]
    programs = CIProgram.query.filter(CIProgram.layer_id == layer_id,
                                     CIProgram.organization_id.in_([m.organization_id for m in memberships])).all()
    return jsonify(viewer_id=uid, organizations=organizations,
                   programs=[dict(id=p.id, name=p.name, organization_id=p.organization_id,
                                  lifecycle=p.lifecycle, revision=p.revision) for p in programs],
                   sources=[ci.source_dict(s, uid) for s in sources],
                   source_limit=100, opportunities=ci.opportunities(layer_id, uid))


@bp.post(API + '/organizations/')
def create_organization(layer_id):
    data = body()
    org = CIOrganization(name=ci.text_field(data, 'name'), created_by=g.ci_user['id'])
    db.session.add(org)
    db.session.flush()
    db.session.add(CIMembership(organization_id=org.id, user_id=g.ci_user['id'], role='administrator'))
    ci.audit(org.id, g.ci_user['id'], org.id, 'organization.created', 1)
    db.session.commit()
    return jsonify(id=org.id), 201


@bp.post(API + '/organizations/<org_id>/members/')
def add_member(layer_id, org_id):
    ci.require_org(org_id, g.ci_user['id'], administrator=True)
    data = body()
    username = ci.text_field(data, 'username', 100)
    role = data.get('role')
    if not isinstance(role, str) or role not in ci.ROLES:
        abort(400, description='Invalid organization role.')
    user = User.query.filter_by(username=username).first()
    if not user or not LayerMember.query.filter_by(layer_id=layer_id, user_id=user.id, status='active').first():
        abort(404)
    if ci.membership(org_id, user.id):
        abort(409, description='Membership already exists.')
    db.session.add(CIMembership(organization_id=org_id, user_id=user.id, role=role))
    ci.audit(org_id, g.ci_user['id'], user.id, 'membership.added', 1)
    db.session.commit()
    return jsonify(ok=True), 201


@bp.delete(API + '/organizations/<org_id>/members/<user_id>/')
def remove_member(layer_id, org_id, user_id):
    ci.require_org(org_id, g.ci_user['id'], administrator=True)
    member = ci.membership(org_id, user_id)
    if not member:
        abort(404)
    if member.role == 'administrator':
        abort(409, description='Administrator removal is not supported in this increment.')
    db.session.delete(member)
    ci.audit(org_id, g.ci_user['id'], user_id, 'membership.removed', 1)
    db.session.commit()
    return jsonify(ok=True)


@bp.post(API + '/programs/')
def create_program(layer_id):
    data = body()
    org_id = ci.text_field(data, 'organization_id', 36)
    ci.require_org(org_id, g.ci_user['id'], steward=True)
    lifecycle = data.get('lifecycle', 'unknown')
    if not isinstance(lifecycle, str) or lifecycle not in ci.LIFECYCLES:
        abort(400, description='Invalid lifecycle.')
    program = CIProgram(organization_id=org_id, layer_id=layer_id,
                        name=ci.text_field(data, 'name'), lifecycle=lifecycle)
    db.session.add(program)
    db.session.flush()
    ci.audit(org_id, g.ci_user['id'], program.id, 'program.created', 1)
    db.session.commit()
    return jsonify(id=program.id), 201


@bp.patch(API + '/programs/<program_id>/')
def lifecycle(layer_id, program_id):
    program = CIProgram.query.filter_by(id=program_id, layer_id=layer_id).first_or_404()
    ci.require_org(program.organization_id, g.ci_user['id'], steward=True)
    data = body()
    if not isinstance(data.get('lifecycle'), str) or data['lifecycle'] not in ci.LIFECYCLES:
        abort(400, description='Invalid lifecycle.')
    ci.advance(CIProgram, program, data.get('revision'))
    program.lifecycle = data['lifecycle']
    program.changed_at = ci.datetime.utcnow()
    program.effective_date = ci.date_field(data, 'effective_date')
    ci.audit(program.organization_id, g.ci_user['id'], program.id, 'program.' + program.lifecycle, program.revision)
    db.session.commit()
    return jsonify(ok=True, revision=program.revision)


@bp.post(API + '/sources/')
def submit(layer_id):
    if not request.files.get('file'):
        abort(400, description='Upload a file. URL ingestion is not enabled in this increment.')
    file = request.files['file']
    title = ci.text_field(request.form, 'title')
    program_id = ci.text_field(request.form, 'program_id', 36)
    extension = (file.filename or '').rsplit('.', 1)[-1].lower()
    source, created = ci.submit_source(layer_id, g.ci_user['id'], program_id, title,
                                       file.read(MAX_BYTES + 1), extension,
                                       ci.date_field(request.form, 'published_date'))
    db.session.commit()
    return jsonify(source=ci.source_dict(source, g.ci_user['id']), duplicate=not created), 202 if created else 200


@bp.get(API + '/sources/<source_id>/')
def detail(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id)
    return jsonify(source=ci.source_dict(source, g.ci_user['id']),
                   claims=[ci.claim_dict(c) for c in CIClaim.query.filter_by(source_id=source.id).order_by(CIClaim.locator).all()])


@bp.get(API + '/sources/<source_id>/original/')
def original(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id)
    return send_file(io.BytesIO(source.original), mimetype='application/octet-stream', as_attachment=True,
                     download_name='evidence.' + source.media_type, conditional=False)


@bp.post(API + '/sources/<source_id>/review/')
def review(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id, steward=True)
    ci.review(source, g.ci_user['id'], body())
    db.session.commit()
    return jsonify(ok=True, revision=source.revision)


@bp.patch(API + '/sources/<source_id>/')
def policy(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id, steward=True)
    data = body()
    if not isinstance(data.get('visibility'), str) or data['visibility'] not in {'private', 'layer'}:
        abort(400, description='Choose private or layer visibility.')
    ci.advance(CISource, source, data.get('revision'))
    if source.state in {'queued', 'processing'}:
        abort(409, description='Wait for extraction before publishing.')
    source.visibility = data['visibility']
    ci.audit(source.organization_id, g.ci_user['id'], source.id, 'permissions.changed', source.revision)
    db.session.commit()
    return jsonify(ok=True, revision=source.revision)


@bp.post(API + '/sources/<source_id>/retry/')
def retry(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id, steward=True)
    ci.advance(CISource, source, body().get('revision'))
    if source.state not in {'failed', 'processing'} or source.attempts >= 3:
        abort(409, description='Only failed/interrupted jobs can retry, up to three attempts.')
    source.state, source.error = 'queued', None
    ci.audit(source.organization_id, g.ci_user['id'], source.id, 'extraction.requeued', source.revision)
    db.session.commit()
    return jsonify(ok=True)


@bp.delete(API + '/sources/<source_id>/')
def remove(layer_id, source_id):
    source = ci.source_for(layer_id, g.ci_user['id'], source_id, steward=True)
    ci.require_org(source.organization_id, g.ci_user['id'], administrator=True)
    ci.withdraw(source, g.ci_user['id'], body().get('revision'))
    db.session.commit()
    return jsonify(ok=True, retention='Removed from active storage. SQLite free pages, WAL and backups follow operator retention; downloaded copies cannot be recalled.')


@bp.post(API + '/answer/')
def answer(layer_id):
    data = body()
    if type(data.get('historical', False)) is not bool:
        abort(400, description='historical must be a boolean.')
    return jsonify(ci.answer(layer_id, g.ci_user['id'], ci.text_field(data, 'question', 500),
                              history=data.get('historical', False)))


@bp.get(API + '/rooms/')
def rooms_list(layer_id):
    from models.community_intelligence import CIRoom
    from services import community_rooms as rooms
    # Audience filtering happens in SQL before limit/count/title serialization.
    from sqlalchemy import exists, func, select
    members = func.json_each(CIRoom.members).table_valued('value').alias('room_member')
    audience = exists(select(1).select_from(members).where(members.c.value == g.ci_user['id']))
    found = CIRoom.query.filter(CIRoom.layer_id == layer_id, audience).order_by(CIRoom.created_at.desc()).limit(100).all()
    return jsonify(rooms=[rooms.describe(r, g.ci_user['id']) for r in found])


@bp.post(API + '/rooms/')
def rooms_create(layer_id):
    from services import community_rooms as rooms
    room = rooms.create_room(layer_id, g.ci_user['id'], body())
    db.session.commit()
    return jsonify(id=room.id), 201


@bp.get(API + '/rooms/<room_id>/')
def rooms_get(layer_id, room_id):
    from services import community_rooms as rooms
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    return jsonify(rooms.describe(room, g.ci_user['id'], full=True))


@bp.post(API + '/rooms/<room_id>/messages/')
def rooms_message(layer_id, room_id):
    from services import community_rooms as rooms
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    message = rooms.post_message(room, g.ci_user['id'], body())
    db.session.commit()
    return jsonify(id=message.id), 201


@bp.post(API + '/rooms/<room_id>/facilitate/')
def rooms_facilitate(layer_id, room_id):
    from services import community_rooms as rooms
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    message = rooms.facilitate(room, g.ci_user['id'], body())
    db.session.commit()
    return jsonify(id=message.id), 201


@bp.post(API + '/rooms/<room_id>/actions/')
def rooms_action(layer_id, room_id):
    from services import community_rooms as rooms
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    action = rooms.propose_action(room, g.ci_user['id'], body())
    db.session.commit()
    return jsonify(id=action.id), 201


@bp.patch(API + '/rooms/<room_id>/actions/<action_id>/')
def rooms_accept_action(layer_id, room_id, action_id):
    from services import community_rooms as rooms
    from models.community_intelligence import CIAction
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    rooms.lock_evidence(rooms.require_current(room, g.ci_user['id']))
    action = CIAction.query.filter_by(id=action_id, room_id=room.id).first_or_404()
    if action.owner_id != g.ci_user['id']:
        abort(403, description='Only the proposed owner can accept or decline this action.')
    data = body()
    if data.get('status') not in ('accepted', 'declined'):
        abort(400, description='Choose accepted or declined.')
    ci.advance(CIAction, action, data.get('revision'))
    if action.status != 'proposed':
        abort(409, description='This action already has an owner response.')
    action.status = data['status']
    action.accepted_at = ci.datetime.utcnow() if action.status == 'accepted' else None
    db.session.commit()
    return jsonify(ok=True, revision=action.revision)


@bp.get(API + '/rooms/<room_id>/proposal-draft/')
def rooms_draft(layer_id, room_id):
    from services import community_rooms as rooms
    room = rooms.room_for(layer_id, g.ci_user['id'], room_id)
    text = rooms.proposal_draft(room, g.ci_user['id'])
    return send_file(io.BytesIO(text.encode()), mimetype='text/markdown', as_attachment=True,
                     download_name='community-proposal-draft.md', conditional=False)


@bp.get(API + '/opportunities/')
def tracked_opportunities(layer_id):
    from models.community_intelligence import CIOpportunity
    from services import community_opportunities as opportunities
    uid = g.ci_user['id']
    items = CIOpportunity.query.filter_by(layer_id=layer_id, user_id=uid).order_by(
        CIOpportunity.updated_at.desc(), CIOpportunity.id).limit(200).all()
    return jsonify(opportunities=[opportunities.describe(item, uid) for item in items])


@bp.post(API + '/opportunities/')
def save_opportunity(layer_id):
    from services import community_opportunities as opportunities
    item = opportunities.save(layer_id, g.ci_user['id'], body())
    result = opportunities.describe(item, g.ci_user['id'])
    db.session.commit()
    return jsonify(result), 201


@bp.patch(API + '/opportunities/<opportunity_id>/')
def update_opportunity(layer_id, opportunity_id):
    from models.community_intelligence import CIOpportunity
    from services import community_opportunities as opportunities
    item = CIOpportunity.query.filter_by(id=opportunity_id, layer_id=layer_id,
                                         user_id=g.ci_user['id']).first_or_404()
    opportunities.change(item, g.ci_user['id'], body())
    result = opportunities.describe(item, g.ci_user['id'])
    db.session.commit()
    return jsonify(result)
