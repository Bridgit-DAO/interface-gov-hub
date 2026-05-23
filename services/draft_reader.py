"""Resolve draft context and load document body for record + reader views."""
from __future__ import annotations

import os
from html import escape
from typing import Any, Dict, Optional, Tuple

from services.documents import DRAFTS, submission_file_pages_words
from services.submissions import get_submission_by_ref
from services.submission_preview_md import markdown_to_safe_preview_html, text_looks_like_markdown
from services.ordinals import (
    process_ordinal_markdown,
    looks_like_html_inscription,
    format_ordinal_html_iframe_preview,
)


def _submission_uses_display_ordinal(submission) -> bool:
    if not submission:
        return False
    src = (getattr(submission, 'displayBodySource', None) or 'file').strip().lower()
    return src == 'ordinal' and bool(getattr(submission, 'displayOrdinalContentUrl', None))


def _load_ordinal_body(url: str, content_type: str, draft: dict) -> Tuple[str, bool, int, int]:
    from flask import current_app

    octype = content_type or ''
    document_content = ''
    render_html = False
    pages = draft.get('pages', 1)
    words = draft.get('words', 0)

    if url and ('text/' in octype or 'application/json' in octype):
        try:
            import requests

            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                raw_content = response.text
                words = len(raw_content.split())
                pages = max(1, (words + 499) // 500)
                draft['pages'] = pages
                draft['words'] = words

                is_markdown = False
                for pattern in (
                    r'^#{1,6}\s+.+$',
                    r'\*\*.+\*\*',
                    r'\*.+\*',
                    r'^\s*[-*+]\s+',
                    r'^\s*\d+\.\s+',
                    r'\[.+\]\(.+\)',
                    r'!\[.*\]\(.+\)',
                ):
                    import re

                    if re.search(pattern, raw_content, re.MULTILINE):
                        is_markdown = True
                        break

                if looks_like_html_inscription(raw_content, content_type):
                    document_content = format_ordinal_html_iframe_preview(url)
                    render_html = True
                elif is_markdown:
                    document_content = process_ordinal_markdown(raw_content)
                    render_html = True
                else:
                    document_content = raw_content
        except Exception as exc:
            current_app.logger.warning('Failed to fetch ordinal content: %s', exc)
            document_content = f'Error loading ordinal content: {exc}'
    elif url and octype.startswith('image/'):
        document_content = (
            f'<img src="{escape(url, quote=True)}" class="img-fluid" '
            f'style="max-width: 100%;" alt="Ordinal image content">'
        )
        render_html = True
    else:
        document_content = (
            f'Ordinal content type: {escape(octype)}\n'
            'Preview not available for this content type.'
        )

    return document_content, render_html, pages, words


def build_draft_context(draft_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """
    Resolve draft dict + submission for a URL ref (draft name, id, or ml_number).
    Returns (None, None) when not found.
    """
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    submission = None

    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            source_type = getattr(submission, 'sourceType', 'file')
            pages_count, words_count = submission_file_pages_words(submission)
            dbs = getattr(submission, 'displayBodySource', None) or 'file'
            displaying_linked = (
                dbs.strip().lower() == 'ordinal'
                and bool(getattr(submission, 'displayOrdinalContentUrl', None))
            )
            draft = {
                'name': submission.draft_name or submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'abstract': submission.abstract or 'Abstract not available for this draft.',
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'rev': getattr(submission, 'revision_number', '') or '00',
                'pages': pages_count,
                'words': words_count,
                'stream': 'mltf',
                'ml_number': submission.ml_number,
                'sourceType': source_type,
                'ordinalId': getattr(submission, 'ordinalId', None),
                'inscriptionNumber': getattr(submission, 'inscriptionNumber', None),
                'blockHeight': getattr(submission, 'blockHeight', None),
                'inscriptionTimestamp': getattr(submission, 'inscriptionTimestamp', None),
                'ordinalContentType': getattr(submission, 'ordinalContentType', ''),
                'is_revision': getattr(submission, 'is_revision', False),
                'revision_number': getattr(submission, 'revision_number', ''),
                'parent_draft_name': getattr(submission, 'parent_draft_name', ''),
                'displayBodySource': dbs,
                'displayOrdinalId': getattr(submission, 'displayOrdinalId', None),
                'displayingLinkedOrdinal': displaying_linked,
            }

    if not draft:
        return None, None

    if not submission:
        submission = get_submission_by_ref(draft.get('name')) or get_submission_by_ref(draft_name)
        if submission:
            dbs = getattr(submission, 'displayBodySource', None) or 'file'
            draft['displayBodySource'] = dbs
            draft['displayOrdinalId'] = getattr(submission, 'displayOrdinalId', None)
            draft['displayingLinkedOrdinal'] = (
                dbs.strip().lower() == 'ordinal'
                and bool(getattr(submission, 'displayOrdinalContentUrl', None))
            )

    return draft, submission


def draft_display_id(draft: dict) -> str:
    if draft.get('status') == 'approved' and draft.get('ml_number'):
        return str(draft['ml_number'])
    return str(draft.get('name') or '')


def load_draft_document_body(
    draft: dict,
    submission,
    draft_name: str,
    *,
    pdf_iframe_height: str = '800px',
) -> Tuple[str, bool, int, int]:
    """
    Load body HTML/text for record or reader view.
    Returns (content, render_as_html, pages, words).
    """
    document_content = 'Document content not available.'
    calculated_pages = draft.get('pages', 1)
    calculated_words = draft.get('words', 0)
    render_document_as_html = False

    if submission and _submission_uses_display_ordinal(submission):
        return _load_ordinal_body(
            submission.displayOrdinalContentUrl,
            submission.displayOrdinalContentType or '',
            draft,
        )

    if submission and draft.get('sourceType') == 'ordinal':
        return _load_ordinal_body(
            getattr(submission, 'ordinalContentUrl', None),
            getattr(submission, 'ordinalContentType', '') or '',
            draft,
        )

    if submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext((submission.filename or '').lower())
        try:
            if ext in ['.txt', '.xml', '.md', '.markdown']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    raw_text = f.read()
                calculated_words = len(raw_text.split())
                calculated_pages = max(1, (calculated_words + 499) // 500)
                if ext in ('.md', '.markdown'):
                    md_html = markdown_to_safe_preview_html(raw_text)
                    if md_html:
                        document_content = md_html
                        render_document_as_html = True
                    else:
                        document_content = raw_text
                elif ext == '.txt':
                    if text_looks_like_markdown(raw_text):
                        md_html = markdown_to_safe_preview_html(raw_text)
                        if md_html:
                            document_content = md_html
                            render_document_as_html = True
                        else:
                            document_content = raw_text
                    else:
                        document_content = raw_text
                else:
                    document_content = raw_text
            elif ext == '.docx':
                from docx import Document

                doc = Document(submission.file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content_parts.append(cell.text)
                document_content = '\n\n'.join(content_parts)
                calculated_words = len(document_content.split())
                calculated_pages = max(1, (calculated_words + 499) // 500)
            elif ext == '.pdf':
                from PyPDF2 import PdfReader

                reader = PdfReader(submission.file_path)
                calculated_pages = len(reader.pages) if reader.pages else 1
                calculated_words = calculated_pages * 275
                file_size_kb = os.path.getsize(submission.file_path) / 1024
                render_document_as_html = True
                document_content = f'''
<div class="pdf-viewer-container">
    <div class="alert alert-info mb-3">
        <i class="bi bi-file-pdf"></i> PDF Document ({calculated_pages} pages, ~{calculated_words} words, {file_size_kb:.1f} KB)
    </div>
    <iframe src="/view/{escape(draft_name, quote=True)}"
            type="application/pdf"
            style="width: 100%; height: {pdf_iframe_height}; border: 1px solid var(--card-border); border-radius: 4px;"
            title="PDF Document Viewer">
        <p>Your browser does not support PDF preview.
           <a href="/download/{escape(draft_name, quote=True)}">Download the PDF</a> to view it.</p>
    </iframe>
</div>
'''
            else:
                document_content = (
                    f'Document content cannot be displayed for {ext.upper()} files. Please download to view.'
                )
        except Exception as exc:
            document_content = f'Error loading document content: {exc}'

        draft['pages'] = calculated_pages
        draft['words'] = calculated_words
        return document_content, render_document_as_html, calculated_pages, calculated_words

    if draft and draft.get('name'):
        authors = draft.get('authors') or []
        document_content = f"""INTERNET-DRAFT                                               {', '.join(authors)}
Intended status: Informational                            Meta-Layer Initiative
Expires: {draft.get('date', 'TBD')}                                      {draft.get('date', 'TBD')}


{draft.get('title', 'Document Title')}


Abstract

{draft.get('abstract', 'Abstract not available.')}


1. Introduction

This document describes {draft.get('title', 'the subject matter')}.

The content of this draft is currently being developed and will be available
in the full document once published.
"""
        return document_content, False, calculated_pages, calculated_words

    return document_content, render_document_as_html, calculated_pages, calculated_words
