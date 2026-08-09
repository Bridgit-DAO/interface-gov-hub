"""Group data service: load_group_data for workgroup/DP definitions."""
import re
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GROUP_ALIASES_PATHS = (
    _REPO_ROOT / 'test' / 'data' / 'group-aliases',
    Path('/home/ubuntu/datatracker/test/data/group-aliases'),
)

_DP_ACRONYM_RE = re.compile(r'^dp(\d+)-', re.IGNORECASE)
_WORKGROUP_SUFFIX_RE = re.compile(
    r'\s+(?:Working Group|Workgroup)\s*$',
    re.IGNORECASE,
)


def extract_dp_number(acronym: str) -> Optional[int]:
    """Return DP number from acronyms like dp1-federated-auth, or None."""
    if not acronym:
        return None
    match = _DP_ACRONYM_RE.match(acronym.strip())
    if not match:
        return None
    return int(match.group(1))


def strip_workgroup_suffix(name: str) -> str:
    """Remove trailing 'Working Group' or 'Workgroup' from a display name."""
    if not name:
        return name
    return _WORKGROUP_SUFFIX_RE.sub('', name.strip())


def format_dp_display_name(acronym: str, title: str) -> str:
    """Format as 'DP{n} - {Title}' for DP workgroups; otherwise return title only."""
    clean_title = strip_workgroup_suffix(title)
    dp_num = extract_dp_number(acronym)
    if dp_num is not None:
        return f'DP{dp_num} - {clean_title}'
    return clean_title


# Desirable Properties mapping for better names and descriptions
DP_DESCRIPTIONS = {
    'dp1-federated-auth': {
        'title': 'Federated Authentication & Accountability',
        'desc': 'Developing standards for federated authentication systems that enable cross-platform identity verification while maintaining accountability and audit trails.'
    },
    'dp2-participant-agency': {
        'title': 'Participant Agency and Empowerment',
        'desc': 'Creating frameworks that empower participants with full control over their digital presence, decision-making authority, and ability to shape their environment.'
    },
    'dp3-adaptive-governance': {
        'title': 'Adaptive Governance Supporting an Exponentially Growing Community',
        'desc': 'Designing governance systems that can scale with exponential community growth while maintaining fairness, participation, and adaptability to emerging challenges.'
    },
    'dp4-data-sovereignty': {
        'title': 'Data Sovereignty and Privacy',
        'desc': 'Establishing protocols for complete data ownership, privacy by design, and user-controlled data portability across the Meta-Layer ecosystem.'
    },
    'dp5-decentralized-namespace': {
        'title': 'Decentralized Namespace',
        'desc': 'Developing decentralized naming systems that provide persistent, user-controlled identifiers and namespaces independent of centralized authorities.'
    },
    'dp6-commerce': {
        'title': 'Commerce',
        'desc': 'Creating secure, transparent commerce protocols that enable value exchange, micropayments, and economic interactions within the Meta-Layer.'
    },
    'dp7-simplicity-interoperability': {
        'title': 'Simplicity and Interoperability',
        'desc': 'Designing systems that reduce complexity while ensuring seamless interoperability between different platforms, tools, and communities.'
    },
    'dp8-collaborative-environment': {
        'title': 'Collaborative Environment and Meta-Communities',
        'desc': 'Building frameworks for meta-communities that span multiple platforms and enable fluid collaboration across organizational boundaries.'
    },
    'dp9-developer-incentives': {
        'title': 'Developer and Community Incentives',
        'desc': 'Creating incentive structures that reward developers and communities for contributing to the ecosystem while aligning with long-term sustainability.'
    },
    'dp10-education': {
        'title': 'Education',
        'desc': 'Developing educational frameworks and tools that help participants understand and effectively use the Meta-Layer capabilities.'
    },
    'dp21-multi-modal': {
        'title': 'Multi-modal',
        'desc': 'Enabling seamless interaction across multiple communication modalities including text, voice, video, AR/VR, and emerging interaction paradigms.'
    },
    'dp11-safe-ethical-ai': {
        'title': 'Safe and Ethical AI',
        'desc': 'Establishing ethical frameworks and safety protocols for AI systems operating within the Meta-Layer to ensure alignment with human values.'
    },
    'dp12-community-ai-governance': {
        'title': 'Community-Based AI Governance',
        'desc': 'Creating community-driven governance models for AI systems that ensure transparency, accountability, and collective oversight.'
    },
    'dp13-ai-containment': {
        'title': 'AI Containment',
        'desc': 'Developing containment strategies and technical measures to prevent AI systems from exceeding intended boundaries or causing unintended consequences.'
    },
    'dp14-trust-transparency': {
        'title': 'Trust and Transparency',
        'desc': 'Building trust through transparent decision-making, auditable processes, and verifiable system behaviors throughout the Meta-Layer.'
    },
    'dp15-security-provenance': {
        'title': 'Security and Provenance',
        'desc': 'Ensuring security through comprehensive provenance tracking, secure infrastructure, and verifiable data lineage across all interactions.'
    },
    'dp16-roadmap-milestones': {
        'title': 'Roadmap and Milestones',
        'desc': 'Developing structured roadmaps with clear milestones that guide the evolution of the Meta-Layer while maintaining community alignment.'
    },
    'dp17-financial-sustainability': {
        'title': 'Financial Sustainability',
        'desc': 'Creating financial models and incentive structures that ensure the long-term sustainability and equitable growth of the Meta-Layer ecosystem.'
    },
    'dp18-feedback-reputation': {
        'title': 'Feedback Loops and Reputation',
        'desc': 'Implementing feedback mechanisms and reputation systems that reward positive contributions and maintain community standards.'
    },
    'dp19-community-engagement': {
        'title': 'Amplifying Presence and Community Engagement',
        'desc': 'Developing systems that amplify community participation, enhance visibility of contributions, and strengthen community bonds.'
    },
    'dp20-community-ownership': {
        'title': 'Community Ownership',
        'desc': 'Ensuring community ownership through decentralized governance, shared decision-making, and equitable distribution of value and control.'
    },
    'dp22-civic-memory-epistemic-continuity': {
        'title': 'Epistemic Continuity & Digital Artifacts',
        'desc': 'Preserving epistemic continuity through durable digital artifacts, provenance, and long-lived knowledge across the Meta-Layer.'
    },
    'dp23-universal-participation-linguistic-interoperability': {
        'title': 'Universal Participation & Linguistic Interoperability',
        'desc': 'Establishing universal participation and linguistic interoperability as foundational conditions for shared global sensemaking across languages and cultures.'
    },
}

