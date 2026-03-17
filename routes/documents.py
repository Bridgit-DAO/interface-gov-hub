"""Documents routes: /doc/active, /doc/all, /doc/draft/*, comments, follow, history, revisions, /test/, annotations."""
import os
import re
import html as html_mod
from datetime import datetime, timedelta

from flask import Blueprint, request, redirect, url_for, flash, session, Response, current_app, jsonify, send_file

from extensions import db
from models import (
    Comment, DocumentHistory, Submission, Artifact, ArtifactRelation,
    Layer, UserFollow,
)
from services.identity import get_current_user, require_auth
from services.submissions import get_submission_by_ref, add_to_document_history
from services.ordinals import process_ordinal_markdown, shorten_inscription_id
from services.documents import (
    load_draft_data,
    DRAFTS,
    build_comment_tree,
    render_comment_tree,
    toggle_comment_like,
    get_comment_likes,
    is_comment_liked,
    is_user_following_draft,
    get_notification_controls,
    add_comment_reply,
    EDIT_DELETE_TIME_MINUTES,
)

bp = Blueprint('documents', __name__, url_prefix='')


def _get_drafts():
    """Get DRAFTS list (cached in services.documents)."""
    return DRAFTS


@bp.route('/doc/active/')
def active_documents():
    """Show active documents (alias for all documents)."""
    return all_documents()


