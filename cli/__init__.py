"""CLI commands. Call register_cli(app) to attach commands to the Flask app."""

from cli.votes import register_vote_cli


def register_cli(app):
    """Register all CLI commands with the Flask app."""
    register_vote_cli(app)