# Two-letter abbreviations from the Noospheric Design Principles infographic.
DP_ABBREVIATIONS = {
    1: 'Au', 2: 'Ae', 3: 'Go', 4: 'So', 5: 'Ns', 6: 'Co',
    7: 'Si', 8: 'Cm', 9: 'In', 10: 'Ed', 21: 'Mm',
    11: 'Ai', 12: 'Cg', 13: 'Ac', 14: 'Tt', 15: 'Sp', 16: 'Rm', 17: 'Fs', 22: 'Ep', 23: 'Up',
    18: 'Fr', 19: 'Ap', 20: 'Ow',
}


def dp_image_url(dp_num: int) -> Optional[str]:
    """Static URL for a DP workgroup card image, or None if unknown."""
    from services.dp_images import dp_card_image_url

    if dp_num not in DP_ABBREVIATIONS:
        return None
    return dp_card_image_url(dp_num)


def _build_group_entry(group_name: str) -> dict:
    if group_name in DP_DESCRIPTIONS:
        dp_info = DP_DESCRIPTIONS[group_name]
        group_title = dp_info['title']
        description = dp_info['desc']
    else:
        group_title = group_name.replace('-', ' ').title()
        description = (
            f'Focuses on {group_title.lower()} standards and protocols '
            'for the Meta-Layer.'
        )
    return {
        'acronym': group_name,
        'name': format_dp_display_name(group_name, group_title),
        'type': 'Workgroup',
        'state': 'Active',
        'chairs': [f'Chair {i+1}' for i in range(1 + (hash(group_name) % 2))],
        'description': description,
        'members_require_approval': False,
    }


def _read_group_alias_acronyms() -> list[str]:
    for path in _GROUP_ALIASES_PATHS:
        if not path.is_file():
            continue
        acronyms: list[str] = []
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                match = re.search(r'xfilter-([^:]+):', line)
                if match:
                    acronyms.append(match.group(1))
        return acronyms
    return sorted(
        DP_DESCRIPTIONS.keys(),
        key=lambda acronym: extract_dp_number(acronym) or 0,
    )


def load_group_data():
    """Load group data from test files"""
    groups = []
    seen: set[str] = set()

    for group_name in _read_group_alias_acronyms():
        groups.append(_build_group_entry(group_name))
        seen.add(group_name)

    for group_name in sorted(
        DP_DESCRIPTIONS.keys(),
        key=lambda acronym: extract_dp_number(acronym) or 0,
    ):
        if group_name not in seen:
            groups.append(_build_group_entry(group_name))

    groups.append({
        'acronym': 'ml-governance',
        'name': 'Interface Governance',
        'type': 'Workgroup',
        'state': 'Active',
        'chairs': [],
        'description': 'Developing governance practices and standards for the interface.',
        'about': (
            'Developing governance practices and standards for the interface that enable '
            'safe human-AI coexistence; connection with greater trust, consent, context; '
            'and even human-AI flourishing.'
        ),
        'members_require_approval': False
    })

    return groups


# Module-level cache for routes (loaded on first import)
GROUPS = load_group_data()
