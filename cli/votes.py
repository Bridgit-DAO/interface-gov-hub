"""Vote lifecycle CLI: flask manage-votes tick"""
from datetime import datetime

import click

from models import Vote
from services.coordination import activate_vote, close_vote


def register_vote_cli(app):
    """Register the manage-votes CLI command with the app."""

    @app.cli.command('manage-votes')
    @click.argument('action')
    def manage_votes_cli(action):
        """Manage vote lifecycle. Usage: flask manage-votes tick"""
        if action == 'tick':
            now = datetime.utcnow()

            # Activate scheduled votes whose start_at has passed
            scheduled = Vote.query.filter(
                Vote.status == 'scheduled',
                Vote.start_at <= now
            ).all()

            activated_count = 0
            for vote in scheduled:
                success, msg = activate_vote(vote)
                if success:
                    activated_count += 1
                print(f"  Activate vote {vote.id}: {msg}")

            # Close active votes whose end_at has passed
            active = Vote.query.filter(
                Vote.status == 'active',
                Vote.end_at <= now
            ).all()

            closed_count = 0
            for vote in active:
                success, msg = close_vote(vote)
                if success:
                    closed_count += 1
                print(f"  Close vote {vote.id}: {msg}")

            print(f"✅ Tick complete: {activated_count} activated, {closed_count} closed")
        else:
            print(f"Unknown action: {action}. Use 'tick'.")
