"""Campaign card thumbnails: PDF auto-extract, draft hero passthrough, upload helpers."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from config import PROJECT_ROOT
from services.campaign_pages import (
    CAMPAIGN_ROOT,
    CampaignConfig,
    reload_campaign_cache,
    resolve_project_path,
)

THUMB_WIDTH = 640
THUMB_HEIGHT = 360

_DRAFT_HERO_SCAFFOLD_KEYS = (
    'heroImageUrl',
    'hero_image_url',
    'coverImageUrl',
    'cover_image_url',
    'heroUrl',
    'coverUrl',
    'cover_url',
)

_BOOK_COVER_MD_RE = re.compile(
    r'!\[[^\]]*\]\((?:https?://[^/]+)?/assets/cover\.png\)',
    re.IGNORECASE,
)
_BOOK_COVER_SRC_RE = re.compile(
    r'''src=["'](?:https?://[^"']+)?/assets/cover\.png["']''',
    re.IGNORECASE,
)
_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_IMG_SRC_RE = re.compile(r'''<img[^>]+src=["']([^"']+)["']''', re.IGNORECASE)

_PDF_DOC_TYPES = frozenset({'paper', 'slide_deck', 'slides'})
_DRAFT_DOC_TYPES = frozenset({'paper', 'draft'})


def campaign_assets_dir(campaign_slug: str) -> str:
    return os.path.join(CAMPAIGN_ROOT, campaign_slug, 'assets')


def thumb_filename(doc_slug: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9_-]+', '-', (doc_slug or 'doc').strip()).strip('-') or 'doc'
    return f'{safe}-thumb.jpg'


def thumb_abs_path(campaign_slug: str, doc_slug: str) -> str:
    return os.path.join(campaign_assets_dir(campaign_slug), thumb_filename(doc_slug))


def thumb_public_url(campaign_slug: str, doc_slug: str) -> str:
    return f'/static/campaign/{campaign_slug}/assets/{thumb_filename(doc_slug)}'


def _youtube_video_id(url: str) -> Optional[str]:
    from services.campaign_render import _youtube_video_id as yt_id

    return yt_id(url)


def explicit_thumbnail(item: Dict[str, Any]) -> Optional[str]:
    explicit = (item.get('thumbnailUrl') or item.get('thumbnail') or '').strip()
    return explicit or None


def extract_pdf_first_page_thumbnail(
    pdf_path: str,
    out_path: str,
    *,
    width: int = THUMB_WIDTH,
    height: int = THUMB_HEIGHT,
) -> bool:
    """Render PDF page 1 to a cached 16:9 JPEG. Idempotent when out_path exists."""
    import fitz
    from PIL import Image

    from services.images import _cover_crop_to_bounds

    if not os.path.isfile(pdf_path):
        return False
    doc = fitz.open(pdf_path)
    try:
        if doc.page_count < 1:
            return False
        page = doc.load_page(0)
        zoom = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        cropped = _cover_crop_to_bounds(img, width, height)
        cropped = cropped.resize((width, height), Image.Resampling.LANCZOS)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        cropped.save(out_path, 'JPEG', quality=85, optimize=True)
        return True
    finally:
        doc.close()


def ensure_pdf_thumbnail(
    campaign_slug: str,
    doc_slug: str,
    pdf_rel_path: str,
    *,
    force: bool = False,
) -> Optional[str]:
    """Create ``<doc-slug>-thumb.jpg`` when missing. Returns public URL or None."""
    out_path = thumb_abs_path(campaign_slug, doc_slug)
    if os.path.isfile(out_path) and not force:
        return thumb_public_url(campaign_slug, doc_slug)
    pdf_path = resolve_project_path(pdf_rel_path)
    try:
        if extract_pdf_first_page_thumbnail(pdf_path, out_path):
            return thumb_public_url(campaign_slug, doc_slug)
    except Exception:
        return None
    return None


def _normalize_public_url(url: str) -> Optional[str]:
    value = (url or '').strip()
    if not value:
        return None
    if value.startswith('/'):
        return value
    if value.startswith(('http://', 'https://')):
        return value
    return None


def _hero_from_knowledge_scaffold(submission) -> Optional[str]:
    if not submission or not getattr(submission, 'artifact_id', None):
        return None
    try:
        from models import Artifact

        art = Artifact.query.get(submission.artifact_id)
    except Exception:
        return None
    scaffold = getattr(art, 'knowledge_scaffold', None) if art else None
    if not isinstance(scaffold, dict):
        return None
    for key in _DRAFT_HERO_SCAFFOLD_KEYS:
        url = _normalize_public_url(str(scaffold.get(key) or ''))
        if url:
            return url
    return None


def _hero_from_text_content(text: str) -> Optional[str]:
    if not text:
        return None
    if _BOOK_COVER_MD_RE.search(text):
        return '/static/images/book/cover.png'
    og = _OG_IMAGE_RE.search(text)
    if og:
        return _normalize_public_url(og.group(1))
    src = _IMG_SRC_RE.search(text)
    if src:
        return _normalize_public_url(src.group(1))
    return None


def _hero_from_submission_file(submission) -> Optional[str]:
    file_path = getattr(submission, 'file_path', None)
    filename = (getattr(submission, 'filename', None) or '').lower()
    if not file_path or not os.path.isfile(file_path):
        return None
    _, ext = os.path.splitext(filename)
    try:
        if ext in ('.htm', '.html', '.md', '.markdown', '.txt'):
            with open(file_path, encoding='utf-8', errors='replace') as handle:
                return _hero_from_text_content(handle.read())
    except Exception:
        return None
    return None


def _hero_from_ordinal_content(submission) -> Optional[str]:
    url = getattr(submission, 'ordinalContentUrl', None)
    content_type = (getattr(submission, 'ordinalContentType', None) or '').lower()
    if not url:
        return None
    if content_type.startswith('image/'):
        return _normalize_public_url(url)
    if 'html' not in content_type and 'text' not in content_type and 'json' not in content_type:
        return None
    try:
        import requests
        from services.url_safety import validate_ordinals_fetch_url

        safe_url = validate_ordinals_fetch_url(url)
        response = requests.get(
            safe_url,
            timeout=8,
            headers={'User-Agent': 'GovHub-CampaignThumb/1.0'},
        )
        if response.status_code != 200:
            return None
        return _hero_from_text_content(response.text)
    except Exception:
        return None


def resolve_draft_hero_url(draft_ref: str) -> Optional[str]:
    """
    Resolve a draft-linked card thumbnail before PDF auto-extract.

    Field names (when added on ``Artifact.knowledge_scaffold``):
    ``heroImageUrl``, ``coverImageUrl`` (snake_case aliases also supported).
    Book HTML/markdown may use ``/assets/cover.png`` (mapped to Gov Hub static cover).
    """
    draft_ref = (draft_ref or '').strip()
    if not draft_ref:
        return None
    try:
        from services.draft_reader import build_draft_context

        draft, submission = build_draft_context(draft_ref)
    except Exception:
        return None
    if not submission:
        return None
    url = _hero_from_knowledge_scaffold(submission)
    if url:
        return url
    url = _hero_from_submission_file(submission)
    if url:
        return url
    if getattr(submission, 'sourceType', None) == 'ordinal':
        return _hero_from_ordinal_content(submission)
    return None


def _pdf_rel_path_for_item(item: Dict[str, Any]) -> Optional[str]:
    deck = (item.get('deckPath') or '').strip()
    if deck:
        return deck
    draft_ref = (item.get('draftRef') or '').strip()
    if not draft_ref:
        return None
    try:
        from services.draft_reader import build_draft_context

        _, submission = build_draft_context(draft_ref)
    except Exception:
        return None
    if not submission or not submission.file_path:
        return None
    if not (submission.filename or '').lower().endswith('.pdf'):
        return None
    rel = os.path.relpath(submission.file_path, PROJECT_ROOT).replace(os.sep, '/')
    return rel


def resolve_campaign_card_thumbnail(
    cfg: Optional[CampaignConfig],
    item: Dict[str, Any],
    *,
    external: bool = False,
) -> Optional[str]:
    """
    Card thumbnail resolution order:
    1. Explicit ``thumbnailUrl`` / ``thumbnail``
    2. Draft hero (paper / draft types with ``draftRef``)
    3. PDF first-page extract (slide_deck / paper with PDF path)
    4. YouTube poster (external links)
    """
    explicit = explicit_thumbnail(item)
    if explicit:
        return explicit

    doc_type = (item.get('type') or '').strip().lower()
    draft_ref = (item.get('draftRef') or '').strip()
    if doc_type in _DRAFT_DOC_TYPES and draft_ref:
        hero = resolve_draft_hero_url(draft_ref)
        if hero:
            return hero

    campaign_slug = getattr(cfg, 'slug', None) if cfg else None
    doc_slug = (item.get('slug') or '').strip()
    if campaign_slug and doc_slug and doc_type in _PDF_DOC_TYPES:
        pdf_rel = _pdf_rel_path_for_item(item)
        if pdf_rel:
            cached = ensure_pdf_thumbnail(campaign_slug, doc_slug, pdf_rel)
            if cached:
                return cached

    url = (item.get('url') or '').strip()
    vid = _youtube_video_id(url)
    if external and vid:
        return f'https://img.youtube.com/vi/{vid}/hqdefault.jpg'
    return None


def persist_document_thumbnail(cfg: CampaignConfig, doc_slug: str, thumbnail_url: str) -> None:
    """Write thumbnail URL to seed JSON and/or Monument structure, then reload cache."""
    from extensions import db
    from models import Monument

    thumbnail_url = (thumbnail_url or '').strip()
    if not thumbnail_url:
        return

    seed_path = os.path.join(CAMPAIGN_ROOT, cfg.slug, 'campaign-seed.json')
    if os.path.isfile(seed_path):
        with open(seed_path, encoding='utf-8') as handle:
            seed = json.load(handle)
        changed = False
        for collection in ('documents', 'externalLinks'):
            for row in seed.get(collection) or []:
                if row.get('slug') == doc_slug:
                    row['thumbnailUrl'] = thumbnail_url
                    changed = True
        if changed:
            with open(seed_path, 'w', encoding='utf-8') as handle:
                json.dump(seed, handle, indent=2)
                handle.write('\n')

    monument = None
    if cfg.monument_id:
        monument = Monument.query.get(cfg.monument_id)
    if not monument:
        monument = Monument.query.filter_by(campaign_slug=cfg.slug).first()
    if monument and monument.structure_json:
        try:
            structure = json.loads(monument.structure_json)
        except (TypeError, ValueError):
            structure = {}
        for node in structure.get('nodes') or []:
            if node.get('slug') == doc_slug:
                node['thumbnailUrl'] = thumbnail_url
        monument.structure_json = json.dumps(structure, indent=2)
        db.session.commit()

    reload_campaign_cache()


def save_uploaded_campaign_thumbnail(
    campaign_slug: str,
    doc_slug: str,
    file_storage,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate upload, save as ``<doc-slug>-thumb.jpg`` under campaign assets.
    Returns ``(public_url, error_message)``.
    """
    from services.utils import allowed_image_file
    from services.images import _cover_crop_to_bounds
    from PIL import Image

    if not file_storage or not file_storage.filename:
        return None, 'No file selected'
    if not allowed_image_file(file_storage.filename):
        return None, 'Invalid file type. Allowed: PNG, JPG, GIF, WebP'

    out_path = thumb_abs_path(campaign_slug, doc_slug)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img.load()
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        elif img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        cropped = _cover_crop_to_bounds(img, THUMB_WIDTH, THUMB_HEIGHT)
        cropped = cropped.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
        cropped.save(out_path, 'JPEG', quality=88, optimize=True)
    except Exception as exc:
        return None, f'Could not process image: {exc}'

    return thumb_public_url(campaign_slug, doc_slug), None


def warm_campaign_pdf_thumbnails(cfg: CampaignConfig) -> int:
    """Pre-generate PDF thumbnails for documents missing explicit overrides."""
    created = 0
    for doc in cfg.documents or []:
        if explicit_thumbnail(doc):
            continue
        doc_type = (doc.get('type') or '').strip().lower()
        slug = (doc.get('slug') or '').strip()
        if not slug or doc_type not in _PDF_DOC_TYPES:
            continue
        pdf_rel = _pdf_rel_path_for_item(doc)
        if not pdf_rel:
            continue
        out_path = thumb_abs_path(cfg.slug, slug)
        if os.path.isfile(out_path):
            continue
        if ensure_pdf_thumbnail(cfg.slug, slug, pdf_rel):
            created += 1
    return created
