"""Image optimize API: convert any raster upload to optimized WebP."""
from flask import Blueprint, jsonify, request, Response

from services.identity import get_current_user
from services.image_optimize import (
    MAX_UPLOAD_BYTES,
    WEBP_QUALITY_DEFAULT,
    optimize_file_storage,
)

bp = Blueprint('images_api', __name__, url_prefix='')


def _int_arg(*names, default=None, lo=1, hi=4096):
    for name in names:
        raw = request.form.get(name)
        if raw is None:
            raw = request.args.get(name)
        if raw is None or raw == '':
            continue
        try:
            return max(lo, min(hi, int(raw)))
        except (TypeError, ValueError):
            continue
    return default


@bp.route('/api/images/optimize', methods=['POST'])
def api_optimize_image():
    """Optimize an uploaded raster image to WebP.

    multipart field: ``file`` (or ``image``)
    optional form/query: max_width, max_height, quality (40-95), fit (inside|cover)
    optional: download=1 to return raw image/webp instead of JSON.

    JSON: { ok, mime, extension, width, height, bytes, quality, data_base64 }
    """
    user = get_current_user()
    if not user:
        return jsonify({'ok': False, 'error': 'Authentication required'}), 401

    length = request.content_length
    if length is not None and length > MAX_UPLOAD_BYTES + 512_000:
        return jsonify({'ok': False, 'error': 'File too large. Maximum size is 8MB.'}), 413

    fs = request.files.get('file') or request.files.get('image')
    if not fs or not fs.filename:
        return jsonify({'ok': False, 'error': 'No image file provided'}), 400

    max_width = _int_arg('max_width', 'maxWidth', default=None)
    max_height = _int_arg('max_height', 'maxHeight', default=None)
    quality = _int_arg('quality', default=WEBP_QUALITY_DEFAULT, lo=40, hi=95)
    fit = (request.form.get('fit') or request.args.get('fit') or 'inside').strip().lower()
    if fit not in ('inside', 'cover'):
        fit = 'inside'

    try:
        payload, meta = optimize_file_storage(
            fs,
            max_width=max_width,
            max_height=max_height,
            quality=quality,
            fit=fit,
        )
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    except Exception:
        return jsonify({'ok': False, 'error': 'Could not decode image'}), 400

    raw = request.form.get('download') or request.args.get('download') or ''
    want_raw = str(raw).lower() in ('1', 'true', 'yes') or 'image/webp' in (request.headers.get('Accept') or '')
    if want_raw and 'application/json' not in (request.headers.get('Accept') or ''):
        resp = Response(payload, mimetype='image/webp')
        resp.headers['X-Image-Width'] = str(meta['width'])
        resp.headers['X-Image-Height'] = str(meta['height'])
        resp.headers['Content-Disposition'] = 'inline; filename="optimized.webp"'
        return resp

    import base64
    body = dict(meta)
    body['ok'] = True
    body['data_base64'] = base64.b64encode(payload).decode('ascii')
    return jsonify(body), 200
