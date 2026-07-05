"""Fake data for soft-launch flows – replace with DB/API when integrating."""
import copy

from services.soft_launch_lifecycle import ORDERED_STATUSES, STAGE_EXPLAINER, STATUS_UI_LABEL

HOMEPAGE = {
    'headline': 'Build decisions, not just discussions',
    'subtext': (
        'A coordination layer where ideas become proposals, proposals move through review, '
        'and approved work becomes reality.'
    ),
    'primary_cta': {'label': 'Get Started', 'href': '/soft-launch/onboarding/'},
    'primary_cta_microcopy': (
        'Start with one idea. Your first contribution takes less than 60 seconds.'
    ),
    'secondary_cta': {'label': 'Explore Activity', 'href': '#sl-live-activity'},
    'how_it_works_title': 'How it works',
    'live_activity_title': 'Live activity',
    'participation_title': 'How do you want to participate?',
    # Civic Mason → GovHub bridge (symbolic layer; flows stay in GovHub)
    'monument': {
        'title': 'Build the Monument',
        'line1': 'Every contribution becomes part of a shared structure.',
        'line2': 'Place a brick. Help shape what persists.',
        'cta_primary': {
            'label': 'Place Your First Brick',
            'href': '/soft-launch/onboarding/',
        },
        'cta_secondary': {
            'label': 'View the Monument',
            'href': '#sl-live-activity',
        },
    },
}

HOW_IT_WORKS_STEPS = [
    {'title': 'Contribute', 'body': 'Share an idea, question, or proposal'},
    {'title': 'Review', 'body': 'Others support, contradict, or expand it'},
    {'title': 'Decide', 'body': 'Ready contributions move into voting and implementation'},
]

# Action-oriented participation cards (homepage)
PARTICIPATION_CARDS = [
    {
        'title': 'Share an idea',
        'body': 'Start a contribution in less than a minute.',
        'cta_label': 'Start Contributing',
        'href': '/soft-launch/onboarding/',
    },
    {
        'title': 'Review work',
        'body': 'Support, contradict, comment, and add evidence.',
        'cta_label': 'Open Contributions',
        'href': '/soft-launch/artifact/?scenario=under_review_ready',
    },
    {
        'title': 'Build what passes',
        'body': 'Help approved work move into implementation.',
        'cta_label': 'View Approved Work',
        'href': '/soft-launch/artifact/?scenario=approved',
    },
]

ACTIVITY_CARDS = [
    {
        'title': 'Consent-based agent boundaries',
        'contribution_type': 'Proposal',
        'status_key': 'under_review',
        'status_ui': 'In Review',
        'space': 'AI Governance',
        'activity_line': '5 comments · 2 supports',
        'updated_ago': 'Updated 2h ago',
        'href': '/soft-launch/artifact/?scenario=under_review_ready',
        'cta_label': 'Open Contribution',
    },
    {
        'title': 'Carbon credit verification model',
        'contribution_type': 'Proposal',
        'status_key': 'draft',
        'status_ui': 'Draft',
        'space': 'Climate',
        'activity_line': '2 supports',
        'updated_ago': 'Updated 1d ago',
        'href': '/soft-launch/artifact/?scenario=draft',
        'cta_label': 'Open Contribution',
    },
]

# Onboarding step 2 – pick a space (fixture only)
SPACES_FIXTURE = [
    {'id': 'space-ai', 'name': 'AI Governance'},
    {'id': 'space-climate', 'name': 'Climate'},
    {'id': 'space-civic', 'name': 'Civic Infrastructure'},
]

ONBOARDING_COPY = {
    'step1_title': 'What do you want to do?',
    'step1_options': [
        {'id': 'share', 'label': 'Share an idea'},
        {'id': 'review', 'label': 'Review contributions'},
        {'id': 'explore', 'label': 'Explore first'},
    ],
    'step2_title': 'Where does this belong?',
    'step2_helper': 'Select a space for this contribution.',
    'step3_title': "What's the idea?",
    'step3_fields': [
        {
            'name': 'title',
            'label': "What's the idea?",
            'placeholder': 'Introduce a trust signal for AI-generated content',
        },
        {
            'name': 'description',
            'label': 'Describe it in a few sentences',
            'placeholder': "What's the problem? What should happen?",
        },
        {
            'name': 'link',
            'label': 'Add a link or reference (optional)',
            'placeholder': 'https://…',
            'optional': True,
        },
    ],
    'step3_cta': 'Publish Contribution',
    'step4_title': 'Your contribution is live',
    'step4_brick_headline': 'Your brick has been placed.',
    'step4_brick_body': (
        'It is now part of the system and open for review, contradiction, and expansion.'
    ),
    'step4_body': (
        'Others can now review, support, contradict, or build on it.'
    ),
    'step5_title': 'Keep it moving',
    'step5_options': [
        'Add evidence',
        'Invite feedback',
        'Review other contributions',
    ],
}

READINESS_CHECKLIST_KEYS = [
    'softLaunch.artifact.readinessRowSufficient',
    'softLaunch.artifact.readinessRowEvidence',
    'softLaunch.artifact.readinessRowContradictions',
    'softLaunch.artifact.readinessRowScope',
    'softLaunch.artifact.readinessRowQuestion',
]


