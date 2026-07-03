"""
Gov Hub models. Import all models so db.create_all() registers them.
Import order: identity -> coordination -> events -> artifact (Layer before EventLog).
"""
from models.referral_attribution import ReferralAttribution
from models.referral_landing import ReferralLanding
from models.layer_program import LayerProgram, LayerProgramSubmission
from models.scoped_email import ScopedEmailCampaign, ScopedEmailDelivery
from models.identity import User, UserLinkedAccount
from models.custodial_wallet import CustodialWallet
from models.layer_prefix import LayerPrefix
from models.coordination import (
    Layer, LayerMember, LayerAdmin,
    Waitlist, WaitlistEntry, WaitlistMilestone, EmailUnsubscribe, WaitlistEmailSignup,
    Workgroup, WorkgroupLayerLink, WorkingGroupMember, WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest,
    Guild, GuildMembership, GuildInvitation, GuildLayerLink, GuildArtifactLink, GuildQuestLink,
    LayerConnectionType, LayerConnection,
    LAYER_CONNECTION_CONNECTOR_KINDS, LAYER_CONNECTION_STATUSES,
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
    Comment, CommentLike, DocumentHistory,
    Artifact, ArtifactRelation,
)
from models.dp_proposal import DpProposal
from models.platform_invitation import PlatformInvitation, PlatformInvitationAcceptance
from models.collection import ArtifactCollection, ArtifactCollectionItem
from models.layer_tag import LayerTag, LayerTagLink, SUBJECT_ARTIFACT, SUBJECT_SUBMISSION
# Legacy tables (migrated to layer_tag); models kept for old DB rows if present
from models.artifact_tag import ArtifactTag, ArtifactTagLink
from models.bridge import Bridge, BridgeSession

__all__ = [
    'User', 'UserLinkedAccount', 'CustodialWallet',
    'UserEventSubscription', 'UserNotification',
    'EventLog', 'StatusChange',
    'Layer', 'LayerMember', 'LayerAdmin',
    'Waitlist', 'WaitlistEntry', 'WaitlistMilestone', 'EmailUnsubscribe', 'WaitlistEmailSignup',
    'Workgroup', 'WorkgroupLayerLink', 'WorkingGroupMember', 'WorkingGroupChair', 'CoordinatorRequest', 'WorkgroupMemberRequest',
    'Guild', 'GuildMembership', 'GuildInvitation', 'LayerInvitation', 'PlatformInvitation', 'PlatformInvitationAcceptance', 'GuildLayerLink', 'GuildArtifactLink', 'GuildQuestLink',
    'LayerConnectionType', 'LayerConnection',
    'LAYER_CONNECTION_CONNECTOR_KINDS', 'LAYER_CONNECTION_STATUSES',
    'Cluster', 'Role', 'RoleImage', 'RoleImageVote',
    'Claim', 'Badge', 'BadgeSkin', 'BadgeCycle', 'OneTimeBadge',
    'Vote', 'VoteEligibilitySnapshot', 'VoteCandidate', 'Ballot',
    'Quest', 'QuestSubmission', 'Monument', 'Brick', 'BrickMessage',
    'Submission', 'SiteConfig', 'InscriptionOrder',
    'Comment', 'CommentLike', 'DocumentHistory',
    'Artifact', 'ArtifactRelation',
    'DpProposal',
    'ArtifactCollection', 'ArtifactCollectionItem',
    'LayerTag', 'LayerTagLink', 'SUBJECT_ARTIFACT', 'SUBJECT_SUBMISSION',
    'ArtifactTag', 'ArtifactTagLink',
    'Bridge', 'BridgeSession',
    'ReferralAttribution',
    'ReferralLanding',
    'LayerProgram',
    'LayerProgramSubmission',
    'ScopedEmailCampaign',
    'ScopedEmailDelivery',
    'LayerPrefix',
]
