"""Time-bounded participation programs on a layer (e.g. DP Challenge on The Metaweb)."""
from datetime import datetime
from uuid import uuid4

from extensions import db

PROGRAM_STATUSES = ('draft', 'waitlist', 'active', 'archived')


class LayerProgram(db.Model):
    """Initiative / cohort on a layer: waitlist funnel → launch → participation hub."""
    __tablename__ = 'layer_program'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    slug = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default='draft', index=True)
    hub_path = db.Column(db.String(255), nullable=True, index=True)
    hub_mode = db.Column(db.String(32), nullable=True)

    waitlist_id = db.Column(db.String(36), db.ForeignKey('waitlist.id'), nullable=True, index=True)
    workgroup_id = db.Column(db.String(36), db.ForeignKey('working_group.id'), nullable=True, index=True)

    launch_at = db.Column(db.DateTime, nullable=True, index=True)
    launched_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    layer = db.relationship('Layer', backref=db.backref('programs', lazy='dynamic'))
    waitlist = db.relationship('Waitlist', backref=db.backref('program', uselist=False))
    workgroup = db.relationship('Workgroup', backref=db.backref('programs', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('layer_id', 'slug', name='uq_layer_program_slug'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'slug': self.slug,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'hub_path': self.hub_path,
            'hub_mode': self.hub_mode,
            'waitlist_id': self.waitlist_id,
            'workgroup_id': self.workgroup_id,
            'launch_at': self.launch_at.isoformat() if self.launch_at else None,
            'launched_at': self.launched_at.isoformat() if self.launched_at else None,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class LayerProgramSubmission(db.Model):
    """Optional explicit draft scope for a program hub."""
    __tablename__ = 'layer_program_submission'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    program_id = db.Column(db.String(36), db.ForeignKey('layer_program.id'), nullable=False, index=True)
    submission_id = db.Column(db.String(36), db.ForeignKey('submission.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    program = db.relationship('LayerProgram', backref=db.backref('submission_links', lazy='dynamic'))
    submission = db.relationship('Submission')

    __table_args__ = (
        db.UniqueConstraint('program_id', 'submission_id', name='uq_layer_program_submission'),
    )
