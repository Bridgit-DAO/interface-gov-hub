"""AI-assisted external workgroup invitation: research, disambiguation, draft, send."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models import PlatformInvitation, User, Workgroup, WorkgroupMemberRequest
from services.assist import (
    LlmCallFailed,
    LlmTemporarilyBusy,
    call_llm,
    clean_draft,
    llm_configured,
    resolve_llm_config,
    strip_em_dashes,
)
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
    'short': (
        'About 120–180 words total (strict band). '
        'Structure: at most 3 short paragraphs before the workgroup invitation; '
        'keep event or workshop mentions to one tight line each; '
        'for Desirable Properties engagement, use a single-sentence summary instead of the full paragraph; '
        'brief workgroup pitch and a crisp close. Must be clearly shorter than medium.'
    ),
    'medium': (
        'About 220–320 words total. '
        'Structure: standard flow—invite content blocks (events, perspectives, engagement as guided), '
        'then workgroup invitation with primary and any additional workgroups, then close with [JOIN_PRIMARY]. '
        'This is the baseline length; do not pad or trim aggressively.'
    ),
    'long': (
        'About 380–520 words total (strict band). '
        'Must be at least ~100 words longer than a medium draft would be for the same invite. '
        'Structure: same opening blocks as medium, then AFTER the workgroup description and BEFORE the closing ask, '
        'add 1–2 extra paragraphs that (a) explain why this specific person is a fit using resolved_person context, '
        '(b) describe what participation looks like (meetings, async contribution, outcomes), and '
        '(c) include role-specific detail tied to the workgroup charter or description. '
        'Do NOT meet the word target by repeating the intro or stretching the sign-off.'
    ),
}

_LENGTH_MIN_WORDS = {
    'short': 100,
    'medium': 180,
    'long': 350,
}

_LENGTH_MAX_WORDS = {
    'short': 200,
    'medium': 380,
    'long': 600,
}

_LENGTH_LONG_EXPAND_THRESHOLD = 350

# Output token budgets for invite draft LLM calls (higher than generic assist
# because long drafts plus invite-content blocks can exceed MAX_OUTPUT_TOKENS).
_INVITE_DRAFT_MAX_TOKENS = {
    'short': 900,
    'medium': 1600,
    'long': 4000,
}
_INVITE_RESEARCH_MAX_TOKENS = 2400
_INVITE_CONTENT_TOKEN_BONUS = 600

_COMPLETE_DRAFT_SUFFIX_RE = re.compile(r'[\]\).!?]["\']?\s*$')
_PLANNING_LEAK_RE = re.compile(
    r'(?i)let me (?:count(?:\s+words)?|adjust|draft(?:\s+more carefully)?)',
)

_TONE_GUIDANCE = {
    'warm': (
        'Warm and personable: open with a friendly greeting, use inclusive "you" language, '
        'express genuine enthusiasm for their expertise, add a human touch (shared interests or prior context), '
        'and close invitingly. Sentences may be slightly longer and conversational.'
    ),
    'professional': (
        'Professional and polished: courteous greeting, balanced formality, clear topic sentences, '
        'measured enthusiasm without exclamation marks, precise wording, and a respectful close. '
        'Avoid slang and overly casual contractions.'
    ),
    'direct': (
        'Direct and concise: minimal preamble after the greeting, short declarative sentences, '
        'state the invitation purpose in the first paragraph, favor bullet-like clarity without bullets, '
        'and a firm clear call to action. Omit filler pleasantries beyond the required greeting.'
    ),
}

_DATE_FORMAT_RULE = (
    'Use natural calendar dates in prose (e.g. "August 10, 2026"), never ISO YYYY-MM-DD. '
    'Do not wrap perspective or event titles in quotation marks when mentioning them in prose.'
)

_DP_ENGAGEMENT_PARAGRAPH = (
    'The Desirable Properties Challenge is a community-led effort to define what we want from '
    'the layered web – governance patterns, interoperability, and human agency. Workgroups like '
    'this one turn those ideas into practice, and your perspective would strengthen that work.'
)

_NO_EM_DASH_RULE = (
    'Never use em dashes (Unicode U+2014); use en dashes (Unicode U+2013), commas, or hyphens instead. '
)


def invite_draft_max_tokens(
    length_key: str,
    *,
    has_invite_content: bool = False,
) -> int:
    """Return the LLM max_tokens budget for an invite draft request."""
    key = (length_key or 'medium').strip().lower()
    if key not in LENGTH_PRESETS:
        key = 'medium'
    budget = _INVITE_DRAFT_MAX_TOKENS.get(key, _INVITE_DRAFT_MAX_TOKENS['medium'])
    if has_invite_content:
        budget += _INVITE_CONTENT_TOKEN_BONUS
    return budget


def invite_draft_looks_complete(draft: str) -> bool:
    """Heuristic: draft ends on a sentence boundary (not mid-clause truncation)."""
    text = (draft or '').strip()
    if not text:
        return False
    if '[JOIN_PRIMARY]' in text.upper():
        return True
    return bool(_COMPLETE_DRAFT_SUFFIX_RE.search(text))


def invite_draft_contains_planning_leak(draft: str) -> bool:
    """True when LLM planning/meta leaked into the visible draft body."""
    return bool(_PLANNING_LEAK_RE.search(draft or ''))


def _invite_word_count(draft: str) -> int:
    return len((draft or '').split())


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
        'Respond with a single JSON object only – no markdown fences, no commentary before or after. '
        f'{_NO_EM_DASH_RULE}'
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
        ], cfg, max_tokens=_INVITE_RESEARCH_MAX_TOKENS))
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


def _format_invite_date(raw: str) -> str:
    """Format ISO-ish dates as natural prose (e.g. August 10, 2026)."""
    cleaned = (raw or '').strip()
    if not cleaned:
        return ''
    date_part = cleaned[:10]
    if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
        try:
            dt = datetime.strptime(date_part, '%Y-%m-%d')
            return f'{dt.strftime("%B")} {dt.day}, {dt.year}'
        except ValueError:
            pass
    return cleaned


def _normalize_invite_content_for_llm(invite_content: Optional[dict]) -> Optional[dict]:
    """Format invite content dates for LLM guidance (human-readable, not ISO)."""
    if not invite_content:
        return None

    events_out = []
    for item in invite_content.get('events') or []:
        if not isinstance(item, dict):
            continue
        event = dict(item)
        for key in ('event_date', 'eventDate', 'next_session_date', 'nextSessionDate', 'series_started', 'seriesStarted'):
            raw = event.get(key)
            if raw:
                event[key] = _format_invite_date(str(raw))
        events_out.append(event)

    perspectives_out = []
    for item in invite_content.get('perspectives') or []:
        if isinstance(item, dict):
            perspectives_out.append(dict(item))

    lead = (invite_content.get('lead') or 'events').strip().lower()
    if lead not in ('events', 'perspectives', 'engagement'):
        lead = 'events'

    return {
        'lead': lead,
        'events': events_out,
        'perspectives': perspectives_out,
    }


def _dp_engagement_instruction(*, length_key: str) -> str:
    """How the LLM should handle the Desirable Properties engagement block."""
    if (length_key or 'medium').strip().lower() == 'short':
        return (
            'DESIRABLE PROPERTIES ENGAGEMENT (one sentence only—do NOT use the full paragraph):\n'
            'Summarize in a single sentence that the Desirable Properties Challenge is a community effort '
            'to define governance patterns, interoperability, and human agency, and that workgroups turn '
            'those ideas into practice.'
        )
    return (
        'DESIRABLE PROPERTIES ENGAGEMENT (include this paragraph verbatim in prose):\n'
        f'{_DP_ENGAGEMENT_PARAGRAPH}'
    )


def _invite_content_guidance(
    invite_content: Optional[dict],
    *,
    length_key: str = 'medium',
) -> str:
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
        return _dp_engagement_instruction(length_key=length_key)

    def event_block() -> str:
        lines = [
            'EVENTS TO MENTION (include FULL absolute URLs in prose – never relative paths):',
            _DATE_FORMAT_RULE,
        ]
        for item in events:
            title = (item.get('title') or '').strip()
            url = (item.get('url') or '').strip()
            desc = (item.get('description') or '').strip()
            kind = (item.get('kind') or 'single').strip().lower()
            if kind not in ('series', 'session', 'single'):
                kind = 'single'
            event_date = _format_invite_date(
                str(item.get('event_date') or item.get('eventDate') or ''),
            )
            next_session = _format_invite_date(
                str(item.get('next_session_date') or item.get('nextSessionDate') or ''),
            )
            series_started = _format_invite_date(
                str(item.get('series_started') or item.get('seriesStarted') or ''),
            )
            detail = f'- {title} [kind={kind}]'
            if url:
                detail += f' – {url}'
            if desc:
                detail += f'. {desc}'
            if kind == 'series':
                if next_session:
                    detail += f'. DATE WORDING: say the next session is on {next_session}'
                elif event_date:
                    detail += f'. DATE WORDING: say the next session is on {event_date}'
                if series_started:
                    detail += (
                        f'; the series is ongoing (started {series_started})'
                        ' – do NOT say the series is starting or coming up on the next session date'
                    )
                else:
                    detail += (
                        '. The series is ongoing – use phrasing like "the next session is on …" '
                        'or "join us for the next session on …"'
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
            'PERSPECTIVES TO MENTION (include FULL absolute URLs in prose – never relative paths):',
            'Mention perspective titles in plain prose without wrapping them in quotation marks.',
        ]
        for item in perspectives:
            title = (item.get('title') or '').strip()
            url = (item.get('url') or '').strip()
            slug = (item.get('slug') or '').strip()
            detail = f'- {title}'
            if url:
                detail += f' – {url}'
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
    is_short = (length_key or 'medium').strip().lower() == 'short'
    dp_step = (
        '1. Desirable Properties engagement (one sentence summary only).'
        if is_short
        else '1. Desirable Properties engagement paragraph (verbatim).'
    )
    if lead == 'engagement':
        structure_lines.extend([
            dp_step,
            '2. Events and/or perspectives blocks in the order listed below.',
            '3. Then transition into the workgroup invitation (primary workgroup, extras, join placeholders).',
        ])
    else:
        dp_inline = (
            '3. One-sentence Desirable Properties engagement summary (not the full paragraph).'
            if is_short
            else (
                '3. Include this Desirable Properties engagement paragraph verbatim:\n'
                f'{_DP_ENGAGEMENT_PARAGRAPH}'
            )
        )
        structure_lines.extend([
            '1. Lead block as specified by invite_lead.',
            '2. Second block if both events and perspectives are selected.',
            dp_inline,
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
    regenerate: bool = False,
    previous_draft: str = '',
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
            f"{latest.get('created_at', '')[:10]} – acknowledge naturally if appropriate."
        )

    invitee_display = (name or '').strip()
    greet_name = _invitee_greeting_name(invitee_display)

    invite_content_for_llm = _normalize_invite_content_for_llm(invite_content)
    invite_content_note = _invite_content_guidance(invite_content_for_llm, length_key=length_key)
    combined_guidance = (extra_guidance or '').strip()
    if invite_content_note:
        combined_guidance = (
            f'{invite_content_note}\n\n{combined_guidance}'.strip()
            if combined_guidance
            else invite_content_note
        )

    tone_guidance = _TONE_GUIDANCE.get(tone_key, _TONE_GUIDANCE['warm'])
    length_guidance = _LENGTH_GUIDANCE[length_key]
    length_band_rule = (
        'Honor the word-count band strictly: short 120–180, medium 220–320, long 380–520. '
        'Long must exceed medium by at least ~100 words via substantive middle paragraphs, not padding.'
    )
    system = (
        'Write a personal invitation email body (plain text, no subject line). '
        'Output only the email text – no analysis, planning, or XML tags. '
        f'The FIRST line MUST be a greeting using the invitee\'s first name, e.g. "Hi {greet_name}," '
        '(or "Hi {full name}," if only one name token). Never skip the greeting. '
        f'{_NO_EM_DASH_RULE}'
        f'{_DATE_FORMAT_RULE} '
    )
    if invite_content_note:
        system += (
            'When invite content is provided, follow the INVITE CONTENT STRUCTURE before the '
            'workgroup invitation. '
        )
    if length_key == 'short':
        system += (
            'SHORT length: keep pre-invite content to at most 3 brief paragraphs; compress workshops/events '
            'to one line each; use a one-sentence DP engagement summary when required. '
        )
    elif length_key == 'long':
        system += (
            'LONG length: after describing the workgroup(s), add 1–2 paragraphs on why this person specifically, '
            'what participation looks like, and role-specific workgroup detail before the closing ask. '
        )
    system += (
        'Lead with the primary workgroup unless invite content blocks come first per structure. '
        'Mention any additional workgroups briefly. '
        'End with a complete closing sentence and sign-off – never stop mid-sentence. '
        'Put the join call-to-action on its own final line using [JOIN_PRIMARY] '
        '(and [JOIN_EXTRA_N] for additional workgroups). Never use raw workgroup join URLs. '
        'Include full absolute URLs (https://…) for events and perspectives when provided – never relative paths. '
        f'TONE ({tone_key}): {tone_guidance} '
        f'LENGTH ({length_key}): {length_guidance} '
        f'{length_band_rule} '
        'Reference previous interaction naturally when provided.'
    )

    previous_draft_text = (previous_draft or '').strip()
    regenerate_note = ''
    if regenerate and previous_draft_text:
        regenerate_note = (
            'Regenerate the invitation: rewrite the previous draft in the requested tone and length. '
            'Change phrasing and structure noticeably while preserving factual content, URLs, and join placeholders.'
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
        'tone': tone_key,
        'length': length_key,
        'tone_guidance': tone_guidance,
        'length_guidance': length_guidance,
        'extra_guidance': combined_guidance,
        'invite_content': invite_content_for_llm,
        'prior_invite_note': prior_note,
        'regenerate': bool(regenerate),
        'previous_draft': previous_draft_text if regenerate else '',
        'regenerate_note': regenerate_note,
    })

    llm_temperature = 0.55 if regenerate else 0.4
    draft_max_tokens = invite_draft_max_tokens(
        length_key,
        has_invite_content=bool(invite_content_for_llm),
    )

    messages = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user_msg},
    ]

    try:
        draft = clean_draft(call_llm(
            messages,
            cfg,
            temperature=llm_temperature,
            max_tokens=draft_max_tokens,
        ), length_preference=length_key, invitee_name=invitee_display)
        draft = ensure_invite_greeting(draft, invitee_display)
        draft = strip_em_dashes(draft)

        word_count = _invite_word_count(draft)
        min_words = _LENGTH_MIN_WORDS.get(length_key, 180)
        max_words = _LENGTH_MAX_WORDS.get(length_key, 380)
        long_too_short = length_key == 'long' and word_count < _LENGTH_LONG_EXPAND_THRESHOLD
        short_too_long = length_key == 'short' and word_count > max_words
        planning_leak = invite_draft_contains_planning_leak(draft)
        needs_retry = (
            word_count < min_words
            or not invite_draft_looks_complete(draft)
            or '[JOIN_PRIMARY]' not in draft.upper()
            or long_too_short
            or short_too_long
            or planning_leak
        )
        if needs_retry:
            if long_too_short:
                retry_note = (
                    'The previous draft is too short for LONG length. '
                    'Expand the MIDDLE sections: add 1–2 paragraphs after the workgroup description '
                    'on why this person specifically, what participation looks like, and role-specific '
                    f'workgroup detail. Target {length_guidance} '
                    'End with [JOIN_PRIMARY] on its own line.'
                )
            elif short_too_long or planning_leak:
                retry_note = (
                    'The previous draft is too long for SHORT length or included planning/meta text. '
                    'Output ONLY the final invitation email body (no analysis, word counts, or revision notes). '
                    'Cut to 120–180 words maximum. '
                    'Keep at most 3 brief paragraphs before the workgroup invitation; compress events to one line each. '
                    'End with [JOIN_PRIMARY] on its own line.'
                )
            else:
                retry_note = (
                    'The previous draft was incomplete or missing [JOIN_PRIMARY]. '
                    'Write the complete invitation email body only (no analysis or XML tags). '
                    f'Target {length_guidance} End with [JOIN_PRIMARY] on its own line.'
                )
            retry_user = json.dumps({
                **json.loads(user_msg),
                'retry_note': retry_note,
                'previous_attempt': draft[:1200],
            })
            draft = clean_draft(call_llm([
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': retry_user},
            ], cfg, temperature=min(llm_temperature + 0.1, 0.7), max_tokens=draft_max_tokens),
                length_preference=length_key, invitee_name=invitee_display)
            draft = ensure_invite_greeting(draft, invitee_display)
            draft = strip_em_dashes(draft)
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

    text = strip_em_dashes((body or '').strip())
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
