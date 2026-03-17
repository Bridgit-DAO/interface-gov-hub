"""Group data service: load_group_data for workgroup/DP definitions."""
import re


def load_group_data():
    """Load group data from test files"""
    groups = []

    # Desirable Properties mapping for better names and descriptions
    dp_descriptions = {
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
        }
    }

    try:
        with open('/home/ubuntu/datatracker/test/data/group-aliases', 'r') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                match = re.search(r'xfilter-([^:]+):', line)
                if match:
                    group_name = match.group(1)

                    if group_name in dp_descriptions:
                        dp_info = dp_descriptions[group_name]
                        group_title = dp_info['title']
                        description = dp_info['desc']
                    else:
                        group_title = group_name.replace('-', ' ').title()
                        description = f'The {group_title} Workgroup focuses on {group_title.lower()} standards and protocols for the Internet.'

                    groups.append({
                        'acronym': group_name,
                        'name': f'{group_title} Workgroup',
                        'type': 'Workgroup',
                        'state': 'Active',
                        'chairs': [f'Chair {i+1}' for i in range(1 + (hash(group_name) % 2))],
                        'description': description,
                        'members_require_approval': False
                    })
    except FileNotFoundError:
        print("Group aliases file not found")

    # Interface Governance Workgroup (ML-GOVERNANCE) - always include
    groups.append({
        'acronym': 'ml-governance',
        'name': 'Interface Governance Workgroup',
        'type': 'Workgroup',
        'state': 'Active',
        'chairs': [],
        'description': 'Developing governance practices and standards for the interface.',
        'about': 'Developing governance practices and standards for the interface that enable safe human-AI coexistence; connection with greater trust, consent, context; and even human-AI flourishing.',
        'members_require_approval': False
    })

    return groups


# Module-level cache for routes (loaded on first import)
GROUPS = load_group_data()
