"""
Gov Hub models. Import all models so db.create_all() registers them.
Import order: identity -> coordination -> events -> artifact (Layer before EventLog).
"""
from models.identity import User, UserFollow, HypothesisAccount, UserLinkedAccount
from models.coordination import (
    Layer, LayerMember, LayerAdmin,
    Waitlist, WaitlistEntry, WaitlistMilestone, EmailUnsubscribe, WaitlistEmailSignup,
    Workgroup, WorkingGroupMember, WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest,
    Guild, GuildMembership, GuildInvitation, GuildLayerLink, GuildArtifactLink,
    Cluster, Role, RoleImage, RoleImageVote,
    Claim, Badge, BadgeSkin, BadgeCycle, OneTimeBadge,
    Vote, VoteEligibilitySnapshot, VoteCandidate, Ballot,
    Quest, QuestSubmission, Monument, Brick, BrickMessage,
)
from models.events import EventLog, StatusChange
from models.artifact import (
    Submission, SiteConfig, InscriptionOrder,
    Comment, DocumentHistory,
    Artifact, ArtifactRelation,
)
from models.collection import ArtifactCollection, ArtifactCollectionItem
from models.bridge import Bridge, BridgeSession

__all__ = [
    'User', 'UserFollow', 'HypothesisAccount', 'UserLinkedAccount',
    'EventLog', 'StatusChange',
    'Layer', 'LayerMember', 'LayerAdmin',
    'Waitlist', 'WaitlistEntry', 'WaitlistMilestone', 'EmailUnsubscribe', 'WaitlistEmailSignup',
    'Workgroup', 'WorkingGroupMember', 'WorkingGroupChair', 'CoordinatorRequest', 'WorkgroupMemberRequest',
    'Guild', 'GuildMembership', 'GuildInvitation', 'GuildLayerLink', 'GuildArtifactLink',
    'Cluster', 'Role', 'RoleImage', 'RoleImageVote',
    'Claim', 'Badge', 'BadgeSkin', 'BadgeCycle', 'OneTimeBadge',
    'Vote', 'VoteEligibilitySnapshot', 'VoteCandidate', 'Ballot',
    'Quest', 'QuestSubmission', 'Monument', 'Brick', 'BrickMessage',
    'Submission', 'SiteConfig', 'InscriptionOrder',
    'Comment', 'DocumentHistory',
    'Artifact', 'ArtifactRelation',
    'ArtifactCollection', 'ArtifactCollectionItem',
    'Bridge', 'BridgeSession',
]
