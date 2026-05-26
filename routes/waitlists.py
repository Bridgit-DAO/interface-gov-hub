"""Waitlists API: layer waitlists, entries, join/leave, milestones, confirm, embed widget."""
import html as html_mod
import json
import os
import secrets
from datetime import datetime

from dateutil import parser as date_parser
from flask import Blueprint, jsonify, request, current_app, abort, session

from extensions import db
from models import (
    Layer, LayerMember, User,
    Waitlist, WaitlistEntry, WaitlistEmailSignup, WaitlistMilestone,
)
from services.identity import get_current_user, require_auth, get_or_create_referral_code
from services.coordination import is_layer_admin
from services.events import emit_event

bp = Blueprint('waitlists', __name__, url_prefix='')

# Embed widget JS - email-first, no auth. Uses join-email API.
EMBED_WIDGET_JS = r"""(function(){
var c=window.__WL_CFG;if(!c)return;
var WAITLIST_ID=c.waitlistId,API_BASE=location.origin,BTN_LABEL=c.btnLabel||'Join';
var SOURCE_URL=location.href,SOURCE_DOMAIN=location.hostname;
var joinInProgress=false;
window.joinWaitlist=async function(){
if(joinInProgress)return;
var btn=document.getElementById('join-btn'),area=document.getElementById('message-area');
var emailEl=document.getElementById('wl-email'),msgEl=document.getElementById('wl-msg');
var email=emailEl?emailEl.value.trim():'';
var msg=msgEl?msgEl.value.trim():'';
if(!email){area.innerHTML='<div class="wl-error">Please enter your email.</div>';return;}
if(email.indexOf('@')===-1||email.indexOf('.')===-1){area.innerHTML='<div class="wl-error">Please enter a valid email address.</div>';return;}
joinInProgress=true;btn.disabled=true;btn.textContent='Sending...';
try{
var joinR=await fetch(API_BASE+'/api/waitlists/'+WAITLIST_ID+'/join-email/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,message:msg,source:'embed:'+SOURCE_DOMAIN,source_url:SOURCE_URL})});
var data=await joinR.json();
if(joinR.ok){
var msg=data.info||(data.message==='joined'?'You\'re on the list!'+(data.position?' #'+data.position:'')+'':'We have sent an email to confirm your place. Please check your inbox and click the link to confirm.');
area.innerHTML='<div class="wl-success">'+msg+'</div>';
btn.style.display='none';if(emailEl)emailEl.style.display='none';if(msgEl)msgEl.style.display='none';
var ec=document.getElementById('entry-count');if(ec&&data.position)ec.textContent=parseInt(ec.textContent,10)+1;
}
else{area.innerHTML='<div class="wl-error">'+(data.error||'Failed')+'</div>';btn.disabled=false;btn.textContent=BTN_LABEL;}
joinInProgress=false;
}catch(e){area.innerHTML='<div class="wl-error">Error. Please try again.</div>';btn.disabled=false;btn.textContent=BTN_LABEL;joinInProgress=false;}
};
})();"""

# Embed auth: Web3Auth modal inline (no popup/tab - avoids blockers)
EMBED_AUTH_JS = r"""(function(){
var web3auth=null, authInProgress=false;
function loadScript(src){return new Promise(function(r,e){var s=document.createElement('script');s.src=src;s.onload=r;s.onerror=e;document.head.appendChild(s);});}
window.showEmbedLogin=async function(onSuccess,onFailure){
if(authInProgress)return;
authInProgress=true;postSent=false;
var done=function(){authInProgress=false;};
var fail=function(){done();if(typeof onFailure==='function')onFailure();};
try{
if(!web3auth){
await loadScript('https://cdn.jsdelivr.net/npm/web3@1.10.0/dist/web3.min.js');
await loadScript('https://unpkg.com/@web3auth/modal@10.13.1/dist/modal.umd.min.js');
await new Promise(function(r){var c=function(){if(window.Modal&&window.Modal.Web3Auth)r();else setTimeout(c,100);};c();});
var C=window.Modal.Web3Auth;
web3auth=new C({clientId:"BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk",web3AuthNetwork:'sapphire_devnet',redirectUrl:location.href,chainConfig:{chainNamespace:'eip155',chainId:'0x1',rpcTarget:'https://rpc.ankr.com/eth',displayName:'Ethereum',blockExplorerUrl:'https://etherscan.io',ticker:'ETH',tickerName:'Ethereum'},uiConfig:{mode:'dark',theme:{primary:'#1d9bf0'},loginMethodsOrder:['google','twitter','email_passwordless','wallet'],defaultLanguage:'en'}});
await web3auth.init();
}
await doConnect(onSuccess,fail);
done();
}catch(e){console.error('Web3Auth failed',e);if(!e.message||e.message.indexOf('user closed')===-1)alert('Sign-in failed: '+(e.message||'Please try again.'));fail();}
};
var postSent=false;
async function doConnect(onSuccess,onFailure){
var p=await web3auth.connect();
var u=await web3auth.getUserInfo();
if(postSent)return;
postSent=true;
var evm='';try{if(p){var w3=new Web3(p);var a=await w3.eth.getAccounts();if(a&&a.length)evm=a[0];}}catch(x){}
var idToken='';try{var ident=await web3auth.getIdentityToken();idToken=(ident&&ident.idToken)||web3auth.idToken||'';}catch(x){}
if(!idToken){postSent=false;alert('Sign-in verification failed: no identity token.');if(typeof onFailure==='function')onFailure();return;}
var pay={idToken:idToken,evmAddress:evm};
var res=await fetch(location.origin+'/api/auth/web3auth',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(pay)});
if(res.ok){if(typeof onSuccess==='function')onSuccess();}else{postSent=false;var j=await res.json().catch(function(){});alert('Login failed: '+(j.error||'Unknown error'));if(typeof onFailure==='function')onFailure();}
}
})();"""


def _embed_widget_params():
    """Parse embed widget query params. Returns dict with defaults."""
    return {
        'desc': request.args.get('desc', '1') == '1',
        'count': request.args.get('count', '1') == '1',
        'spots': request.args.get('spots', '1') == '1',
        'msg': request.args.get('msg', 'none'),
        'msg_placeholder': request.args.get('msg_placeholder', 'Add a message (optional)'),
        'btn': request.args.get('btn', 'Join Waitlist') or 'Join Waitlist',
        'fg': request.args.get('fg', '#ffffff'),
        'bg': request.args.get('bg', '#667eea'),
    }


