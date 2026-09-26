"""Real API requests with delegated credentials on disposable databases."""
import io
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from test_community_intelligence import world, req, organization, upload, process, review, share
from test_community_rooms import setup_room
from extensions import db
from models import LayerMember
from models.community_intelligence import CIAccessToken


def issue(w, scopes=None, owner=0):
    r=req(w,w['clients'][owner],'/tokens/','POST',dict(name='test integration',scopes=scopes or ['read'],expires_in_days=1))
    assert r.status_code==201,r.get_data(as_text=True)
    return r.json


def call(w, token, path='/', method='GET', data=None, **kwargs):
    headers={'Authorization':'Bearer '+token}
    headers.update(kwargs.pop('headers',{}))
    return w['app'].test_client().open(w['api']+path,method=method,json=data,headers=headers,**kwargs)


def test_bearer_reads_and_answer_without_session_or_csrf(world):
    w=world;setup_room(w);t=issue(w)
    r=call(w,t['token']);assert r.status_code==200 and len(r.json['opportunities'])==1
    assert r.headers['X-Community-API-Version']=='1' and 'no-store' in r.headers['Cache-Control']
    r=call(w,t['token'],'/answer/','POST',{'question':'training'})
    assert r.status_code==200 and len(r.json['citations'])==2
    with w['app'].app_context():
        saved=db.session.get(CIAccessToken,t['id'])
        assert saved.digest!=t['token'] and len(saved.digest)==64
    listing=req(w,w['clients'][0],'/tokens/').get_data(as_text=True)
    assert t['token'] not in listing and 'digest' not in listing


def test_scope_allowlist_and_no_cookie_fallback(world):
    w=world;rid,_,_=setup_room(w);t=issue(w)
    assert call(w,t['token'],'/rooms/'+rid+'/messages/','POST',{'message':'x','request_key':'message-1'}).status_code==403
    wide=issue(w,['read','contribute','coordinate'])
    for path,method in [('/tokens/','POST'),('/organizations/','POST'),('/rooms/'+rid+'/actions/not-real/','PATCH')]:
        assert call(w,wide['token'],path,method,{}).status_code==403
    r=w['clients'][0].get(w['api']+'/',headers={'Authorization':'Bearer invalid'})
    assert r.status_code==401 and r.is_json and r.headers['WWW-Authenticate'].startswith('Bearer')
    assert w['clients'][0].post(w['api']+'/tokens/',json={'name':'no csrf'}).status_code==403


def test_expiry_revocation_ownership_and_layer_membership(world):
    w=world;t=issue(w)
    other=w['clients'][1]
    assert req(w,other,'/tokens/'+t['id']+'/','DELETE').status_code==404
    assert call(w,t['token']).status_code==200
    r=w['app'].test_client().get('/api/layers/'+w['other']+'/community/',headers={'Authorization':'Bearer '+t['token']})
    assert r.status_code==401
    assert req(w,w['clients'][0],'/tokens/'+t['id']+'/','DELETE').status_code==200
    assert call(w,t['token']).status_code==401
    t=issue(w)
    with w['app'].app_context():
        db.session.get(CIAccessToken,t['id']).expires_at=datetime.utcnow()-timedelta(seconds=1)
        db.session.commit()
    assert call(w,t['token']).status_code==401
    t=issue(w)
    with w['app'].app_context():
        LayerMember.query.filter_by(layer_id=w['layer'],user_id=w['users'][0]).update({'status':'inactive'})
        db.session.commit()
    assert call(w,t['token']).status_code==404


def test_cors_preflight_and_actual_request_boundaries(world):
    w=world;w['app'].config['COMMUNITY_API_ORIGINS']=('https://partner.example',)
    t=issue(w);c=w['app'].test_client()
    headers={'Origin':'https://partner.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization, content-type'}
    r=c.options(w['api']+'/answer/',headers=headers)
    assert r.status_code==204 and r.headers['Access-Control-Allow-Origin']==headers['Origin']
    assert 'Access-Control-Allow-Credentials' not in r.headers
    r=call(w,t['token'],'/answer/','POST',{'question':'training'},headers={'Origin':headers['Origin']})
    assert r.status_code==200 and r.headers['Access-Control-Allow-Origin']==headers['Origin']
    assert c.get(w['api']+'/',headers={'Origin':headers['Origin']}).status_code==403
    for origin in ['https://evil.example','null']:
        r=c.options(w['api']+'/',headers={**headers,'Origin':origin})
        assert r.status_code==403 and 'Access-Control-Allow-Origin' not in r.headers
        assert call(w,t['token'],headers={'Origin':origin}).status_code==403


