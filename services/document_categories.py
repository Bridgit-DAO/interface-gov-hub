"""Model C document category (structured type) for submissions."""
from __future__ import annotations

from typing import Optional

DOCUMENT_CATEGORIES = (
    'document',
    'template',
    'tool',
    'guide',
    'glossary',
    'policy',
)

DEFAULT_DOCUMENT_CATEGORY = 'document'

_CATEGORY_LABELS = {
    'document': 'Document',
    'template': 'Template',
    'tool': 'Tool',
    'guide': 'Guide',
    'glossary': 'Glossary',
    'policy': 'Policy',
}


def normalize_document_category(value: Optional[str]) -> str:
    if not value or not str(value).strip():
        return DEFAULT_DOCUMENT_CATEGORY
    v = str(value).strip().lower()
    return v if v in DOCUMENT_CATEGORIES else DEFAULT_DOCUMENT_CATEGORY


def document_category_label(slug: str) -> str:
    return _CATEGORY_LABELS.get(slug, slug.replace('-', ' ').title())


def document_category_options_html(selected: str = '') -> str:
    sel = normalize_document_category(selected)
    parts = []
    for cat in DOCUMENT_CATEGORIES:
        s = ' selected' if cat == sel else ''
        parts.append(
            f'<option value="{cat}"{s}>{document_category_label(cat)}</option>'
        )
    return ''.join(parts)
