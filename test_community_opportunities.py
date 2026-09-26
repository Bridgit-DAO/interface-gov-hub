"""Opportunity lifecycle and evidence boundary integration tests."""
from test_community_intelligence import world, req, share, detail, review
from test_community_rooms import setup_room
from extensions import db
from models import LayerMember
from models.community_intelligence import CIOpportunity, CISource


def suggestion(w):
    o = req(w, w['clients'][0], '/').json['opportunities'][0]
    return dict(claim_ids=[c['claim_id'] for c in o['citations']], evidence=o['evidence'])


def test_personal_lifecycle_idempotency_and_conflicts(world):
    w=world; setup_room(w); c=w['clients'][0]; data=suggestion(w)
    a=req(w,c,'/opportunities/','POST',data)
    assert a.status_code==201; item=a.json
    assert req(w,c,'/opportunities/','POST',data).json['id']==item['id']
    path='/opportunities/'+item['id']+'/'
    for version,state in enumerate(['exploring','dismissed','saved'],1):
        r=req(w,c,path,'PATCH',dict(revision=version,status=state))
        assert r.status_code==200 and r.json['status']==state
    assert req(w,c,path,'PATCH',dict(revision=1,status='dismissed')).status_code==409
    assert req(w,c,path,'PATCH',dict(revision=4,status='partnership')).status_code==400
    assert len(req(w,c,'/opportunities/').json['opportunities'])==1


def test_tracker_is_private_to_member_and_layer(world):
    w=world;setup_room(w);c=w['clients'][0];data=suggestion(w)
    item=req(w,c,'/opportunities/','POST',data).json
    for outsider in [w['clients'][1],w['clients'][2],w['clients'][4]]:
        assert req(w,outsider,'/opportunities/').json['opportunities']==[]
        assert req(w,outsider,'/opportunities/'+item['id']+'/','PATCH',dict(revision=1,status='dismissed')).status_code==404
    assert req(w,w['clients'][3],'/opportunities/').status_code==404
    r=c.patch('/api/layers/'+w['other']+'/community/opportunities/'+item['id']+'/',json=dict(revision=1,status='dismissed'),headers={'X-CSRFToken':'test-csrf'})
    assert r.status_code==404
    other=req(w,w['clients'][1],'/opportunities/','POST',data).json
    assert other['id']!=item['id']


def test_correction_invalidates_saved_and_inflight_suggestions(world):
    w=world;_,sources,_=setup_room(w);c=w['clients'][0];data=suggestion(w)
    old=req(w,c,'/opportunities/','POST',data).json
    review(w,c,sources[0],kind='need',topic='training',statement='We need revised training support.')
    assert req(w,c,'/opportunities/','POST',data).status_code==409
    listed=req(w,c,'/opportunities/').json['opportunities'][0]
    assert listed==dict(id=old['id'],stale=True,title='Opportunity needs refreshed evidence')
    assert req(w,c,'/opportunities/'+old['id']+'/','PATCH',dict(revision=1,status='exploring')).status_code==409
    fresh=req(w,c,'/opportunities/','POST',suggestion(w)).json
    assert fresh['id']!=old['id'] and fresh['status']=='saved'


def test_private_retired_removed_and_revoked_evidence(world):
    w=world;_,sources,_=setup_room(w);c=w['clients'][0];data=suggestion(w)
    item=req(w,c,'/opportunities/','POST',data).json
    share(w,c,sources[0],'private')
    assert req(w,c,'/opportunities/','POST',data).status_code==404
    assert req(w,c,'/opportunities/').json['opportunities'][0]['stale']
    share(w,c,sources[0])
    fresh=req(w,c,'/opportunities/','POST',suggestion(w)).json
    s=detail(w,c,sources[0])['source']
    assert req(w,c,'/programs/'+s['program_id']+'/','PATCH',dict(revision=s['program_revision'],lifecycle='discontinued')).status_code==200
    assert all(o['stale'] for o in req(w,c,'/opportunities/').json['opportunities'])
    assert req(w,c,'/sources/'+sources[0]+'/','DELETE',dict(revision=s['revision'])).status_code==200
    with w['app'].app_context():
        # Records retain IDs/revisions only, no source or discussion text.
        assert set(db.session.get(CIOpportunity,item['id']).evidence[0])=={'claim_id','source_id','source_revision','program_id','program_revision'}
        LayerMember.query.filter_by(layer_id=w['layer'],user_id=w['users'][0]).update({'status':'inactive'})
        db.session.commit()
    assert req(w,c,'/opportunities/').status_code==404


def test_revoke_before_save_response_withholds_content(world,monkeypatch):
    w=world;_,sources,_=setup_room(w);c=w['clients'][0];data=suggestion(w)
    from services import community_opportunities as opportunities
    original=opportunities.describe
    def interleave(*args):
        result=original(*args)
        source=db.session.get(CISource,sources[0]);source.visibility='private';source.revision+=1
        return result
    monkeypatch.setattr(opportunities,'describe',interleave)
    r=req(w,c,'/opportunities/','POST',data)
    assert r.status_code==409 and 'citations' not in r.json
