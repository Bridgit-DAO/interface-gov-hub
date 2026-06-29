"""Tests for layer programs (Metaweb initiatives)."""
import os
import unittest

os.environ.setdefault('REFERRAL_TOKEN_SECRET', 'test-secret-for-share-ref-token')


class LayerProgramTests(unittest.TestCase):
    def test_normalize_program_slug(self):
        from services.layer_programs import normalize_program_slug

        self.assertEqual(normalize_program_slug('DP Challenge'), 'dp-challenge')
        self.assertEqual(normalize_program_slug('  Foo Bar!!  '), 'foo-bar')

    def test_resolve_program_for_dp_challenge_hub(self):
        from app import app
        from extensions import db
        from models import Layer, LayerProgram

        with app.app_context():
            layer = Layer.query.filter_by(slug='the-metaweb').first()
            if not layer:
                self.skipTest('the-metaweb layer not in test DB')
            existing = LayerProgram.query.filter_by(layer_id=layer.id, slug='dp-challenge').first()
            if not existing:
                program = LayerProgram(
                    layer_id=layer.id,
                    slug='dp-challenge',
                    name='DP Challenge',
                    status='active',
                    hub_path='/dp-challenge/',
                    hub_mode='dp',
                )
                db.session.add(program)
                db.session.commit()
            from services.layer_programs import resolve_program_for_hub

            resolved = resolve_program_for_hub('/dp-challenge/')
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved.slug, 'dp-challenge')
            self.assertEqual(resolved.layer_id, layer.id)

    def test_programs_api_lists_metaweb_programs(self):
        from app import app
        from models import Layer

        with app.app_context():
            layer = Layer.query.filter_by(slug='the-metaweb').first()
            if not layer:
                self.skipTest('the-metaweb layer not in test DB')
            client = app.test_client()
            r = client.get(f'/api/layers/{layer.id}/programs/')
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertIn('programs', data)
            slugs = [p.get('slug') for p in data['programs']]
            self.assertIn('dp-challenge', slugs)

    def test_dp_challenge_prelaunch_page_and_notify_config(self):
        from app import app
        from models import Layer, LayerProgram

        with app.app_context():
            layer = Layer.query.filter_by(slug='the-metaweb').first()
            if not layer:
                self.skipTest('the-metaweb layer not in test DB')
            program = LayerProgram.query.filter_by(layer_id=layer.id, slug='dp-challenge').first()
            if not program:
                self.skipTest('dp-challenge program not seeded')
            client = app.test_client()
            r = client.get('/dp-challenge/')
            self.assertEqual(r.status_code, 200)
            self.assertIn(b'Notify me when the Challenge opens', r.data)
            self.assertIn(b'dp-challenge-notify.js', r.data)
            cfg = client.get('/api/programs/notify-config/?hub_path=/dp-challenge/')
            self.assertEqual(cfg.status_code, 200)
            data = cfg.get_json()
            self.assertTrue(data.get('is_prelaunch'))
            self.assertIn('dp_options', data)
            self.assertIn('notify_api_path', data)


if __name__ == '__main__':
    unittest.main()
