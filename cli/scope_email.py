"""CLI: process due scoped email deliveries."""
from services.scope_email import process_due_deliveries


def register_scope_email_cli(app):
    @app.cli.command('scope-email-process')
    def scope_email_process_command():
        """Send due layer/guild admin email campaign deliveries."""
        summary = process_due_deliveries()
        print(
            'scope-email-process: '
            f"processed={summary.get('processed', 0)} "
            f"sent={summary.get('sent', 0)} "
            f"failed={summary.get('failed', 0)} "
            f"skipped={summary.get('skipped', 0)}"
        )
