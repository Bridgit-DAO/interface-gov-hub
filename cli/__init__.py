"""CLI commands. Call register_cli(app) to attach commands to the Flask app."""

from cli.votes import register_vote_cli
from cli.notification_digest import register_notification_digest_cli
from cli.scope_email import register_scope_email_cli


def register_cli(app):
    """Register all CLI commands with the Flask app."""
    register_vote_cli(app)
    register_notification_digest_cli(app)
    register_scope_email_cli(app)