def _send_waitlist_verification_email(signup, waitlist, confirm_url):
    """Send verification email via Resend. Returns True on success."""
    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    from_email = os.environ.get('RESEND_FROM', 'MLGH <onboarding@resend.dev>').strip()
    if not api_key:
        current_app.logger.warning("RESEND_API_KEY not set - skipping verification email")
        return False
    try:
        import resend
        resend.api_key = api_key
        params = {
            "from": from_email,
            "to": [signup.email],
            "subject": f"Confirm your place on {waitlist.name}",
            "html": f"""<p>You requested to join the waitlist for <strong>{waitlist.name}</strong>.</p>
<p>Please click the link below to confirm your place on the list:</p>
<p><a href="{confirm_url}" style="background:#1d9bf0;color:#fff;padding:8px 16px;text-decoration:none;border-radius:6px;display:inline-block;">Confirm my place</a></p>
<p>Or copy this link: {confirm_url}</p>
<p>If you didn't request this, you can ignore this email.</p>
<p>— MLGH</p>""",
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send waitlist verification email: {e}")
        return False


@bp.route('/api/layers/<layer_id>/waitlists/', methods=['GET'])
def list_waitlists(layer_id):
    """List waitlists for a project. Only active+visible ones for non-admins."""
    project = Layer.query.get_or_404(layer_id)
    current_user = get_current_user()
    is_admin = current_user and is_layer_admin(project, current_user)

    query = Waitlist.query.filter_by(layer_id=layer_id, archived=False)
    if not is_admin:
        query = query.filter_by(active=True)
        if not current_user:
            query = query.filter_by(public=True)
        else:
            is_member = LayerMember.query.filter_by(layer_id=layer_id, user_id=current_user['id'], status='active').first() is not None
            if not is_member:
                query = query.filter_by(public=True)

    waitlists = query.order_by(Waitlist.created_at.desc()).all()
    result = []
    for w in waitlists:
        d = w.to_dict()
        if d.get('milestones'):
            d['milestones'] = [{'id': m.id, 'title': m.title, 'description': m.description, 'threshold': m.threshold, 'action_type': m.action_type} for m in w.milestone_list.order_by(WaitlistMilestone.threshold).all()]
        else:
            d['milestones'] = []
        if current_user:
            entry = WaitlistEntry.query.filter_by(waitlist_id=w.id, user_id=current_user['id'], left_at=None).first()
            d['my_entry'] = {'position': entry.position, 'joined_at': entry.joined_at.isoformat()} if entry else None
            if w.referrals:
                user = User.query.get(current_user['id'])
                ref_code = get_or_create_referral_code(user)
                d['referral_url'] = f"{request.host_url}layers/{project.slug}/waitlist/{w.id}/?ref={ref_code}"
        else:
            d['my_entry'] = None
            d['referral_url'] = None
        result.append(d)

    return jsonify({'waitlists': result, 'count': len(result)})


@bp.route('/api/layers/<layer_id>/waitlists/', methods=['POST'])
@require_auth
def create_waitlist(layer_id):
    """Create waitlist - project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can create waitlists'}), 403

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    start_date = None
    if data.get('start_date'):
        try:
            start_date = date_parser.parse(data['start_date'])
        except Exception:
            return jsonify({'error': 'Invalid start_date'}), 400
    if not start_date:
        start_date = datetime.utcnow()

    closing_date = None
    if data.get('closing_date'):
        try:
            closing_date = date_parser.parse(data['closing_date'])
        except Exception:
            pass

    waitlist = Waitlist(
        layer_id=layer_id,
        name=name,
        description=data.get('description', ''),
        image_url=data.get('image_url'),
        public=data.get('public', True),
        referrals=data.get('referrals', False),
        active=data.get('active', True),
        start_date=start_date,
        closing_date=closing_date,
        max_number=data.get('max_number'),
        milestones=data.get('milestones', False),
        show_milestones=(data.get('show_milestones') or 'all')[:20]
    )
    db.session.add(waitlist)
    db.session.commit()

    return jsonify({'waitlist': waitlist.to_dict()}), 201


@bp.route('/api/waitlists/<waitlist_id>/', methods=['GET'])
def get_waitlist(waitlist_id):
    """Get single waitlist with milestones and user's entry."""
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    current_user = get_current_user()
    is_admin = current_user and is_layer_admin(project, current_user)

    if not waitlist.active and not is_admin:
        return jsonify({'error': 'Waitlist not found'}), 404

    d = waitlist.to_dict()
    d['milestones'] = [{'id': m.id, 'title': m.title, 'description': m.description, 'threshold': m.threshold, 'action_type': m.action_type} for m in waitlist.milestone_list.order_by(WaitlistMilestone.threshold).all()]

    if current_user:
        entry = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, user_id=current_user['id'], left_at=None).first()
        d['my_entry'] = {'position': entry.position, 'joined_at': entry.joined_at.isoformat()} if entry else None
        if waitlist.referrals:
            user = User.query.get(current_user['id'])
            ref_code = get_or_create_referral_code(user)
            d['referral_url'] = f"{request.host_url}layers/{project.slug}/waitlist/{waitlist.id}/?ref={ref_code}"
    else:
        d['my_entry'] = None
        d['referral_url'] = None

    return jsonify(d)


@bp.route('/api/waitlists/<waitlist_id>/', methods=['PATCH'])
@require_auth
def update_waitlist(waitlist_id):
    """Update waitlist - project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can edit waitlists'}), 403

    data = request.get_json() or {}
    if 'name' in data and data['name']:
        waitlist.name = data['name'].strip()
    if 'description' in data:
        waitlist.description = data['description']
    if 'public' in data:
        waitlist.public = bool(data['public'])
    if 'referrals' in data:
        waitlist.referrals = bool(data['referrals'])
    if 'active' in data:
        waitlist.active = bool(data['active'])
    if 'archived' in data:
        waitlist.archived = bool(data['archived'])
    if 'max_number' in data:
        waitlist.max_number = data['max_number'] if data['max_number'] is not None else None
    if 'milestones' in data:
        waitlist.milestones = bool(data['milestones'])
    if 'show_milestones' in data:
        waitlist.show_milestones = (data['show_milestones'] or 'all')[:20]
    if 'start_date' in data and data['start_date']:
        try:
            waitlist.start_date = date_parser.parse(data['start_date'])
        except Exception:
            pass
    if 'closing_date' in data:
        if data['closing_date'] is None or data['closing_date'] == '':
            waitlist.closing_date = None
        else:
            try:
                waitlist.closing_date = date_parser.parse(data['closing_date'])
            except Exception:
                pass

    db.session.commit()
    return jsonify({'waitlist': waitlist.to_dict()}), 200


@bp.route('/api/waitlists/<waitlist_id>/entries/', methods=['GET'])
@require_auth
def list_waitlist_entries(waitlist_id):
    """List entries (names) - project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can view the entry list'}), 403

    user_entries = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, left_at=None).order_by(WaitlistEntry.position).all()
    email_entries = WaitlistEmailSignup.query.filter_by(waitlist_id=waitlist_id, left_at=None).filter(WaitlistEmailSignup.verified_at.isnot(None)).order_by(WaitlistEmailSignup.position).all()
    entries = []
    for e in user_entries:
        entries.append({'id': f"u{e.id}", 'type': 'user', 'user_id': e.user_id, 'username': e.user.username, 'display_name': e.user.displayName or e.user.username, 'email': e.user.email, 'position': e.position, 'joined_at': e.joined_at.isoformat() if e.joined_at else None, 'referred_by': e.referred_by.displayName or e.referred_by.username if e.referred_by else None})
    for e in email_entries:
        entries.append({'id': f"e{e.id}", 'type': 'email', 'email': e.email, 'display_name': e.email, 'position': e.position, 'joined_at': e.verified_at.isoformat() if e.verified_at else None, 'message': e.message})
    entries.sort(key=lambda x: x['position'])
    return jsonify({'entries': entries}), 200


