"""Manual verification script for services.images after the upload-cap relaxation.

Run from /home/ubuntu/gov-hub-dev:
    python scripts/_verify_image_upload.py

This file is NOT committed – it is a one-off check the user can delete after running.
"""
import io
import os
import tempfile

from PIL import Image

from services.images import upload_image_600x600, upload_banner


class _BytesFile:
    """Minimal FileStorage-like wrapper exposing .filename, .save(path), .seek(pos), .read()."""

    def __init__(self, data: bytes, filename: str):
        self._buf = io.BytesIO(data)
        self.filename = filename

    def seek(self, pos, whence=0):
        return self._buf.seek(pos, whence)

    def tell(self):
        return self._buf.tell()

    def read(self, n=-1):
        return self._buf.read(n)

    def save(self, dst):
        self._buf.seek(0)
        with open(dst, 'wb') as fh:
            fh.write(self._buf.read())


def _make_test_jpeg(w: int, h: int) -> bytes:
    img = Image.new('RGB', (w, h), color=(80, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=80)
    return buf.getvalue()


def _make_test_png(w: int, h: int) -> bytes:
    img = Image.new('RGB', (w, h), color=(10, 200, 30))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_profile_square():
    print('--- upload_image_600x600 (4000x3000 JPEG) ---')
    raw = _make_test_jpeg(4000, 3000)
    fs = _BytesFile(raw, 'big.jpg')
    with tempfile.TemporaryDirectory() as tmp:
        url, err = upload_image_600x600(fs, tmp, '/uploads/test', filename_prefix='profile')
        assert not err, f'unexpected error: {err}'
        out_path = os.path.join(tmp, url.split('/')[-1])
        with Image.open(out_path) as img:
            assert img.size == (600, 600), f'expected 600x600, got {img.size}'
            assert img.format == 'JPEG', f'expected JPEG, got {img.format}'
        print('OK: 4000x3000 JPEG → 600x600 JPEG')


def test_profile_png():
    print('--- upload_image_600x600 (3000x5000 PNG) ---')
    raw = _make_test_png(3000, 5000)
    fs = _BytesFile(raw, 'big.png')
    with tempfile.TemporaryDirectory() as tmp:
        url, err = upload_image_600x600(fs, tmp, '/uploads/test', filename_prefix='profile')
        assert not err, f'unexpected error: {err}'
        out_path = os.path.join(tmp, url.split('/')[-1])
        with Image.open(out_path) as img:
            assert img.size == (600, 600), f'expected 600x600, got {img.size}'
            assert img.format == 'PNG', f'expected PNG, got {img.format}'
        print('OK: 3000x5000 PNG → 600x600 PNG')


def test_banner():
    print('--- upload_banner (5000x100 JPEG) ---')
    raw = _make_test_jpeg(5000, 100)
    fs = _BytesFile(raw, 'wide.jpg')
    with tempfile.TemporaryDirectory() as tmp:
        url, err = upload_banner(fs, tmp, '/uploads/test', filename_prefix='banner')
        assert not err, f'unexpected error: {err}'
        out_path = os.path.join(tmp, url.split('/')[-1])
        with Image.open(out_path) as img:
            w, h = img.size
            assert w <= 1920 and h <= 600, f'expected within 1920x600, got {w}x{h}'
            assert img.format == 'JPEG', f'expected JPEG, got {img.format}'
        print(f'OK: 5000x100 JPEG → {w}x{h} JPEG')


if __name__ == '__main__':
    test_profile_square()
    test_profile_png()
    test_banner()
    print('All image-upload verifications passed.')
