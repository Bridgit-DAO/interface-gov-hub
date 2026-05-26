"""Contribution type (`knowledge_form`) + optional `knowledge_scaffold` per artifact_contribution_schema.md / briefing §5."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# All IFP-aligned values (storage: lowercase snake). Matches wiki [[Form]] vocabulary.
KNOWLEDGE_FORM_VALUES = frozenset({
    'inquiry',
    'principle',
    'model',
    'claim',
    'decision',
    'gloss',
    'scenario',
    'pattern',
    'boundary',
    'domain',
    'case',
    'reference',
    'research',
    'skill',
    'opus',
})

# Default when opening picker (first value in allowed list matches)
ARTIFACT_TYPE_DEFAULT_FORM: Dict[str, str] = {
    'proposal': 'decision',
    'document': 'model',
    'evidence': 'model',
    'meeting_summary': 'model',
    'decision': 'decision',
    'bridge': 'gloss',
    'translation': 'gloss',
    'monument_context': 'scenario',
    'comment': 'claim',
    'poll': 'decision',
    'announcement': 'decision',
    'event': 'scenario',
    'submission': 'model',
    'support': 'claim',
    'opposition': 'claim',
    # Document / layer UI artifact picker (routes/documents.py)
    'monument': 'scenario',
    'insight': 'model',
    'reflection': 'claim',
    'implementation': 'decision',
}

# Allowed values per artifact_type (includes default). `document` / `submission` = full catalog.
ARTIFACT_TYPE_ALLOWED_FORMS: Dict[str, frozenset] = {
    'proposal': KNOWLEDGE_FORM_VALUES,
    'document': KNOWLEDGE_FORM_VALUES,
    'evidence': frozenset({
        'model', 'scenario', 'principle', 'gloss', 'pattern', 'case', 'reference',
        'research', 'domain', 'boundary',
    }),
    'meeting_summary': frozenset({
        'model', 'scenario', 'inquiry', 'decision', 'case', 'pattern', 'domain', 'principle',
    }),
    'decision': frozenset({
        'decision', 'principle', 'model', 'scenario', 'boundary', 'pattern', 'case', 'opus',
    }),
    'bridge': frozenset({
        'gloss', 'model', 'principle', 'inquiry', 'boundary', 'reference', 'domain', 'case',
    }),
    'translation': frozenset({
        'gloss', 'principle', 'model', 'domain', 'reference', 'case',
    }),
    'monument_context': frozenset({
        'scenario', 'principle', 'gloss', 'model', 'domain', 'case', 'boundary', 'pattern',
    }),
    'comment': frozenset({
        'claim', 'inquiry', 'principle', 'model', 'pattern', 'boundary', 'gloss',
    }),
    'poll': frozenset({
        'decision', 'inquiry', 'principle', 'pattern', 'domain',
    }),
    'announcement': frozenset({
        'decision', 'principle', 'model', 'opus', 'domain',
    }),
    'event': frozenset({
        'scenario', 'inquiry', 'model', 'case', 'pattern', 'opus',
    }),
    'submission': KNOWLEDGE_FORM_VALUES,
    'support': frozenset({
        'claim', 'principle', 'model', 'pattern', 'boundary', 'case',
    }),
    'opposition': frozenset({
        'claim', 'principle', 'model', 'pattern', 'boundary', 'case',
    }),
    'monument': frozenset({
        'scenario', 'principle', 'gloss', 'model', 'domain', 'case', 'reference', 'boundary',
    }),
    'insight': frozenset({
        'model', 'principle', 'inquiry', 'scenario', 'pattern', 'research', 'case',
        'boundary', 'domain', 'skill',
    }),
    'reflection': frozenset({
        'claim', 'inquiry', 'principle', 'model', 'pattern', 'boundary', 'case', 'domain',
    }),
    'implementation': frozenset({
        'decision', 'principle', 'model', 'scenario', 'skill', 'case', 'pattern',
        'boundary', 'research',
    }),
}

SCAFFOLD_MAX_STRING_LEN = 2000

# Allowed JSON keys per knowledge_form (briefing §5)
SCAFFOLD_KEYS_BY_FORM: Dict[str, frozenset] = {
    'inquiry': frozenset({'what_is_unclear', 'status'}),
    'principle': frozenset({'why_matters'}),
    'model': frozenset({'key_assumptions'}),
    'claim': frozenset({'why_believe'}),
    'decision': frozenset({'what_resolves', 'status'}),
    'gloss': frozenset({'definition'}),
    'scenario': frozenset({'actors_context'}),
    'pattern': frozenset({'recurring_tension', 'resolution'}),
    'boundary': frozenset({'authority_scope', 'where_it_ends'}),
    'domain': frozenset({'area_label', 'relationship_to_parent'}),
    'case': frozenset({'what_we_tried', 'what_happened', 'takeaway'}),
    'reference': frozenset({'must_know_summary', 'pointer_notes'}),
    'research': frozenset({'central_question', 'status'}),
    'skill': frozenset({'procedure_summary', 'verification'}),
    'opus': frozenset({'thesis', 'stakes'}),
}

INQUIRY_STATUSES = frozenset({'open', 'closed'})
DECISION_SCAFFOLD_STATUSES = frozenset({'draft', 'final'})
RESEARCH_STATUSES = frozenset({'active', 'paused', 'complete'})

# Optional: human-readable “core question” per form (for tooltips / docs; also exposed in schema).
KNOWLEDGE_FORM_CORE_QUESTIONS: Dict[str, str] = {
    'model': 'How do these elements relate?',
    'claim': 'What do we believe is true?',
    'decision': 'Why did we choose this over alternatives?',
    'pattern': 'What resolves this recurring tension?',
    'principle': 'What must we always or never do?',
    'gloss': 'What does this concept mean?',
    'inquiry': 'What should we think about next?',
    'boundary': 'Where does authority end?',
    'scenario': 'What might happen if these forces play out?',
    'domain': 'What knowledge area is this?',
    'case': 'What happened when we tried this?',
    'reference': 'What do I need to know about this domain?',
    'research': 'What are we investigating?',
    'skill': 'How does an agent execute this reliably?',
    'opus': 'What am I saying here?',
}

# Renamed conviction → claim; accept legacy slug on read/write.
KNOWLEDGE_FORM_LEGACY_ALIASES: Dict[str, str] = {
    'conviction': 'claim',
}


def canonical_knowledge_form(value: Optional[str]) -> Optional[str]:
    """Normalize stored/API knowledge_form; maps legacy slugs to current vocabulary."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    return KNOWLEDGE_FORM_LEGACY_ALIASES.get(v, v)


