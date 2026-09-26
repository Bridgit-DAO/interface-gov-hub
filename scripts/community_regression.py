"""Run existing regression checks against a new disposable database only."""
import os, sys
from pathlib import Path
repo = Path(__file__).resolve().parents[1]
os.chdir(repo); sys.path.insert(0, str(repo))
os.environ['FLASK_ENV']='development'
os.environ['GOVHUB_SKIP_SHARED_DB_MIGRATIONS']='1'
from fixtures.isolated_app import isolated_app, make_user
with isolated_app() as ctx:
    from extensions import db
    from models import Layer, LayerMember
    import app as module
    module.app = ctx.app
    with ctx.app.app_context():
        admin = make_user(username='admin', email='synthetic@example.invalid', role='admin')
        layer = Layer(name='Regression layer', slug='regression-layer', initiator_id=admin.id, approval_status='approved')
        db.session.add(layer); db.session.flush()
        db.session.add(LayerMember(layer_id=layer.id, user_id=admin.id, status='active'))
        db.session.commit()
        from services.product_rollout import set_rollout_config
        set_rollout_config({'artifacts': True})
    import pytest
    raise SystemExit(pytest.main(['test_core_features.py','test_access_policy.py','test_nav_pills.py','test_knowledge_layer_integration.py','-q','--disable-warnings']))
