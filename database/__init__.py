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
            migrate_knowledge_form_conviction_to_claim,
            migrate_layer_enabled_features,
            migrate_layer_nav_pill_config,
            migrate_artifact_tags,
            migrate_layer_tags,
            migrate_submission_document_category,
            migrate_guild_unified_phase1,
            migrate_access_control_v1,
            migrate_notifications_stack_v1,
            migrate_submission_draft_name_backfill,
            migrate_user_profile_columns,
            migrate_public_id,
            migrate_entity_image_url,
            migrate_badge_system,
            migrate_workgroup_links,
            migrate_bridge,
            migrate_civic_mason,
            migrate_civic_mason_seed_daveed,
            migrate_user_linked_account,
            migrate_coordinator_and_member_requests,
            migrate_chair_nomination_fields,
            migrate_workgroup_nomination_flow,
            migrate_workgroup_charter_goals,
            sync_dp_workgroup_documents,
            sync_sequential_ml_draft_numbers,
            migrate_submission_content_hash,
            migrate_layer_invitations,
            migrate_product_rollout_seed,
            migrate_workgroup_layer_links,
            migrate_meta_layer_governance_metaweb_link,
            migrate_dp_proposals,
            migrate_dp_proposal_rationale_reference,
            migrate_platform_invitations,
            migrate_user_bitcoin_wallet_v1,
            migrate_layer_nft_gate_v1,
            migrate_canopi_community_sync_v1,
            migrate_custodial_wallet_v1,
            migrate_comment_is_deleted_v1,
            migrate_comment_like_v1,
            migrate_invitation_shareable_v1,
            migrate_reader_comments_v1,
            migrate_layer_org_connections_v1,
            migrate_overweb_connection_types_seed,
            migrate_referral_attribution_v1,
            migrate_referral_landing_v1,
            migrate_layer_programs_v1,
            migrate_dp_challenge_notify_waitlist_v1,
            migrate_scoped_email_v1,
            migrate_hardcoded_users,
        )

        migrate_submission_layer_id(app)
        migrate_ordinals_support(app)
        migrate_inscription_order_and_config(app)
        migrate_vote_ballot_order_seed(app)
        migrate_vote_artifact_id(app)
        migrate_artifact_spec_fields(app)
        migrate_knowledge_layer_integration(app)
        migrate_knowledge_form_conviction_to_claim(app)
        migrate_layer_enabled_features(app)
        migrate_layer_nav_pill_config(app)
        migrate_artifact_tags(app)
        migrate_layer_tags(app)
        migrate_submission_document_category(app)
        migrate_guild_unified_phase1(app)
        migrate_access_control_v1(app)
        migrate_notifications_stack_v1(app)
        migrate_submission_draft_name_backfill(app)
        migrate_user_profile_columns(app)
        migrate_public_id(app)
        db.create_all()  # Ensure layer_member, waitlist, etc. exist
        migrate_entity_image_url(app)
        migrate_badge_system(app)
        migrate_workgroup_links(app)
        migrate_bridge(app)
        migrate_civic_mason(app)
        migrate_user_linked_account(app)

        if User.query.count() == 0:
            migrate_hardcoded_users(app)
        migrate_civic_mason_seed_daveed(app)
        migrate_coordinator_and_member_requests(app)
        migrate_chair_nomination_fields(app)
        migrate_workgroup_nomination_flow(app)
        migrate_workgroup_charter_goals(app)
        sync_dp_workgroup_documents(app)
        sync_sequential_ml_draft_numbers(app)
        migrate_submission_content_hash(app)
        migrate_layer_invitations(app)
        migrate_product_rollout_seed(app)
        migrate_workgroup_layer_links(app)
        migrate_meta_layer_governance_metaweb_link(app)
        migrate_dp_proposals(app)
        migrate_dp_proposal_rationale_reference(app)
        migrate_platform_invitations(app)
        migrate_user_bitcoin_wallet_v1(app)
        migrate_layer_nft_gate_v1(app)
        migrate_canopi_community_sync_v1(app)
        migrate_custodial_wallet_v1(app)
        migrate_comment_is_deleted_v1(app)
        migrate_comment_like_v1(app)
        migrate_invitation_shareable_v1(app)
        migrate_reader_comments_v1(app)
        migrate_layer_org_connections_v1(app)
        migrate_overweb_connection_types_seed(app)
        migrate_referral_attribution_v1(app)
        migrate_referral_landing_v1(app)
        migrate_layer_programs_v1(app)
        migrate_dp_challenge_notify_waitlist_v1(app)
        migrate_scoped_email_v1(app)

        print(f"Database initialized: {User.query.count()} users")