def allowed_forms_for_artifact_type(artifact_type: Optional[str]) -> frozenset:
    """Return allowed knowledge_form values; unknown types → empty set (only null allowed)."""
    if not artifact_type:
        return frozenset()
    return ARTIFACT_TYPE_ALLOWED_FORMS.get(artifact_type.strip().lower(), frozenset())


def default_form_for_artifact_type(artifact_type: Optional[str]) -> Optional[str]:
    if not artifact_type:
        return None
    return ARTIFACT_TYPE_DEFAULT_FORM.get(artifact_type.strip().lower())


def public_schema_dict(config: dict) -> dict:
    """Payload for GET /api/knowledge-layer/schema/ (client pickers)."""
    atype_map = {}
    for atype in sorted(ARTIFACT_TYPE_ALLOWED_FORMS.keys()):
        allowed = sorted(ARTIFACT_TYPE_ALLOWED_FORMS[atype])
        atype_map[atype] = {
            'default': ARTIFACT_TYPE_DEFAULT_FORM.get(atype),
            'allowed': allowed,
        }
    return {
        'feature_flags': {
            'knowledge_contribution_type_enabled': bool(config.get('KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED', True)),
            'knowledge_scaffold_enabled': bool(config.get('KNOWLEDGE_SCAFFOLD_ENABLED', False)),
            'knowledge_contribution_filters_enabled': bool(config.get('KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED', True)),
            'layer_tags_enabled': bool(config.get('LAYER_TAGS_ENABLED', config.get('ARTIFACT_TAGS_ENABLED', True))),
            'layer_tag_filters_enabled': bool(config.get('LAYER_TAG_FILTERS_ENABLED', config.get('ARTIFACT_TAG_FILTERS_ENABLED', True))),
            'document_tags_enabled': bool(config.get('DOCUMENT_TAGS_ENABLED', True)),
            'artifact_tags_enabled': bool(config.get('LAYER_TAGS_ENABLED', config.get('ARTIFACT_TAGS_ENABLED', True))),
            'artifact_tag_filters_enabled': bool(config.get('LAYER_TAG_FILTERS_ENABLED', config.get('ARTIFACT_TAG_FILTERS_ENABLED', True))),
        },
        'knowledge_forms': sorted(KNOWLEDGE_FORM_VALUES),
        'knowledge_form_core_questions': {
            k: KNOWLEDGE_FORM_CORE_QUESTIONS[k] for k in sorted(KNOWLEDGE_FORM_CORE_QUESTIONS)
        },
        'artifact_types': atype_map,
        'scaffold_keys_by_form': {k: sorted(v) for k, v in sorted(SCAFFOLD_KEYS_BY_FORM.items())},
        'scaffold_status_enums': {
            'inquiry': sorted(INQUIRY_STATUSES),
            'decision': sorted(DECISION_SCAFFOLD_STATUSES),
            'research': sorted(RESEARCH_STATUSES),
        },
        'scaffold_max_string_len': SCAFFOLD_MAX_STRING_LEN,
    }


