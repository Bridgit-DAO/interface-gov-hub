"""Workgroup position types for member nominations."""

WORKGROUP_POSITIONS = {
    'chair': {
        'label': 'Coordinator',
        'description': 'Leads the workgroup, sets agenda, and coordinates contributors.',
        'icon': 'fa-star',
    },
    'co_lead': {
        'label': 'Co-lead',
        'description': 'Shares recruitment, member approvals, and contributor coordination with the lead.',
        'icon': 'fa-user-friends',
    },
    'editor': {
        'label': 'Editor',
        'description': 'Edits drafts, coordinates document revisions, and maintains quality.',
        'icon': 'fa-pen',
    },
    'presenter': {
        'label': 'Presenter',
        'description': 'Presents workgroup output at meetings, webinars, or public sessions.',
        'icon': 'fa-microphone',
    },
    'facilitator': {
        'label': 'Facilitator',
        'description': 'Facilitates meetings and helps the group reach consensus.',
        'icon': 'fa-handshake',
        'placeholder': True,
    },
    'liaison': {
        'label': 'Liaison',
        'description': 'Coordinates with other workgroups, layers, or external partners.',
        'icon': 'fa-link',
        'placeholder': True,
    },
    'recorder': {
        'label': 'Recorder',
        'description': 'Captures meeting notes, decisions, and action items.',
        'icon': 'fa-clipboard-list',
        'placeholder': True,
    },
}

NOMINATION_STATUS_PENDING_NOMINEE = 'pending_nominee'
NOMINATION_STATUS_NOMINEE_ACCEPTED = 'nominee_accepted'
NOMINATION_STATUS_NOMINEE_DECLINED = 'nominee_declined'
NOMINATION_STATUS_APPROVED = 'approved'
NOMINATION_STATUS_REJECTED = 'rejected'

ACTIVE_NOMINATION_STATUSES = (
    NOMINATION_STATUS_PENDING_NOMINEE,
    NOMINATION_STATUS_NOMINEE_ACCEPTED,
    NOMINATION_STATUS_APPROVED,
)


def position_label(key: str) -> str:
    pos = WORKGROUP_POSITIONS.get(key or 'chair')
    return pos['label'] if pos else (key or 'Chair').replace('_', ' ').title()


def positions_for_api():
    return [
        {
            'key': key,
            'label': meta['label'],
            'description': meta['description'],
            'icon': meta.get('icon', 'fa-user'),
            'placeholder': bool(meta.get('placeholder')),
        }
        for key, meta in WORKGROUP_POSITIONS.items()
    ]


def status_label(status: str) -> str:
    labels = {
        NOMINATION_STATUS_PENDING_NOMINEE: 'Awaiting nominee',
        NOMINATION_STATUS_NOMINEE_ACCEPTED: 'Pending approval',
        NOMINATION_STATUS_NOMINEE_DECLINED: 'Declined by nominee',
        NOMINATION_STATUS_APPROVED: 'Approved',
        NOMINATION_STATUS_REJECTED: 'Rejected',
    }
    return labels.get(status or '', status or 'Unknown')
