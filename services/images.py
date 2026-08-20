"""Image upload and role image vote helpers."""
import io
import os

from extensions import db
from models import RoleImage, RoleImageVote
from services.utils import allowed_image_file

# Same limits as main app
IMAGE_MAX_DIMENSION = 600
BANNER_MAX_DIMENSION = (1920, 600)
MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _cover_crop_square(img):
    """Center-cover crop an image to a square of min(w, h) on each side."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def _cover_crop_to_bounds(img, max_width, max_height):
    """Center-cover crop to fit within (max_width, max_height)."""
    w, h = img.size
    if w == 0 or h == 0:
        return img
    target_ratio = max_width / max_height
    src_ratio = w / h
    if src_ratio > target_ratio:
        # source is wider than target – crop sides
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    # source is taller than target – crop top/bottom
    new_h = int(round(w / target_ratio))
    top = (h - new_h) // 2
    return img.crop((0, top, w, top + new_h))


def _save_with_format(img, ext, file_path):
    """Save a Pillow Image to ``file_path`` using format-appropriate options.

    Keeps the original format on output:
      PNG → optimize
      JPEG → quality 92
      WebP → quality 90 (lossless when alpha present)
      GIF → first frame, preserves palette
    """
    save_kwargs = {}
    target_format = None

    if ext == 'png':
        target_format = 'PNG'
        save_kwargs = {'optimize': True}
        if img.mode not in ('RGB', 'RGBA', 'P', 'L', 'LA'):
            img = img.convert('RGBA')
    elif ext in ('jpg', 'jpeg'):
        target_format = 'JPEG'
        save_kwargs = {'quality': 92, 'optimize': True}
        if img.mode in ('RGBA', 'LA', 'P'):
            background = img if img.mode == 'RGBA' else None
            if img.mode == 'P':
                img = img.convert('RGBA')
                background = img
            if background is not None and background.mode == 'RGBA':
                rgb = img.convert('RGB') if img.mode != 'RGBA' else img
                bg = Image.new('RGB', rgb.size, (255, 255, 255))
                bg.paste(rgb, mask=rgb.split()[3] if rgb.mode == 'RGBA' else None)
                img = bg
            else:
                img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
    elif ext == 'webp':
        target_format = 'WEBP'
        if img.mode in ('RGBA', 'LA'):
            save_kwargs = {'lossless': True}
        else:
            save_kwargs = {'quality': 90, 'method': 4}
    elif ext == 'gif':
        target_format = 'GIF'
        if img.mode != 'P':
            img = img.convert('P', palette=Image.ADAPTIVE)
        save_kwargs = {'optimize': True}
    else:
        # Unknown / unsupported – fall back to PNG.
        target_format = 'PNG'
        save_kwargs = {'optimize': True}
        if img.mode not in ('RGB', 'RGBA', 'P', 'L', 'LA'):
            img = img.convert('RGBA')

    img.save(file_path, format=target_format, **save_kwargs)


def upload_image(file_storage, upload_folder, url_prefix, filename_prefix='img', max_dimension=None):
    """
    Validate and save an uploaded image.

    Accepts images of any reasonable size; when ``max_dimension`` is provided,
    the image is center-cover cropped to a square of side ``min(w, h)`` then
    downscaled (LANCZOS) to ``max_dimension × max_dimension``. For
    ``max_dimension`` passed as a 2-tuple ``(width, height)``, the image is
    center-cover cropped to that aspect and downscaled preserving aspect
    within those bounds (used for banners).

    Returns ``(image_url, None)`` on success, ``(None, error_message)`` on failure.
    """
    if not file_storage or not file_storage.filename:
        return None, 'No file provided'
    filename = file_storage.filename
    if not allowed_image_file(filename):
        return None, 'Invalid file type. Allowed: PNG, JPG, GIF, WebP, SVG'
    ext = filename.rsplit('.', 1)[1].lower()

    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)
    if file_size > MAX_IMAGE_FILE_SIZE:
        return None, f'File too large. Maximum size is {MAX_IMAGE_FILE_SIZE // (1024*1024)}MB.'

    # SVG is treated as a no-resize passthrough.
    if ext == 'svg' or max_dimension is None:
        safe_name = f"{filename_prefix}_{os.urandom(8).hex()}.{ext}"
        file_path = os.path.join(upload_folder, safe_name)
        try:
            file_storage.seek(0)
            file_storage.save(file_path)
        except Exception as e:
            return None, f'Failed to save file: {e}'
        return f"{url_prefix}/{safe_name}", None

    # Pillow-based defensive resize.
    try:
        from PIL import Image, ImageOps

        file_storage.seek(0)
        img = Image.open(file_storage)
        img.load()
        # Auto-rotate based on EXIF orientation before any cropping/scaling.
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        if isinstance(max_dimension, (tuple, list)):
            max_w, max_h = int(max_dimension[0]), int(max_dimension[1])
            img = _cover_crop_to_bounds(img, max_w, max_h)
            img.thumbnail((max_w, max_h), Image.LANCZOS)
        else:
            side = int(max_dimension)
            img = _cover_crop_square(img)
            img = img.resize((side, side), Image.LANCZOS)

        from services.image_optimize import encode_webp
        os.makedirs(upload_folder, exist_ok=True)
        safe_name = f"{filename_prefix}_{os.urandom(8).hex()}.webp"
        file_path = os.path.join(upload_folder, safe_name)
        with open(file_path, 'wb') as fh:
            fh.write(encode_webp(img))
    except Exception as e:
        return None, f'Invalid image or unsupported format: {e}'

    return f"{url_prefix}/{safe_name}", None


def upload_image_600x600(file_storage, upload_folder, url_prefix, filename_prefix='img'):
    """Square 600×600 output – accepts any size, cover-crops and downscales."""
    return upload_image(file_storage, upload_folder, url_prefix,
                        filename_prefix=filename_prefix, max_dimension=IMAGE_MAX_DIMENSION)


def upload_banner(file_storage, upload_folder, url_prefix, filename_prefix='banner',
                  max_dimension=None):
    """Wide-aspect banner upload. Default max is 1920×600."""
    if max_dimension is None:
        max_dimension = BANNER_MAX_DIMENSION
    return upload_image(file_storage, upload_folder, url_prefix,
                        filename_prefix=filename_prefix, max_dimension=max_dimension)


def update_image_vote_counts(image_id):
    """Recalculate vote counts for a role image."""
    image = RoleImage.query.get(image_id)
    if not image:
        return False
    votes = RoleImageVote.query.filter_by(image_id=image_id).all()
    upvotes = sum(1 for v in votes if v.value == 1)
    downvotes = sum(1 for v in votes if v.value == -1)
    image.upvotes = upvotes
    image.downvotes = downvotes
    image.net_score = upvotes - downvotes
    db.session.commit()
    return True