def _normalize_string(s: Any) -> Optional[str]:
    if s is None:
        return None
    if not isinstance(s, str):
        return None
    t = s.strip()
    return t if t else None


def _normalize_scaffold(
    knowledge_form: str,
    raw: Any,
    *,
    scaffold_enabled: bool,
) -> Tuple[Optional[dict], Optional[str]]:
    if not scaffold_enabled:
        return None, None
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, 'knowledge_scaffold must be a JSON object'
    allowed_keys = SCAFFOLD_KEYS_BY_FORM.get(knowledge_form)
    if not allowed_keys:
        return None, 'invalid knowledge_form for scaffold'
    out: Dict[str, Any] = {}
    for key, val in raw.items():
        if key not in allowed_keys:
            continue
        if key in ('status',):
            if val is None or val == '':
                continue
            if not isinstance(val, str):
                return None, f'{key} must be a string'
            v = val.strip().lower()
            if knowledge_form == 'inquiry':
                if v not in INQUIRY_STATUSES:
                    return None, f'inquiry.status must be one of {sorted(INQUIRY_STATUSES)}'
            elif knowledge_form == 'decision':
                if v not in DECISION_SCAFFOLD_STATUSES:
                    return None, f'decision.status must be one of {sorted(DECISION_SCAFFOLD_STATUSES)}'
            elif knowledge_form == 'research':
                if v not in RESEARCH_STATUSES:
                    return None, f'research.status must be one of {sorted(RESEARCH_STATUSES)}'
            else:
                return None, f'status is not valid for knowledge_form {knowledge_form!r}'
            out[key] = v
            continue
        # string fields
        ns = _normalize_string(val)
        if ns is None:
            continue
        if len(ns) > SCAFFOLD_MAX_STRING_LEN:
            return None, f'{key} exceeds max length ({SCAFFOLD_MAX_STRING_LEN})'
        out[key] = ns
    return out or None, None


