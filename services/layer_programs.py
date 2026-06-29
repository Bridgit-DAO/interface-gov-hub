"""Layer programs: resolve hubs, scope submissions, launch lifecycle."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from extensions import db
from models import Layer, LayerMember, LayerProgram, LayerProgramSubmission, Submission, User, Waitlist, WaitlistEntry, Workgroup
from services.coordination import is_layer_admin
from services.dp_proposals import is_dp_submission, list_approved_submissions_for_mode, submission_draft_ref, workgroup_for_submission
from services.workgroup_links import extract_dp_number_from_title

PROGRAM_STATUSES = ('draft', 'waitlist', 'active', 'archived')
LAUNCH_TIMEZONE = 'America/Los_Angeles'


def _normalize_hub_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = path.strip()
    if not p.startswith('/'):
        p = '/' + p
    if not p.endswith('/'):
        p = p + '/'
    return p


def normalize_program_slug(raw: str) -> str:
    slug = (raw or '').strip().lower()
    slug = re.sub(r'[^a-z0-9-]+', '-', slug)
    slug = re.sub(r'-{2,}', '-', slug).strip('-')
    return slug[:80]


def get_program(program_id: str) -> Optional[LayerProgram]:
    return LayerProgram.query.get(program_id)


def get_program_by_slug(layer_id: str, slug: str) -> Optional[LayerProgram]:
    return LayerProgram.query.filter_by(layer_id=layer_id, slug=normalize_program_slug(slug)).first()


def list_programs_for_layer(layer_id: str) -> List[LayerProgram]:
    return (
        LayerProgram.query.filter_by(layer_id=layer_id)
        .order_by(LayerProgram.created_at.desc())
        .all()
    )


def resolve_program_for_hub(
    hub_path: str,
    *,
    program_slug: Optional[str] = None,
    layer_slug: Optional[str] = None,
) -> Optional[LayerProgram]:
    """Resolve a program for a public hub path (/dp-challenge/, etc.)."""
    normalized = _normalize_hub_path(hub_path)
    if not normalized:
        return None

    if program_slug and layer_slug:
        layer = Layer.query.filter_by(slug=layer_slug.strip()).first()
        if layer:
            return get_program_by_slug(layer.id, program_slug)

    q = LayerProgram.query.filter(LayerProgram.hub_path == normalized)
    if program_slug:
        q = q.filter(LayerProgram.slug == normalize_program_slug(program_slug))
    else:
        q = q.filter(LayerProgram.status.in_(('waitlist', 'active', 'archived')))
    program = q.order_by(LayerProgram.launched_at.desc(), LayerProgram.created_at.desc()).first()
    if program:
        maybe_auto_launch_program(program)
    return program


def format_launch_at_pacific(launch_at: Optional[datetime]) -> Optional[str]:
    if not launch_at:
        return None
    try:
        from zoneinfo import ZoneInfo

        utc = launch_at.replace(tzinfo=ZoneInfo('UTC'))
        local = utc.astimezone(ZoneInfo(LAUNCH_TIMEZONE))
        return local.strftime('%B %d, %Y at %I:%M %p').replace(' 0', ' ').replace(' AM', ' AM').replace(' PM', ' PM') + ' Pacific'
    except Exception:
        return launch_at.strftime('%Y-%m-%d %H:%M UTC')


def program_has_opened(program: Optional[LayerProgram]) -> bool:
    if not program:
        return True
    if program.status == 'archived':
        return True
    if program.status != 'active':
        return False
    if program.launch_at and datetime.utcnow() < program.launch_at:
        return False
    return True


def maybe_auto_launch_program(program: LayerProgram) -> bool:
    """Flip waitlist → active when launch_at has passed."""
    if not program or program.status != 'waitlist' or not program.launch_at:
        return False
    if datetime.utcnow() < program.launch_at:
        return False
    program.status = 'active'
    program.launched_at = program.launched_at or datetime.utcnow()
    db.session.commit()
    _send_launch_notifications(program)
    return True


def linked_submission_ids(program: LayerProgram) -> Optional[Set[str]]:
    rows = LayerProgramSubmission.query.filter_by(program_id=program.id).all()
    if not rows:
        return None
    return {r.submission_id for r in rows}


def submission_in_program_scope(submission: Optional[Submission], program: Optional[LayerProgram]) -> bool:
    if not program or not submission:
        return True
    linked = linked_submission_ids(program)
    if linked is not None:
        return submission.id in linked
    if program.workgroup_id:
        wg = Workgroup.query.get(program.workgroup_id)
        if wg:
            matched = workgroup_for_submission(submission)
            return matched is not None and matched.id == wg.id
    return True


def filter_submissions_for_program(submissions: List[Submission], program: Optional[LayerProgram]) -> List[Submission]:
    if not program:
        return submissions
    return [s for s in submissions if submission_in_program_scope(s, program)]


def filter_submission_id_set(program: Optional[LayerProgram]) -> Optional[Set[str]]:
    if not program:
        return None
    linked = linked_submission_ids(program)
    if linked is not None:
        return linked
    if program.workgroup_id:
        wg = Workgroup.query.get(program.workgroup_id)
        if not wg:
            return set()
        ids: Set[str] = set()
        for sub in Submission.query.filter_by(status='approved', doc_type='draft').all():
            matched = workgroup_for_submission(sub)
            if matched and matched.id == wg.id:
                ids.add(sub.id)
        return ids
    return None


def program_public_view(program: LayerProgram, user: Optional[dict] = None) -> Dict[str, Any]:
    layer = Layer.query.get(program.layer_id)
    data = program.to_dict()
    data['layer_slug'] = layer.slug if layer else None
    data['layer_name'] = layer.name if layer else None
    data['launch_at_label'] = format_launch_at_pacific(program.launch_at)
    data['is_prelaunch'] = not program_has_opened(program) and program.status in ('waitlist', 'draft')
    if program.waitlist_id:
        wl = Waitlist.query.get(program.waitlist_id)
        if wl and layer:
            data['waitlist_url'] = f'/layers/{layer.slug}/waitlist/{wl.id}/'
            data['waitlist_name'] = wl.name
    if program.hub_path and layer:
        data['layer_program_url'] = f'/layers/{layer.slug}/#program-{program.slug}'
    data['submission_count'] = LayerProgramSubmission.query.filter_by(program_id=program.id).count()
    if user and user.get('id') and program.waitlist_id:
        entry = get_user_notify_entry(program, user['id'])
        data['notify_joined'] = entry is not None
        if entry:
            data['notify_dp_interests'] = parse_entry_dp_interests(entry)
    else:
        data['notify_joined'] = False
    return data


def _short_dp_name(title: str) -> str:
    t = (title or '').strip()
    m = re.match(r'^DP\s*(\d+)\s*[-–—:]\s*(.+)$', t, re.IGNORECASE)
    return m.group(2).strip() if m else t


def format_dp_option_label(sub: Submission) -> str:
    dp_num = extract_dp_number_from_title(sub.title or '')
    name = _short_dp_name(sub.title or '') or (sub.title or '').strip() or 'Draft'
    dp_part = f'DP{dp_num:02d}' if dp_num is not None else 'DP'
    ml = (sub.ml_number or '').strip()
    if ml:
        ml_match = re.match(r'ML-Draft-(\d+)', ml, re.IGNORECASE)
        ml_num = ml_match.group(1) if ml_match else ml
        return f'{dp_part} - {name} (ML-DRAFT {ml_num})'
    return f'{dp_part} - {name}'


def list_notify_dp_options(program: Optional[LayerProgram] = None) -> List[Dict[str, Any]]:
    mode = (program.hub_mode if program and program.hub_mode else 'dp')
    subs = list_approved_submissions_for_mode(mode, program=program)
    options: List[Dict[str, Any]] = []
    for sub in subs:
        if mode == 'dp' and not is_dp_submission(sub):
            continue
        dp_num = extract_dp_number_from_title(sub.title or '')
        options.append({
            'submission_id': sub.id,
            'draft_ref': submission_draft_ref(sub),
            'label': format_dp_option_label(sub),
            'dp_number': dp_num,
        })
    options.sort(key=lambda o: (o.get('dp_number') if o.get('dp_number') is not None else 9999, o.get('label') or ''))
    return options


def parse_entry_dp_interests(entry: WaitlistEntry) -> List[Dict[str, Any]]:
    if not entry or not entry.metadata_json:
        return []
    try:
        meta = json.loads(entry.metadata_json)
    except (TypeError, json.JSONDecodeError):
        return []
    interests = meta.get('dp_interests') or []
    return interests if isinstance(interests, list) else []


def get_user_notify_entry(program: LayerProgram, user_id: str) -> Optional[WaitlistEntry]:
    if not program.waitlist_id or not user_id:
        return None
    return WaitlistEntry.query.filter_by(
        waitlist_id=program.waitlist_id,
        user_id=user_id,
        left_at=None,
    ).first()


def _normalize_dp_interests(raw: Any, program: LayerProgram) -> List[Dict[str, Any]]:
    if not raw:
        return []
    allowed = {o['submission_id']: o for o in list_notify_dp_options(program)}
    by_ref = {o['draft_ref']: o for o in allowed.values() if o.get('draft_ref')}
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    items = raw if isinstance(raw, list) else [raw]
    for item in items:
        if isinstance(item, dict):
            sid = (item.get('submission_id') or '').strip()
            ref = (item.get('draft_ref') or '').strip()
        else:
            sid = ''
            ref = str(item or '').strip()
        picked = None
        if sid and sid in allowed:
            picked = allowed[sid]
        elif ref and ref in by_ref:
            picked = by_ref[ref]
        if not picked or picked['submission_id'] in seen:
            continue
        seen.add(picked['submission_id'])
        out.append({
            'submission_id': picked['submission_id'],
            'draft_ref': picked.get('draft_ref'),
            'label': picked.get('label'),
        })
    return out


def notify_config_for_program(program: LayerProgram, user: Optional[dict] = None) -> Dict[str, Any]:
    entry = get_user_notify_entry(program, user['id']) if user and user.get('id') else None
    return {
        'program_id': program.id,
        'program_slug': program.slug,
        'program_name': program.name,
        'layer_slug': Layer.query.get(program.layer_id).slug if program.layer_id else None,
        'launch_at': program.launch_at.isoformat() if program.launch_at else None,
        'launch_at_label': format_launch_at_pacific(program.launch_at),
        'is_prelaunch': not program_has_opened(program) and program.status in ('waitlist', 'draft'),
        'waitlist_id': program.waitlist_id,
        'joined': entry is not None,
        'dp_interests': parse_entry_dp_interests(entry) if entry else [],
        'dp_options': list_notify_dp_options(program),
        'notify_api_path': f'/api/layers/{program.layer_id}/programs/{program.id}/notify/',
    }


def join_program_notify_list(
    program: LayerProgram,
    user: dict,
    *,
    dp_interests: Optional[List[Any]] = None,
    source: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    if not program.waitlist_id:
        return None, 'This program has no notify waitlist configured', 400
    if program_has_opened(program) and program.status == 'active':
        return None, 'This program is already open for participation', 400

    waitlist = Waitlist.query.get(program.waitlist_id)
    if not waitlist or not waitlist.active:
        return None, 'Notify list is not available', 400

    user_row = User.query.get(user['id'])
    if not user_row:
        return None, 'User not found', 404

    now = datetime.utcnow()
    if now < waitlist.start_date:
        return None, 'Notify list has not opened yet', 400
    if waitlist.closing_date and now >= waitlist.closing_date:
        return None, 'Notify list is closed', 400

    interests = _normalize_dp_interests(dp_interests, program)
    metadata = {
        'kind': 'program_notify',
        'program_id': program.id,
        'program_slug': program.slug,
        'dp_interests': interests,
    }
    meta_str = json.dumps(metadata)

    count = WaitlistEntry.query.filter_by(waitlist_id=waitlist.id, left_at=None).count()
    existing = WaitlistEntry.query.filter_by(waitlist_id=waitlist.id, user_id=user['id']).first()
    if existing:
        if not existing.left_at:
            existing.metadata_json = meta_str
            if source:
                existing.source = source
            if source_url:
                existing.source_url = source_url
            db.session.commit()
            _send_notify_confirmation(user_row, program, interests, updated=True)
            return {
                'joined': True,
                'updated': True,
                'position': existing.position,
                'dp_interests': interests,
            }, None, 200
        existing.left_at = None
        existing.position = count + 1
        existing.metadata_json = meta_str
        existing.joined_at = now
        db.session.commit()
        _send_notify_confirmation(user_row, program, interests, updated=False)
        return {
            'joined': True,
            'updated': False,
            'position': existing.position,
            'dp_interests': interests,
        }, None, 200

    entry = WaitlistEntry(
        waitlist_id=waitlist.id,
        user_id=user['id'],
        message='Notify when DP Challenge opens',
        position=count + 1,
        metadata_json=meta_str,
        source=source or 'dp-challenge-notify',
        source_url=source_url,
    )
    db.session.add(entry)
    db.session.commit()
    _send_notify_confirmation(user_row, program, interests, updated=False)
    return {
        'joined': True,
        'updated': False,
        'position': entry.position,
        'dp_interests': interests,
    }, None, 201


def create_program(layer: Layer, user: dict, payload: dict) -> Tuple[Optional[LayerProgram], Optional[str], int]:
    if not is_layer_admin(layer, user):
        return None, 'Layer admin required', 403

    slug = normalize_program_slug(payload.get('slug') or payload.get('name') or '')
    if not slug:
        return None, 'slug is required', 400
    if get_program_by_slug(layer.id, slug):
        return None, 'A program with this slug already exists on this layer', 409

    status = (payload.get('status') or 'draft').strip().lower()
    if status not in PROGRAM_STATUSES:
        return None, f'status must be one of: {", ".join(PROGRAM_STATUSES)}', 400

    hub_mode = (payload.get('hub_mode') or '').strip().lower() or None
    program = LayerProgram(
        layer_id=layer.id,
        slug=slug,
        name=(payload.get('name') or slug).strip()[:255],
        description=(payload.get('description') or '').strip() or None,
        status=status,
        hub_path=_normalize_hub_path(payload.get('hub_path')),
        hub_mode=hub_mode,
        waitlist_id=(payload.get('waitlist_id') or None),
        workgroup_id=(payload.get('workgroup_id') or None),
    )
    db.session.add(program)
    db.session.commit()
    return program, None, 201


def update_program(program: LayerProgram, layer: Layer, user: dict, payload: dict) -> Tuple[Optional[LayerProgram], Optional[str], int]:
    if not is_layer_admin(layer, user):
        return None, 'Layer admin required', 403

    if 'name' in payload:
        program.name = (payload.get('name') or program.name).strip()[:255]
    if 'description' in payload:
        program.description = (payload.get('description') or '').strip() or None
    if 'hub_path' in payload:
        program.hub_path = _normalize_hub_path(payload.get('hub_path'))
    if 'hub_mode' in payload:
        program.hub_mode = (payload.get('hub_mode') or '').strip().lower() or None
    if 'waitlist_id' in payload:
        program.waitlist_id = payload.get('waitlist_id') or None
    if 'workgroup_id' in payload:
        program.workgroup_id = payload.get('workgroup_id') or None
    if 'launch_at' in payload:
        raw = payload.get('launch_at')
        if raw:
            try:
                from dateutil import parser as date_parser
                program.launch_at = date_parser.parse(str(raw))
            except Exception:
                return None, 'Invalid launch_at', 400
        else:
            program.launch_at = None
    if 'status' in payload:
        status = (payload.get('status') or program.status).strip().lower()
        if status not in PROGRAM_STATUSES:
            return None, f'status must be one of: {", ".join(PROGRAM_STATUSES)}', 400
        program.status = status
        if status == 'archived' and not program.archived_at:
            program.archived_at = datetime.utcnow()
        if status == 'active' and not program.launched_at:
            program.launched_at = datetime.utcnow()

    db.session.commit()
    return program, None, 200


def set_program_submissions(
    program: LayerProgram,
    layer: Layer,
    user: dict,
    submission_ids: List[str],
) -> Tuple[Optional[LayerProgram], Optional[str], int]:
    if not is_layer_admin(layer, user):
        return None, 'Layer admin required', 403

    LayerProgramSubmission.query.filter_by(program_id=program.id).delete()
    for sid in submission_ids:
        sid = (sid or '').strip()
        if not sid:
            continue
        sub = Submission.query.get(sid)
        if not sub:
            continue
        db.session.add(LayerProgramSubmission(program_id=program.id, submission_id=sid))
    db.session.commit()
    return program, None, 200


def launch_program(
    program: LayerProgram,
    layer: Layer,
    user: dict,
    *,
    promote_waitlist: bool = False,
    join_policy_after: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    if not is_layer_admin(layer, user):
        return None, 'Layer admin required', 403
    if program.status == 'archived':
        return None, 'Archived programs cannot be launched', 400

    now = datetime.utcnow()
    program.status = 'active'
    program.launched_at = program.launched_at or now

    promoted = 0
    if promote_waitlist and program.waitlist_id:
        entries = (
            WaitlistEntry.query.filter_by(waitlist_id=program.waitlist_id, left_at=None)
            .order_by(WaitlistEntry.position.asc())
            .all()
        )
        for entry in entries:
            existing = LayerMember.query.filter_by(layer_id=layer.id, user_id=entry.user_id).first()
            if existing and existing.status == 'active' and existing.left_at is None:
                continue
            if existing:
                existing.status = 'active'
                existing.joined_at = now
                existing.left_at = None
                if entry.referred_by_id and not existing.referred_by_id:
                    existing.referred_by_id = entry.referred_by_id
            else:
                db.session.add(
                    LayerMember(
                        layer_id=layer.id,
                        user_id=entry.user_id,
                        referred_by_id=entry.referred_by_id,
                        role='contributor',
                    )
                )
            promoted += 1

    if join_policy_after:
        layer.join_policy = join_policy_after

    db.session.commit()
    launch_mail = _send_launch_notifications(program)
    return {
        'program': program_public_view(program),
        'promoted_waitlist_members': promoted,
        'launch_emails': launch_mail,
    }, None, 200


def _send_notify_confirmation(user_row: User, program: LayerProgram, interests: List[Dict[str, Any]], *, updated: bool) -> None:
    try:
        from services.program_notify_mail import send_program_notify_confirmation

        send_program_notify_confirmation(
            user=user_row,
            program=program,
            dp_interests=interests,
            updated=updated,
        )
    except Exception:
        try:
            from flask import current_app
            current_app.logger.exception('Program notify confirmation email failed')
        except RuntimeError:
            pass


def _send_launch_notifications(program: LayerProgram) -> Dict[str, Any]:
    try:
        from services.program_notify_mail import send_program_launch_notifications

        return send_program_launch_notifications(program)
    except Exception as exc:
        try:
            from flask import current_app
            current_app.logger.exception('Program launch notification emails failed')
        except RuntimeError:
            pass
        return {'sent': 0, 'failed': 0, 'total': 0, 'error': str(exc)}


def hub_access_state(program: Optional[LayerProgram], user: Optional[dict]) -> str:
    """Return full | waitlist | draft | none for hub rendering."""
    if not program:
        return 'full'
    maybe_auto_launch_program(program)
    if program.status == 'archived':
        return 'full'
    if program_has_opened(program):
        return 'full'
    if program.status == 'waitlist':
        return 'waitlist'
    if program.status == 'draft':
        layer = Layer.query.get(program.layer_id)
        if layer and user and is_layer_admin(layer, user):
            return 'full'
        return 'draft'
    return 'none'
