"""Tests for campaign thumbnail admin crop UI wiring."""
from __future__ import annotations


def test_thumbnail_admin_page_includes_crop_scripts_and_attributes():
    from app import app
    from database import init_db
    from models import User

    with app.app_context():
        init_db(app)
        admin = User.query.filter(User.role.in_(['admin', 'editor'])).first()
        if not admin:
            return

        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user'] = admin.username

        resp = client.get('/campaign/teilhard/admin/thumbnails/')
        if resp.status_code == 404:
            return

        assert resp.status_code == 200, resp.status_code

        html = resp.get_data(as_text=True)
        assert 'data-gh-aspect="16/9"' in html
        assert 'data-gh-output-width="640"' in html
        assert 'data-gh-output-height="360"' in html
        assert 'data-gh-title="Crop thumbnail"' in html
        assert 'gh-image-crop.js?v=20260820d' in html
        assert 'gh-image-upload.js?v=20260820d' in html
        assert 'bootstrap.bundle.min.js' in html
        assert 'gh-image-upload-form' in html
        assert 'name="csrf_token"' in html
        assert 'type="submit"' in html and 'disabled' in html


def test_gh_image_upload_js_blocks_submit_until_crop_ready():
    from config import PROJECT_ROOT
    import os

    path = os.path.join(PROJECT_ROOT, 'static/js/gh-image-upload.js')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()

    assert "addEventListener('submit'" in src
    assert 'ghCropReady' in src
    assert 'ghCropPending' in src
    assert 'notifyCropUnavailable' in src
    assert 'optimizeViaApi(file, opts).then(resolve)' not in src
