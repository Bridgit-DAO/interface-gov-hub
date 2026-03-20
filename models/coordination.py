"""Coordination models: coordinators, workgroups, layers, badges, votes, etc."""
from extensions import db
from datetime import datetime
from uuid import uuid4


# ============================================================================
# Coordinator and Workgroup Request Models
# ============================================================================

class CoordinatorRequest(db.Model):
    """User-requested coordinator role; requires approval. Ties coordinator to user id."""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    group_acronym = db.Column(db.String(50), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)  # known user
    username = db.Column(db.String(100), index=True)  # always set for lookup
    display_name = db.Column(db.String(200))  # for display in lists
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.String(100), nullable=True)


class WorkgroupMemberRequest(db.Model):
    """Pending member join when workgroup has members_require_approval=True."""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    group_acronym = db.Column(db.String(50), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    user_name = db.Column(db.String(100), index=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.String(100), nullable=True)


class WorkingGroupChair(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    group_acronym = db.Column(db.String(50), index=True)
    chair_name = db.Column(db.String(100))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)  # set when created from CoordinatorRequest
    approved = db.Column(db.Boolean, default=False)
    set_at = db.Column(db.DateTime, default=datetime.utcnow)


class WorkingGroupMember(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    group_acronym = db.Column(db.String(50), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)  # primary lookup
    user_name = db.Column(db.String(100), index=True)  # for display
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# Badge System Models (BadgeSkin, BadgeCycle, OneTimeBadge)
# ============================================================================

class BadgeSkin(db.Model):
    """Layout template for rendering a badge"""
    __tablename__ = 'badge_skin'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    layout_spec = db.Column(db.JSON, nullable=True)  # regions, placement, font sizes, etc.
    preview_image_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'layout_spec': self.layout_spec,
            'preview_image_url': self.preview_image_url,
        }


class BadgeCycle(db.Model):
    """Tracks one submission+voting cycle for a role or workgroup badge"""
    __tablename__ = 'badge_cycle'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type = db.Column(db.String(20), nullable=False, index=True)  # 'role' | 'workgroup'
    entity_id = db.Column(db.String(100), nullable=False, index=True)   # role_slug or workgroup id
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)

    first_submission_at = db.Column(db.DateTime, nullable=True)
    submission_ends_at = db.Column(db.DateTime, nullable=True)
    voting_starts_at = db.Column(db.DateTime, nullable=True)
    voting_ends_at = db.Column(db.DateTime, nullable=True)

    # submission | delay | voting | completed
    status = db.Column(db.String(20), default='submission', index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'layer_id': self.layer_id,
            'first_submission_at': self.first_submission_at.isoformat() if self.first_submission_at else None,
            'submission_ends_at': self.submission_ends_at.isoformat() if self.submission_ends_at else None,
            'voting_starts_at': self.voting_starts_at.isoformat() if self.voting_starts_at else None,
            'voting_ends_at': self.voting_ends_at.isoformat() if self.voting_ends_at else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# Layers, Workgroups, and Guilds Models
# ============================================================================

class Layer(db.Model):
    """Primary organizing entity for submissions, documents, and workgroups (formerly Project)"""
    __tablename__ = 'layer'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # Initiator
    initiator_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    # Status (descriptive, not evaluative)
    status = db.Column(db.String(20), default='proposed', index=True)
    # proposed, active, stabilizing, maintaining, dormant, concluded, archived
    status_reason = db.Column(db.Text, nullable=True)
    
    # Image
    image_url = db.Column(db.String(500), nullable=True)
    
    # Admin approval
    approval_status = db.Column(db.String(20), default='pending', index=True)
    # pending, approved, rejected
    approved_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Mission and description
    mission = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    about_content = db.Column(db.Text, nullable=True)  # Markdown for /about/ page
    carousel_config = db.Column(db.Text, nullable=True)  # JSON: {auto_items: {...}, custom_items: [...]}

    # Activity tracking
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Succession
    superseded_by_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Immortalize wizard: opt-in for tier pricing
    offer_tier_pricing = db.Column(db.Boolean, default=False)
    
    # Meta-domain: ordinal-sourced domain for layer identity (e.g. example.com.meta)
    meta_domain_inscription_id = db.Column(db.String(255), nullable=True, index=True)
    meta_domain = db.Column(db.Text, nullable=True)  # Cached domain string from ordinal content
    
    # Relationships
    initiator = db.relationship('User', foreign_keys=[initiator_id], backref='initiated_layers')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_layers')
    superseded_by = db.relationship('Layer', remote_side=[id], backref='supersedes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'name': self.name,
            'slug': self.slug,
            'initiator_id': self.initiator_id,
            'initiator_name': self.initiator.displayName or self.initiator.username if self.initiator else None,
            'status': self.status,
            'status_reason': self.status_reason,
            'approval_status': self.approval_status,
            'mission': self.mission,
            'description': self.description,
            'about_content': self.about_content,
            'carousel_config': self.carousel_config,
            'image_url': self.image_url,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'meta_domain_inscription_id': getattr(self, 'meta_domain_inscription_id', None),
            'meta_domain': getattr(self, 'meta_domain', None),
        }


class LayerMember(db.Model):
    """Track layer membership and referrals (formerly ProjectMember)"""
    __tablename__ = 'layer_member'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Referral tracking
    referred_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    referral_code = db.Column(db.String(50), nullable=True)  # The referral code used to join
    
    # Role in project (optional)
    role = db.Column(db.String(100), nullable=True)  # contributor, maintainer, etc.
    
    # Status
    status = db.Column(db.String(20), default='active')  # active, inactive, left
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    left_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    layer = db.relationship('Layer', backref='layer_members', foreign_keys=[layer_id])
    user = db.relationship('User', backref='layer_memberships', foreign_keys=[user_id])
    referred_by = db.relationship('User', backref='referrals_made', foreign_keys=[referred_by_id])
    
    # Unique constraint: one membership per user per layer
    __table_args__ = (
        db.UniqueConstraint('layer_id', 'user_id', name='unique_layer_member'),
        db.Index('idx_layer_member_status', 'status'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'user_id': self.user_id,
            'referred_by_id': self.referred_by_id,
            'role': self.role,
            'status': self.status,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'left_at': self.left_at.isoformat() if self.left_at else None,
        }


class LayerAdmin(db.Model):
    """Assigned layer admins (in addition to initiator/owner). Owner cannot be removed. (formerly ProjectAdmin)"""
    __tablename__ = 'layer_admin'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('layer_id', 'user_id', name='uq_layer_admin_layer_user'),
    )
    
    layer = db.relationship('Layer', backref=db.backref('layer_admins', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('layer_admin_of', lazy='dynamic'))


class OneTimeBadge(db.Model):
    """A badge for a specific one-time task"""
    __tablename__ = 'one_time_badge'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Timing
    earliest_start = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)  # # of badges to award
    submission_days = db.Column(db.Integer, default=14, nullable=False)
    delay_days = db.Column(db.Integer, default=2)
    voting_days = db.Column(db.Integer, default=7, nullable=False)

    # Voting
    voting_regular = db.Column(db.Boolean, default=True)
    voting_time_weighted = db.Column(db.Boolean, default=False)
    voting_quadratic = db.Column(db.Boolean, default=False)

    # Skin
    badge_skin_id = db.Column(db.String(36), db.ForeignKey('badge_skin.id'), nullable=True)

    # Lifecycle: draft | upcoming | submission | delay | voting | completed
    status = db.Column(db.String(20), default='draft', index=True)
    first_submission_at = db.Column(db.DateTime, nullable=True)
    submission_ends_at = db.Column(db.DateTime, nullable=True)
    voting_starts_at = db.Column(db.DateTime, nullable=True)
    voting_ends_at = db.Column(db.DateTime, nullable=True)

    created_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    layer = db.relationship('Layer', backref=db.backref('one_time_badges', lazy=True))
    badge_skin = db.relationship('BadgeSkin', foreign_keys=[badge_skin_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'title': self.title,
            'description': self.description,
            'earliest_start': self.earliest_start.isoformat() if self.earliest_start else None,
            'quantity': self.quantity,
            'submission_days': self.submission_days,
            'delay_days': self.delay_days,
            'voting_days': self.voting_days,
            'voting_regular': self.voting_regular,
            'voting_time_weighted': self.voting_time_weighted,
            'voting_quadratic': self.voting_quadratic,
            'badge_skin_id': self.badge_skin_id,
            'status': self.status,
            'first_submission_at': self.first_submission_at.isoformat() if self.first_submission_at else None,
            'submission_ends_at': self.submission_ends_at.isoformat() if self.submission_ends_at else None,
            'voting_starts_at': self.voting_starts_at.isoformat() if self.voting_starts_at else None,
            'voting_ends_at': self.voting_ends_at.isoformat() if self.voting_ends_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Waitlist(db.Model):
    """Project waitlist: name, description, public/private, referrals, active, dates, max, milestones."""
    __tablename__ = 'waitlist'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    public = db.Column(db.Boolean, default=True)  # False = only project members or link-holders see it
    referrals = db.Column(db.Boolean, default=False)  # If True, joiners get referral link; referrer gets credit
    active = db.Column(db.Boolean, default=True)  # If False, tab not shown
    start_date = db.Column(db.DateTime, nullable=False)  # Join disabled until start
    closing_date = db.Column(db.DateTime, nullable=True)
    max_number = db.Column(db.Integer, nullable=True)  # "Full" when reached
    archived = db.Column(db.Boolean, default=False)  # Soft delete / archive
    
    # Image
    image_url = db.Column(db.String(500), nullable=True)
    
    milestones = db.Column(db.Boolean, default=False)
    show_milestones = db.Column(db.String(20), default='all')  # 'all', 'next', 'future'
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    layer = db.relationship('Layer', backref=db.backref('waitlists', lazy='dynamic'))
    
    def to_dict(self):
        user_count = WaitlistEntry.query.filter_by(waitlist_id=self.id, left_at=None).count()
        email_count = WaitlistEmailSignup.query.filter_by(waitlist_id=self.id, left_at=None).filter(WaitlistEmailSignup.verified_at.isnot(None)).count()
        count = user_count + email_count
        try:
            max_val = int(self.max_number) if self.max_number not in (None, '') else None
        except (ValueError, TypeError):
            max_val = None
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'name': self.name,
            'description': self.description,
            'public': self.public,
            'referrals': self.referrals,
            'active': self.active,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'closing_date': self.closing_date.isoformat() if self.closing_date else None,
            'max_number': self.max_number,
            'archived': self.archived,
            'image_url': self.image_url,
            'milestones': self.milestones,
            'show_milestones': self.show_milestones,
            'count': count,
            'full': max_val is not None and count >= max_val,
            'closed': self.closing_date is not None and datetime.utcnow() >= self.closing_date,
            'started': self.start_date is not None and datetime.utcnow() >= self.start_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WaitlistEntry(db.Model):
    """One user on a waitlist; can leave (left_at set). Position = order of join."""
    __tablename__ = 'waitlist_entry'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    waitlist_id = db.Column(db.String(36), db.ForeignKey('waitlist.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False)  # 1-based queue order
    referred_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    referral_code = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(255), nullable=True)  # Track signup source (e.g., 'embed:example.com', 'direct', 'referral')
    source_url = db.Column(db.String(500), nullable=True)  # Full URL where signup occurred
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    left_at = db.Column(db.DateTime, nullable=True)  # If set, user left
    
    waitlist = db.relationship('Waitlist', backref=db.backref('entries', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('waitlist_entries', lazy='dynamic'))
    referred_by = db.relationship('User', foreign_keys=[referred_by_id])
    
    __table_args__ = (db.UniqueConstraint('waitlist_id', 'user_id', name='uq_waitlist_entry_user'),)


class EmailUnsubscribe(db.Model):
    """Users/emails who opted out of project emails."""
    __tablename__ = 'email_unsubscribe'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.Index('idx_email_unsub_layer_user', 'layer_id', 'user_id'), db.Index('idx_email_unsub_layer_email', 'layer_id', 'email'),)


class WaitlistEmailSignup(db.Model):
    """Email-only waitlist signup (embed). Separate from WaitlistEntry (user-based)."""
    __tablename__ = 'waitlist_email_signup'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    waitlist_id = db.Column(db.String(36), db.ForeignKey('waitlist.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=True)
    verification_token = db.Column(db.String(64), nullable=True, index=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    position = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(255), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    left_at = db.Column(db.DateTime, nullable=True)
    
    waitlist = db.relationship('Waitlist', backref=db.backref('email_signups', lazy='dynamic'))


class WaitlistMilestone(db.Model):
    """Milestone: activates at threshold (number on waitlist). Order by threshold."""
    __tablename__ = 'waitlist_milestone'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    waitlist_id = db.Column(db.String(36), db.ForeignKey('waitlist.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    threshold = db.Column(db.Integer, nullable=False)  # Number on waitlist to activate (ordering = by this)
    action_type = db.Column(db.String(50), nullable=True)  # e.g. email, badge, webhook
    action_payload = db.Column(db.Text, nullable=True)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    waitlist = db.relationship('Waitlist', backref=db.backref('milestone_list', lazy='dynamic', order_by='WaitlistMilestone.threshold'))


class Workgroup(db.Model):
    """Task-focused group within a layer"""
    __tablename__ = 'working_group'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid4()))
    acronym = db.Column(db.String(50), unique=True, index=True)  # Legacy field
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), index=True)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(50), nullable=True)  # Legacy field
    state = db.Column(db.String(20), nullable=True)  # Legacy field
    
    # Layer relationship (required)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    
    # Image
    image_url = db.Column(db.String(500), nullable=True)

    # Badge settings
    badge_enabled = db.Column(db.Boolean, default=False)
    badge_submission_days = db.Column(db.Integer, nullable=True)
    badge_voting_days = db.Column(db.Integer, nullable=True)
    badge_delay_days = db.Column(db.Integer, nullable=True)
    badge_earliest_start = db.Column(db.Date, nullable=True)
    badge_cycle_spacing_days = db.Column(db.Integer, default=365)
    badge_end_date = db.Column(db.Date, nullable=True)
    badge_end_at_next_closing = db.Column(db.Boolean, default=False)
    badge_voting_regular = db.Column(db.Boolean, default=True)
    badge_voting_time_weighted = db.Column(db.Boolean, default=False)
    badge_voting_quadratic = db.Column(db.Boolean, default=False)
    badge_skin_id = db.Column(db.String(36), db.ForeignKey('badge_skin.id'), nullable=True)

    # Coordinator (formerly "chair")
    coordinator_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    
    # Status
    status = db.Column(db.String(20), default='active', index=True)
    # active, inactive, completed, archived, concluded
    
    # Approval
    approval_status = db.Column(db.String(20), default='pending', index=True)
    # pending, approved, rejected
    approved_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('workgroups', lazy=True))
    coordinator = db.relationship('User', foreign_keys=[coordinator_id], backref='coordinated_workgroups')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_workgroups')
    
    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'acronym': self.acronym,
            'name': self.name,
            'slug': self.slug or self.acronym,
            'layer_id': self.layer_id,
            'layer_name': self.layer.name if self.layer else None,
            'coordinator_id': self.coordinator_id,
            'coordinator_name': self.coordinator.displayName or self.coordinator.username if self.coordinator else None,
            'status': self.status,
            'approval_status': self.approval_status,
            'description': self.description,
            'image_url': self.image_url,
            'type': self.type,
            'state': self.state,
            'badge_enabled': self.badge_enabled,
            'badge_submission_days': self.badge_submission_days,
            'badge_voting_days': self.badge_voting_days,
            'badge_delay_days': self.badge_delay_days,
            'badge_earliest_start': self.badge_earliest_start.isoformat() if self.badge_earliest_start else None,
            'badge_cycle_spacing_days': self.badge_cycle_spacing_days,
            'badge_end_date': self.badge_end_date.isoformat() if self.badge_end_date else None,
            'badge_end_at_next_closing': self.badge_end_at_next_closing,
            'badge_voting_regular': self.badge_voting_regular,
            'badge_voting_time_weighted': self.badge_voting_time_weighted,
            'badge_voting_quadratic': self.badge_voting_quadratic,
            'badge_skin_id': self.badge_skin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Guild(db.Model):
    """Cross-project collaboration group"""
    __tablename__ = 'guild'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # Initiator (automatically becomes admin)
    initiator_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    # Description
    description = db.Column(db.Text, nullable=True)
    
    # Image
    image_url = db.Column(db.String(500), nullable=True)
    
    # Status (guilds don't require approval - instant registration)
    status = db.Column(db.String(20), default='active', index=True)
    # active, archived
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    initiator = db.relationship('User', backref='initiated_guilds')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'initiator_id': self.initiator_id,
            'initiator_name': self.initiator.displayName or self.initiator.username if self.initiator else None,
            'description': self.description,
            'image_url': self.image_url,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class GuildMembership(db.Model):
    """Guild membership with roles"""
    __tablename__ = 'guild_membership'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    guild_id = db.Column(db.String(36), db.ForeignKey('guild.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Role: initiator, admin, member
    role = db.Column(db.String(20), default='member', nullable=False)
    
    # Timestamps
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    guild = db.relationship('Guild', backref=db.backref('memberships', lazy=True))
    user = db.relationship('User', backref=db.backref('guild_memberships', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('guild_id', 'user_id', name='unique_guild_membership'),
        db.Index('idx_guild_membership_guild', 'guild_id'),
        db.Index('idx_guild_membership_user', 'user_id'),
    )


class GuildInvitation(db.Model):
    """Guild invitation system"""
    __tablename__ = 'guild_invitation'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    guild_id = db.Column(db.String(36), db.ForeignKey('guild.id'), nullable=False, index=True)
    inviter_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    invitee_email = db.Column(db.String(255), nullable=False, index=True)
    invitee_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)  # If user exists
    
    # Status
    status = db.Column(db.String(20), default='pending', index=True)
    # pending, accepted, declined, expired
    
    # Token for email verification
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # 7 days from creation
    responded_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    guild = db.relationship('Guild', backref=db.backref('invitations', lazy=True))
    inviter = db.relationship('User', foreign_keys=[inviter_id], backref='sent_guild_invitations')
    invitee = db.relationship('User', foreign_keys=[invitee_id], backref='received_guild_invitations')
    
    __table_args__ = (
        db.Index('idx_guild_invitation_guild', 'guild_id'),
        db.Index('idx_guild_invitation_status', 'status'),
        db.Index('idx_guild_invitation_token', 'token'),
    )


# ============================================================================
# Roles, Claims, and Badges Models
# ============================================================================

class Cluster(db.Model):
    """Organizational grouping of roles within a project"""
    __tablename__ = 'cluster'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    cluster_slug = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(20), default='active')
    # active, archived
    
    # Audit
    created_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('clusters', lazy=True))
    created_by = db.relationship('User', backref='created_clusters')
    
    __table_args__ = (
        db.UniqueConstraint('layer_id', 'cluster_slug', name='unique_cluster_slug_per_layer'),
        db.Index('idx_cluster_layer_status', 'layer_id', 'status'),
        db.Index('idx_cluster_layer_order', 'layer_id', 'order'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'layer_id': self.layer_id,
            'cluster_slug': self.cluster_slug,
            'name': self.name,
            'description': self.description,
            'order': self.order,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Role(db.Model):
    """Defined unit of responsibility scoped to a project"""
    __tablename__ = 'role'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    role_slug = db.Column(db.String(100), nullable=False)
    
    # Titles
    title_guild = db.Column(db.String(255), nullable=False)
    title_operational = db.Column(db.String(255), nullable=True)
    
    # Description and image
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    
    # Organization
    cluster_id = db.Column(db.String(36), db.ForeignKey('cluster.id'), nullable=True)
    order = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(20), default='draft', index=True)
    # draft, approved, deprecated, archived
    
    # Visibility
    public_visible = db.Column(db.Boolean, default=False, index=True)
    
    # Configuration
    claim_requires_approval = db.Column(db.Boolean, default=False)
    requires_election = db.Column(db.Boolean, default=False)  # Role must be filled via election vote
    badge_enabled = db.Column(db.Boolean, default=True)
    badge_requires_approval = db.Column(db.Boolean, default=True)

    # Badge cycle settings
    badge_submission_days = db.Column(db.Integer, default=14)
    badge_voting_days = db.Column(db.Integer, default=7)
    badge_delay_days = db.Column(db.Integer, default=2)
    badge_earliest_start = db.Column(db.Date, nullable=True)
    badge_cycle_spacing_days = db.Column(db.Integer, default=365)
    badge_end_date = db.Column(db.Date, nullable=True)
    badge_end_at_next_closing = db.Column(db.Boolean, default=False)

    # Voting type flags
    badge_voting_regular = db.Column(db.Boolean, default=True)
    badge_voting_time_weighted = db.Column(db.Boolean, default=False)
    badge_voting_quadratic = db.Column(db.Boolean, default=False)

    # Badge skin (layout template)
    badge_skin_id = db.Column(db.String(36), db.ForeignKey('badge_skin.id'), nullable=True)

    # Civic Mason: badge from this role grants brick placement eligibility
    civic_mason_eligible = db.Column(db.Boolean, default=False)

    # Audit
    created_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    approved_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('roles', lazy=True))
    cluster = db.relationship('Cluster', backref=db.backref('roles', lazy=True))
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_roles')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_roles')
    
    __table_args__ = (
        db.UniqueConstraint('layer_id', 'role_slug', name='unique_role_slug_per_layer'),
        db.Index('idx_role_layer_status', 'layer_id', 'status'),
        db.Index('idx_role_layer_visible', 'layer_id', 'public_visible'),
        db.Index('idx_role_status_visible', 'status', 'public_visible'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'layer_id': self.layer_id,
            'role_slug': self.role_slug,
            'slug': self.role_slug,
            'title_guild': self.title_guild,
            'title_operational': self.title_operational,
            'description': self.description,
            'image_url': self.image_url,
            'cluster_id': self.cluster_id,
            'order': self.order,
            'status': self.status,
            'public_visible': self.public_visible,
            'claim_requires_approval': self.claim_requires_approval,
            'requires_election': getattr(self, 'requires_election', False),
            'badge_enabled': self.badge_enabled,
            'badge_requires_approval': self.badge_requires_approval,
            'civic_mason_eligible': getattr(self, 'civic_mason_eligible', False),
            'badge_submission_days': self.badge_submission_days,
            'badge_voting_days': self.badge_voting_days,
            'badge_delay_days': self.badge_delay_days,
            'badge_earliest_start': self.badge_earliest_start.isoformat() if self.badge_earliest_start else None,
            'badge_cycle_spacing_days': self.badge_cycle_spacing_days,
            'badge_end_date': self.badge_end_date.isoformat() if self.badge_end_date else None,
            'badge_end_at_next_closing': self.badge_end_at_next_closing,
            'badge_voting_regular': self.badge_voting_regular,
            'badge_voting_time_weighted': self.badge_voting_time_weighted,
            'badge_voting_quadratic': self.badge_voting_quadratic,
            'badge_skin_id': self.badge_skin_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class RoleImage(db.Model):
    """Visual representation proposed for a role"""
    __tablename__ = 'role_image'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True, index=True)
    role_slug = db.Column(db.String(100), nullable=False, index=True)  # kept for backward compat

    # Polymorphic entity reference
    entity_type = db.Column(db.String(20), default='role', index=True)  # 'role' | 'workgroup' | 'one_time_badge'
    entity_id = db.Column(db.String(100), nullable=True, index=True)    # role_slug, wg id, or otb id

    # Cycle association
    cycle_id = db.Column(db.String(36), db.ForeignKey('badge_cycle.id'), nullable=True, index=True)

    # Source
    source_type = db.Column(db.String(20), nullable=False)  # 'upload', 'url', 'ordinal'
    image_url = db.Column(db.String(500), nullable=True)  # For upload or URL source
    file_path = db.Column(db.String(500), nullable=True)  # For uploaded files
    
    # Ordinal metadata (optional)
    chain = db.Column(db.String(50), nullable=True)  # 'bitcoin', etc.
    inscription_id = db.Column(db.String(255), nullable=True, index=True)
    content_type = db.Column(db.String(100), nullable=True)  # MIME type
    
    # Status and promotion
    is_primary = db.Column(db.Boolean, default=False, index=True)  # Primary role image
    is_hidden = db.Column(db.Boolean, default=False, index=True)  # Hidden by admin
    
    # Voting (aggregated)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    net_score = db.Column(db.Integer, default=0, index=True)  # upvotes - downvotes
    
    # Admin actions
    admin_note = db.Column(db.Text, nullable=True)
    promoted_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    promoted_at = db.Column(db.DateTime, nullable=True)
    
    # Audit
    submitted_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    submitted_by = db.relationship('User', foreign_keys=[submitted_by_id], backref='submitted_role_images')
    promoted_by = db.relationship('User', foreign_keys=[promoted_by_id], backref='promoted_role_images')
    
    __table_args__ = (
        db.Index('idx_role_image_role_primary', 'role_slug', 'is_primary'),
        db.Index('idx_role_image_role_score', 'role_slug', 'net_score'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'role_slug': self.role_slug,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'cycle_id': self.cycle_id,
            'source_type': self.source_type,
            'image_url': self.image_url,
            'file_path': self.file_path,
            'chain': self.chain,
            'inscription_id': self.inscription_id,
            'content_type': self.content_type,
            'is_primary': self.is_primary,
            'is_hidden': self.is_hidden,
            'upvotes': self.upvotes,
            'downvotes': self.downvotes,
            'net_score': self.net_score,
            'admin_note': self.admin_note,
            'submitted_by_id': self.submitted_by_id,
            'submitted_by_name': self.submitted_by.displayName or self.submitted_by.username if self.submitted_by else 'Unknown',
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'promoted_by_id': self.promoted_by_id,
            'promoted_at': self.promoted_at.isoformat() if self.promoted_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class RoleImageVote(db.Model):
    """User vote on a role image proposal"""
    __tablename__ = 'role_image_vote'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    image_id = db.Column(db.String(36), db.ForeignKey('role_image.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Vote value: 1 (upvote) or -1 (downvote)
    value = db.Column(db.Integer, nullable=False)  # 1 or -1
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    image = db.relationship('RoleImage', backref=db.backref('votes', lazy=True))
    user = db.relationship('User', backref=db.backref('role_image_votes', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('image_id', 'user_id', name='unique_user_image_vote'),
        db.Index('idx_vote_image', 'image_id'),
        db.Index('idx_vote_user', 'user_id'),
    )


class Claim(db.Model):
    """User's declaration of stewarding a role"""
    __tablename__ = 'claim'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    role_id = db.Column(db.String(36), db.ForeignKey('role.id'), nullable=False, index=True)
    claimant_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Intent and evidence
    intent = db.Column(db.Text, nullable=True)
    evidence_links = db.Column(db.JSON, default=list)
    
    # Status
    status = db.Column(db.String(20), default='active', index=True)
    # active, pending_approval, paused, expired, revoked
    
    # Approval (if required)
    approval_required = db.Column(db.Boolean, default=False)
    approved_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Term (optional time-bounding)
    term_start = db.Column(db.Date, nullable=True)
    term_end = db.Column(db.Date, nullable=True)
    term_duration_days = db.Column(db.Integer, nullable=True)
    term_status = db.Column(db.String(20), nullable=True)
    # active, expired, paused, canceled
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('claims', lazy=True))
    role = db.relationship('Role', backref=db.backref('claims', lazy=True))
    claimant = db.relationship('User', foreign_keys=[claimant_id], backref='role_claims')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_claims')
    
    __table_args__ = (
        db.Index('idx_claim_layer_status', 'layer_id', 'status'),
        db.Index('idx_claim_role_status', 'role_id', 'status'),
        db.Index('idx_claim_claimant_status', 'claimant_id', 'status'),
        db.Index('idx_claim_created', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'layer_id': self.layer_id,
            'role_id': self.role_id,
            'claimant_id': self.claimant_id,
            'intent': self.intent,
            'evidence_links': self.evidence_links,
            'status': self.status,
            'approval_required': self.approval_required,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'term_start': self.term_start.isoformat() if self.term_start else None,
            'term_end': self.term_end.isoformat() if self.term_end else None,
            'term_duration_days': self.term_duration_days,
            'term_status': self.term_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Badge(db.Model):
    """Recognition artifact linked to a claim"""
    __tablename__ = 'badge'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    claim_id = db.Column(db.String(36), db.ForeignKey('claim.id'), nullable=False, index=True)
    role_id = db.Column(db.String(36), db.ForeignKey('role.id'), nullable=False)
    claimant_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    requested_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    # Badge type
    badge_type = db.Column(db.String(50), default='role_badge')
    # role_badge, founding_wave_badge, term_renewal_marker
    
    # Status
    status = db.Column(db.String(20), default='requested', index=True)
    # requested, needs_info, approved, issued, denied, canceled
    
    # Evidence
    evidence_links = db.Column(db.JSON, default=list)
    
    # Custody
    custody_mode = db.Column(db.String(20), default='user_wallet')
    # user_wallet, overweb_treasury
    btc_taproot_address = db.Column(db.String(255), nullable=True)
    
    # Approval
    approved_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approval_note = db.Column(db.Text, nullable=True)
    
    # Issuance (ordinal metadata)
    issuance_kind = db.Column(db.String(20), default='offchain')
    # offchain, ordinal
    inscription_id = db.Column(db.String(255), nullable=True)
    tx_ref = db.Column(db.String(255), nullable=True)
    chain = db.Column(db.String(50), default='bitcoin', nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('badges', lazy=True))
    claim = db.relationship('Claim', backref=db.backref('badges', lazy=True))
    role = db.relationship('Role', backref=db.backref('badges', lazy=True))
    claimant = db.relationship('User', foreign_keys=[claimant_id], backref='badges_received')
    requested_by = db.relationship('User', foreign_keys=[requested_by_id], backref='badges_requested')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='badges_approved')
    
    __table_args__ = (
        db.Index('idx_badge_layer_status', 'layer_id', 'status'),
        db.Index('idx_badge_claim_status', 'claim_id', 'status'),
        db.Index('idx_badge_status', 'status'),
        db.Index('idx_badge_created', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'claim_id': self.claim_id,
            'role_id': self.role_id,
            'claimant_id': self.claimant_id,
            'badge_type': self.badge_type,
            'status': self.status,
            'evidence_links': self.evidence_links,
            'custody_mode': self.custody_mode,
            'btc_taproot_address': self.btc_taproot_address,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'approval_note': self.approval_note,
            'issuance_kind': self.issuance_kind,
            'inscription_id': self.inscription_id,
            'tx_ref': self.tx_ref,
            'chain': self.chain,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# ================================================================
# QUEST + QUEST SUBMISSION (GOV-HUB-3 Phase 2.1)
# ================================================================

class Quest(db.Model):
    """Layer-scoped bounty/contribution task. Submissions link via QuestSubmission."""
    __tablename__ = 'quest'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    creator_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quest_type = db.Column(db.String(50), default='contribution', nullable=False, index=True)
    difficulty = db.Column(db.String(20), default='medium', nullable=False)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)
    acceptance_criteria = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    layer = db.relationship('Layer', backref=db.backref('quests', lazy='dynamic'))
    creator = db.relationship('User', backref=db.backref('created_quests', lazy='dynamic'))


class QuestSubmission(db.Model):
    """Submission of an artifact (e.g. draft) for a quest. Tracks review state."""
    __tablename__ = 'quest_submission'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    quest_id = db.Column(db.String(36), db.ForeignKey('quest.id'), nullable=False, index=True)
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)
    submitter_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending_review', nullable=False, index=True)
    review_notes = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    quest = db.relationship('Quest', backref=db.backref('submissions', lazy='dynamic'))
    artifact = db.relationship('Artifact', backref=db.backref('quest_submissions', lazy='dynamic'))
    submitter = db.relationship('User', foreign_keys=[submitter_user_id])
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_user_id])


# ================================================================
# MONUMENT (GOV-HUB-3 Phase 2.5 — Digital Monuments Registry)
# ================================================================

class Monument(db.Model):
    """Layer-scoped digital monument; references external URI, links to artifacts."""
    __tablename__ = 'monument'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    monument_type = db.Column(db.String(50), default='reference', nullable=False, index=True)
    steward_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    uri = db.Column(db.String(500), nullable=True)
    provenance = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    layer = db.relationship('Layer', backref=db.backref('monuments', lazy='dynamic'))
    steward = db.relationship('User', backref=db.backref('stewarded_monuments', lazy='dynamic'))


# ================================================================
# BRICK (GOV-HUB-3 Phase 3.2 — Civic Mason)
# Global wall; not layer-scoped. Badge-gated placement.
# ================================================================

class Brick(db.Model):
    """Civic Mason brick: global wall. Requires Civic Mason-eligible badge to place."""
    __tablename__ = 'brick'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    grid_x = db.Column(db.Float, nullable=False)  # Half-offset: row 0 = int, row 1 = .5, 1.5, ...
    grid_y = db.Column(db.Float, nullable=False)
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)
    badge_id = db.Column(db.String(36), db.ForeignKey('badge.id'), nullable=True, index=True)
    year = db.Column(db.Integer, nullable=False)  # For annual color palette
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('grid_x', 'grid_y', name='uq_brick_position'),
        db.Index('idx_brick_grid', 'grid_x', 'grid_y'),
    )

    user = db.relationship('User', backref=db.backref('bricks', lazy='dynamic'))
    artifact = db.relationship('Artifact', backref=db.backref('bricks', lazy='dynamic'), foreign_keys=[artifact_id])
    badge = db.relationship('Badge', backref=db.backref('bricks', lazy='dynamic'), foreign_keys=[badge_id])
    messages = db.relationship('BrickMessage', backref='brick', cascade='all, delete-orphan', lazy='dynamic', order_by='BrickMessage.created_at')

    def to_dict(self):
        latest = BrickMessage.query.filter_by(brick_id=self.id).order_by(BrickMessage.created_at.desc()).first()
        return {
            'id': self.id,
            'user_id': self.user_id,
            'grid_x': self.grid_x,
            'grid_y': self.grid_y,
            'message': (latest.message or '') if latest else '',
            'artifact_id': self.artifact_id,
            'badge_id': self.badge_id,
            'year': self.year,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BrickMessage(db.Model):
    """Append-only message history for a brick."""
    __tablename__ = 'brick_message'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    brick_id = db.Column(db.String(36), db.ForeignKey('brick.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    message = db.Column(db.String(200), nullable=False, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('brick_messages', lazy='dynamic'))


# ================================================================
# VOTING MODELS
# ================================================================

class Vote(db.Model):
    """A vote/ballot on a draft submission within a project context."""
    __tablename__ = 'vote'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    submission_id = db.Column(db.String(36), db.ForeignKey('submission.id'), nullable=True, index=True)
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)
    created_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    
    quorum_count = db.Column(db.Integer, nullable=False)
    win_threshold = db.Column(db.Float, nullable=False, default=0.5)
    
    status = db.Column(db.String(20), nullable=False, default='scheduled', index=True)
    result = db.Column(db.String(20), nullable=True)
    result_summary = db.Column(db.Text, nullable=True)
    vote_type = db.Column(db.String(20), default='approval', nullable=False, index=True)  # approval | election
    role_id = db.Column(db.String(36), db.ForeignKey('role.id'), nullable=True, index=True)
    seats = db.Column(db.Integer, default=1, nullable=False)
    ballot_order_seed = db.Column(db.Integer, nullable=True)  # For randomized candidate order on ballot
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    layer = db.relationship('Layer', backref=db.backref('votes', lazy=True))
    role = db.relationship('Role', backref=db.backref('election_votes', lazy='dynamic'), foreign_keys=[role_id])
    submission = db.relationship('Submission', backref=db.backref('votes', lazy=True))
    artifact = db.relationship('Artifact', backref=db.backref('votes', lazy='dynamic'), foreign_keys=[artifact_id])
    created_by = db.relationship('User', backref='created_votes')


class VoteEligibilitySnapshot(db.Model):
    """Snapshot of eligible voters at vote activation time."""
    __tablename__ = 'vote_eligibility_snapshot'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    vote_id = db.Column(db.String(36), db.ForeignKey('vote.id'), nullable=False, index=True)
    person_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    is_eligible = db.Column(db.Boolean, default=True, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    captured_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('vote_id', 'person_id', name='unique_vote_eligibility'),
    )
    
    vote = db.relationship('Vote', backref=db.backref('eligibility_snapshot', lazy=True))
    person = db.relationship('User', backref=db.backref('vote_eligibility', lazy=True))


class VoteCandidate(db.Model):
    """Candidate in an election-style vote (GOV-HUB-3 Phase 2.4)."""
    __tablename__ = 'vote_candidate'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    vote_id = db.Column(db.String(36), db.ForeignKey('vote.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    display_name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='approved', nullable=False)  # approved, withdrawn
    display_order = db.Column(db.Integer, default=0, nullable=False)  # randomized ballot order
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    vote = db.relationship('Vote', backref=db.backref('candidates', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('vote_candidacies', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('vote_id', 'user_id', name='unique_vote_candidate'),
    )


class Ballot(db.Model):
    """A single person's ballot cast in a vote."""
    __tablename__ = 'ballot'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    vote_id = db.Column(db.String(36), db.ForeignKey('vote.id'), nullable=False, index=True)
    person_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    choice = db.Column(db.String(50), nullable=False)  # 'yes'|'no'|'abstain' or candidate_id for elections
    cast_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('vote_id', 'person_id', name='unique_ballot'),
    )
    
    vote = db.relationship('Vote', backref=db.backref('ballots', lazy=True))
    person = db.relationship('User', backref=db.backref('ballots_cast', lazy=True))