@bp.route('/api/waitlists/<waitlist_id>/join-email/', methods=['POST'])
def join_waitlist_email(waitlist_id):
    """Join waitlist via email (no auth). Sends verification link. For embed widget."""
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    Layer.query.get_or_404(waitlist.layer_id)

    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    message = (data.get('message') or '').strip()
    source = data.get('source', 'embed')
    source_url = data.get('source_url', '')

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'Please enter a valid email address'}), 400

    now = datetime.utcnow()
    if now < waitlist.start_date:
        return jsonify({'error': 'Waitlist has not started yet'}), 400
    if waitlist.closing_date and now >= waitlist.closing_date:
        return jsonify({'error': 'Waitlist is closed'}), 400

    user_count = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, left_at=None).count()
    email_count = WaitlistEmailSignup.query.filter_by(waitlist_id=waitlist_id, left_at=None).filter(WaitlistEmailSignup.verified_at.isnot(None)).count()
    total = user_count + email_count
    try:
        max_val = int(waitlist.max_number) if waitlist.max_number not in (None, '') else None
    except (ValueError, TypeError):
        max_val = None
    if max_val is not None and total >= max_val:
        return jsonify({'error': 'Waitlist is full'}), 400

    existing = WaitlistEmailSignup.query.filter_by(waitlist_id=waitlist_id, email=email, left_at=None).first()
    if existing and existing.verified_at:
        return jsonify({'error': 'This email is already on the waitlist'}), 400

    token = secrets.token_urlsafe(32)
    scheme = 'https' if (request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https') else 'http'
    base = f"{scheme}://{request.host}"
    confirm_url = f"{base}/waitlist/confirm/{token}"

    if existing:
        existing.verification_token = token
        existing.message = message or existing.message
        existing.source = source
        existing.source_url = source_url
        db.session.commit()
        signup = existing
    else:
        position = total + 1
        signup = WaitlistEmailSignup(
            waitlist_id=waitlist_id,
            email=email,
            message=message,
            verification_token=token,
            position=position,
            source=source,
            source_url=source_url,
        )
        db.session.add(signup)
        db.session.commit()

    email_sent = _send_waitlist_verification_email(signup, waitlist, confirm_url)
    if not email_sent:
        is_dev = current_app.config.get('IS_DEVELOPMENT', False)
        if is_dev and not os.environ.get('RESEND_API_KEY', '').strip():
            signup.verified_at = datetime.utcnow()
            signup.verification_token = None
            db.session.commit()
            return jsonify({
                'message': 'joined',
                'info': 'You\'re on the list! (Dev mode: email verification skipped)',
                'position': signup.position,
            }), 201
        return jsonify({'error': 'Failed to send verification email. Please try again.'}), 500

    return jsonify({
        'message': 'verification_sent',
        'info': 'We have sent an email to confirm your place. Please check your inbox and click the link to confirm.',
    }), 201


@bp.route('/waitlist/confirm/<token>')
def waitlist_confirm(token):
    """Confirm email signup via link. Renders success page."""
    signup = WaitlistEmailSignup.query.filter_by(verification_token=token, left_at=None).first()
    if not signup:
        return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invalid link</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Invalid or expired link</h2>
        <p>This confirmation link is invalid or has already been used.</p>
        <p><a href="/">Return to MLGH</a></p></body></html>""", 404

    signup.verified_at = datetime.utcnow()
    signup.verification_token = None
    waitlist = Waitlist.query.get_or_404(signup.waitlist_id)
    emit_event('waitlist_joined', actor_type='email', actor_id=None,
               subject_type='waitlist', subject_id=str(signup.waitlist_id), layer_id=waitlist.layer_id,
               payload={'waitlist_name': waitlist.name, 'position': signup.position})
    db.session.commit()
    project = Layer.query.get_or_404(waitlist.layer_id)

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>You're on the list!</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:500px;margin:40px auto;padding:24px;background:#f7f9fa;">
<h1 style="color:#00ba7c;">You're on the list!</h1>
<p>Your place on <strong>{waitlist.name}</strong> has been confirmed.</p>
<p>We'll be in touch. In the meantime, you can <a href="/layers/{project.slug}/">visit the project</a>.</p>
<p><a href="/" style="color:#1d9bf0;">Return to MLGH</a></p>
</body></html>""", 200


@bp.route('/api/waitlists/<waitlist_id>/join/', methods=['POST'])
@require_auth
def join_waitlist(waitlist_id):
    """Join waitlist. If referred and not on project, add to project. Optional message."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)

    now = datetime.utcnow()
    if now < waitlist.start_date:
        return jsonify({'error': 'Waitlist has not started yet'}), 400
    if waitlist.closing_date and now >= waitlist.closing_date:
        return jsonify({'error': 'Waitlist is closed'}), 400
    count = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, left_at=None).count()
    try:
        max_val = int(waitlist.max_number) if waitlist.max_number not in (None, '') else None
    except (ValueError, TypeError):
        max_val = None
    if max_val is not None and count >= max_val:
        return jsonify({'error': 'Waitlist is full'}), 400

    existing = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, user_id=current_user['id']).first()
    if existing:
        if existing.left_at:
            existing.left_at = None
            existing.position = count + 1
            existing.message = (request.get_json() or {}).get('message', existing.message)
            existing.referred_by_id = None
            existing.referral_code = None
            db.session.commit()
        else:
            return jsonify({'error': 'Already on waitlist'}), 400
    else:
        data = request.get_json() or {}
        message = data.get('message', '')
        referral_code = data.get('referral_code')
        source = data.get('source')
        source_url = data.get('source_url')
        referred_by_id = None
        if referral_code:
            referrer = User.query.filter_by(referral_code=referral_code).first()
            if referrer and referrer.id != current_user['id']:
                referred_by_id = referrer.id
                pm = LayerMember.query.filter_by(layer_id=project.id, user_id=current_user['id'], status='active').first()
                if not pm:
                    pm = LayerMember(layer_id=project.id, user_id=current_user['id'], referred_by_id=referred_by_id, referral_code=referral_code, role='contributor')
                    db.session.add(pm)

        entry = WaitlistEntry(waitlist_id=waitlist_id, user_id=current_user['id'], message=message, position=count + 1, referred_by_id=referred_by_id, referral_code=referral_code, source=source, source_url=source_url)
        db.session.add(entry)
        emit_event('waitlist_joined', actor_type='user', actor_id=current_user['id'],
                   subject_type='waitlist', subject_id=str(waitlist_id), layer_id=waitlist.layer_id,
                   payload={'waitlist_name': waitlist.name, 'position': count + 1})
        db.session.commit()

    entry = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, user_id=current_user['id'], left_at=None).first()
    return jsonify({'entry': {'position': entry.position, 'joined_at': entry.joined_at.isoformat()}, 'waitlist': waitlist.to_dict()}), 201


@bp.route('/api/waitlists/<waitlist_id>/leave/', methods=['POST'])
@require_auth
def leave_waitlist(waitlist_id):
    """Leave waitlist."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    entry = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, user_id=current_user['id'], left_at=None).first()
    if not entry:
        return jsonify({'error': 'Not on waitlist'}), 404
    entry.left_at = datetime.utcnow()
    emit_event('waitlist_left', actor_type='user', actor_id=current_user['id'],
               subject_type='waitlist', subject_id=str(waitlist_id), layer_id=waitlist.layer_id,
               payload={'waitlist_name': waitlist.name})
    db.session.commit()
    return jsonify({'message': 'Left waitlist'}), 200


@bp.route('/api/waitlists/<waitlist_id>/milestones/', methods=['GET'])
def list_waitlist_milestones(waitlist_id):
    """List milestones for a waitlist."""
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    ms = waitlist.milestone_list.order_by(WaitlistMilestone.threshold).all()
    return jsonify({'milestones': [{'id': m.id, 'title': m.title, 'description': m.description, 'threshold': m.threshold, 'action_type': m.action_type} for m in ms]}), 200


@bp.route('/api/waitlists/<waitlist_id>/milestones/', methods=['POST'])
@require_auth
def create_waitlist_milestone(waitlist_id):
    """Add milestone - project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can add milestones'}), 403

    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    threshold = data.get('threshold', 0)
    try:
        threshold = int(threshold)
    except (TypeError, ValueError):
        threshold = 0

    m = WaitlistMilestone(waitlist_id=waitlist_id, title=title, description=data.get('description'), threshold=threshold, action_type=data.get('action_type'), action_payload=data.get('action_payload'))
    db.session.add(m)
    db.session.commit()
    return jsonify({'milestone': {'id': m.id, 'title': m.title, 'description': m.description, 'threshold': m.threshold, 'action_type': m.action_type}}), 201


@bp.route('/api/waitlists/<waitlist_id>/milestones/<milestone_id>/', methods=['DELETE'])
@require_auth
def delete_waitlist_milestone(waitlist_id, milestone_id):
    """Delete milestone - project admin only."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project admins can delete milestones'}), 403
    m = WaitlistMilestone.query.filter_by(id=milestone_id, waitlist_id=waitlist_id).first_or_404()
    db.session.delete(m)
    db.session.commit()
    return jsonify({'message': 'Milestone deleted'}), 200


# ============================================================================
# Embed widget (static JS, waitlist widget, builder)
# ============================================================================

@bp.route('/embed/static/embed-widget.js')
def embed_widget_js():
    """Serve embed widget JS - external file avoids inline script parsing issues."""
    return EMBED_WIDGET_JS, 200, {'Content-Type': 'application/javascript; charset=utf-8'}


@bp.route('/embed/static/embed-auth.js')
def embed_auth_js():
    """Web3Auth for embed - modal inline, no popup/tab."""
    return EMBED_AUTH_JS, 200, {'Content-Type': 'application/javascript; charset=utf-8'}


@bp.route('/embed/waitlist/<waitlist_id>/')
def embed_waitlist_widget(waitlist_id):
    """Embeddable waitlist widget - customizable via query params. Compact layout."""
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)

    if not waitlist.public and not waitlist.active:
        return "Waitlist not available", 404

    user_count = WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, left_at=None).count()
    email_count = WaitlistEmailSignup.query.filter_by(waitlist_id=waitlist_id, left_at=None).filter(WaitlistEmailSignup.verified_at.isnot(None)).count()
    entry_count = user_count + email_count
    now = datetime.utcnow()
    is_upcoming = now < waitlist.start_date
    is_closed = waitlist.archived or not waitlist.active or (waitlist.closing_date and now >= waitlist.closing_date)
    try:
        max_val = int(waitlist.max_number) if waitlist.max_number not in (None, '') else None
    except (ValueError, TypeError):
        max_val = None
    is_full = max_val is not None and entry_count >= max_val
    base_url = request.url_root.rstrip('/')
    opts = _embed_widget_params()
    btn_esc = html_mod.escape(opts['btn'])
    msg_ph_esc = html_mod.escape(opts['msg_placeholder'])
    fg_esc = html_mod.escape(opts['fg'])
    bg_esc = html_mod.escape(opts['bg'])
    footer_link_style = f"color:{bg_esc}"
    footer_css_rule = ".wl-footer a{" + footer_link_style + "}"
    show_desc = opts['desc'] and (waitlist.description or '')
    show_count = opts['count']
    show_spots = opts['spots'] and max_val is not None
    msg_mode = opts['msg']
    show_msg = msg_mode in ('allow', 'require')
    msg_required = msg_mode == 'require'
    desc_html = f'<p class="wl-desc">{html_mod.escape(waitlist.description or "")}</p>' if show_desc else ''
    stats_parts = []
    if show_count:
        stats_parts.append(f'<div class="wl-stat"><span class="wl-stat-val" id="entry-count">{entry_count}</span><span class="wl-stat-lbl">Members</span></div>')
    if show_spots and max_val is not None:
        stats_parts.append(f'<div class="wl-stat"><span class="wl-stat-val">{max_val - entry_count}</span><span class="wl-stat-lbl">Spots Left</span></div>')
    stats_html = f'<div class="wl-stats">{"".join(stats_parts)}</div>' if stats_parts else ''
    status_msg = ''
    if is_upcoming:
        status_msg = f'<p class="wl-status">Opens {waitlist.start_date.strftime("%B %d, %Y")}</p>'
    elif is_closed:
        status_msg = '<p class="wl-status">This waitlist is closed</p>'
    elif is_full:
        status_msg = '<p class="wl-status">Waitlist is full</p>'
    btn_disabled = ' disabled' if (is_upcoming or is_closed or is_full) else ''
    email_html = f'<div class="wl-email-wrap"><input type="email" id="wl-email" class="wl-email" placeholder="Your email" required></div>'
    msg_html = ''
    if show_msg:
        req_attr = ' required' if msg_required else ''
        msg_html = f'<div class="wl-msg-wrap"><textarea id="wl-msg" class="wl-msg" rows="3" placeholder="{msg_ph_esc}"{req_attr}></textarea></div>'
    cfg = {'waitlistId': waitlist_id, 'msgRequired': msg_required, 'btnLabel': btn_esc}
    cfg_js = json.dumps(cfg).replace('</', '<\\u002F')
    widget_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
