"""Tests for shared WebP image optimization."""
from __future__ import annotations

import io

from PIL import Image


def _png_bytes(w=80, h=60, color=(20, 80, 180, 255)):
    img = Image.new('RGBA', (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_optimize_png_to_webp_smaller_and_valid():
    from services.image_optimize import optimize_image_bytes

    src = _png_bytes(400, 300)
    out, meta = optimize_image_bytes(src, max_width=200, quality=80)
    assert meta['mime'] == 'image/webp'
    assert meta['extension'] == 'webp'
    assert meta['width'] <= 200
    assert out[:4] == b'RIFF'
    assert len(out) < len(src)


def test_cover_fit_exact_size():
    from services.image_optimize import optimize_image_bytes

    src = _png_bytes(800, 200)
    out, meta = optimize_image_bytes(src, max_width=64, max_height=64, fit='cover')
    assert meta['width'] == 64
    assert meta['height'] == 64
    img = Image.open(io.BytesIO(out))
    assert img.format == 'WEBP'


def test_upload_image_persists_webp(tmp_path):
    from werkzeug.datastructures import FileStorage
    from services.images import upload_image

    storage = FileStorage(stream=io.BytesIO(_png_bytes(120, 120)), filename='avatar.png', content_type='image/png')
    url, err = upload_image(storage, str(tmp_path), '/uploads/test', filename_prefix='t', max_dimension=60)
    assert err is None
    assert url.endswith('.webp')
    saved = tmp_path / url.rsplit('/', 1)[-1]
    assert saved.is_file()
    assert Image.open(saved).format == 'WEBP'
    assert Image.open(saved).size == (60, 60)
