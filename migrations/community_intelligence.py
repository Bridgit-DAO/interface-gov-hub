"""Explicit, additive migration; no startup migration or existing table changes."""
from extensions import db
from models.community_intelligence import CIOrganization, CIMembership, CIProgram, CISource, CIClaim, CIAudit

TABLES = [m.__table__ for m in (CIOrganization, CIMembership, CIProgram, CISource, CIClaim, CIAudit)]


def upgrade():
    db.metadata.create_all(bind=db.engine, tables=TABLES)