.wl-widget{max-width:380px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:13px}
.wl-header{padding:6px 10px;border-radius:6px 6px 0 0;color:%s;background:%s}
.wl-header h3{margin:0;font-size:1rem;font-weight:600}
.wl-body{padding:6px 10px;background:#fff;border:1px solid #e1e8ed;border-top:none;border-radius:0 0 6px 6px}
.wl-desc{margin:2px 0 0 0;font-size:0.8rem;opacity:0.95;line-height:1.3}
.wl-stats{display:flex;gap:12px;margin:4px 0;padding:4px 0;border-bottom:1px solid #eee}
.wl-stat{text-align:center}
.wl-stat-val{font-weight:700;font-size:1rem;display:block}
.wl-stat-lbl{font-size:0.7rem;color:#657786}
.wl-email-wrap,.wl-msg-wrap{margin:4px 0}
.wl-email,.wl-msg{width:100%%;padding:4px 6px;font-size:0.85rem;border:1px solid #ddd;border-radius:4px;box-sizing:border-box}
.wl-msg{resize:vertical}
.wl-msg::placeholder,.wl-email::placeholder{color:#999}
.wl-btn{width:100%%;padding:6px 10px;font-size:0.9rem;font-weight:600;border:none;border-radius:4px;cursor:pointer;color:%s;background:%s}
.wl-btn:hover:not(:disabled){opacity:0.9}
.wl-btn:disabled{opacity:0.6;cursor:not-allowed}
.wl-status{margin:0;font-size:0.8rem;color:#657786;text-align:center}
.wl-success{background:#00ba7c;color:#fff;padding:6px;border-radius:4px;margin-top:4px;font-size:0.85rem;text-align:center}
.wl-error{background:#f4212e;color:#fff;padding:6px;border-radius:4px;margin-top:4px;font-size:0.85rem;text-align:center}
.wl-footer{text-align:center;margin-top:4px;font-size:0.7rem;color:#999}
%s
</style>
</head>
<body>
<div class="wl-widget">
<div class="wl-header"><h3>%s</h3>%s</div>
<div class="wl-body">
%s
<div id="join-section">%s
%s
%s
<button class="wl-btn" onclick="joinWaitlist()" id="join-btn"%s>%s</button>
</div>
<div id="message-area"></div>
<div class="wl-footer">Powered by <a href="%s" target="_blank">MLGH</a></div>
</div>
</div>
<script>window.__WL_CFG=%s;</script>
<script src="/embed/static/embed-widget.js"></script>
</body>
</html>""" % (
        fg_esc, bg_esc, fg_esc, bg_esc, footer_css_rule,
        html_mod.escape(waitlist.name), desc_html, stats_html, status_msg, email_html, msg_html, btn_disabled, btn_esc,
        base_url, cfg_js
    )
    return widget_html, 200, {'Content-Type': 'text/html; charset=utf-8', 'X-Frame-Options': 'ALLOWALL'}


@bp.route('/embed/waitlist/<waitlist_id>/build/')
@require_auth
def embed_waitlist_builder(waitlist_id):
    """Embed builder page: configure options and preview. Project admin only."""
    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    current_user = get_current_user()
    if not current_user or not is_layer_admin(project, current_user):
        return "Permission denied", 403
    scheme = 'https' if (request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https') else 'http'
    proj_name_esc = html_mod.escape(project.name or '')
    wl_name_esc = html_mod.escape(waitlist.name or '')
    content = f"""
<div class="container-fluid py-2 px-3">
    <nav aria-label="breadcrumb"><ol class="breadcrumb py-0 mb-2 small">
        <li class="breadcrumb-item"><a href="/layers/">Layers</a></li>
        <li class="breadcrumb-item"><a href="/layers/{project.slug}/">{proj_name_esc}</a></li>
        <li class="breadcrumb-item"><a href="/waitlists/{waitlist_id}/">{wl_name_esc}</a></li>
        <li class="breadcrumb-item active">Customize Embed</li>
    </ol></nav>

    <div class="row g-3">
        <div class="col-lg-4 col-md-5">
            <div class="card mb-3">
                <div class="card-header"><h6 class="mb-0">Display Options</h6></div>
                <div class="card-body">
                    <div class="row g-2">
                        <div class="col-12">
                            <p class="text-muted small mb-2">Choose what to show in the widget:</p>
                            <div class="d-flex flex-wrap gap-3">
                                <div class="form-check mb-0">
                                    <input class="form-check-input" type="checkbox" id="opt-desc" checked>
                                    <label class="form-check-label" for="opt-desc">Description</label>
                                </div>
                                <div class="form-check mb-0">
                                    <input class="form-check-input" type="checkbox" id="opt-count" checked>
                                    <label class="form-check-label" for="opt-count">Member count</label>
                                </div>
                                <div class="form-check mb-0">
                                    <input class="form-check-input" type="checkbox" id="opt-spots" checked>
                                    <label class="form-check-label" for="opt-spots">Spots remaining</label>
                                </div>
                            </div>
                        </div>
                        <div class="col-12"><hr class="my-1"></div>
                        <div class="col-12">
                            <label class="form-label fw-semibold mb-1">Message field</label>
                            <select class="form-select form-select-sm mb-2" id="opt-msg">
                                <option value="none">No message field</option>
                                <option value="allow">Optional message</option>
                                <option value="require">Required message</option>
                            </select>
                            <div id="msg-placeholder-wrap" style="display:none">
                                <label class="form-label small mb-1">Textarea prompt / placeholder text</label>
                                <input type="text" class="form-control form-control-sm" id="opt-msg-placeholder" value="Add a message (optional)" placeholder="e.g. Why do you want to join?">
                                <div class="form-text">This text appears inside the textarea as a hint to the user.</div>
                            </div>
                        </div>
                        <div class="col-12"><hr class="my-1"></div>
                        <div class="col-12">
                            <label class="form-label fw-semibold mb-1">Button label</label>
                            <input type="text" class="form-control form-control-sm" id="opt-btn" value="Join Waitlist">
                        </div>
                        <div class="col-6">
                            <label class="form-label small mb-1">Background color</label>
                            <div class="d-flex align-items-center gap-2">
                                <input type="color" class="form-control form-control-color" id="opt-bg" value="#667eea" style="width:40px;height:32px;padding:2px;">
                                <input type="text" class="form-control form-control-sm font-monospace" id="opt-bg-hex" value="#667eea" maxlength="7" style="width:80px;">
                            </div>
                        </div>
                        <div class="col-6">
                            <label class="form-label small mb-1">Text / button color</label>
                            <div class="d-flex align-items-center gap-2">
                                <input type="color" class="form-control form-control-color" id="opt-fg" value="#ffffff" style="width:40px;height:32px;padding:2px;">
                                <input type="text" class="form-control form-control-sm font-monospace" id="opt-fg-hex" value="#ffffff" maxlength="7" style="width:80px;">
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><h6 class="mb-0">Embed Code</h6></div>
                <div class="card-body">
                    <textarea class="form-control form-control-sm font-monospace" id="embed-code" rows="3" readonly style="font-size:11px;"></textarea>
                    <button class="btn btn-sm btn-outline-primary mt-2 w-100" id="copy-btn" onclick="copyCode()">Copy to Clipboard</button>
                </div>
            </div>
        </div>
        <div class="col-lg-8 col-md-7">
            <div class="card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Live Preview</h6>
                    <span class="badge bg-secondary" id="preview-status">Loading...</span>
                </div>
                <div class="card-body d-flex justify-content-center align-items-start pt-3" style="background: repeating-linear-gradient(45deg,#f0f0f0,#f0f0f0 10px,#fafafa 10px,#fafafa 20px);">
                    <iframe id="embed-preview" style="width:100%%;max-width:420px;height:300px;border:none;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.15);" sandbox="allow-scripts allow-same-origin allow-forms"></iframe>
                </div>
                <div class="card-footer text-muted small">Preview updates automatically as you change options.</div>
            </div>
        </div>
    </div>
</div>

<script>
const EMBED_BASE = '{scheme}://' + location.host + '/embed/waitlist/{waitlist_id}/';
let debounceTimer = null;
function buildParams() {{
    const desc = document.getElementById('opt-desc').checked ? '1' : '0';
    const count = document.getElementById('opt-count').checked ? '1' : '0';
    const spots = document.getElementById('opt-spots').checked ? '1' : '0';
    const msg = document.getElementById('opt-msg').value;
    const ph = encodeURIComponent(document.getElementById('opt-msg-placeholder').value || '');
    const btn = encodeURIComponent(document.getElementById('opt-btn').value || 'Join Waitlist');
    const fg = encodeURIComponent(document.getElementById('opt-fg').value);
    const bg = encodeURIComponent(document.getElementById('opt-bg').value);
    return `desc=${{desc}}&count=${{count}}&spots=${{spots}}&msg=${{msg}}&msg_placeholder=${{ph}}&btn=${{btn}}&fg=${{fg}}&bg=${{bg}}`;
}}
function buildUrl() {{ return EMBED_BASE + '?' + buildParams(); }}
function refreshPreview() {{
    const url = buildUrl();
    const iframe = document.getElementById('embed-preview');
    document.getElementById('preview-status').textContent = 'Updating...';
    document.getElementById('preview-status').className = 'badge bg-warning text-dark';
    iframe.src = url;
    iframe.onload = () => {{ document.getElementById('preview-status').textContent = 'Live'; document.getElementById('preview-status').className = 'badge bg-success'; }};
    document.getElementById('embed-code').value = '<iframe src="' + url + '" width="100%" height="280" frameborder="0" style="border:none;border-radius:6px;display:block;"></iframe>';
}}
function scheduleUpdate(immediate) {{
    clearTimeout(debounceTimer);
    if (immediate) refreshPreview();
    else debounceTimer = setTimeout(refreshPreview, 220);
}}
function updateMsgPlaceholderVisibility() {{
    const show = document.getElementById('opt-msg').value !== 'none';
    document.getElementById('msg-placeholder-wrap').style.display = show ? 'block' : 'none';
}}
['opt-desc','opt-count','opt-spots'].forEach(id => {{ document.getElementById(id)?.addEventListener('change', () => scheduleUpdate(true)); }});
document.getElementById('opt-msg')?.addEventListener('change', () => {{ updateMsgPlaceholderVisibility(); scheduleUpdate(true); }});
['opt-btn','opt-msg-placeholder'].forEach(id => {{ const el = document.getElementById(id); if(el) {{ el.addEventListener('input', () => scheduleUpdate(false)); el.addEventListener('change', () => scheduleUpdate(true)); }} }});
document.getElementById('opt-bg').addEventListener('input', () => {{ document.getElementById('opt-bg-hex').value = document.getElementById('opt-bg').value; scheduleUpdate(false); }});
document.getElementById('opt-bg').addEventListener('change', () => scheduleUpdate(true));
document.getElementById('opt-bg-hex').addEventListener('input', () => {{ const v = document.getElementById('opt-bg-hex').value.trim(); if(/^#[0-9a-fA-F]{{6}}$/.test(v)) {{ document.getElementById('opt-bg').value = v; scheduleUpdate(false); }} }});
document.getElementById('opt-fg').addEventListener('input', () => {{ document.getElementById('opt-fg-hex').value = document.getElementById('opt-fg').value; scheduleUpdate(false); }});
document.getElementById('opt-fg').addEventListener('change', () => scheduleUpdate(true));
document.getElementById('opt-fg-hex').addEventListener('input', () => {{ const v = document.getElementById('opt-fg-hex').value.trim(); if(/^#[0-9a-fA-F]{{6}}$/.test(v)) {{ document.getElementById('opt-fg').value = v; scheduleUpdate(false); }} }});
function copyCode() {{ navigator.clipboard.writeText(document.getElementById('embed-code').value).then(() => {{ const btn = document.getElementById('copy-btn'); btn.innerHTML = '✓ Copied!'; btn.classList.replace('btn-outline-primary','btn-success'); setTimeout(() => {{ btn.innerHTML = 'Copy to Clipboard'; btn.classList.replace('btn-success','btn-outline-primary'); }}, 2000); }}); }}
scheduleUpdate(true);
</script>
"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Embed: {html_mod.escape(waitlist.name or '')} - MLGH</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>body{{background:#0d1117;color:#c9d1d9;}} .card{{background:#161b22;border-color:#30363d;}} .card-header{{border-color:#30363d;}} .form-control,.form-select{{background:#0d1117;border-color:#30363d;color:#c9d1d9;}} .breadcrumb{{background:transparent;}} .breadcrumb-item a{{color:#58a6ff;}}</style>
</head>
<body class="p-3">
{content}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


def _get_page_imports():
    """Late imports for page routes."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/waitlists/<waitlist_id>/')
def waitlist_detail(waitlist_id):
    """Standalone waitlist detail page"""
    render_page, generate_user_menu = _get_page_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    waitlist = Waitlist.query.get_or_404(waitlist_id)
    project = Layer.query.get_or_404(waitlist.layer_id)
    is_admin = bool(current_user and is_layer_admin(project, current_user))

    if not waitlist.active and not is_admin:
        abort(404)

    is_admin_json = 'true' if is_admin else 'false'
    is_auth_json = 'true' if current_user else 'false'
    waitlist_id_js = json.dumps(str(waitlist_id))  # UUID must be quoted in JS
    project_slug_js = project.slug

    # Pre-compute conditional HTML blocks (can't use triple-quoted strings inside f-string expressions)
    entries_card_html = '<div class="card mb-4" id="entries-card"><div class="card-header"><i class="fas fa-users me-2"></i>Members</div><div class="card-body p-0" id="entries-body"><div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></div></div></div>' if is_admin else ''

    edit_modal_html = ''
    if is_admin:
        edit_modal_html = '''
    <div class="modal fade" id="editWaitlistModal" tabindex="-1">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-edit me-2"></i>Edit Waitlist</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div id="edit-alert"></div>
            <div class="row g-3">
              <div class="col-12">
                <label class="form-label fw-semibold">Name *</label>
                <input type="text" id="edit-name" class="form-control">
              </div>
              <div class="col-12">
                <label class="form-label fw-semibold">Description</label>
                <textarea id="edit-description" class="form-control" rows="3"></textarea>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">Max Spots</label>
                <input type="number" id="edit-max-number" class="form-control" min="0" placeholder="Unlimited">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">Start Date</label>
                <input type="datetime-local" id="edit-start-date" class="form-control">
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">Closing Date</label>
                <input type="datetime-local" id="edit-closing-date" class="form-control">
              </div>
              <div class="col-12">
                <div class="d-flex flex-wrap gap-4 mt-1">
                  <div class="form-check"><input class="form-check-input" type="checkbox" id="edit-active"><label class="form-check-label" for="edit-active">Active</label></div>
                  <div class="form-check"><input class="form-check-input" type="checkbox" id="edit-public"><label class="form-check-label" for="edit-public">Public</label></div>
                  <div class="form-check"><input class="form-check-input" type="checkbox" id="edit-archived"><label class="form-check-label" for="edit-archived">Archived</label></div>
                  <div class="form-check"><input class="form-check-input" type="checkbox" id="edit-referrals"><label class="form-check-label" for="edit-referrals">Enable Referrals</label></div>
                  <div class="form-check"><input class="form-check-input" type="checkbox" id="edit-milestones"><label class="form-check-label" for="edit-milestones">Enable Milestones</label></div>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary" onclick="saveWaitlistEdit()"><i class="fas fa-save me-1"></i>Save</button>
          </div>
        </div>
      </div>
    </div>'''

    add_ms_modal_html = ''
    if is_admin:
        add_ms_modal_html = '''
    <div class="modal fade" id="addMilestoneModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-flag me-2"></i>Add Milestone</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div id="ms-alert"></div>
            <div class="mb-3">
              <label class="form-label fw-semibold">Threshold (# of members)</label>
              <input type="number" id="ms-threshold" class="form-control" min="1" placeholder="e.g. 100">
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">Title *</label>
              <input type="text" id="ms-title" class="form-control" placeholder="Milestone title">
            </div>
            <div class="mb-3">
              <label class="form-label fw-semibold">Description</label>
              <textarea id="ms-description" class="form-control" rows="2" placeholder="Optional description"></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary" onclick="saveMilestone()"><i class="fas fa-plus me-1"></i>Add</button>
          </div>
        </div>
      </div>
    </div>'''

    content = f"""
    <div class="gh-page container mt-4">

      <!-- Breadcrumb -->
      <nav aria-label="breadcrumb" class="mb-3">
        <ol class="breadcrumb">
          <li class="breadcrumb-item"><a href="/waitlists/">Waitlists</a></li>
          <li class="breadcrumb-item"><a href="/layers/{project.slug}/">{project.name}</a></li>
          <li class="breadcrumb-item active" id="breadcrumb-name">{waitlist.name}</li>
        </ol>
      </nav>

      <!-- Header card -->
      <div class="card mb-4" id="waitlist-header-card">
        <div class="card-body">
          <div class="d-flex flex-wrap justify-content-between align-items-start gap-3">
            <div>
              <h1 class="h3 mb-1" id="wl-name">{waitlist.name}</h1>
              <p class="text-muted mb-2">
                <i class="fas fa-layer-group me-1"></i>
                <a href="/layers/{project.slug}/">{project.name}</a>
              </p>
              <div id="wl-badges" class="mb-2"></div>
            </div>
            <div class="text-end">
              <div id="wl-counts" class="mb-2"></div>
              {'<button class="btn btn-outline-primary btn-sm" onclick="openEditModal()"><i class="fas fa-edit me-1"></i>Edit Waitlist</button>' if is_admin else ''}
            </div>
          </div>
          <p id="wl-description" class="mt-2 mb-0"></p>
        </div>
      </div>

      <div class="row">
        <!-- Left column: embed widget + milestones -->
        <div class="col-lg-7">

          <!-- Embed preview -->
          <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
              <span><i class="fas fa-window-maximize me-2"></i>Live Widget Preview</span>
              <a href="/embed/waitlist/{waitlist_id}/build/" class="btn btn-outline-secondary btn-sm" target="_blank">
                <i class="fas fa-sliders-h me-1"></i>Customize Embed
              </a>
            </div>
            <div class="card-body p-3">
              <iframe src="/embed/waitlist/{waitlist_id}/" style="width:100%;height:280px;border:none;border-radius:8px;" loading="lazy"></iframe>
            </div>
          </div>

          <!-- Milestones -->
          <div class="card mb-4" id="milestones-card">
            <div class="card-header d-flex justify-content-between align-items-center">
              <span><i class="fas fa-flag me-2"></i>Milestones</span>
              {'<button class="btn btn-primary btn-sm" onclick="openAddMilestoneModal()"><i class="fas fa-plus me-1"></i>Add Milestone</button>' if is_admin else ''}
            </div>
            <div class="card-body" id="milestones-body">
              <div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></div>
            </div>
          </div>

        </div>

        <!-- Right column: join action + entries -->
        <div class="col-lg-5">

          <!-- Join / status action card -->
          <div class="card mb-4">
            <div class="card-body" id="action-body">
              <div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></div>
            </div>
          </div>

          <!-- Entries (admin only) -->
          {entries_card_html}

        </div>
      </div>
    </div>

    <!-- Edit Waitlist Modal (admin only) -->
    {edit_modal_html}

    <!-- Add Milestone Modal (admin only) -->
    {add_ms_modal_html}

    <!-- Join Waitlist Modal -->
    <div class="modal fade" id="joinWaitlistModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title"><i class="fas fa-list-alt me-2"></i>Join Waitlist</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <p>You're joining <strong id="join-wl-name"></strong>.</p>
            <div class="mb-3">
              <label class="form-label">Message (optional)</label>
              <textarea id="join-message" class="form-control" rows="2" placeholder="Add a note..."></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
            <button class="btn btn-primary" onclick="submitJoin()">Join</button>
          </div>
        </div>
      </div>
    </div>

    <script>
    const WAITLIST_ID = {waitlist_id_js};
    const PROJECT_SLUG = '{project_slug_js}';
    const IS_ADMIN = {is_admin_json};
    const IS_AUTH = {is_auth_json};
    let wlData = null;

    function esc(s) {{
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(new RegExp('<','g'),'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}

    function toLocalInput(isoStr) {{
        if (!isoStr) return '';
        const d = new Date(isoStr);
        const pad = n => String(n).padStart(2,'0');
        return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    }}

    async function loadWaitlist() {{
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/`);
            if (!res.ok) {{ document.getElementById('waitlist-header-card').innerHTML = '<div class="card-body"><div class="alert alert-danger">Waitlist not found.</div></div>'; return; }}
            wlData = await res.json();
            renderHeader();
            renderAction();
            renderMilestones(wlData.milestones || []);
            if (IS_ADMIN) loadEntries();
        }} catch(e) {{
            console.error(e);
        }}
    }}

    function renderHeader() {{
        const w = wlData;
        document.getElementById('wl-name').textContent = w.name || '';
        document.getElementById('breadcrumb-name').textContent = w.name || '';
        document.getElementById('wl-description').textContent = w.description || '';

        const now = new Date();
        const startDate = w.start_date ? new Date(w.start_date) : null;
        const closingDate = w.closing_date ? new Date(w.closing_date) : null;
        const isFull = w.max_number && w.count >= w.max_number;
        let statusHtml = '';
        if (!w.active || w.archived) {{
            statusHtml = '<span class="badge bg-secondary">Closed</span>';
        }} else if (startDate && now < startDate) {{
            statusHtml = '<span class="badge bg-info">Upcoming</span>';
        }} else if (isFull) {{
            statusHtml = '<span class="badge bg-warning text-dark">Full</span>';
        }} else if (closingDate && now > closingDate) {{
            statusHtml = '<span class="badge bg-secondary">Closed</span>';
        }} else {{
            statusHtml = '<span class="badge bg-success">Active</span>';
        }}
        if (w.referrals) statusHtml += ' <span class="badge bg-primary"><i class="fas fa-users"></i> Referrals</span>';
        if (w.milestones) statusHtml += ' <span class="badge bg-info"><i class="fas fa-flag"></i> Milestones</span>';
        document.getElementById('wl-badges').innerHTML = statusHtml;

        let countHtml = '<span class="fw-bold fs-5">' + (w.count || 0) + '</span> <span class="text-muted">member' + ((w.count||0)!==1?'s':'') + '</span>';
        if (w.max_number) {{
            const remaining = w.max_number - (w.count || 0);
            countHtml += '<br><small class="text-muted">' + remaining + ' spot' + (remaining!==1?'s':'') + ' remaining</small>';
        }}
        document.getElementById('wl-counts').innerHTML = countHtml;
    }}

    function renderAction() {{
        const w = wlData;
        const el = document.getElementById('action-body');
        const now = new Date();
        const startDate = w.start_date ? new Date(w.start_date) : null;
        const closingDate = w.closing_date ? new Date(w.closing_date) : null;
        const isFull = w.max_number && w.count >= w.max_number;
        const started = !startDate || now >= startDate;
        const closed = (!w.active || w.archived) || (closingDate && now > closingDate) || isFull;

        let html = '';
        if (w.my_entry) {{
            html += '<div class="text-center py-3">';
            html += '<span class="badge bg-success fs-6 mb-2"><i class="fas fa-check-circle me-1"></i>You&#39;re on this waitlist</span><br>';
            html += '<span class="text-muted">Position #' + w.my_entry.position + '</span><br>';
            if (w.referral_url) {{
                html += '<div class="mt-3"><p class="small text-muted mb-1">Your referral link:</p><div class="input-group input-group-sm"><input type="text" class="form-control" value="' + esc(w.referral_url) + '" id="ref-link-input" readonly><button class="btn btn-outline-secondary" onclick="copyRefLink()"><i class="fas fa-copy"></i></button></div></div>';
            }}
            html += '<button class="btn btn-outline-danger btn-sm mt-3" onclick="leaveWaitlist()"><i class="fas fa-sign-out-alt me-1"></i>Leave Waitlist</button>';
            html += '</div>';
        }} else if (!IS_AUTH) {{
            html = '<div class="text-center py-3"><p class="mb-3">Sign in to join this waitlist.</p><a href="/login/" class="btn btn-primary">Sign In</a></div>';
        }} else if (!started) {{
            html = '<div class="text-center py-3"><span class="badge bg-info fs-6">Opens ' + (startDate ? startDate.toLocaleDateString() : '') + '</span></div>';
        }} else if (isFull) {{
            html = '<div class="text-center py-3"><span class="badge bg-warning text-dark fs-6">Waitlist Full</span></div>';
        }} else if (closed) {{
            html = '<div class="text-center py-3"><span class="badge bg-secondary fs-6">Waitlist Closed</span></div>';
        }} else {{
            html = '<div class="text-center py-3"><button class="btn btn-primary btn-lg" onclick="showJoinModal()"><i class="fas fa-list-alt me-2"></i>Join Waitlist</button></div>';
        }}
        el.innerHTML = html;
    }}

    function renderMilestones(milestones) {{
        const el = document.getElementById('milestones-body');
        if (!milestones || milestones.length === 0) {{
            el.innerHTML = '<p class="text-muted p-3 mb-0">No milestones yet.</p>';
            return;
        }}
        let html = '<ul class="list-group list-group-flush">';
        milestones.forEach(m => {{
            html += '<li class="list-group-item d-flex justify-content-between align-items-start">';
            html += '<div><span class="badge bg-secondary me-2">' + m.threshold + '</span>';
            html += '<strong>' + esc(m.title) + '</strong>';
            if (m.description) html += '<br><small class="text-muted">' + esc(m.description) + '</small>';
            html += '</div>';
            if (IS_ADMIN) {{
                html += '<button class="btn btn-outline-danger btn-sm" data-milestone-id="' + esc(m.id || '') + '" onclick="deleteMilestone(this.dataset.milestoneId)"><i class="fas fa-trash"></i></button>';
            }}
            html += '</li>';
        }});
        html += '</ul>';
        el.innerHTML = html;
    }}

    async function loadEntries(page) {{
        page = page || 1;
        const el = document.getElementById('entries-body');
        if (!el) return;
        el.innerHTML = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div></div>';
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/entries/`);
            const data = await res.json();
            const entries = data.entries || [];
            if (entries.length === 0) {{
                el.innerHTML = '<p class="text-muted p-3 mb-0">No members yet.</p>';
                return;
            }}
            const pageSize = 25;
            const totalPages = Math.ceil(entries.length / pageSize);
            const start = (page - 1) * pageSize;
            const pageEntries = entries.slice(start, start + pageSize);

            let html = '<div class="table-responsive"><table class="table table-sm table-hover mb-0"><thead><tr><th>#</th><th>Member</th><th>Referred By</th><th>Joined</th></tr></thead><tbody>';
            pageEntries.forEach(e => {{
                html += '<tr><td>' + e.position + '</td>';
                if (e.type === 'email') {{
                    html += '<td><span class="text-muted">' + esc(e.email) + '</span>' + (e.message ? ' <small class="text-muted">' + esc(e.message) + '</small>' : '') + '</td>';
                }} else {{
                    html += '<td><a href="/profile/' + esc(e.username) + '/">' + esc(e.display_name || e.username) + '</a></td>';
                }}
                html += '<td>' + (e.referred_by ? esc(e.referred_by) : '—') + '</td>';
                html += '<td>' + (e.joined_at ? new Date(e.joined_at).toLocaleDateString() : '—') + '</td>';
                html += '</tr>';
            }});
            html += '</tbody></table></div>';
            if (totalPages > 1) {{
                html += '<div class="d-flex justify-content-between align-items-center p-2">';
                html += '<small class="text-muted">Showing ' + (start+1) + '–' + Math.min(start+pageSize, entries.length) + ' of ' + entries.length + '</small>';
                html += '<div class="btn-group btn-group-sm">';
                if (page > 1) html += '<button class="btn btn-outline-secondary" onclick="loadEntries(' + (page-1) + ')">Prev</button>';
                if (page < totalPages) html += '<button class="btn btn-outline-secondary" onclick="loadEntries(' + (page+1) + ')">Next</button>';
                html += '</div></div>';
            }}
            el.innerHTML = html;
        }} catch(e) {{
            el.innerHTML = '<div class="alert alert-danger m-2">Error loading entries</div>';
        }}
    }}

    /* ---- Join / Leave ---- */
    function showJoinModal() {{
        document.getElementById('join-wl-name').textContent = wlData ? wlData.name : '';
        document.getElementById('join-message').value = '';
        new bootstrap.Modal(document.getElementById('joinWaitlistModal')).show();
    }}

    async function submitJoin() {{
        const msg = document.getElementById('join-message').value;
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/join/`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{message: msg}})
            }});
            const data = await res.json();
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('joinWaitlistModal')).hide();
                loadWaitlist();
            }} else {{
                alert(data.error || 'Failed to join');
            }}
        }} catch(e) {{ alert('Failed to join'); }}
    }}

    async function leaveWaitlist() {{
        if (!confirm('Leave this waitlist?')) return;
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/leave/`, {{method: 'POST'}});
            if (res.ok) loadWaitlist();
            else {{ const d = await res.json(); alert(d.error || 'Failed to leave'); }}
        }} catch(e) {{ alert('Failed to leave'); }}
    }}

    function copyRefLink() {{
        const el = document.getElementById('ref-link-input');
        if (el) {{ el.select(); document.execCommand('copy'); }}
    }}

    /* ---- Admin: Edit Waitlist ---- */
    function openEditModal() {{
        if (!wlData) return;
        const w = wlData;
        document.getElementById('edit-name').value = w.name || '';
        document.getElementById('edit-description').value = w.description || '';
        document.getElementById('edit-max-number').value = w.max_number || '';
        document.getElementById('edit-start-date').value = toLocalInput(w.start_date);
        document.getElementById('edit-closing-date').value = toLocalInput(w.closing_date);
        document.getElementById('edit-active').checked = !!w.active;
        document.getElementById('edit-public').checked = !!w.public;
        document.getElementById('edit-archived').checked = !!w.archived;
        document.getElementById('edit-referrals').checked = !!w.referrals;
        document.getElementById('edit-milestones').checked = !!w.milestones;
        document.getElementById('edit-alert').innerHTML = '';
        new bootstrap.Modal(document.getElementById('editWaitlistModal')).show();
    }}

    async function saveWaitlistEdit() {{
        const name = document.getElementById('edit-name').value.trim();
        if (!name) {{ document.getElementById('edit-alert').innerHTML = '<div class="alert alert-danger">Name is required.</div>'; return; }}
        const maxNum = document.getElementById('edit-max-number').value;
        const startVal = document.getElementById('edit-start-date').value;
        const closingVal = document.getElementById('edit-closing-date').value;
        const payload = {{
            name,
            description: document.getElementById('edit-description').value,
            max_number: maxNum ? parseInt(maxNum) : null,
            start_date: startVal || null,
            closing_date: closingVal || null,
            active: document.getElementById('edit-active').checked,
            public: document.getElementById('edit-public').checked,
            archived: document.getElementById('edit-archived').checked,
            referrals: document.getElementById('edit-referrals').checked,
            milestones: document.getElementById('edit-milestones').checked,
        }};
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/`, {{
                method: 'PATCH',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(payload)
            }});
            const data = await res.json();
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('editWaitlistModal')).hide();
                loadWaitlist();
            }} else {{
                document.getElementById('edit-alert').innerHTML = '<div class="alert alert-danger">' + esc(data.error || 'Save failed') + '</div>';
            }}
        }} catch(e) {{
            document.getElementById('edit-alert').innerHTML = '<div class="alert alert-danger">Network error</div>';
        }}
    }}

    /* ---- Admin: Milestones ---- */
    function openAddMilestoneModal() {{
        document.getElementById('ms-threshold').value = '';
        document.getElementById('ms-title').value = '';
        document.getElementById('ms-description').value = '';
        document.getElementById('ms-alert').innerHTML = '';
        new bootstrap.Modal(document.getElementById('addMilestoneModal')).show();
    }}

    async function saveMilestone() {{
        const title = document.getElementById('ms-title').value.trim();
        if (!title) {{ document.getElementById('ms-alert').innerHTML = '<div class="alert alert-danger">Title is required.</div>'; return; }}
        const threshold = parseInt(document.getElementById('ms-threshold').value) || 0;
        const description = document.getElementById('ms-description').value.trim();
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/milestones/`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{title, threshold, description}})
            }});
            const data = await res.json();
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('addMilestoneModal')).hide();
                loadWaitlist();
            }} else {{
                document.getElementById('ms-alert').innerHTML = '<div class="alert alert-danger">' + esc(data.error || 'Failed to add') + '</div>';
            }}
        }} catch(e) {{
            document.getElementById('ms-alert').innerHTML = '<div class="alert alert-danger">Network error</div>';
        }}
    }}

    async function deleteMilestone(milestoneId) {{
        if (!confirm('Delete this milestone?')) return;
        try {{
            const res = await fetch(`/api/waitlists/${{WAITLIST_ID}}/milestones/${{milestoneId}}/`, {{method: 'DELETE'}});
            if (res.ok) loadWaitlist();
            else {{ const d = await res.json(); alert(d.error || 'Failed to delete'); }}
        }} catch(e) {{ alert('Failed to delete'); }}
    }}

    // Init
    loadWaitlist();
    </script>
    """

    return render_page(f"{waitlist.name} - Waitlist", content, theme=current_theme, user_menu=user_menu)
