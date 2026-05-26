"""
Gov Hub models. Import all models so db.create_all() registers them.
Import order: identity -> coordination -> events -> artifact (Layer before EventLog).
"""
from models.identity import User, UserLinkedAccount
from models.coordination import (
    Layer, LayerMember, LayerAdmin,
    Waitlist, WaitlistEntry, WaitlistMilestone, EmailUnsubscribe, WaitlistEmailSignup,
    Workgroup, WorkgroupLayerLink, WorkingGroupMember, WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest,
    Guild, GuildMembership, GuildInvitation, GuildLayerLink, GuildArtifactLink, GuildQuestLink,
    LayerInvitation,
    Cluster, Role, RoleImage, RoleImageVote,
    Claim, Badge, BadgeSkin, BadgeCycle, OneTimeBadge,
    Vote, VoteEligibilitySnapshot, VoteCandidate, Ballot,
    Quest, QuestSubmission, Monument, Brick, BrickMessage,
)
from models.events import EventLog, StatusChange
from models.notifications import UserEventSubscription, UserNotification
from models.artifact import (
    Submission, SiteConfig, InscriptionOrder,
    Comment, DocumentHistory,
    Artifact, ArtifactRelation,
)
from models.dp_proposal import DpProposal
from models.collection import ArtifactCollection, ArtifactCollectionItem
from models.artifact_tag import ArtifactTag, ArtifactTagLink
from models.bridge import Bridge, BridgeSession

__all__ = [
    'User', 'UserLinkedAccount',
    'UserEventSubscription', 'UserNotification',
    'EventLog', 'StatusChange',
    'Layer', 'LayerMember', 'LayerAdmin',
    'Waitlist', 'WaitlistEntry', 'WaitlistMilestone', 'EmailUnsubscribe', 'WaitlistEmailSignup',
    'Workgroup', 'WorkgroupLayerLink', 'WorkingGroupMember', 'WorkingGroupChair', 'CoordinatorRequest', 'WorkgroupMemberRequest',
    'Guild', 'GuildMembership', 'GuildInvitation', 'LayerInvitation', 'GuildLayerLink', 'GuildArtifactLink', 'GuildQuestLink',
    'Cluster', 'Role', 'RoleImage', 'RoleImageVote',
    'Claim', 'Badge', 'BadgeSkin', 'BadgeCycle', 'OneTimeBadge',
    'Vote', 'VoteEligibilitySnapshot', 'VoteCandidate', 'Ballot',
    'Quest', 'QuestSubmission', 'Monument', 'Brick', 'BrickMessage',
    'Submission', 'SiteConfig', 'InscriptionOrder',
    'Comment', 'DocumentHistory',
    'Artifact', 'ArtifactRelation',
    'DpProposal',
    'ArtifactCollection', 'ArtifactCollectionItem',
    'ArtifactTag', 'ArtifactTagLink',
    'Bridge', 'BridgeSession',
]