def _readiness_rows(relationships: dict, activity: list):
    """
    Checklist rows with copy that points to on-page Relationships / Activity anchors.
    """
    rel = relationships or {}
    act = activity or []
    n_act = len(act)
    n_sup = len(rel.get('supports') or [])
    n_opp = len(rel.get('opposes') or [])
    return [
        {
            'label_key': 'softLaunch.artifact.readinessRowSufficient',
            'detail_key': 'softLaunch.artifact.readinessDetailTemplate.discussion',
            'detail_count': n_act,
            'href': '#sl-artifact-activity',
            'link_label_key': 'softLaunch.artifact.readinessViewActivity',
        },
        {
            'label_key': 'softLaunch.artifact.readinessRowEvidence',
            'detail_key': 'softLaunch.artifact.readinessDetailTemplate.supports',
            'detail_count': n_sup,
            'href': '#sl-rel-supports',
            'link_label_key': 'softLaunch.artifact.readinessViewSupports',
        },
        {
            'label_key': 'softLaunch.artifact.readinessRowContradictions',
            'detail_key': 'softLaunch.artifact.readinessDetailTemplate.opposes',
            'detail_count': n_opp,
            'href': '#sl-rel-opposition',
            'link_label_key': 'softLaunch.artifact.readinessViewOpposition',
        },
        {
            'label_key': 'softLaunch.artifact.readinessRowScope',
            'detail_key': 'softLaunch.artifact.readinessDetailTemplate.scope',
            'href': None,
            'link_label_key': None,
        },
        {
            'label_key': 'softLaunch.artifact.readinessRowQuestion',
            'detail_key': 'softLaunch.artifact.readinessDetailTemplate.question',
            'href': None,
            'link_label_key': None,
        },
    ]

MODAL_READINESS_CHECKLIST = [
    'Has the proposal been clearly stated?',
    'Have supporting arguments been added?',
    'Have contradictions been surfaced?',
    'Is the scope specific enough to vote on?',
    'Is there a clear implementation path if approved?',
]


def lifecycle_steps_for_json():
    """Stages for stepper UI + API consumers."""
    out = []
    for key in ORDERED_STATUSES:
        out.append({
            'status': key,
            'ui_label': STATUS_UI_LABEL[key],
            'explainer': STAGE_EXPLAINER[key],
        })
    return out


def demo_artifact(stored_status: str = 'under_review', readiness_met: bool = False):
    """
    Single demo contribution for scaffold pages.

    `readiness_met` drives transition callout visibility (heuristic stub).
    """
    s = (stored_status or 'under_review').strip().lower()
    _rel = {
        'supports': [{'title_key': 'softLaunch.artifact.demo.relArtifactA', 'ref': 'aaaabbbbio'}],
        'opposes': [{'title_key': 'softLaunch.artifact.demo.relArtifactB', 'ref': 'cccddddeio'}],
        'builds_on': [{'title_key': 'softLaunch.artifact.demo.relArtifactC', 'ref': 'eeefffggio'}],
    }
    _activity = [
        {'actor': 'Alex', 'verb_key': 'softLaunch.artifact.demo.activityCommented', 'when': '2h ago'},
        {'actor': 'Sam', 'verb_key': 'softLaunch.artifact.demo.activityEvidence', 'when': '5h ago'},
        {'actor': 'Jordan', 'verb_key': 'softLaunch.artifact.demo.activitySupported', 'when': '1d ago'},
    ]
    return {
        'id': 'soft-launch-demo-artifact',
        'public_ref': 'demo01io',
        'title_key': 'softLaunch.artifact.demo.title',
        'artifact_type_key': 'softLaunch.artifact.demo.type',
        'space_name_key': 'softLaunch.artifact.demo.space',
        'layer_display_name': 'AI Governance Layer',
        'status': s,
        'status_ui': STATUS_UI_LABEL.get(s, s),
        'body_key': 'softLaunch.artifact.demo.body',
        'readiness_met': readiness_met,
        'readiness_checklist': copy.deepcopy(READINESS_CHECKLIST_KEYS),
        'readiness_rows': _readiness_rows(_rel, _activity),
        'modal_readiness_checklist': copy.deepcopy(MODAL_READINESS_CHECKLIST),
        'decision_question_placeholder': (
            'Should this proposal be adopted by the AI Governance space?'
        ),
        'activity': _activity,
        'relationships': _rel,
        'voting': {
            'closes_in_label': '3 days',
            'opened_on_label': '2026-03-24',
            'supports': 12,
            'opposes': 3,
            'abstains': 2,
        },
        'vote_context': {
            'evidence_count': 4,
            'opposition_count': 2,
            'comment_count': 9,
            'related_contributions_count': 3,
        },
    }


def full_fixtures_payload():
    """Everything the demo API returns."""
    return {
        'homepage': HOMEPAGE,
        'how_it_works': HOW_IT_WORKS_STEPS,
        'participation_cards': PARTICIPATION_CARDS,
        'activity_cards': ACTIVITY_CARDS,
        'spaces': SPACES_FIXTURE,
        'onboarding': ONBOARDING_COPY,
        'lifecycle': lifecycle_steps_for_json(),
        'artifacts': {
            'draft': demo_artifact('draft', readiness_met=False),
            'under_review': demo_artifact('under_review', readiness_met=False),
            'under_review_ready': demo_artifact('under_review', readiness_met=True),
            'vote_scheduled': demo_artifact('vote_scheduled', readiness_met=True),
            'vote_open': demo_artifact('vote_open', readiness_met=True),
            'approved': demo_artifact('approved', readiness_met=True),
            'implemented': demo_artifact('implemented', readiness_met=True),
        },
    }
