"""Stage 2 coordination tests, using the real app with disposable databases."""
from test_community_intelligence import world, req, organization, upload, process, review, share, detail
from extensions import db
from models.community_intelligence import CIRoom, CIRoomMessage, CIAction, CISource


def setup_room(w):
    citations = []
    source_ids = []
    for i, kind in enumerate(['need', 'offer']):
        _, program = organization(w, i)
        c = w['clients'][i]
        sid = upload(w, c, program, ('We '+kind+' training.').encode()).json['source']['id']
        process(w, sid); review(w, c, sid, kind=kind, topic='training'); share(w, c, sid)
        citations.append(detail(w, c, sid)['claims'][0]['id']); source_ids.append(sid)
    payload = dict(title='Explore a training pilot', members=['curriculum-steward'],
                   claim_ids=citations, request_key='room-create-0001')
    r = req(w, w['clients'][0], '/rooms/', 'POST', payload)
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.json['id'], source_ids, payload


def test_discussion_facilitation_action_acceptance_and_draft(world):
    w = world; rid, sources, payload = setup_room(w); owner, other = w['clients'][:2]
    path = '/rooms/'+rid
    r = req(w, owner, path+'/messages/', 'POST', {'message':'I can explore a small pilot, but dates are unresolved.', 'request_key':'message-0001'})
    assert r.status_code == 201
    assert req(w, other, path+'/messages/', 'POST', {'message':'We disagree about timing; capacity needs review.', 'request_key':'message-0002'}).status_code == 201
    assert req(w, owner, path+'/facilitate/', 'POST', {'question':'What remains unresolved?', 'request_key':'guide-00001'}).status_code == 201
    r = req(w, owner, path+'/actions/', 'POST', {'text':'Arrange a 20-minute scoping call', 'owner_id':w['users'][1], 'request_key':'action-0001'})
    assert r.status_code == 201; aid=r.json['id']
    assert req(w, owner, path+'/actions/'+aid+'/', 'PATCH', {'revision':1,'status':'accepted'}).status_code == 403
    r = req(w, other, path+'/actions/'+aid+'/', 'PATCH', {'revision':1,'status':'accepted'})
    assert r.status_code == 200
    room = req(w, owner, path+'/').json
    assert len(room['citations']) == 2 and len(room['messages']) == 3
    assert room['actions'][0]['accepted_at'] and room['actions'][0]['status']=='accepted'
    draft=req(w, owner, path+'/proposal-draft/')
    assert draft.status_code==200
    text=draft.get_data(as_text=True)
    assert 'We disagree about timing' in text and 'ACCEPTED' in text and 'DRAFT FOR REVIEW' in text
    assert req(w, other, path+'/actions/'+aid+'/', 'PATCH', {'revision':1,'status':'declined'}).status_code==409


def test_fixed_audience_and_cross_layer_isolation(world):
    w=world;rid,_,_=setup_room(w)
    for outsider in w['clients'][2:]:
        response=req(w, outsider, '/rooms/'+rid+'/')
        assert response.status_code==404
        if outsider != w['clients'][3]:
            assert req(w, outsider, '/rooms/').json['rooms']==[]
    r=w['clients'][0].get('/api/layers/'+w['other']+'/community/rooms/'+rid+'/')
    assert r.status_code==404
    assert req(w,w['clients'][0],'/rooms/'+rid+'/','PATCH',{'members':w['users']}).status_code==405


def test_private_evidence_never_enters_room_and_stale_history_is_hidden(world):
    w=world;rid,sources,payload=setup_room(w); owner=w['clients'][0]
    assert req(w,owner,'/rooms/'+rid+'/messages/','POST',{'message':'Sensitive discussion derived from evidence','request_key':'private-text1'}).status_code==201
    share(w,owner,sources[0],'private')
    for c in w['clients'][:2]:
        room=req(w,c,'/rooms/'+rid+'/').json
        assert room['stale'] and 'messages' not in room and 'citations' not in room and 'members' not in room
        assert room['title']=='Discussion needs refreshed evidence'
        assert req(w,c,'/rooms/'+rid+'/proposal-draft/').status_code==409
    payload['request_key']='room-private-2'
    assert req(w,owner,'/rooms/','POST',payload).status_code==404
    share(w,owner,sources[0])
    assert req(w,owner,'/rooms/'+rid+'/').json['stale']  # old room cannot be resurrected


def test_retirement_invalidates_room_and_blocks_acceptance(world):
    w=world;rid,sources,_=setup_room(w);owner=w['clients'][0]
    a=req(w,owner,'/rooms/'+rid+'/actions/','POST',{'text':'Explore','owner_id':w['users'][0],'request_key':'retire-action'}).json['id']
    s=detail(w,owner,sources[0])['source']
    assert req(w,owner,'/programs/'+s['program_id']+'/','PATCH',{'revision':s['program_revision'],'lifecycle':'discontinued'}).status_code==200
    assert req(w,owner,'/rooms/'+rid+'/').json['stale']
    assert req(w,owner,'/rooms/'+rid+'/actions/'+a+'/','PATCH',{'revision':1,'status':'accepted'}).status_code==409


def test_duplicate_requests_and_withdrawal_clear_persisted_copies(world):
    w=world;rid,sources,payload=setup_room(w);owner=w['clients'][0]
    assert req(w,owner,'/rooms/','POST',payload).json['id']==rid
    data={'message':'Copied source text','request_key':'same-message'}
    a=req(w,owner,'/rooms/'+rid+'/messages/','POST',data).json['id']
    assert req(w,owner,'/rooms/'+rid+'/messages/','POST',data).json['id']==a
    req(w,owner,'/rooms/'+rid+'/actions/','POST',{'text':'Copied action','owner_id':w['users'][0],'request_key':'same-action1'})
    d=detail(w,owner,sources[0])
    assert req(w,owner,'/sources/'+sources[0]+'/','DELETE',{'revision':d['source']['revision']}).status_code==200
    with w['app'].app_context():
        assert CIRoomMessage.query.filter_by(room_id=rid).count()==0
        assert CIAction.query.filter_by(room_id=rid).count()==0
        assert db.session.get(CIRoom,rid).title=='Discussion evidence removed'


def test_revocation_during_facilitation_discards_response(world,monkeypatch):
    w=world;rid,sources,_=setup_room(w);owner=w['clients'][0]
    from services import community_rooms as rooms
    original=rooms.facilitate
    def interleave(*args,**kwargs):
        message=original(*args,**kwargs)
        # Same transaction simulates a policy update before delivery/commit.
        source=db.session.get(CISource,sources[0]);source.visibility='private';source.revision+=1
        return message
    monkeypatch.setattr(rooms,'facilitate',interleave)
    r=req(w,owner,'/rooms/'+rid+'/facilitate/','POST',{'question':'Training?','request_key':'interleave-1'})
    assert r.status_code==409 and 'id' not in r.json
