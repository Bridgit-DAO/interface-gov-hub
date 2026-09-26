"""Explicit migrations and bounded queue draining, using the configured local app."""
import click
from flask import current_app
from extensions import db


def register(app):
    @app.cli.command('community-migrate')
    def migrate():
        if not current_app.config.get('IS_DEVELOPMENT'):
            raise click.ClickException('Run this pilot migration only in development after a verified backup.')
        from migrations.community_intelligence import upgrade
        upgrade()
        click.echo('Community Intelligence tables created; feature remains gated by layer IDs.')

    @app.cli.command('community-work')
    @click.option('--limit', type=click.IntRange(1, 100), default=10)
    def work(limit):
        from models.community_intelligence import CISource
        from services.community_intelligence import process_source
        ids = [s.id for s in CISource.query.filter(
            CISource.state == 'queued',
            CISource.layer_id.in_(current_app.config.get('COMMUNITY_INTELLIGENCE_LAYERS', ()))
        ).order_by(CISource.created_at).limit(limit).all()]
        db.session.rollback()
        for source_id in ids:
            process_source(source_id)
        click.echo(f'Inspected {len(ids)} queued sources. Failures remain visible in the workspace.')
