"""Synthetic three-organization foundation fixture, never real customer data."""
from uuid import uuid4
from extensions import db
from models import User, Layer, LayerMember
from models.community_intelligence import CIOrganization, CIMembership, CIProgram, CISource
from services.community_intelligence import submit_source, process_source, review


def seed_community_fixture(app):
    """Requires a disposable initialized database. Returns layer and demo users."""
    with app.app_context():
        if User.query.first():
            raise RuntimeError('Demo seeding requires an empty, disposable database.')
        users = []
        for name in ['Learning Neighbors', 'Curriculum Commons', 'Open Door Venue']:
            user = User(id=str(uuid4()), username=name.lower().replace(' ', '-'),
                        displayName=name + ' steward', email=None,
                        password_hash='!synthetic-no-password', role='user')
            db.session.add(user); users.append(user)
        db.session.flush()
        layer = Layer(name='Community Learning Pilot', slug='community-learning-pilot',
                      initiator_id=users[0].id, approval_status='approved', display_status='active',
                      description='Fictional organizations exploring a small community learning pilot.')
        db.session.add(layer); db.session.flush()
        app.config['COMMUNITY_INTELLIGENCE_LAYERS'] = (layer.id,)
        for user in users:
            db.session.add(LayerMember(layer_id=layer.id, user_id=user.id, status='active'))
        db.session.commit()
        inputs = [
            ('Learning Neighbors', 'Neighborhood workshops', 'We need a training partner and an accessible venue for neighborhood workshops.', 'need'),
            ('Curriculum Commons', 'Community curriculum', 'We offer a community training curriculum and facilitation materials.', 'offer'),
            ('Open Door Venue', 'Learning room', 'We offer an accessible venue for community training workshops.', 'offer'),
        ]
        sources = []
        for user, (name, program_name, statement, kind) in zip(users, inputs):
            org = CIOrganization(name=name, created_by=user.id)
            db.session.add(org); db.session.flush()
            db.session.add(CIMembership(organization_id=org.id, user_id=user.id, role='administrator'))
            program = CIProgram(organization_id=org.id, layer_id=layer.id, name=program_name, lifecycle='active')
            db.session.add(program); db.session.flush()
            source, _ = submit_source(layer.id, user.id, program.id, name + ' · current program note',
                                      statement.encode(), 'md')
            sid = source.id; db.session.commit(); process_source(sid)
            from models.community_intelligence import CIClaim
            source = db.session.get(CISource, sid)
            review(source, user.id, {'revision': source.revision, 'decisions': [
                dict(id=c.id, standing='confirmed', kind=kind, topic='community training')
                for c in CIClaim.query.filter_by(source_id=sid).all()]})
            source.visibility = 'layer'
            db.session.commit(); sources.append(sid)
        # A tentative newsletter stays private and unconfirmed.
        first_program = db.session.get(CISource, sources[0]).program_id
        pending, _ = submit_source(layer.id, users[0].id, first_program, 'Autumn newsletter · needs review',
                                    b'We hope to launch a new evening training series next spring. Dates and capacity are not confirmed.', 'md')
        pending_id = pending.id; db.session.commit(); process_source(pending_id)
        # A real PNG image fixture exercises the explicit unavailable-OCR state.
        import io
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (640, 140), 'white'); ImageDraw.Draw(image).text((20, 50), 'Scanned note: venue availability needs steward review.', fill='black')
        buffer = io.BytesIO(); image.save(buffer, format='PNG')
        scanned, _ = submit_source(layer.id, users[0].id, first_program, 'Scanned venue note · OCR required', buffer.getvalue(), 'png')
        scanned_id = scanned.id; db.session.commit(); process_source(scanned_id)
        return dict(layer_id=layer.id, users=[u.username for u in users], source_ids=sources)
