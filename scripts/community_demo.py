#!/usr/bin/env python3
"""Loopback-only synthetic demonstration. Does not use an existing database."""
import os
import secrets
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['FLASK_ENV'] = 'development'
os.environ['GOVHUB_SKIP_SHARED_DB_MIGRATIONS'] = '1'
os.environ.setdefault('SECRET_KEY', secrets.token_hex(32))
os.environ.setdefault('REFERRAL_TOKEN_SECRET', secrets.token_hex(32))

from flask import abort, redirect, request, session
from app import create_app
from extensions import db
from fixtures.community_intelligence import seed_community_fixture
from services.community_intelligence import process_source
from models.community_intelligence import CISource


def main():
    with tempfile.TemporaryDirectory(prefix='govhub-community-demo-') as directory:
        app = create_app(database_uri='sqlite:///' + directory + '/demo.db', testing=True)
        with app.app_context():
            db.create_all()
        fixture = seed_community_fixture(app)
        token = secrets.token_urlsafe(24)
        @app.get('/community-demo/<key>/')
        def login(key):
            if not secrets.compare_digest(key, token):
                abort(404)
            user = request.args.get('as', fixture['users'][0])
            if user not in fixture['users']:
                abort(404)
            session.clear(); session['user'] = user
            return redirect('/layers/' + fixture['layer_id'] + '/community/')
        @app.after_request
        def demo_banner(response):
            if response.mimetype == 'text/html' and response.status_code == 200:
                links = ' | '.join(f'<a href="/community-demo/{token}/?as={u}">{u}</a>' for u in fixture['users'])
                banner = '<div style="padding:12px;background:#fff1c7;color:#242424;text-align:center">Synthetic local demo · switch steward: ' + links + '</div>'
                response.set_data(response.get_data(as_text=True).replace('<main class="ci"', banner + '<main class="ci"', 1))
            return response
        # Development-only local worker. Each job uses its own app/session context.
        import threading
        import time
        def worker():
            while True:
                time.sleep(2)
                with app.app_context():
                    ids = [s.id for s in CISource.query.filter_by(state='queued').limit(5).all()]
                    db.session.rollback()
                    for sid in ids:
                        process_source(sid)
        threading.Thread(target=worker, daemon=True).start()
        print(f'LOCAL_DEMO_URL=http://127.0.0.1:5000/community-demo/{token}/', flush=True)
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