def apply_knowledge_patch(art, data: dict, app_config: dict) -> List[str]:
    """
    Apply optional knowledge_form / knowledge_scaffold from JSON PATCH/POST body.
    Mutates art. Returns error strings; empty = success.

    Rules:
    - If contribution type feature disabled, reject any body keys knowledge_form / knowledge_scaffold.
    - Clearing knowledge_form clears knowledge_scaffold.
    - Changing knowledge_form clears previous scaffold (v1); then applies new scaffold if sent in same request.
    - knowledge_scaffold alone requires existing or simultaneous knowledge_form.
    """
    ce = bool(app_config.get('KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED', True))
    se = bool(app_config.get('KNOWLEDGE_SCAFFOLD_ENABLED', False))
    if not ce:
        if 'knowledge_form' in data or 'knowledge_scaffold' in data:
            return ['knowledge contribution type is disabled']
        return []

    if 'knowledge_form' not in data and 'knowledge_scaffold' not in data:
        return []

    atype = getattr(art, 'artifact_type', None) or ''
    old_form = getattr(art, 'knowledge_form', None)
    old_form_n = (old_form or '').strip().lower() or None if old_form else None

    new_form = old_form_n
    if 'knowledge_form' in data:
        raw = data['knowledge_form']
        if raw is None or (isinstance(raw, str) and raw.strip() == ''):
            new_form = None
        elif not isinstance(raw, str):
            return ['knowledge_form must be a string or null']
        else:
            new_form = canonical_knowledge_form(raw)
            if new_form not in KNOWLEDGE_FORM_VALUES:
                return [f'knowledge_form must be one of {sorted(KNOWLEDGE_FORM_VALUES)}']
        allowed = allowed_forms_for_artifact_type(atype)
        if new_form is not None and (not allowed or new_form not in allowed):
            return [f'knowledge_form not allowed for artifact_type {atype!r}']

    new_scaffold = getattr(art, 'knowledge_scaffold', None)

    if new_form is None:
        new_scaffold = None
        if 'knowledge_scaffold' in data and data['knowledge_scaffold'] not in (None, {}):
            return ['knowledge_scaffold requires knowledge_form to be set']
        art.knowledge_form = None
        art.knowledge_scaffold = None
        return []

    # new_form is set
    form_changed = ('knowledge_form' in data) and (new_form != old_form_n)
    if form_changed:
        new_scaffold = None

    if 'knowledge_scaffold' in data:
        sc_raw = data['knowledge_scaffold']
        norm, err = _normalize_scaffold(new_form, sc_raw, scaffold_enabled=se)
        if err:
            return [err]
        new_scaffold = norm
    elif form_changed:
        new_scaffold = None

    art.knowledge_form = new_form
    art.knowledge_scaffold = new_scaffold
    return []


def validate_knowledge_for_create(
    artifact_type: str,
    knowledge_form: Any,
    knowledge_scaffold: Any,
    app_config: dict,
) -> Tuple[Optional[str], Optional[dict], List[str]]:
    """For POST create: returns (form, scaffold, errors)."""
    ce = bool(app_config.get('KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED', True))
    se = bool(app_config.get('KNOWLEDGE_SCAFFOLD_ENABLED', False))
    if not ce:
        if knowledge_form is not None or knowledge_scaffold is not None:
            return None, None, ['knowledge contribution type is disabled']
        return None, None, []

    form: Optional[str] = None
    if knowledge_form is not None and not (isinstance(knowledge_form, str) and knowledge_form.strip() == ''):
        if not isinstance(knowledge_form, str):
            return None, None, ['knowledge_form must be a string or null']
        form = canonical_knowledge_form(knowledge_form)
        if form not in KNOWLEDGE_FORM_VALUES:
            return None, None, [f'knowledge_form must be one of {sorted(KNOWLEDGE_FORM_VALUES)}']
        allowed = allowed_forms_for_artifact_type(artifact_type)
        if not allowed or form not in allowed:
            return None, None, [f'knowledge_form not allowed for artifact_type {artifact_type!r}']

    if form is None:
        if knowledge_scaffold not in (None, {}):
            return None, None, ['knowledge_scaffold requires knowledge_form to be set']
        return None, None, []

    norm, err = _normalize_scaffold(form, knowledge_scaffold, scaffold_enabled=se)
    if err:
        return None, None, [err]
    return form, norm, []