@bp.route('/doc/all/')
def all_documents():
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    drafts = _get_drafts()

    all_docs = []
    all_docs.extend(drafts)

    approved_submissions = Submission.query.filter(
        Submission.status.in_(['approved', 'published']),
        Submission.is_revision == False
    ).all()

    for submission in approved_submissions:
        parent_refs = [submission.id]
        if submission.draft_name:
            parent_refs.append(submission.draft_name)
        latest_revision = Submission.query.filter(
            Submission.parent_draft_name.in_(parent_refs),
            Submission.is_revision == True,
            Submission.status.in_(['approved', 'published'])
        ).order_by(Submission.revision_number.desc()).first()

        display_submission = latest_revision if latest_revision else submission
        pages = display_submission.pages if display_submission.pages else 1
        words = display_submission.words if display_submission.words else 0
        is_revision = getattr(display_submission, 'is_revision', False)
        revision_number = getattr(display_submission, 'revision_number', '')

        all_docs.append({
            'name': display_submission.id,
            'title': display_submission.title,
            'authors': display_submission.authors if isinstance(display_submission.authors, list) else [display_submission.authors] if display_submission.authors else [],
            'group': display_submission.group or 'N/A',
            'status': display_submission.status,
            'rev': revision_number if is_revision else '00',
            'pages': pages,
            'words': words,
            'date': display_submission.submitted_at.strftime('%Y-%m-%d') if display_submission.submitted_at else '',
            'abstract': display_submission.abstract or '',
            'ml_number': display_submission.ml_number,
            'is_revision': is_revision,
            'revision_number': revision_number
        })

    docs_html = ""
    for draft in all_docs:
        display_id = draft.get('ml_number') or draft['name']
        is_revision = draft.get('is_revision', False)
        revision_number = draft.get('revision_number', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''

        docs_html += f"""
        <div class="col-md-6 document-card">
            <div class="card">
                <div class="card-body">
                    <h5 class="card-title document-title">
                        <a href="/doc/draft/{draft['name']}/">{display_id}</a>
                        {revision_badge}
                    </h5>
                    <p class="card-text">{draft['title']}</p>
                    <div class="document-meta">
                        <span class="badge bg-secondary status-badge">{draft['status']}</span>
                        <span class="ms-2">Rev: {draft['rev']}</span>
                        <span class="ms-2">{draft['pages']} pages</span>
                        <span class="ms-2">{draft['words']} words</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Authors: {', '.join(draft['authors']) if draft['authors'] else 'N/A'}<br>
                            Group: {draft['group']}<br>
                            Date: {draft['date']}
                        </small>
                    </div>
                    <div class="mt-2">
                        <a href="/doc/draft/{draft['name']}/comments/" class="btn btn-sm btn-outline-primary">Comments</a>
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-sm btn-outline-secondary">History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-sm btn-outline-info">Revisions</a>
                    </div>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <h1>All Documents</h1>
        <p>Showing {len(all_docs)} documents</p>

        <div class="row">
            {docs_html}
        </div>
    </div>
    """

    return _format_base_template(title="All Documents - MLGH", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/doc/draft/<path:draft_name>.txt')
def draft_text(draft_name):
    """Serve draft content as plain text."""
    DRAFTS = _get_drafts()
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    submission = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            draft = {
                'name': submission.draft_name or submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'abstract': submission.abstract or 'Abstract not available for this draft.',
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
            }

    if not draft:
        return "Document not found", 404

    document_content = "Document content not available."

    if submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
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
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                document_content = '\n\n'.join(content_parts)
                document_content = re.sub(r'\n+', '\n', document_content)
                document_content = re.sub(r' +', ' ', document_content)
            else:
                document_content = f"Document content cannot be displayed for {ext.upper()} files. Please download to view."
        except Exception as e:
            document_content = f"Error loading document content: {str(e)}"

    elif draft and 'name' in draft:
        document_content = f"""INTERNET-DRAFT                                               {', '.join(draft.get('authors', []))}
Intended status: Informational                            Meta-Layer Initiative
Expires: {draft.get('date', 'TBD')}                                      {draft.get('date', 'TBD')}


{draft.get('title', 'Document Title')}


Abstract

{draft.get('abstract', 'Abstract not available.')}


1. Introduction

This document describes {draft.get('title', 'the subject matter')}.

The content of this draft is currently being developed and will be available
in the full document once published.

2. Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions
of BCP 78 and BCP 79.

Meta-Layer Drafts are working documents of the Meta-Layer Task Force
(MLGH). These documents represent proposals and specifications for the
Meta-Layer ecosystem. The list of current Meta-Layer Drafts is available
in the MLGH datatracker.

Internet-Drafts are draft documents valid for a maximum of six months and
may be updated, replaced, or obsoleted by other documents at any time. It is
inappropriate to use Internet-Drafts as reference material or to cite them
other than as "work in progress."

This Internet-Draft will expire on {draft.get('date', 'TBD')}.


3. References

[MLGH] MLGH Datatracker, https://rfc.themetalayer.org/

Authors' Addresses

{chr(10).join([f'{author} <email@example.com>' for author in draft.get('authors', [])])}

Meta-Layer Initiative
"""

    return Response(document_content, mimetype='text/plain; charset=utf-8')


@bp.route('/doc/draft/<path:draft_name>/')
def draft_detail(draft_name):
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER
    from services.hypothesis import generate_hypothesis_config, HYPOTHESIS_ENABLED

    drafts = _get_drafts()
    draft = next((d for d in drafts if d['name'] == draft_name), None)

    submission = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            source_type = getattr(submission, 'sourceType', 'file')
            pages_count = 1
            words_count = 0
            ordinal_content_url = getattr(submission, 'ordinalContentUrl', None)
            ordinal_content_type = getattr(submission, 'ordinalContentType', '')

            if source_type == 'ordinal':
                if ordinal_content_url and ('text/' in ordinal_content_type or 'application/json' in ordinal_content_type):
                    try:
                        import requests
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            text_content = response.text
                            words_count = len(text_content.split())
                            pages_count = max(1, (words_count + 499) // 500)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to fetch ordinal content for word/page count: {e}")
                        pass

            draft = {
                'name': submission.draft_name or submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'abstract': submission.abstract or 'Abstract not available for this draft.',
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'rev': '00',
                'pages': pages_count,
                'words': words_count,
                'stream': 'mltf',
                'ml_number': submission.ml_number,
                'sourceType': source_type,
                'ordinalId': getattr(submission, 'ordinalId', None),
                'inscriptionNumber': getattr(submission, 'inscriptionNumber', None),
                'blockHeight': getattr(submission, 'blockHeight', None),
                'inscriptionTimestamp': getattr(submission, 'inscriptionTimestamp', None),
                'ordinalContentType': ordinal_content_type,
                'is_revision': getattr(submission, 'is_revision', False),
                'revision_number': getattr(submission, 'revision_number', ''),
                'parent_draft_name': getattr(submission, 'parent_draft_name', '')
            }

    if not draft:
        return "Document not found", 404

    document_content = "Document content not available."
    calculated_pages = draft.get('pages', 1)
    calculated_words = draft.get('words', 0)

    if submission and draft.get('sourceType') == 'ordinal':
        ordinal_content_url = getattr(submission, 'ordinalContentUrl', None)
        ordinal_content_type = getattr(submission, 'ordinalContentType', '')

        if ordinal_content_url and ('text/' in ordinal_content_type or 'application/json' in ordinal_content_type):
            try:
                import requests
                import markdown2
                import bleach
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    raw_content = response.text
                    words = len(raw_content.split())
                    calculated_pages = max(1, (words + 499) // 500)
                    calculated_words = words
                    draft['pages'] = calculated_pages
                    draft['words'] = calculated_words

                    is_markdown = False
                    markdown_patterns = [
                        r'^#{1,6}\s+.+$',
                        r'\*\*.+\*\*',
                        r'\*.+\*',
                        r'^\s*[-*+]\s+',
                        r'^\s*\d+\.\s+',
                        r'\[.+\]\(.+\)',
                        r'!\[.*\]\(.+\)'
                    ]
                    for pattern in markdown_patterns:
                        if re.search(pattern, raw_content, re.MULTILINE):
                            is_markdown = True
                            break

                    if is_markdown:
                        document_content = process_ordinal_markdown(raw_content)
                    else:
                        document_content = raw_content
            except Exception as e:
                current_app.logger.warning(f"Failed to fetch ordinal content for display: {e}")
                document_content = f"Error loading ordinal content: {str(e)}"
        elif ordinal_content_url and ordinal_content_type.startswith('image/'):
            document_content = f'<img src="{ordinal_content_url}" class="img-fluid" style="max-width: 100%;" alt="Ordinal image content">'
        else:
            document_content = f"Ordinal content type: {ordinal_content_type}\nPreview not available for this content type."

    elif submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
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
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                calculated_pages = len(reader.pages) if reader.pages else 1
                calculated_words = calculated_pages * 275
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                document_content = f'''
<div class="pdf-viewer-container">
    <div class="alert alert-info mb-3">
        <i class="bi bi-file-pdf"></i> PDF Document ({calculated_pages} pages, ~{calculated_words} words, {file_size_kb:.1f} KB)
    </div>
    <iframe src="/view/{draft_name}"
            type="application/pdf"
            style="width: 100%; height: 800px; border: 1px solid var(--card-border); border-radius: 4px;"
            title="PDF Document Viewer">
        <p>Your browser does not support PDF preview.
           <a href="/download/{draft_name}">Download the PDF</a> to view it.</p>
    </iframe>
</div>
'''
            else:
                document_content = f"Document content cannot be displayed for {ext.upper()} files. Please download to view."
        except Exception as e:
            document_content = f"Error loading document content: {str(e)}"
        if submission:
            draft['pages'] = calculated_pages
            draft['words'] = calculated_words

    elif draft and 'name' in draft:
        document_content = f"""INTERNET-DRAFT                                               {', '.join(draft.get('authors', []))}
Intended status: Informational                            Meta-Layer Initiative
Expires: {draft.get('date', 'TBD')}                                      {draft.get('date', 'TBD')}


{draft.get('title', 'Document Title')}


Abstract

{draft.get('abstract', 'Abstract not available.')}


1. Introduction

This document describes {draft.get('title', 'the subject matter')}.

The content of this draft is currently being developed and will be available
in the full document once published.

2. Status of This Memo

This Internet-Draft is submitted in full conformance with the provisions
of BCP 78 and BCP 79.

Meta-Layer Drafts are working documents of the Meta-Layer Task Force
(MLGH). These documents represent proposals and specifications for the
Meta-Layer ecosystem. The list of current Meta-Layer Drafts is available
in the MLGH datatracker.

Internet-Drafts are draft documents valid for a maximum of six months and
may be updated, replaced, or obsoleted by other documents at any time. It is
inappropriate to use Internet-Drafts as reference material or to cite them
other than as "work in progress."

This Internet-Draft will expire on {draft.get('date', 'TBD')}.


3. References

[MLGH] MLGH Datatracker, https://rfc.themetalayer.org/

Authors' Addresses

{chr(10).join([f'{author} <email@example.com>' for author in draft.get('authors', [])])}

Meta-Layer Initiative
"""

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    _sub = submission
    if not _sub and draft:
        _sub = get_submission_by_ref(draft.get('name')) or get_submission_by_ref(draft.get('ml_number')) or get_submission_by_ref(draft_name)
    artifact_id = getattr(_sub, 'artifact_id', None) if _sub else None
    layer_slug = None
    supports = []
    opposes = []
    support_oppose_card_html = ''
    if artifact_id:
        artifact = Artifact.query.get(artifact_id)
        if artifact and artifact.layer_id:
            layer = Layer.query.get(artifact.layer_id)
            layer_slug = layer.slug if layer else None
            incoming = ArtifactRelation.query.filter(
                ArtifactRelation.to_object_type == 'artifact',
                ArtifactRelation.to_object_id == artifact_id,
            ).all()
            supports = [r for r in incoming if r.relation_type == 'supports']
            opposes = [r for r in incoming if r.relation_type == 'opposes']

            def _so_row(r):
                a = Artifact.query.get(r.from_object_id)
                t = (a.title or a.id[:8]) if a else r.from_object_id[:8]
                return f'<li class="list-group-item list-group-item-action"><a href="/layers/{layer_slug}/artifacts/{r.from_object_id}/" class="text-decoration-none">{html_mod.escape(str(t)[:50])}</a></li>'
            supports_li = ''.join(_so_row(r) for r in supports) if supports else '<li class="list-group-item text-muted small">No support yet</li>'
            opposes_li = ''.join(_so_row(r) for r in opposes) if opposes else '<li class="list-group-item text-muted small">No opposition yet</li>'
            if current_user:
                add_btns = f'''
                    <div class="d-flex gap-2 mt-2">
                        <button type="button" class="btn btn-outline-success btn-sm flex-grow-1" data-bs-toggle="modal" data-bs-target="#addSupportModal"><i class="fas fa-thumbs-up me-1"></i>Add support</button>
                        <button type="button" class="btn btn-outline-danger btn-sm flex-grow-1" data-bs-toggle="modal" data-bs-target="#addOppositionModal"><i class="fas fa-thumbs-down me-1"></i>Add opposition</button>
                    </div>
                    <div class="modal fade" id="addSupportModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Add support</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-2"><label class="form-label">Title</label><input type="text" class="form-control" id="support-title" placeholder="Support for this proposal"></div>
                            <div class="mb-2"><label class="form-label">Summary (optional)</label><textarea class="form-control" id="support-summary" rows="2"></textarea></div>
                            <div id="support-alert" class="alert d-none"></div>
                        </div>
                        <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-success" id="support-submit-btn">Add support</button></div>
                    </div></div></div>
                    <div class="modal fade" id="addOppositionModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
                        <div class="modal-header"><h5 class="modal-title">Add opposition</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                        <div class="modal-body">
                            <div class="mb-2"><label class="form-label">Title</label><input type="text" class="form-control" id="opposition-title" placeholder="Opposition to this proposal"></div>
                            <div class="mb-2"><label class="form-label">Summary (optional)</label><textarea class="form-control" id="opposition-summary" rows="2"></textarea></div>
                            <div id="opposition-alert" class="alert d-none"></div>
                        </div>
                        <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-danger" id="opposition-submit-btn">Add opposition</button></div>
                    </div></div></div>
                    <script>
                    (function(){{const aid='{artifact_id}';
                    document.getElementById('support-submit-btn').addEventListener('click',async function(){{const btn=this;btn.disabled=true;const alert=document.getElementById('support-alert');alert.classList.add('d-none');try{{const r=await fetch('/api/artifacts/'+aid+'/support/',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title:document.getElementById('support-title').value,summary:document.getElementById('support-summary').value}}),credentials:'same-origin'}});const d=await r.json();if(r.ok)location.reload();else{{alert.textContent=d.error||'Failed';alert.className='alert alert-danger';alert.classList.remove('d-none');}}}}catch(e){{alert.textContent=e.message;alert.className='alert alert-danger';alert.classList.remove('d-none');}}btn.disabled=false;}});
                    document.getElementById('opposition-submit-btn').addEventListener('click',async function(){{const btn=this;btn.disabled=true;const alert=document.getElementById('opposition-alert');alert.classList.add('d-none');try{{const r=await fetch('/api/artifacts/'+aid+'/opposition/',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title:document.getElementById('opposition-title').value,summary:document.getElementById('opposition-summary').value}}),credentials:'same-origin'}});const d=await r.json();if(r.ok)location.reload();else{{alert.textContent=d.error||'Failed';alert.className='alert alert-danger';alert.classList.remove('d-none');}}}}catch(e){{alert.textContent=e.message;alert.className='alert alert-danger';alert.classList.remove('d-none');}}btn.disabled=false;}});
                    }})();
                    </script>
'''
            else:
                add_btns = '<p class="small text-muted mt-2 mb-0"><a href="/login/">Sign in</a> to add support or opposition.</p>'
            support_oppose_card_html = f'''
                <div class="card mt-3">
                    <div class="card-header"><h5>Support &amp; Opposition</h5></div>
                    <div class="card-body">
                        <div class="row g-2">
                            <div class="col-6"><h6 class="text-success small">Support ({len(supports)})</h6><ul class="list-group list-group-flush small">{supports_li}</ul></div>
                            <div class="col-6"><h6 class="text-danger small">Opposition ({len(opposes)})</h6><ul class="list-group list-group-flush small">{opposes_li}</ul></div>
                        </div>
                        {add_btns}
                        <a href="/layers/{layer_slug}/artifacts/{artifact_id}/" class="btn btn-outline-secondary btn-sm mt-2 w-100">View full artifact</a>
                    </div>
                </div>
'''
    if not layer_slug and _sub and getattr(_sub, 'layer_id', None):
        layer = Layer.query.get(_sub.layer_id)
        layer_slug = layer.slug if layer else None

    def _artifact_card_and_modal_html(draft, sub, aid, lslug, user):
        if not lslug or not user:
            return ''
        if not sub and not aid:
            return ''
        has_artifact = bool(aid)
        sub_id = getattr(sub, 'id', None) if sub else None
        artifact_types = ['proposal', 'evidence', 'insight', 'reflection', 'translation', 'implementation', 'decision', 'monument', 'bridge', 'submission']
        aid_js = f"'{aid}'" if aid else 'null'
        sub_id_js = f"'{sub_id}'" if sub_id else 'null'
        return f'''
        <div class="card mt-3">
            <div class="card-header"><h5>Artifact</h5></div>
            <div class="card-body">
                {f'<a href="/layers/{lslug}/artifacts/{aid}/" class="btn btn-outline-secondary btn-sm mb-2 w-100">View full artifact</a>' if aid else ''}
                <button type="button" class="btn btn-outline-primary btn-sm w-100" id="artifact-modal-btn" data-artifact-id={aid_js} data-submission-id={sub_id_js}>
                    <i class="fas fa-edit me-1"></i>{'Edit Artifact' if has_artifact else 'Create Artifact'}
                </button>
            </div>
        </div>
        <div class="modal fade" id="artifactModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="artifactModalTitle">Edit Artifact</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div id="artifact-alert" class="alert d-none mb-2"></div>
                        <div class="mb-2"><label class="form-label">Type</label><select class="form-select" id="artifact-type"><option value="">—</option>{''.join(f'<option value="{t}">{t}</option>' for t in artifact_types)}</select></div>
                        <div class="mb-2"><label class="form-label">Subtype</label><input type="text" class="form-control" id="artifact-subtype" placeholder="e.g. governance proposal"></div>
                        <div class="mb-2"><label class="form-label">Title</label><input type="text" class="form-control" id="artifact-title" placeholder="Artifact title"></div>
                        <div class="mb-2"><label class="form-label">Summary</label><textarea class="form-control" id="artifact-summary" rows="2" placeholder="Brief summary"></textarea></div>
                        <div class="mb-2"><label class="form-label">Body</label><textarea class="form-control" id="artifact-body" rows="4" placeholder="Full content"></textarea></div>
                        <div class="mb-2"><label class="form-label">URI</label><input type="text" class="form-control" id="artifact-uri" placeholder="https://..."></div>
                        <div class="mb-2"><label class="form-label">Status</label><select class="form-select" id="artifact-status"><option value="draft">draft</option><option value="published">published</option><option value="archived">archived</option></select></div>
                        <div class="row"><div class="col-6"><label class="form-label">Source language</label><input type="text" class="form-control" id="artifact-source-lang" placeholder="en"></div><div class="col-6"><label class="form-label">Current language</label><input type="text" class="form-control" id="artifact-current-lang" placeholder="en"></div></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="artifact-save-btn">Save</button>
                    </div>
                </div>
            </div>
        </div>
        <script>
        (function(){{
            const btn = document.getElementById('artifact-modal-btn');
            if (!btn) return;
            const aid = btn.dataset.artifactId;
            const subId = btn.dataset.submissionId;
            const modal = new bootstrap.Modal(document.getElementById('artifactModal'));
            const modalTitle = document.getElementById('artifactModalTitle');
            const saveBtn = document.getElementById('artifact-save-btn');
            const alertEl = document.getElementById('artifact-alert');
            const fields = ['artifact_type','artifact_subtype','title','summary','body','uri','status','source_language','current_language'];
            const ids = {{artifact_type:'artifact-type',artifact_subtype:'artifact-subtype',title:'artifact-title',summary:'artifact-summary',body:'artifact-body',uri:'artifact-uri',status:'artifact-status',source_language:'artifact-source-lang',current_language:'artifact-current-lang'}};
            function showAlert(msg,type){{
                alertEl.textContent=msg; alertEl.className='alert alert-'+type; alertEl.classList.remove('d-none');
            }}
            function getPayload(){{
                const p={{}};
                for (const f of fields){{ const el=document.getElementById(ids[f]); if(el) p[f]=el.value===''?null:el.value; }}
                return p;
            }}
            function setFields(art){{
                for (const f of fields){{ const el=document.getElementById(ids[f]); if(el&&art[f]!==undefined) el.value=art[f]||''; }}
            }}
            btn.addEventListener('click', async function(){{
                modalTitle.textContent = aid ? 'Edit Artifact' : 'Create Artifact';
                if (aid) {{
                    try {{
                        const r = await fetch('/api/artifacts/'+aid+'/', {{credentials:'same-origin'}});
                        const d = await r.json();
                        if (r.ok) setFields(d); else showAlert(d.error||'Failed to load','danger');
                    }} catch(e) {{ showAlert(e.message,'danger'); }}
                }} else {{
                    setFields({{}});
                }}
                modal.show();
            }});
            saveBtn.addEventListener('click', async function(){{
                saveBtn.disabled=true; alertEl.classList.add('d-none');
                try {{
                    let d;
                    if (aid) {{
                        const r = await fetch('/api/artifacts/'+aid+'/', {{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(getPayload()),credentials:'same-origin'}});
                        d = await r.json();
                        if (r.ok) {{ location.reload(); saveBtn.disabled=false; return; }}
                    }} else {{
                        if (!subId) {{ showAlert('No submission','danger'); saveBtn.disabled=false; return; }}
                        const r0 = await fetch('/api/submissions/'+subId+'/ensure-artifact/', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{}}),credentials:'same-origin'}});
                        d = await r0.json();
                        if (r0.ok && d.artifact_id) {{
                            const r1 = await fetch('/api/artifacts/'+d.artifact_id+'/', {{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(getPayload()),credentials:'same-origin'}});
                            d = await r1.json();
                            if (r1.ok) {{ location.reload(); saveBtn.disabled=false; return; }}
                        }}
                    }}
                    showAlert(d.error||'Failed','danger');
                }} catch(e) {{ showAlert(e.message,'danger'); }}
                saveBtn.disabled=false;
            }});
        }})();
        </script>
        '''

    if draft.get('status') == 'approved' and draft.get('ml_number'):
        display_id = draft.get('ml_number')
    else:
        display_id = draft['name']
    is_revision = draft.get('is_revision', False)
    revision_number = draft.get('revision_number', '')
    revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''

    if draft.get('sourceType') == 'ordinal':
        content_style = "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 1em; line-height: 1.6;"
    else:
        content_style = "font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.4; white-space: pre-wrap;"

    content = f"""
    <div class="container mt-4">
        <h1>{display_id} {revision_badge}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Information</h5>
                    </div>
                    <div class="card-body">
                        <table class="table" style="color: var(--text-primary) !important;">
                            <tr><td style="color: var(--text-secondary) !important;"><strong>ID:</strong></td><td style="color: var(--text-primary) !important;">{display_id}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Title:</strong></td><td style="color: var(--text-primary) !important;">{draft['title']}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Status:</strong></td><td style="color: var(--text-primary) !important;"><span class="badge bg-secondary">{draft['status']}</span></td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Authors:</strong></td><td style="color: var(--text-primary) !important;">{', '.join(draft['authors'])}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Group:</strong></td><td style="color: var(--text-primary) !important;">{draft['group'] or 'N/A'}</td></tr>
                            <tr><td style="color: var(--text-secondary) !important;"><strong>Date:</strong></td><td style="color: var(--text-primary) !important;">{draft['date']}</td></tr>
                            {f'<tr><td colspan="2" style="padding-top: 15px;"><hr style="border-color: var(--border-color);"></td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Source:</strong></td><td style="color: var(--text-primary) !important;"><span class="badge bg-info"><i class="bi bi-coin"></i> Bitcoin Ordinal</span></td></tr>' if draft.get('sourceType') == 'ordinal' else f'<tr><td style="color: var(--text-secondary) !important;"><strong>Revision:</strong></td><td style="color: var(--text-primary) !important;">{draft["rev"]}</td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Pages:</strong></td><td style="color: var(--text-primary) !important;">{draft["pages"]}</td></tr><tr><td style="color: var(--text-secondary) !important;"><strong>Words:</strong></td><td style="color: var(--text-primary) !important;">{draft["words"]}</td></tr>'}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Inscription #:</strong></td><td style="color: var(--text-primary) !important;">{draft["inscriptionNumber"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('inscriptionNumber') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Block Height:</strong></td><td style="color: var(--text-primary) !important;">{draft["blockHeight"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('blockHeight') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Timestamp:</strong></td><td style="color: var(--text-primary) !important;">{draft["inscriptionTimestamp"].strftime("%Y-%m-%d %H:%M UTC") if draft.get("inscriptionTimestamp") else "N/A"}</td></tr>' if draft.get('sourceType') == 'ordinal' else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Content Type:</strong></td><td style="color: var(--text-primary) !important;">{draft["ordinalContentType"]}</td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('ordinalContentType') else ''}
                            {f'<tr><td style="color: var(--text-secondary) !important;"><strong>Inscription ID:</strong></td><td style="color: var(--text-primary) !important;"><a href="https://ordinals.com/inscription/{draft["ordinalId"]}" target="_blank" class="text-decoration-none" style="color: var(--accent-color) !important;"><code style="font-family: monospace; font-size: 0.85em;">{shorten_inscription_id(draft["ordinalId"], 8)}</code></a></td></tr>' if draft.get('sourceType') == 'ordinal' and draft.get('ordinalId') else ''}
                        </table>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Abstract</h5>
                    </div>
                    <div class="card-body">
                        <p>{draft.get('abstract', 'Abstract not available for this draft.')}</p>
                    </div>
                </div>

                <div class="card mt-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">Document Content</h5>
                        <div>
                            {'' if draft.get('sourceType') == 'ordinal' else f'''
                            <a href="/download/{draft['name']}" class="btn btn-sm btn-outline-primary" target="_blank">
                                <i class="fas fa-download me-1"></i>Download
                            </a>
                            <a href="/doc/draft/{draft['name']}.txt" class="btn btn-sm btn-outline-secondary" target="_blank">
                                <i class="fas fa-external-link-alt me-1"></i>View TXT
                            </a>
                            '''}
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="document-content" style="{content_style} background-color: var(--input-bg) !important; color: var(--text-primary) !important; padding: 20px; border-radius: 8px; max-height: 800px; overflow-y: auto; border: 1px solid var(--input-border);">
{document_content}
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                {_artifact_card_and_modal_html(draft, _sub, artifact_id, layer_slug, current_user)}
                {support_oppose_card_html}
                <div class="card">
                    <div class="card-header">
                        <h5>Actions</h5>
                    </div>
                    <div class="card-body">
                        {f'<a href="/doc/draft/{draft["name"]}/comments/" class="btn btn-primary w-100 mb-2">View Comments ({Comment.query.filter_by(draft_name=draft_name).count()})</a>' if draft.get('status') == 'approved' else ''}
                        {f'<div class="small text-muted mb-2" id="annotation-count">Loading annotation count...</div>' if HYPOTHESIS_ENABLED else ''}
                        <a href="/doc/draft/{draft['name']}/history/" class="btn btn-secondary w-100 mb-2">View History</a>
                        <a href="/doc/draft/{draft['name']}/revisions/" class="btn btn-info w-100 mb-2">View Revisions</a>

                        {f'''<div class="border-top pt-2 mt-2">
                            <h6 class="text-muted mb-2">Annotations</h6>
                            <button id="toggle-annotations" class="btn btn-outline-info w-100 mb-2" onclick="toggleAnnotations()">
                                <i class="fas fa-comment-dots me-1"></i>
                                <span id="annotations-text">Enable Annotations</span>
                            </button>
                            {'<div class="alert alert-info small mt-2" role="alert"><i class="fas fa-user-plus me-1"></i><strong>First time?</strong> <a href="https://hypothes.is/signup" target="_blank" class="alert-link">Create free Hypothesis account</a> (30 seconds) to annotate and highlight text.</div>' if not current_user or not current_user.get('hypothesis_account') else ''}
                            <small class="text-muted d-block">
                                Powered by <a href="https://hypothes.is" target="_blank" class="text-decoration-none">Hypothesis</a>.
                                Public annotations visible to everyone.
                            </small>
                        </div>''' if HYPOTHESIS_ENABLED else ''}
                        {f'<a href="/submit/revision/{draft["name"]}/" class="btn btn-success w-100 mb-2"><i class="fas fa-plus me-1"></i>Submit New Revision</a>' if current_user and draft.get('status') == 'approved' else ''}
                        {'' if draft.get('sourceType') == 'ordinal' else f'<a href="/download/{draft["name"]}" class="btn btn-outline-primary w-100 mb-2">Download Document</a>'}
                        {'<form method="post" action="/doc/draft/' + draft['name'] + '/follow/" style="display: inline;" class="mb-2"><select name="notification_level" class="form-select form-select-sm mb-1"><option value="all">All changes & comments</option><option value="significant">Significant changes only</option><option value="major">Major changes only</option><option value="comments">Comments only</option><option value="none">No notifications</option></select><button type="submit" class="btn btn-success w-100"><i class="fas fa-bell me-1"></i>Follow Document</button></form>' if current_user and draft.get('status') == 'approved' and not is_user_following_draft(draft_name, current_user) else ''}
                        {'<form method="post" action="/doc/draft/' + draft['name'] + '/unfollow/" style="display: inline;" class="mb-2"><button type="submit" class="btn btn-warning w-100"><i class="fas fa-bell-slash me-1"></i>Unfollow Document</button></form>' if current_user and draft.get('status') == 'approved' and is_user_following_draft(draft_name, current_user) else ''}
                        {get_notification_controls(draft_name, current_user) if current_user and draft.get('status') == 'approved' and is_user_following_draft(draft_name, current_user) else ''}
                        {'' if not current_user else ''}
                    </div>
                </div>

                <div class="card mt-3" id="votes-card" style="display: none;">
                    <div class="card-header">
                        <h5>Votes</h5>
                    </div>
                    <div class="card-body" id="votes-container">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                {f'''<div class="card mt-3">
                    <div class="card-header">
                        <h5>Quick Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST" action="/doc/draft/{draft['name']}/comments/">
                            <div class="mb-3">
                                <textarea class="form-control" name="comment" rows="3" placeholder="Add a quick comment..." required></textarea>
                    </div>
                            <button type="submit" class="btn btn-success btn-sm w-100">Post Comment</button>
                        </form>
        </div>
    </div>''' if draft.get('status') == 'approved' else ''}

                <div class="card mt-3">
                    <div class="card-header">
                        <h5>Related Documents</h5>
                    </div>
                <div class="card-body">
                        <p>Related documents would appear here in the real datatracker.</p>
                    </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
        const submissionId = '{draft["name"] if submission else draft_name}';

        async function loadDraftVotes() {{
            try {{
                const allProjects = await fetch('/api/layers/').then(r => r.json());
                let votes = [];

                for (const proj of allProjects.layers || []) {{
                    const res = await fetch(`/api/layers/${{proj.id}}/votes/`);
                    const data = await res.json();
                    const matchingVotes = (data.votes || []).filter(v => v.submission_id === submissionId);
                    votes.push(...matchingVotes);
                }}

                if (votes.length === 0) {{
                    return;
                }}

                document.getElementById('votes-card').style.display = 'block';
                const container = document.getElementById('votes-container');

                let html = '';
                for (const v of votes) {{
                    const statusBadge = v.status === 'active' ? '<span class="badge bg-success">Active</span>' : v.status === 'closed' ? '<span class="badge bg-secondary">Closed</span>' : '<span class="badge bg-info">Scheduled</span>';
                    const resultBadge = v.result ? '<span class="badge bg-' + (v.result === 'passed' ? 'success' : v.result === 'failed' ? 'danger' : 'warning') + ' ms-1">' + v.result + '</span>' : '';
                    html += '<div class="mb-3">';
                    html += '<h6><a href="/votes/' + v.public_id + '/">' + v.title + '</a> ' + statusBadge + resultBadge + '</h6>';
                    html += '<p class="small mb-1">' + (v.description || '') + '</p>';
                    html += '<p class="small text-muted mb-0">Ends: ' + new Date(v.end_at).toLocaleString() + '</p>';
                    html += '</div>';
                }}

                container.innerHTML = html;
            }} catch (e) {{
                console.error('Error loading votes:', e);
            }}
        }}

        loadDraftVotes();
        </script>
        """

    content = content.replace('{document_content}', document_content)

    if draft.get('status') == 'approved' and draft.get('ml_number'):
        title_id = draft.get('ml_number')
    else:
        title_id = draft['name']

    hypothesis_config = generate_hypothesis_config(document_name=draft['name'], document_type='draft')

    return _format_base_template(
        title=f"{title_id} - MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=content,
        build_number=BUILD_NUMBER,
        hypothesis_config=hypothesis_config
    )


@bp.route('/doc/draft/<path:draft_name>/comments/', methods=['GET', 'POST'])
@require_auth
def draft_comments(draft_name):
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER

    DRAFTS = _get_drafts()
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)

    submission = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'ml_number': submission.ml_number
            }

    if not draft:
        return "Document not found", 404

    display_id = draft.get('ml_number') or draft_name

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    current_user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action', 'comment')

        if action == 'comment':
            comment_text = request.form.get('comment', '').strip()
            if comment_text:
                new_comment = Comment(
                    draft_name=draft_name,
                    text=comment_text,
                    author=current_user['name']
                )
                db.session.add(new_comment)
                db.session.commit()
                add_to_document_history(draft_name, 'Comment added', current_user['name'], f'Added comment: {comment_text[:50]}...')
                flash('Comment added successfully!', 'success')
                return redirect(url_for('documents.draft_comments', draft_name=draft_name))
            else:
                flash('Please enter a comment.', 'error')

        elif action == 'like':
            comment_id = request.form.get('comment_id')
            if comment_id:
                liked = toggle_comment_like(draft_name, comment_id, current_user['name'])
                action_text = 'liked' if liked else 'unliked'
                flash(f'Comment {action_text}!', 'success')
                return redirect(url_for('documents.draft_comments', draft_name=draft_name))
            else:
                flash('Invalid comment ID.', 'error')

        elif action == 'reply':
            parent_comment_id = request.form.get('parent_comment_id')
            reply_text = request.form.get('reply_text', '').strip()
            if reply_text and parent_comment_id:
                add_comment_reply(draft_name, parent_comment_id, reply_text, current_user)
                flash('Reply added successfully!', 'success')
                return redirect(url_for('documents.draft_comments', draft_name=draft_name))
            else:
                flash('Please enter a reply.', 'error')

        elif action == 'edit':
            comment_id = request.form.get('comment_id')
            new_text = request.form.get('new_text', '').strip()
            if comment_id and new_text:
                comment = Comment.query.filter_by(id=comment_id).first()
                if comment and comment.author == current_user['name']:
                    time_diff = datetime.utcnow() - comment.timestamp
                    time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
                    if time_diff <= time_limit and not comment.is_deleted:
                        if not comment.original_text:
                            comment.original_text = comment.text
                        comment.text = new_text
                        comment.edited_at = datetime.utcnow()
                        db.session.commit()
                        flash('Comment updated successfully!', 'success')
                    else:
                        flash('Edit time limit has expired.', 'error')
                else:
                    flash('You can only edit your own comments.', 'error')
                return redirect(url_for('documents.draft_comments', draft_name=draft_name))
            else:
                flash('Invalid comment or empty text.', 'error')

        elif action == 'delete':
            comment_id = request.form.get('comment_id')
            if comment_id:
                comment = Comment.query.filter_by(id=comment_id).first()
                if comment and comment.author == current_user['name']:
                    time_diff = datetime.utcnow() - comment.timestamp
                    time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
                    if time_diff <= time_limit and not comment.is_deleted:
                        comment.is_deleted = True
                        comment.text = '[Deleted]'
                        db.session.commit()
                        flash('Comment deleted successfully!', 'success')
                    else:
                        flash('Delete time limit has expired.', 'error')
                else:
                    flash('You can only delete your own comments.', 'error')
                return redirect(url_for('documents.draft_comments', draft_name=draft_name))
            else:
                flash('Invalid comment ID.', 'error')

    all_comments = build_comment_tree(draft_name)
    comments_html = render_comment_tree(all_comments, draft_name, get_current_user, get_comment_likes, is_comment_liked)

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">Comments</li>
            </ol>
        </nav>

        <h1>Comments for {display_id}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary me-2">History</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>

        <div class="row">
            <div class="col-md-8">
                <h3>Comments ({len(all_comments)})</h3>
                <div id="flash-messages"></div>
                {comments_html}

                <div class="card mt-4">
                    <div class="card-header">
                        <h5>Add a Comment</h5>
                    </div>
                    <div class="card-body">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="comment" class="form-label">Your Comment</label>
                                <textarea class="form-control" id="comment" name="comment" rows="4" placeholder="Enter your comment here..." required></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary">Submit Comment</button>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Document Info</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Title:</strong> {draft['title']}</p>
                        <p><strong>Authors:</strong> {', '.join(draft['authors'])}</p>
                        <p><strong>Status:</strong> <span class="badge bg-secondary">{draft['status']}</span></p>
                        <p><strong>Last Updated:</strong> {draft['date']}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleLike(commentId) {{
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'like';
            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;
            form.appendChild(actionInput);
            form.appendChild(commentIdInput);
            document.body.appendChild(form);
            form.submit();
        }}

        function toggleReply(commentId) {{
            const replyForm = document.getElementById('reply-form-' + commentId);
            if (replyForm) {{
                if (replyForm.style.display === 'none' || replyForm.style.display === '') {{
                replyForm.style.display = 'block';
            }} else {{
                replyForm.style.display = 'none';
            }}
            }}
        }}

        function editComment(commentId) {{
            const commentCard = document.getElementById('comment-' + commentId);
            if (!commentCard) return;
            const commentText = commentCard.querySelector('p.mb-2');
            if (!commentText) return;
            const currentText = commentText.textContent.trim();
            const editForm = document.createElement('form');
            editForm.method = 'POST';
            editForm.style.marginTop = '10px';
            const textarea = document.createElement('textarea');
            textarea.className = 'form-control';
            textarea.name = 'new_text';
            textarea.rows = 3;
            textarea.value = currentText;
            textarea.required = true;
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'edit';
            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;
            const buttonDiv = document.createElement('div');
            buttonDiv.className = 'd-flex gap-2 mt-2';
            const saveBtn = document.createElement('button');
            saveBtn.type = 'submit';
            saveBtn.className = 'btn btn-sm btn-primary';
            saveBtn.textContent = 'Save';
            const cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'btn btn-sm btn-secondary';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.onclick = function() {{
                commentText.style.display = 'block';
                editForm.remove();
            }};
            buttonDiv.appendChild(saveBtn);
            buttonDiv.appendChild(cancelBtn);
            editForm.appendChild(actionInput);
            editForm.appendChild(commentIdInput);
            editForm.appendChild(textarea);
            editForm.appendChild(buttonDiv);
            commentText.style.display = 'none';
            commentText.parentNode.insertBefore(editForm, commentText.nextSibling);
        }}

        function deleteComment(commentId) {{
            if (!confirm('Are you sure you want to delete this comment? This action cannot be undone.')) {{
                return;
            }}
            const form = document.createElement('form');
            form.method = 'POST';
            form.style.display = 'none';
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'action';
            actionInput.value = 'delete';
            const commentIdInput = document.createElement('input');
            commentIdInput.type = 'hidden';
            commentIdInput.name = 'comment_id';
            commentIdInput.value = commentId;
            form.appendChild(actionInput);
            form.appendChild(commentIdInput);
            document.body.appendChild(form);
            form.submit();
        }}
    </script>
"""

    return _format_base_template(title=f"Comments - {draft_name}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/doc/draft/<path:draft_name>/history/')
def draft_history(draft_name):
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER

    DRAFTS = _get_drafts()
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)

    submission = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'ml_number': submission.ml_number,
            }

    if not draft:
        return "Document not found", 404

    display_id = draft.get('ml_number', draft_name) or draft_name

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    history = DocumentHistory.query.filter_by(draft_name=draft_name).order_by(DocumentHistory.timestamp.desc()).all()

    history_html = ""
    if history:
        for entry in history:
            history_html += f"""
            <div class="card mb-3">
                        <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <span class="badge bg-primary">{entry.action}</span>
                        <small class="text-muted">{entry.timestamp.strftime('%Y-%m-%d %H:%M')}</small>
                            </div>
                    <p class="mb-1"><strong>User:</strong> {entry.user}</p>
                    <p class="mb-0">{entry.details}</p>
                        </div>
                    </div>
            """
    else:
        history_html = """
        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            No history available for this draft.
        </div>
        """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">History</li>
            </ol>
        </nav>

        <h1>History for {display_id}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary">Revisions</a>
        </div>

                {history_html}
            </div>
    """

    return _format_base_template(title=f"History - {display_id}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/doc/draft/<path:draft_name>/follow/', methods=['POST'])
def follow_draft(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to follow documents.', 'error')
        return redirect(url_for('documents.draft_detail', draft_name=draft_name))

    existing_follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if existing_follow:
        flash('You are already following this document.', 'info')
    else:
        notification_level = request.form.get('notification_level', 'all')
        follow = UserFollow(
            user_id=current_user['id'],
            draft_name=draft_name,
            notification_level=notification_level
        )
        db.session.add(follow)
        db.session.commit()
        level_desc = UserFollow.NOTIFICATION_LEVELS.get(notification_level, 'All changes and comments')
        flash(f'You are now following this document with {level_desc.lower()} notifications.', 'success')

    return redirect(url_for('documents.draft_detail', draft_name=draft_name))


@bp.route('/doc/draft/<path:draft_name>/unfollow/', methods=['POST'])
def unfollow_draft(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to unfollow documents.', 'error')
        return redirect(url_for('documents.draft_detail', draft_name=draft_name))

    follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash('You have stopped following this document.', 'success')
    else:
        flash('You were not following this document.', 'info')

    return redirect(url_for('documents.draft_detail', draft_name=draft_name))


@bp.route('/doc/draft/<path:draft_name>/update-notification/', methods=['POST'])
def update_notification_level(draft_name):
    current_user = get_current_user()
    if not current_user:
        flash('You must be logged in to update notification settings.', 'error')
        return redirect(url_for('documents.draft_detail', draft_name=draft_name))

    follow = UserFollow.query.filter_by(user_id=current_user['id'], draft_name=draft_name).first()
    if not follow:
        flash('You are not following this document.', 'error')
        return redirect(url_for('documents.draft_detail', draft_name=draft_name))

    notification_level = request.form.get('notification_level', 'all')
    if notification_level in UserFollow.NOTIFICATION_LEVELS:
        follow.notification_level = notification_level
        db.session.commit()
        level_desc = UserFollow.NOTIFICATION_LEVELS[notification_level]
        flash(f'Notification level updated to: {level_desc}', 'success')
    else:
        flash('Invalid notification level.', 'error')

    return redirect(url_for('documents.draft_detail', draft_name=draft_name))


@bp.route('/doc/draft/<path:draft_name>/revisions/')
def draft_revisions(draft_name):
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER

    current_user = get_current_user()
    DRAFTS = _get_drafts()
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)

    submission = None
    original_submission_id = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission:
            if getattr(submission, 'is_revision', False) and getattr(submission, 'parent_draft_name', ''):
                original_submission_id = submission.parent_draft_name
            else:
                original_submission_id = submission.id

            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': submission.authors,
                'status': submission.status,
                'group': submission.group,
                'date': submission.submitted_at.strftime('%Y-%m-%d') if submission.submitted_at else '',
                'rev': getattr(submission, 'revision_number', '00') or '00',
                'pages': submission.pages or 1,
                'words': submission.words or 0,
                'is_revision': getattr(submission, 'is_revision', False),
                'parent_draft_name': getattr(submission, 'parent_draft_name', ''),
                'original_submission_id': original_submission_id,
                'ml_number': submission.ml_number,
            }

    if not draft:
        return "Document not found", 404

    display_id = draft.get('ml_number', draft_name) or draft_name

    calculated_pages = draft.get('pages', 1)
    calculated_words = draft.get('words', 0)

    if submission and submission.file_path and os.path.exists(submission.file_path):
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    document_content = f.read()
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
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
                words = len(document_content.split())
                calculated_pages = max(1, (words + 499) // 500)
                calculated_words = words
            elif ext == '.pdf':
                from PyPDF2 import PdfReader
                reader = PdfReader(submission.file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                document_content = '\n\n'.join(content_parts)
                document_content = re.sub(r'\n+', '\n', document_content)
                document_content = re.sub(r' +', ' ', document_content)
                words = len(document_content.split())
                calculated_pages = len(reader.pages) if reader.pages else max(1, (words + 499) // 500)
                calculated_words = words
        except Exception:
            pass

        draft['pages'] = calculated_pages
        draft['words'] = calculated_words

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    original_id = draft.get('original_submission_id', draft['name'])
    original_submission = get_submission_by_ref(original_id)

    all_revisions = Submission.query.filter(
        Submission.parent_draft_name == original_id,
        Submission.is_revision == True,
        Submission.status.in_(['approved', 'published'])
    ).order_by(Submission.revision_number.desc()).all()

    revisions_list_html = ""
    for rev in all_revisions:
        status_badge_class = {
            'submitted': 'bg-warning text-dark',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'published': 'bg-info'
        }.get(rev.status, 'bg-secondary')

        what_changed = getattr(rev, 'what_changed', '')
        what_changed_html = f'<p class="mb-2"><strong>What changed:</strong> {what_changed}</p>' if what_changed else ''

        is_current = (rev.id == draft['name'])
        current_badge = '<span class="badge bg-primary ms-2">Current</span>' if is_current else ''

        revisions_list_html += f"""
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <a href="/doc/draft/{rev.id}/" class="text-decoration-none">Revision {rev.revision_number}</a>
                    {current_badge}
                </h6>
                <span class="badge {status_badge_class}">{rev.status.title()}</span>
            </div>
            <div class="card-body">
                <p class="mb-2"><strong>Published:</strong> {rev.approved_at.strftime('%Y-%m-%d') if rev.approved_at and rev.status == 'approved' else (rev.submitted_at.strftime('%Y-%m-%d') if rev.submitted_at else 'N/A')}</p>
                <p class="mb-2"><strong>Pages:</strong> {rev.pages or 1} | <strong>Words:</strong> {rev.words or 0}</p>
                {what_changed_html}
            </div>
        </div>
        """

    revisions_html = f"""
                <h4>Revision History</h4>
                {revisions_list_html if revisions_list_html else '<p class="text-muted">No revisions yet.</p>'}

                <div class="card mt-3">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            <a href="/doc/draft/{original_id}/" class="text-decoration-none">Original Version (Rev 00)</a>
                        </h6>
                        <span class="badge bg-success">Approved</span>
                    </div>
                    <div class="card-body">
                        <p class="mb-2"><strong>Published:</strong> {original_submission.approved_at.strftime('%Y-%m-%d') if original_submission and original_submission.approved_at else (original_submission.submitted_at.strftime('%Y-%m-%d') if original_submission and original_submission.submitted_at else draft['date'])}</p>
                        <p class="mb-0"><strong>Pages:</strong> {original_submission.pages if original_submission else 1} | <strong>Words:</strong> {original_submission.words if original_submission else 0}</p>
                    </div>
                </div>

    <div class="alert alert-info mt-3">
        <i class="fas fa-info-circle me-2"></i>
        Detailed revision history and diff viewing would be implemented in a full datatracker system.
            </div>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/doc/all/">Documents</a></li>
                <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{display_id}</a></li>
                <li class="breadcrumb-item active">Revisions</li>
            </ol>
        </nav>

        <h1>Revisions for {display_id}</h1>
        <p class="lead">{draft['title']}</p>

        <div class="mb-4">
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
                <i class="fas fa-arrow-left me-1"></i>Back to Draft
            </a>
            {f'<a href="/submit/revision/{draft_name}/" class="btn btn-success me-2"><i class="fas fa-plus me-1"></i>Submit New Revision</a>' if current_user and draft.get('status') == 'approved' else ''}
            <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
            <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary">History</a>
        </div>

        {revisions_html}
    </div>
    """

    return _format_base_template(title=f"Revisions - {display_id}", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER, hypothesis_config="")


# ============================================================================
# Test/draft pages and annotations
# ============================================================================

def _safe_draft_path(filename):
    """Resolve filename under drafts/; return None if path escapes."""
    drafts_dir = os.path.abspath(os.path.join(current_app.root_path, 'drafts'))
    if not filename or ".." in filename or filename.startswith("/"):
        return None
    path = os.path.abspath(os.path.normpath(os.path.join(drafts_dir, filename)))
    if not path.startswith(drafts_dir):
        return None
    return path


@bp.route('/test/', methods=['GET'])
@bp.route('/test/<path:filename>', methods=['GET'])
def draft_page(filename=None):
    """Serve drafts/<filename> as text/html. /test/ serves digitalartifacts.htm."""
    name = filename or "digitalartifacts.htm"
    path = _safe_draft_path(name)
    if not path or not os.path.isfile(path):
        return jsonify({'error': 'Draft page not found'}), 404
    return send_file(path, mimetype='text/html; charset=utf-8')


@bp.route('/api/annotations/<document_name>/count')
def annotation_count(document_name):
    """Get annotation count for a document (Hypothesis)."""
    from services.hypothesis import get_document_annotations
    annotations = get_document_annotations(document_name, 'draft')
    return jsonify({
        'count': len(annotations),
        'document': document_name
    })