def test_machine_upload_through_real_middleware_and_coordination(world,monkeypatch):
    w=world;_,program=organization(w);t=issue(w,['read','contribute','coordinate'])
    # Exercise middleware's non-test multipart path, not its pytest bypass.
    w['app'].config['TESTING']=False
    with monkeypatch.context() as m:
        m.delitem(sys.modules,'pytest')
        c=w['app'].test_client()
        r=c.post(w['api']+'/sources/',headers={'Authorization':'Bearer '+t['token']},data={
            'program_id':program,'title':'Agent contribution','file':(io.BytesIO(b'We need training.'),'agent.md')})
    assert r.status_code==202,r.get_data(as_text=True)
    rid,_,_=setup_room(w)
    r=call(w,t['token'],'/rooms/'+rid+'/messages/','POST',dict(message='Checking availability, no commitment.',request_key='agent-msg-1'))
    assert r.status_code==201
    suggestion=call(w,t['token']).json['opportunities'][0]
    assert call(w,t['token'],'/opportunities/','POST',dict(claim_ids=[c['claim_id'] for c in suggestion['citations']],evidence=suggestion['evidence'])).status_code==201


def test_no_private_evidence_leak_and_token_revalidation(world,monkeypatch):
    w=world;rid,sources,_=setup_room(w);share(w,w['clients'][0],sources[0],'private')
    t=issue(w,owner=1)
    assert call(w,t['token'],'/sources/'+sources[0]+'/').status_code==404
    assert call(w,t['token'],'/rooms/'+rid+'/').json['stale']
    from services import community_intelligence as ci
    original=ci.answer
    def revoke(*args,**kwargs):
        result=original(*args,**kwargs)
        db.session.get(CIAccessToken,t['id']).revoked_at=datetime.utcnow()
        db.session.commit()
        return result
    monkeypatch.setattr(ci,'answer',revoke)
    r=call(w,t['token'],'/answer/','POST',{'question':'training'})
    assert r.status_code==409 and 'citations' not in r.json


def test_spec_matches_machine_allowlist_and_rate_limit(world,monkeypatch):
    w=world;t=issue(w)
    r=call(w,t['token'],'/openapi.json')
    assert r.status_code==200 and r.json['openapi']=='3.0.3'
    paths=r.json['paths']
    for path,operations in paths.items():
        for method,operation in operations.items():
            assert operation['x-required-scope'] in ['read','contribute','coordinate']
            assert 'responses' in operation
    from services import utils
    monkeypatch.setattr(utils,'check_rate_limit',lambda *a,**kw:False)
    r=call(w,t['token'])
    assert r.status_code==429 and r.headers['Retry-After']=='60'


def test_https_requirement_and_issuance_validation(world):
    w=world;t=issue(w)
    for data in [dict(name='bad',scopes=['admin']),dict(name='bad',expires_in_days=100),dict(name='bad',expires_in_days=True)]:
        assert req(w,w['clients'][0],'/tokens/','POST',data).status_code==400
    w['app'].config['IS_DEVELOPMENT']=False
    w['app'].config['TESTING']=False
    assert call(w,t['token']).status_code==403
    assert call(w,t['token'],base_url='https://localhost').status_code==200


def test_contract_covers_every_allowed_machine_route(world):
    from services.community_api import ENDPOINT_SCOPES
    import re
    spec=json.loads((Path(__file__).parent/'docs/community-intelligence/openapi.json').read_text())
    operations=set()
    for rule in world['app'].url_map.iter_rules():
        name=rule.endpoint.removeprefix('community_intelligence.')
        if not rule.endpoint.startswith('community_intelligence.') or name not in ENDPOINT_SCOPES:
            continue
        suffix=rule.rule.split('/community',1)[1]
        suffix=re.sub(r'<([^>]+)>',r'{\1}',suffix)
        for method in rule.methods-{'HEAD','OPTIONS'}:
            operation=spec['paths'][suffix][method.lower()]
            assert operation['x-required-scope']==ENDPOINT_SCOPES[name]
            operations.add((suffix,method.lower()))
    assert operations=={(path,method) for path,methods in spec['paths'].items() for method in methods}
