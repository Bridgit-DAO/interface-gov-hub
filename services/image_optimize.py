"""Shared WebP encode/optimize for Gov Hub uploads and /api/images/optimize."""
from __future__ import annotations

import io
from typing import Any, Dict, Optional, Tuple, Union

from PIL import Image, ImageOps

WEBP_QUALITY_DEFAULT = 82
WEBP_METHOD = 6
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000

FitMode = str  # 'inside' | 'cover'


def _cover_crop(img: Image.Image, max_width: int, max_height: int) -> Image.Image:
    w, h = img.size
    if w == 0 or h == 0:
        return img
    target = max_width / float(max_height)
    src = w / float(h)
    if src > target:
        new_w = int(round(h * target))
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    new_h = int(round(w / target))
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def _as_int(value, default=None, *, lo=1, hi=4096):
    if value is None or value == '':
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _open_image(data: bytes) -> Image.Image:
    if not data:
        raise ValueError('Empty image')
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('Image exceeds 8MB')
    img = Image.open(io.BytesIO(data))
    img.load()
    w, h = img.size
    if w * h > MAX_PIXELS:
        raise ValueError('Image dimensions are too large')
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    return img


def _fit_image(img: Image.Image, max_width: Optional[int], max_height: Optional[int], fit: FitMode) -> Image.Image:
    if not max_width and not max_height:
        return img
    mw = int(max_width or img.width)
    mh = int(max_height or img.height)
    if mw < 1 or mh < 1:
        return img
    if fit == 'cover':
        cropped = _cover_crop(img, mw, mh)
        return cropped.resize((mw, mh), Image.Resampling.LANCZOS)
    copy = img.copy()
    copy.thumbnail((mw, mh), Image.Resampling.LANCZOS)
    return copy


def encode_webp(
    img: Image.Image,
    *,
    quality: int = WEBP_QUALITY_DEFAULT,
) -> bytes:
    quality = max(40, min(95, int(quality)))
    has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
    if has_alpha:
        out = img.convert('RGBA') if img.mode != 'RGBA' else img
    else:
        out = img.convert('RGB') if img.mode != 'RGB' else img
    buf = io.BytesIO()
    out.save(buf, format='WEBP', quality=quality, method=WEBP_METHOD)
    return buf.getvalue()


def optimize_image_bytes(
    data: bytes,
    *,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: int = WEBP_QUALITY_DEFAULT,
    fit: FitMode = 'inside',
) -> Tuple[bytes, Dict[str, Any]]:
    """Decode any raster image, optionally resize, return WebP bytes and metadata."""
    img = _open_image(data)
    img = _fit_image(img, max_width, max_height, fit if fit in ('inside', 'cover') else 'inside')
    payload = encode_webp(img, quality=quality)
    return payload, {
        'mime': 'image/webp',
        'extension': 'webp',
        'width': img.width,
        'height': img.height,
        'bytes': len(payload),
        'quality': max(40, min(95, int(quality))),
    }


def optimize_file_storage(file_storage, **kwargs) -> Tuple[bytes, Dict[str, Any]]:
    if not file_storage:
        raise ValueError('No file provided')
    stream = getattr(file_storage, 'stream', None) or file_storage
    if hasattr(stream, 'seek'):
        stream.seek(0)
    data = stream.read()
    if hasattr(stream, 'seek'):
        stream.seek(0)
    return optimize_image_bytes(data, **kwargs)
