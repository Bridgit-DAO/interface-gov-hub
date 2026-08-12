"""AI-assisted external workgroup invitation: research, disambiguation, draft, send."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models import PlatformInvitation, User, Workgroup, WorkgroupMemberRequest
from services.assist import LlmCallFailed, LlmTemporarilyBusy, call_llm, clean_draft, llm_configured, resolve_llm_config
from services.platform_invitation_mail import (
    build_multi_workgroup_invite_mailto,
    invite_body_uses_join_placeholders,
    send_multi_workgroup_invitation_email,
    substitute_workgroup_join_placeholders,
)
from services.platform_invitations import (
    can_invite,
    invitation_landing_url,
    lookup_prior_workgroup_invitations,
    normalize_invitee_email,
    validate_invitee_email,
)
from services.utils import generate_invitation_token
from services.web_research import research_person_corpus
from services.workgroup_authority import is_workgroup_member
from services.workgroup_links import is_dp_workgroup, query_workgroups_for_layer

_INVITE_TTL_DAYS = 7

TONE_PRESETS = ('warm', 'professional', 'direct')
LENGTH_PRESETS = ('short', 'medium', 'long')

_LENGTH_GUIDANCE = {
    'short': 'About 120–180 words.',
    'medium': 'About 220–320 words.',
    'long': 'About 380–520 words.',
}

_DP_ENGAGEMENT_PARAGRAPH = (
    'The Desirable Properties Challenge is a community-led effort to define what we want from '
    'the layered web — governance patterns, interoperability, and human agency. Workgroups like '
    'this one turn those ideas into practice, and your perspective would strengthen that work.'
)


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences LLMs often wrap around JSON."""
    cleaned = (text or '').strip()
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```\s*$', '', cleaned)
    return cleaned.strip()


def _extract_first_json_object(text: str) -> str:
    """Return the first top-level `{...}` substring using brace matching."""
    start = text.find('{')
    if start < 0:
        raise json.JSONDecodeError('No JSON object found', text, 0)

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise json.JSONDecodeError('Unbalanced JSON object', text, start)


def _parse_json_object(text: str) -> dict:
    """Parse a JSON object from messy LLM output (fences, prose, trailing text)."""
    cleaned = _strip_markdown_fences(text)
    if not cleaned:
        raise json.JSONDecodeError('Empty LLM JSON response', text or '', 0)

    attempts = [cleaned]
    # Leading commentary before the object
    if not cleaned.startswith('{'):
        try:
            attempts.append(_extract_first_json_object(cleaned))
        except json.JSONDecodeError:
            pass

    last_err: Optional[json.JSONDecodeError] = None
    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
            raise json.JSONDecodeError('Expected JSON object', candidate, 0)
        except json.JSONDecodeError as exc:
            last_err = exc
            # Trailing commentary after a valid object ("Extra data")
            try:
                parsed, _ = json.JSONDecoder().raw_decode(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as raw_exc:
                last_err = raw_exc
            try:
                sliced = _extract_first_json_object(candidate)
                parsed = json.loads(sliced)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as slice_exc:
                last_err = slice_exc

    if last_err:
        raise last_err
    raise json.JSONDecodeError('Expected JSON object', cleaned, 0)


def _dp_workgroup_catalog(primary: Workgroup) -> List[dict]:
    rows = query_workgroups_for_layer(primary.layer_id, status='active')
    catalog = []
    for wg in rows:
        if wg.id == primary.id:
            continue
        if wg.approval_status != 'approved':
            continue
        if not is_dp_workgroup(wg):
            continue
        catalog.append({
            'id': wg.id,
            'name': wg.name,
            'slug': wg.slug or wg.acronym,
            'description': (wg.description or '')[:500],
            'charter': (wg.charter or '')[:800],
        })
    return catalog


def check_invite_blocked(workgroup: Workgroup, email: str) -> Optional[str]:
    norm = normalize_invitee_email(email)
    if not norm:
        return 'Valid email is required'

    invitee = User.query.filter(db.func.lower(User.email) == norm).first()
    if invitee and is_workgroup_member(workgroup.acronym, invitee.id):
        return f'{norm} is already a member of this workgroup.'

    pending = WorkgroupMemberRequest.query.filter_by(
        group_acronym=workgroup.acronym,
        status='pending',
    ).all()
    if invitee:
        for req in pending:
            if req.user_id == invitee.id:
                return f'{norm} already has a pending membership request for this workgroup.'

    return None


def research_external_contact(
    *,
    workgroup: Workgroup,
    inviter: dict,
    name: str,
    email: str,
    linkedin_url: str = '',
    previous_interaction: str = '',
    extra_links: Optional[List[str]] = None,
    selected_candidate_index: Optional[int] = None,
) -> Tuple[dict, int]:
    if not is_workgroup_member(workgroup.acronym, inviter):
        return {'error': 'Only workgroup members can use the AI invite tool'}, 403

    block = check_invite_blocked(workgroup, email)
    if block:
        return {'blocked': True, 'error': block}, 200

    corpus = research_person_corpus(
        name=name,
        linkedin_url=linkedin_url,
        extra_links=extra_links or [],
    )

    if not llm_configured():
        return {'error': 'No LLM API key configured for AI invite'}, 503

    cfg = resolve_llm_config()
    if not cfg:
        return {'error': 'No LLM API key configured for AI invite'}, 503

    system = (
        'You analyze public information about a person for a workgroup recruitment email. '
        'Respond with a single JSON object only — no markdown fences, no commentary before or after. '
        'Required keys: '
        'ambiguous (boolean), candidates (array of {name, headline, source_urls[]}), '
        'resolved_person ({name, headline, summary, expertise_tags[]}), '
        'suggested_workgroups (array of {workgroup_id, rationale}). '
        'Mark ambiguous=true when multiple distinct people match or roles conflict. '
        'Only suggest workgroup_id values from the provided catalog.'
    )
    catalog = _dp_workgroup_catalog(workgroup)
    user_msg = json.dumps({
        'target_name': name.strip(),
        'email': normalize_invitee_email(email),
        'previous_interaction': (previous_interaction or '').strip(),
        'corpus': corpus.get('combined_text', '')[:8000],
        'search_results': corpus.get('search_results', [])[:6],
        'primary_workgroup': {
            'id': workgroup.id,
            'name': workgroup.name,
            'description': workgroup.description or '',
        },
        'other_workgroups_catalog': catalog,
        'selected_candidate_index': selected_candidate_index,
    })
    try:
        raw = clean_draft(call_llm([
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg},
        ], cfg))
        analysis = _parse_json_object(raw)
    except (json.JSONDecodeError, LlmCallFailed, LlmTemporarilyBusy) as exc:
        return {'error': f'AI research failed: {exc}'}, 502

    prior = lookup_prior_workgroup_invitations(normalize_invitee_email(email))

    ambiguous = bool(analysis.get('ambiguous'))
    if selected_candidate_index is not None and analysis.get('resolved_person'):
        ambiguous = False

    suggested = []
    for item in analysis.get('suggested_workgroups') or []:
        wg_id = (item.get('workgroup_id') or '').strip()
        if not wg_id or wg_id == workgroup.id:
            continue
        wg = Workgroup.query.get(wg_id)
        if wg and is_dp_workgroup(wg):
            suggested.append({
                'workgroup_id': wg.id,
                'name': wg.name,
                'slug': wg.slug or wg.acronym,
                'rationale': (item.get('rationale') or '')[:400],
            })

    return {
        'success': True,
        'ambiguous': ambiguous,
        'candidates': analysis.get('candidates') or [],
        'resolved_person': analysis.get('resolved_person'),
        'suggested_workgroups': suggested,
        'prior_invitations': prior,
        'corpus_meta': {
            'urls_fetched': len(corpus.get('url_corpus') or []),
            'search_hits': len(corpus.get('search_results') or []),
            'search_available': corpus.get('search_available'),
        },
    }, 200


def _invitee_greeting_name(name: str) -> str:
    """First name when available, else full name, else a neutral fallback."""
    cleaned = re.sub(r'\s+', ' ', (name or '').strip())
    if not cleaned:
        return 'there'
    first = cleaned.split(' ', 1)[0]
    # Drop trailing punctuation from titles/initials edge cases.
    first = first.strip('.,;:')
    return first or cleaned


def ensure_invite_greeting(draft: str, invitee_name: str) -> str:
    """Guarantee the email body opens with Hi {name}, (LLM sometimes omits it)."""
    text = (draft or '').strip()
    if not text:
        return text
    # Already starts with a salutation (Hi / Hello / Dear …).
    if re.match(r'^(hi|hello|dear)\b', text, flags=re.IGNORECASE):
        return text
    greet = _invitee_greeting_name(invitee_name)
    return f'Hi {greet},\n\n{text}'


def _invite_content_guidance(invite_content: Optional[dict]) -> str:
    if not invite_content:
        return ''

    events = invite_content.get('events') or []
    perspectives = invite_content.get('perspectives') or []
    if not events and not perspectives:
        return ''

    lead = (invite_content.get('lead') or 'events').strip().lower()
    if lead not in ('events', 'perspectives', 'engagement'):
        lead = 'events'

    def engagement_block() -> str:
        return (
            'DESIRABLE PROPERTIES ENGAGEMENT (include this paragraph verbatim in prose):\n'
            f'{_DP_ENGAGEMENT_PARAGRAPH}'
        )

    def event_block() -> str:
        lines = [
            'EVENTS TO MENTION (include FULL absolute URLs in prose — never relative paths):',
        ]
        for item in events:
            title = (item.get('title') or '').strip()
            url = (item.get('url') or '').strip()
            desc = (item.get('description') or '').strip()
            kind = (item.get('kind') or 'single').strip().lower()
            if kind not in ('series', 'session', 'single'):
                kind = 'single'
            event_date = (item.get('event_date') or item.get('eventDate') or '')[:10]
            next_session = (item.get('next_session_date') or item.get('nextSessionDate') or '')[:10]
            series_started = (item.get('series_started') or item.get('seriesStarted') or '')[:10]
            detail = f'- {title} [kind={kind}]'
            if url:
                detail += f' — {url}'
            if desc:
                detail += f'. {desc}'
            if kind == 'series':
                if next_session:
                    detail += f'. DATE WORDING: say the next session is on {next_session}'
                elif event_date:
                    detail += f'. DATE WORDING: say the next session is on {event_date}'
                if series_started:
                    detail += (
                        f'; the series already started on {series_started}'
                        ' — do NOT say the series is starting or coming up on the next session date'
                    )
                else:
                    detail += (
                        '. Do NOT say the series is starting or coming up on the next session date'
                        ' — use phrasing like "the next session is on …" or "join us for the next session on …"'
                    )
            elif kind == 'session':
                session_date = next_session or event_date
                if session_date:
                    detail += f'. DATE WORDING: this session is on {session_date}'
            else:
                if event_date:
                    detail += f'. DATE WORDING: this event is on {event_date}'
            lines.append(detail)
        return '\n'.join(lines)

    def perspective_block() -> str:
        lines = [
            'PERSPECTIVES TO MENTION (include FULL absolute URLs in prose — never relative paths):',
        ]
        for item in perspectives:
            title = (item.get('title') or '').strip()
            url = (item.get('url') or '').strip()
            slug = (item.get('slug') or '').strip()
            detail = f'- {title}'
            if url:
                detail += f' — {url}'
            if slug:
                detail += f' (slug: {slug})'
            lines.append(detail)
        return '\n'.join(lines)

    blocks = []
    content_blocks = []
    if events:
        content_blocks.append(('events', event_block()))
    if perspectives:
        content_blocks.append(('perspectives', perspective_block()))

    if lead == 'engagement':
        blocks.append(engagement_block())
        for _, block in content_blocks:
            blocks.append(block)
    elif lead == 'perspectives':
        for kind, block in content_blocks:
            if kind == 'perspectives':
                blocks.insert(0, block)
            else:
                blocks.append(block)
    else:
        for kind, block in content_blocks:
            if kind == 'events':
                blocks.insert(0, block)
            else:
                blocks.append(block)

    structure_lines = [
        'INVITE CONTENT STRUCTURE (before the workgroup invitation):',
    ]
    if lead == 'engagement':
        structure_lines.extend([
            '1. Desirable Properties engagement paragraph (verbatim).',
            '2. Events and/or perspectives blocks in the order listed below.',
            '3. Then transition into the workgroup invitation (primary workgroup, extras, join placeholders).',
        ])
    else:
        structure_lines.extend([
            '1. Lead block as specified by invite_lead.',
            '2. Second block if both events and perspectives are selected.',
            f'3. Include this Desirable Properties engagement paragraph verbatim:\n{_DP_ENGAGEMENT_PARAGRAPH}',
            '4. Then transition into the workgroup invitation (primary workgroup, extras, join placeholders).',
        ])

    structure = [
        *structure_lines,
        '',
        *blocks,
    ]
    return '\n'.join(structure)


def draft_invitation_email(
    *,
    workgroup: Workgroup,
    inviter: dict,
    name: str,
    email: str,
    tone: str = 'warm',
    length: str = 'medium',
    previous_interaction: str = '',
    extra_guidance: str = '',
    resolved_person: Optional[dict] = None,
    additional_workgroup_ids: Optional[List[str]] = None,
    prior_invitations: Optional[List[dict]] = None,
    invite_content: Optional[dict] = None,
) -> Tuple[dict, int]:
    if not is_workgroup_member(workgroup.acronym, inviter):
        return {'error': 'Only workgroup members can use the AI invite tool'}, 403

    block = check_invite_blocked(workgroup, email)
    if block:
        return {'blocked': True, 'error': block}, 200

    tone_key = (tone or 'warm').strip().lower()
    length_key = (length or 'medium').strip().lower()
    if tone_key not in TONE_PRESETS:
        tone_key = 'warm'
    if length_key not in LENGTH_PRESETS:
        length_key = 'medium'

    if not llm_configured():
        return {'error': 'No LLM API key configured for AI invite'}, 503
    cfg = resolve_llm_config()
    if not cfg:
        return {'error': 'No LLM API key configured for AI invite'}, 503

    inviter_user = User.query.get(inviter['id'])
    inviter_name = (inviter_user.displayName or inviter_user.username or 'A member') if inviter_user else 'A member'

    extra_wgs = []
    for wg_id in additional_workgroup_ids or []:
        wg = Workgroup.query.get(wg_id)
        if wg and wg.id != workgroup.id:
            extra_wgs.append({'id': wg.id, 'name': wg.name, 'slug': wg.slug or wg.acronym})

    prior = prior_invitations if prior_invitations is not None else lookup_prior_workgroup_invitations(
        normalize_invitee_email(email),
    )
    prior_note = ''
    if prior:
        latest = prior[0]
        prior_note = (
            f"We previously invited this person ({latest.get('status')}) on "
            f"{latest.get('created_at', '')[:10]} — acknowledge naturally if appropriate."
        )

    invitee_display = (name or '').strip()
    greet_name = _invitee_greeting_name(invitee_display)

    invite_content_note = _invite_content_guidance(invite_content)
    combined_guidance = (extra_guidance or '').strip()
    if invite_content_note:
        combined_guidance = (
            f'{invite_content_note}\n\n{combined_guidance}'.strip()
            if combined_guidance
            else invite_content_note
        )

    system = (
        'Write a personal invitation email body (plain text, no subject line). '
        f'The FIRST line MUST be a greeting using the invitee\'s first name, e.g. "Hi {greet_name}," '
        '(or "Hi {full name}," if only one name token). Never skip the greeting. '
    )
    if invite_content_note:
        system += (
            'When invite content is provided, follow the INVITE CONTENT STRUCTURE before the '
            'workgroup invitation. '
        )
    system += (
        'Lead with the primary workgroup unless invite content blocks come first per structure. '
        'Mention any additional workgroups briefly. '
        'Do NOT include URLs for workgroup joins — placeholders [JOIN_PRIMARY] and [JOIN_EXTRA_N] will be inserted later. '
        'Include full absolute URLs (https://…) for events and perspectives when provided — never relative paths. '
        f'Tone: {tone_key}. Length: {_LENGTH_GUIDANCE[length_key]}. '
        'Reference previous interaction naturally when provided.'
    )
    user_msg = json.dumps({
        'inviter_name': inviter_name,
        'invitee_name': invitee_display,
        'invitee_first_name': greet_name,
        'primary_workgroup': workgroup.name,
        'primary_description': (workgroup.description or workgroup.charter or '')[:600],
        'additional_workgroups': extra_wgs,
        'resolved_person': resolved_person or {'name': invitee_display},
        'previous_interaction': (previous_interaction or '').strip(),
        'extra_guidance': combined_guidance,
        'invite_content': invite_content or None,
        'prior_invite_note': prior_note,
    })

    try:
        draft = clean_draft(call_llm([
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_msg},
        ], cfg))
        draft = ensure_invite_greeting(draft, invitee_display)
    except (LlmCallFailed, LlmTemporarilyBusy) as exc:
        return {'error': f'AI draft failed: {exc}'}, 502

    return {
        'success': True,
        'draft': draft,
        'tone': tone_key,
        'length': length_key,
        'prior_invitations': prior,
    }, 200


def send_ai_workgroup_invitations(
    *,
    workgroup: Workgroup,
    inviter_id: str,
    name: str,
    email: str,
    body: str,
    additional_workgroup_ids: Optional[List[str]] = None,
    send_mode: str = 'platform',
) -> Tuple[dict, int]:
    mode = (send_mode or 'platform').strip().lower()
    if mode not in ('platform', 'client'):
        return {'error': 'send_mode must be platform or client'}, 400

    norm_email = normalize_invitee_email(email)
    if not validate_invitee_email(norm_email):
        return {'error': 'Valid email is required'}, 400

    inviter = User.query.get(inviter_id)
    if not inviter:
        return {'error': 'Inviter not found'}, 404

    ok, err = can_invite(inviter_id, 'join_workgroup', {'workgroup_id': workgroup.id})
    if not ok:
        return {'error': err or 'Not allowed to invite'}, 403

    block = check_invite_blocked(workgroup, norm_email)
    if block:
        return {'blocked': True, 'error': block}, 400

    text = (body or '').strip()
    if not text:
        return {'error': 'Email body is required'}, 400

    wg_ids = [workgroup.id]
    for wg_id in additional_workgroup_ids or []:
        if wg_id and wg_id not in wg_ids:
            wg = Workgroup.query.get(wg_id)
            if wg:
                ok_extra, err_extra = can_invite(inviter_id, 'join_workgroup', {'workgroup_id': wg.id})
                if ok_extra:
                    wg_ids.append(wg.id)

    now = datetime.utcnow()
    invitee = User.query.filter(db.func.lower(User.email) == norm_email).first()
    invitations = []

    for wg_id in wg_ids:
        wg = Workgroup.query.get(wg_id)
        if not wg:
            continue
        target = {
            'workgroup_id': wg.id,
            'workgroup_slug': wg.slug or wg.acronym,
            'workgroup_name': wg.name,
            'workgroup_acronym': wg.acronym,
            'layer_id': wg.layer_id,
        }
        inv = PlatformInvitation(
            invite_type='join_workgroup',
            rate_category='standard',
            inviter_id=inviter_id,
            invitee_email=norm_email,
            invitee_id=invitee.id if invitee else None,
            message=text if wg_id == workgroup.id else None,
            target_json=json.dumps(target),
            status='pending',
            token=generate_invitation_token(),
            expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
        )
        db.session.add(inv)
        db.session.flush()
        invitations.append((inv, wg))

    if not invitations:
        return {'error': 'No invitations created'}, 400

    links = [
        {
            'workgroup_name': wg.name,
            'landing_url': invitation_landing_url(inv),
        }
        for inv, wg in invitations
    ]

    inline_join_links = invite_body_uses_join_placeholders(text)
    resolved_text = substitute_workgroup_join_placeholders(text, links)
    primary_inv, _ = invitations[0]
    primary_inv.message = resolved_text

    sent = False
    mailto_payload = None
    if mode == 'platform':
        sent = send_multi_workgroup_invitation_email(
            inviter=inviter,
            invitee_email=norm_email,
            invitee_name=name.strip(),
            body_text=resolved_text,
            links=links,
            inline_join_links=inline_join_links,
        )
    else:
        mailto_payload = build_multi_workgroup_invite_mailto(
            invitee_email=norm_email,
            invitee_name=name.strip(),
            body_text=resolved_text,
            links=links,
            inline_join_links=inline_join_links,
        )

    from services.workgroup_membership import (
        emit_workgroup_invite_event,
        workgroup_invite_event_payload,
    )

    payload = workgroup_invite_event_payload(
        workgroup,
        invitee_email=norm_email,
        invitee_name=name.strip(),
        invitation_id=primary_inv.id,
    )
    payload['workgroup_ids'] = wg_ids
    payload['send_mode'] = mode
    emit_workgroup_invite_event(
        'workgroup_invite_sent',
        workgroup=workgroup,
        actor_user_id=inviter_id,
        subject_type='platform_invitation',
        subject_id=primary_inv.id,
        payload=payload,
    )
    db.session.commit()

    result = {
        'success': True,
        'send_mode': mode,
        'email_sent': sent,
        'invitation_ids': [inv.id for inv, _ in invitations],
        'links': links,
    }
    if mailto_payload:
        result.update(mailto_payload)
    return result, 201
