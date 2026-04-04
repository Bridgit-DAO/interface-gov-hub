"""Database initialization and migrations."""

from extensions import db
from models import User


def init_db(app):
    """Initialize database and create tables. Run migrations."""
    with app.app_context():
        db.create_all()

        from migrations import (
            migrate_submission_layer_id,
            migrate_ordinals_support,
            migrate_inscription_order_and_config,
            migrate_vote_ballot_order_seed,
            migrate_vote_artifact_id,
            migrate_artifact_spec_fields,
            migrate_knowledge_layer_integration,
            migrate_submission_draft_name_backfill,
            migrate_user_profile_columns,
            migrate_public_id,
            migrate_entity_image_url,
            migrate_badge_system,
            migrate_bridge,
            migrate_civic_mason,
            migrate_civic_mason_seed_daveed,
            migrate_user_linked_account,
            migrate_coordinator_and_member_requests,
            migrate_hardcoded_users,
        )

        migrate_submission_layer_id(app)
        migrate_ordinals_support(app)
        migrate_inscription_order_and_config(app)
        migrate_vote_ballot_order_seed(app)
        migrate_vote_artifact_id(app)
        migrate_artifact_spec_fields(app)
        migrate_knowledge_layer_integration(app)
        migrate_submission_draft_name_backfill(app)
        migrate_user_profile_columns(app)
        migrate_public_id(app)
        db.create_all()  # Ensure layer_member, waitlist, etc. exist
        migrate_entity_image_url(app)
        migrate_badge_system(app)
        migrate_bridge(app)
        migrate_civic_mason(app)
        migrate_user_linked_account(app)

        if User.query.count() == 0:
            migrate_hardcoded_users(app)
        migrate_civic_mason_seed_daveed(app)
        migrate_coordinator_and_member_requests(app)

        print(f"Database initialized: {User.query.count()} users")
