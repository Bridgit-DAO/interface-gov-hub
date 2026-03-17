"""Image upload and role image vote helpers."""
import os

from extensions import db
from models import RoleImage, RoleImageVote
from services.utils import allowed_image_file

# Same limits as main app
IMAGE_MAX_DIMENSION = 600
MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def upload_image_600x600(file_storage, upload_folder, url_prefix, filename_prefix='img'):
    """
    Validate and save an uploaded image with max dimensions 600x600.
    Returns (image_url, None) on success, or (None, error_message) on failure.
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
    if ext != 'svg':
        try:
            from PIL import Image
            img = Image.open(file_storage)
            img.load()
            w, h = img.size
            if w > IMAGE_MAX_DIMENSION or h > IMAGE_MAX_DIMENSION:
                return None, f'Image dimensions must be at most {IMAGE_MAX_DIMENSION}x{IMAGE_MAX_DIMENSION} pixels (got {w}x{h}).'
            file_storage.seek(0)
        except Exception as e:
            file_storage.seek(0)
            return None, f'Invalid image or unsupported format: {e}'
    safe_name = f"{filename_prefix}_{os.urandom(8).hex()}.{ext}"
    file_path = os.path.join(upload_folder, safe_name)
    try:
        file_storage.save(file_path)
    except Exception as e:
        return None, f'Failed to save file: {e}'
    return f"{url_prefix}/{safe_name}", None


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
