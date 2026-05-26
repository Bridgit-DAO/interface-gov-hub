"""Shared validation for draft submission file uploads."""
from __future__ import annotations

import os

from flask import current_app
from werkzeug.utils import secure_filename

from services.utils import allowed_file


def max_submission_upload_bytes() -> int:
    return int(current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))


def validate_submission_upload(file_storage) -> tuple[str | None, str | None]:
    """
    Validate uploaded draft file. Returns (safe_filename, error_message).
    safe_filename is the original name sanitized for storage (without submission id prefix).
    """
    if not file_storage or not file_storage.filename:
        return None, 'File is required'

    original = file_storage.filename
    if not allowed_file(original):
        return None, 'Invalid file type. Allowed: txt, pdf, xml, doc, docx'

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    max_size = max_submission_upload_bytes()
    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        return None, f'File too large. Maximum size is {max_mb:.0f}MB.'

    safe_name = secure_filename(original)
    if not safe_name:
        ext = original.rsplit('.', 1)[-1].lower() if '.' in original else 'bin'
        if ext not in {'txt', 'pdf', 'xml', 'doc', 'docx'}:
            return None, 'Invalid file type. Allowed: txt, pdf, xml, doc, docx'
        safe_name = f'upload.{ext}'

    return safe_name, None


def save_submission_upload(file_storage, submission_id: str) -> tuple[str | None, str | None, str | None]:
    """
    Validate and save upload under UPLOAD_FOLDER.
    Returns (stored_filename, file_path, error_message).
    """
    safe_name, err = validate_submission_upload(file_storage)
    if err:
        return None, None, err

    stored = f'{submission_id}-{safe_name}'
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], stored)
    file_storage.save(file_path)
    return stored, file_path, None
