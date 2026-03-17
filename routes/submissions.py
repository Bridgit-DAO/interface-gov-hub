"""Submissions API and actions: list, approve, reject, view, download, admin/submissions."""
import os
import random
import string
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request, redirect, url_for, flash, send_file, current_app, session, render_template_string, g

from extensions import db
from models import Submission, Layer
from services.identity import get_current_user, require_auth, require_role
from services.submissions import get_submission_by_ref, add_to_document_history, get_next_ml_number
from services.documents import load_draft_data
from services.ordinals import shorten_inscription_id

bp = Blueprint('submissions', __name__, url_prefix='')


# ---------------------------------------------------------------------------
# Submission form routes (submit_draft, submit_revision, submission_status, submission_detail)
# ---------------------------------------------------------------------------

SUBMISSION_STATUS_TEMPLATE = """
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="{{ home_url }}">Home</a></li>
            <li class="breadcrumb-item"><a href="{{ submit_url }}">Submit Draft</a></li>
            <li class="breadcrumb-item active">Submission Status</li>
        </ol>
    </nav>

    <h1>Submission Status</h1>
    <p class="lead">Track your Internet-Draft submission</p>

    <div id="flash-messages"></div>

    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>
                        Submission Details
                        {% if is_revision %}
                        <span class="badge bg-success ms-2">Revision {{ revision_number }}</span>
                        {% endif %}
                    </h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submission ID:</strong></div>
                        <div class="col-sm-9"><code>{{ submission.id }}</code></div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Status:</strong></div>
                        <div class="col-sm-9">
                            <span class="badge bg-primary">{{ submission_status_title }}</span>
                            {% if is_ordinal %}
                            <span class="badge bg-info ms-2"><i class="bi bi-coin"></i> Ordinal</span>
                            {% else %}
                            <span class="badge bg-secondary ms-2"><i class="bi bi-file-earmark"></i> File</span>
                            {% endif %}
                        </div>
                    </div>
                    {% if is_revision %}
                    <div class="alert alert-info mb-3">
                        <strong><i class="fas fa-code-branch me-2"></i>This is a revision</strong><br>
                        Revision <strong>{{ revision_number }}</strong> of
                        <a href="{{ parent_draft_url }}">{{ parent_draft_name }}</a>
                    </div>
                    {% endif %}
                    {% if what_changed %}
                    <div class="card mb-3">
                        <div class="card-header">
                            <strong>What changed (submitter's explanation)</strong>
                        </div>
                        <div class="card-body">
                            <p class="mb-0">{{ what_changed }}</p>
                        </div>
                    </div>
                    {% endif %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Title:</strong></div>
                        <div class="col-sm-9">{{ submission_title }}</div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Authors:</strong></div>
                        <div class="col-sm-9">{{ submission_authors_joined }}</div>
                    </div>
                    {% if ml_number %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>ML Number:</strong></div>
                        <div class="col-sm-9"><code>{{ ml_number }}</code></div>
                    </div>
                    {% endif %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Draft ID:</strong></div>
                        <div class="col-sm-9"><code>{{ submission_id }}</code></div>
                    </div>
                    {% if artifact_id and artifact_layer_slug %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Artifact:</strong></div>
                        <div class="col-sm-9"><a href="/layers/{{ artifact_layer_slug }}/artifacts/{{ artifact_id }}/" class="btn btn-outline-secondary btn-sm">View Artifact</a></div>
                    </div>
                    {% endif %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Submitted:</strong></div>
                        <div class="col-sm-9">{{ submission_submitted_at }}</div>
                    </div>
                    {% if is_file %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>File:</strong></div>
                        <div class="col-sm-9">
                            <code>{{ submission_filename }}</code>
                            <a href="{{ download_url }}" class="btn btn-sm btn-outline-primary ms-2">Download</a>
                        </div>
                    </div>
                    {% endif %}
                    {% if submission_abstract %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Abstract:</strong></div>
                        <div class="col-sm-9">{{ submission_abstract }}</div>
                    </div>
                    {% endif %}

                    {% if is_ordinal %}
                    <h6 class="mt-4">Ordinal Metadata</h6>
                    <div class="card mb-3" style="background-color: var(--bg-secondary);">
                        <div class="card-body">
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Inscription ID:</strong></div>
                                <div class="col-sm-8">
                                    <a href="https://ordinals.com/inscription/{{ ordinal_id }}" target="_blank" class="text-decoration-none" style="color: var(--accent-color);">
                                        <code style="font-size: 0.85em;">{{ ordinal_id_short }}</code>
                                    </a>
                                </div>
                            </div>
                            {% if inscription_number %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Inscription Number:</strong></div>
                                <div class="col-sm-8">{{ inscription_number }}</div>
                            </div>
                            {% endif %}
                            {% if block_height %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Block Height:</strong></div>
                                <div class="col-sm-8">{{ block_height }}</div>
                            </div>
                            {% endif %}
                            {% if inscription_timestamp %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Timestamp:</strong></div>
                                <div class="col-sm-8">{{ inscription_timestamp }}</div>
                            </div>
                            {% endif %}
                            <div class="row mb-2">
                                <div class="col-sm-4"><strong>Content Type:</strong></div>
                                <div class="col-sm-8"><code>{{ ordinal_content_type }}</code></div>
                            </div>
                            <div class="row">
                                <div class="col-sm-12">
                                    <a href="https://ordinals.com/inscription/{{ ordinal_id }}" target="_blank" class="btn btn-sm btn-outline-primary">
                                        <i class="bi bi-box-arrow-up-right"></i> View on Ordinals.com
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endif %}

                    <h6 class="mt-4">Content Preview</h6>
                    {% if content_preview_html %}
                    <div class="border rounded p-3" style="background-color: var(--input-bg); border-color: var(--input-border);">
                        {{ content_preview_html|safe }}
                    </div>
                    {% else %}
                    <div class="border rounded p-3" style="background-color: var(--input-bg); border-color: var(--input-border);">
                        <pre class="mb-0" style="font-size: 0.9em; max-height: 400px; overflow-y: auto; color: var(--text-primary);">{{ file_content }}</pre>
                    </div>
                    {% endif %}

                    {% if is_submitted and is_admin %}
                    <div class="row mb-3">
                        <div class="col-sm-3"><strong>Actions:</strong></div>
                        <div class="col-sm-9">
                            <form method="POST" action="{{ approve_url }}" style="display: inline;">
                                <button type="submit" class="btn btn-success btn-sm">Approve & Publish</button>
                            </form>
                            <form method="POST" action="{{ reject_url }}" style="display: inline; margin-left: 10px;">
                                <button type="submit" class="btn btn-danger btn-sm">Reject</button>
                            </form>
                        </div>
                    </div>
                    {% endif %}
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">
                    <h5>Review Timeline</h5>
                </div>
                <div class="card-body">
                    <div class="timeline">
                        <div class="timeline-item">
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Submitted</h6>
                                <p class="text-muted small">{{ submission_submitted_at }}</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            {% if is_approved_or_rejected %}
                            <div class="timeline-marker bg-success"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">
                                    {% if is_approved %}Completed{% else %}Rejected{% endif %}
                                    {% if submission_approved_at %}
                                    - {{ submission_approved_at }}
                                    {% elif submission_rejected_at %}
                                    - {{ submission_rejected_at }}
                                    {% endif %}
                                </p>
                            </div>
                            {% else %}
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Initial Review</h6>
                                <p class="text-muted small">In Progress</p>
                            </div>
                            {% endif %}
                        </div>
                        {% if is_approved %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-primary"></div>
                            <div class="timeline-content">
                                <h6>Published</h6>
                                <p class="text-muted small">Available in document repository</p>
                            </div>
                        </div>
                        {% else %}
                        <div class="timeline-item">
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>Workgroup Review</h6>
                                <p class="text-muted small">Pending initial approval</p>
                            </div>
                        </div>
                        <div class="timeline-item">
                            <div class="timeline-marker bg-secondary"></div>
                            <div class="timeline-content">
                                <h6>MLSG Review</h6>
                                <p class="text-muted small">Pending workgroup review</p>
                            </div>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Actions</h5>
                </div>
                <div class="card-body">
                    <a href="{{ submit_url }}" class="btn btn-primary w-100 mb-2">Submit Another Draft</a>
                    <a href="{{ doc_all_url }}" class="btn btn-outline-secondary w-100 mb-2">View All Documents</a>
                    <a href="{{ home_url }}" class="btn btn-outline-secondary w-100">Back to Home</a>
                </div>
            </div>

            <div class="card mt-3">
                <div class="card-header">
                    <h5>Need Help?</h5>
                </div>
                <div class="card-body">
                    <p class="small">If you have questions about your submission:</p>
                    <ul class="small">
                        <li>Check the <a href="#" target="_blank">submission guidelines</a></li>
                        <li>Contact the <a href="mailto:draft@metalayer.org">MLGH Secretariat</a></li>
                        <li>Join the <a href="#" target="_blank">MLGH discussion list</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<style>
.timeline {
    position: relative;
    padding-left: 30px;
}

.timeline-item {
    position: relative;
    margin-bottom: 20px;
}

.timeline-marker {
    position: absolute;
    left: -25px;
    top: 5px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 2px #dee2e6;
}

.timeline-content h6 {
    margin-bottom: 5px;
    font-weight: 600;
}

.timeline-content p {
    margin-bottom: 0;
}
</style>
"""


@bp.route('/submit/', methods=['GET', 'POST'])
@require_auth
def submit_draft():
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    from services.groups import GROUPS
    from templates.html_templates import SUBMIT_TEMPLATE
    from services.documents import calculate_pages_and_words

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Generate workgroup options dynamically
    group_options = '<option value="">Select a Workgroup</option>'
    for group in GROUPS:
        group_options += f'<option value="{group["acronym"]}">{group["name"]}</option>'

    # Replace the hardcoded options in the template (multiple occurrences for both tabs)
    submit_template = SUBMIT_TEMPLATE
    for _ in range(2):  # Replace in both upload and ordinal tabs
        submit_template = submit_template.replace(
            '''<option value="">Select a Workgroup</option>
                                        <option value="httpbis">HTTP</option>
                                        <option value="quic">QUIC</option>
                                        <option value="tls">TLS</option>
                                        <option value="dnsop">DNSOP</option>
                                        <option value="rtgwg">RTGWG</option>''',
            group_options,
            1  # Replace only one occurrence at a time
        )

    # Layer selector: required for project_id. Use g.layer, ?layer= slug, ?layer_id= id, or dropdown.
    layers = Layer.query.filter(Layer.approval_status == 'approved').order_by(Layer.name).all()
    layer_from_param = None
    if request.args.get('layer'):
        layer_from_param = Layer.query.filter_by(slug=request.args.get('layer').strip()).first()
    elif request.args.get('layer_id'):
        layer_from_param = Layer.query.get(request.args.get('layer_id').strip())
    effective_layer = g.get('layer') or layer_from_param
    if not effective_layer and request.method == 'POST' and request.form.get('layer_id'):
        effective_layer = Layer.query.get(request.form.get('layer_id').strip())
    if effective_layer:
        layer_selector = f'''
                                <div class="mb-3">
                                    <label class="form-label">Layer *</label>
                                    <p class="form-control-plaintext mb-0"><strong>{effective_layer.name}</strong> <small class="text-muted">(from layer view)</small></p>
                                    <input type="hidden" name="layer_id" value="{effective_layer.id}">
                                </div>'''
    elif layers:
        opts = '<option value="">Select a layer...</option>' + ''.join(
            f'<option value="{p.id}">{p.name}</option>' for p in layers
        )
        layer_selector = f'''
                                <div class="mb-3">
                                    <label for="layer_id" class="form-label">Layer *</label>
                                    <select class="form-select" id="layer_id" name="layer_id" required>
                                        {opts}
                                    </select>
                                    <div class="form-text">Drafts are submitted to a specific layer.</div>
                                </div>'''
    else:
        layer_selector = '''
                                <div class="mb-3">
                                    <p class="text-warning mb-0">No approved layers available. Submit from a layer subdomain (e.g. overweb.themetalayer.org) or create a layer first.</p>
                                </div>'''
    submit_template = submit_template.replace('{{LAYER_SELECTOR}}', layer_selector)
    stripe_pk = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    submit_template = submit_template.replace('{{STRIPE_PK}}', stripe_pk)
    offer_tier = effective_layer and getattr(effective_layer, 'offer_tier_pricing', False)
    submit_template = submit_template.replace('{{OFFER_TIER_PRICING}}', 'true' if offer_tier else 'false')
    submit_template = submit_template.replace('{build_number}', str(BUILD_NUMBER))

    if request.method == 'POST':
        # Get common fields
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        source_type = request.form.get('sourceType', 'file').strip()
        form_layer_id = request.form.get('layer_id', '').strip()
        layer_id = form_layer_id or (effective_layer.id if effective_layer else None)

        # Validate layer_id when layers exist
        if not layer_id and layers:
            flash('Please select a layer for this submission.', 'error')
            return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")

        # Process authors (comma-separated)
        authors_list = [a.strip() for a in authors.split(',') if a.strip()]

        # Generate submission ID
        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Handle based on source type
        if source_type == 'ordinal':
            # Ordinal submission
            ordinal_id = request.form.get('ordinalId', '').strip()
            ordinal_content_url = request.form.get('ordinalContentUrl', '').strip()
            ordinal_content_type = request.form.get('ordinalContentType', '').strip()
            inscription_number = request.form.get('inscriptionNumber', '').strip()
            block_height = request.form.get('blockHeight', '').strip()
            inscription_timestamp = request.form.get('inscriptionTimestamp', '').strip()

            # Validation
            if not title or not authors or not ordinal_id:
                flash('Title, authors, and inscription ID are required', 'error')
                return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")

            if not ordinal_content_url:
                flash('Please preview the ordinal before submitting', 'error')
                return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")

            # Fetch ordinal content and calculate pages/words
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=30)
                response.raise_for_status()
                content_text = response.text

                # Calculate pages and words from text
                word_count = len(content_text.split())
                chars_per_page = 3000
                page_count = max(1, (len(content_text) + chars_per_page - 1) // chars_per_page)
            except Exception as e:
                current_app.logger.error(f"Failed to fetch ordinal content for pages/words: {e}")
                page_count = 1
                word_count = 0

            # Create submission record with ordinal data
            current_user_info = get_current_user()
            current_app.logger.info(f"📝 CREATING SUBMISSION:")
            current_app.logger.info(f"   current_user_info: {current_user_info}")
            current_app.logger.info(f"   submitted_by will be: {current_user_info['name']}")

            # Get doc_type from form (default to 'draft')
            doc_type = request.form.get('doc_type', 'draft').strip() or 'draft'
            if doc_type not in ['draft', 'rfc']:
                doc_type = 'draft'

            submission = Submission(
                draft_name=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                layer_id=layer_id,
                submitted_by=current_user_info['name'],
                sourceType='ordinal',
                doc_type=doc_type,
                ordinalId=ordinal_id,
                ordinalContentUrl=ordinal_content_url,
                ordinalContentType=ordinal_content_type,
                inscriptionNumber=int(inscription_number) if inscription_number else None,
                blockHeight=int(block_height) if block_height else None,
                inscriptionTimestamp=datetime.strptime(inscription_timestamp.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S') if inscription_timestamp else None,
                pages=page_count,
                words=word_count
            )

        else:
            # File upload submission
            file = request.files.get('file')

            # Validation
            if not title or not authors or not file:
                flash('Title, authors, and file are required', 'error')
                return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")

            # Security: Check file size (max 50MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                flash(f'File too large. Maximum size is 50MB. Your file is {file_size / (1024*1024):.1f}MB.', 'error')
                return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")

            # Save file
            filename = f"{submission_id}-{file.filename}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Calculate pages and words
            pages, words = calculate_pages_and_words(file_path, filename)

            # Create submission record with file data
            submission = Submission(
                draft_name=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                layer_id=layer_id,
                filename=filename,
                file_path=file_path,
                submitted_by=get_current_user()['name'],
                sourceType='file',
                pages=pages,
                words=words
            )

        # Save to database
        db.session.add(submission)
        db.session.commit()

        # Log the action
        source_desc = f"from ordinal {submission.ordinalId}" if source_type == 'ordinal' else "via file upload"
        add_to_document_history(f"draft-{submission_id}", "submitted", get_current_user()['name'], f"New draft submitted {source_desc}: {title}")

        flash('Draft submitted successfully!', 'success')
        return redirect(url_for('submissions.submission_detail', submission_id=submission.draft_name or submission.id))

    return _format_base_template(title="Submit a Meta-Layer Draft - MLGH", theme=current_theme, user_menu=user_menu, content=submit_template, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/submit/revision/<draft_name>/', methods=['GET', 'POST'])
@require_auth
def submit_revision(draft_name):
    """Submit a new revision of an existing draft"""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    from services.groups import GROUPS
    from services.documents import calculate_pages_and_words, load_draft_data, DRAFTS

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Find the current draft
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)

    # If not found in DRAFTS, try to find as a submission
    submission = None
    if not draft:
        submission = get_submission_by_ref(draft_name)
        if submission and submission.status == 'approved':
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': ', '.join(submission.authors) if isinstance(submission.authors, list) else submission.authors,
                'abstract': submission.abstract or '',
                'group': submission.group or '',
                'rev': submission.revision_number or '00',
                'ml_number': submission.ml_number,
            }
        elif submission:
            flash('Cannot create revision of unapproved submission', 'error')
            return redirect(url_for('submissions.submission_detail', submission_id=submission.id))

    if not draft:
        flash('Draft not found', 'error')
        return redirect(url_for('documents.all_documents'))

    # Inherit project_id from parent draft (revisions belong to same layer)
    parent_sub = get_submission_by_ref(draft_name)
    revision_layer_id = parent_sub.layer_id if parent_sub else (g.layer.id if g.get('layer') else None)

    # Determine display ID (ML-Draft-XXX or internal ID)
    display_id = draft.get('ml_number', draft_name) or draft_name

    # Calculate new revision number
    current_rev = int(draft.get('rev', '00'))
    new_rev = f"{current_rev + 1:02d}"

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        authors = request.form.get('authors', '').strip()
        abstract = request.form.get('abstract', '').strip()
        group = request.form.get('group', '').strip()
        what_changed = request.form.get('what_changed', '').strip()
        source_type = request.form.get('sourceType', 'file').strip()

        # Process authors
        authors_list = [a.strip() for a in authors.split(',') if a.strip()]

        # Generate submission ID
        submission_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Handle based on source type
        if source_type == 'ordinal':
            # Ordinal submission
            ordinal_id = request.form.get('ordinalId', '').strip()
            ordinal_content_url = request.form.get('ordinalContentUrl', '').strip()
            ordinal_content_type = request.form.get('ordinalContentType', '').strip()
            inscription_number = request.form.get('inscriptionNumber', '').strip()
            block_height = request.form.get('blockHeight', '').strip()
            inscription_timestamp = request.form.get('inscriptionTimestamp', '').strip()

            # Validation
            if not title or not authors or not ordinal_id:
                flash('Title, authors, and inscription ID are required', 'error')
                return redirect(url_for('submissions.submit_revision', draft_name=draft_name))

            if not ordinal_content_url:
                flash('Please preview the ordinal before submitting', 'error')
                return redirect(url_for('submissions.submit_revision', draft_name=draft_name))

            # Fetch ordinal content and calculate pages/words
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Connection': 'keep-alive'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=30)
                response.raise_for_status()
                content_text = response.text

                word_count = len(content_text.split())
                chars_per_page = 3000
                page_count = max(1, (len(content_text) + chars_per_page - 1) // chars_per_page)
            except Exception as e:
                current_app.logger.error(f"Failed to fetch ordinal content: {e}")
                page_count = 1
                word_count = 0

            # Create revision submission with ordinal data
            submission = Submission(
                draft_name=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                layer_id=revision_layer_id,
                submitted_by=get_current_user()['name'],
                sourceType='ordinal',
                doc_type='draft',
                ordinalId=ordinal_id,
                ordinalContentUrl=ordinal_content_url,
                ordinalContentType=ordinal_content_type,
                inscriptionNumber=int(inscription_number) if inscription_number else None,
                blockHeight=int(block_height) if block_height else None,
                inscriptionTimestamp=datetime.strptime(inscription_timestamp.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S') if inscription_timestamp else None,
                pages=page_count,
                words=word_count,
                parent_draft_name=draft_name,
                revision_number=new_rev,
                what_changed=what_changed,
                is_revision=True
            )
        else:
            # File upload submission
            file = request.files.get('file')

            # Validation
            if not title or not authors or not file:
                flash('Title, authors, and file are required', 'error')
                return redirect(url_for('submissions.submit_revision', draft_name=draft_name))

            # Security: Check file size (max 50MB)
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            max_size = 50 * 1024 * 1024
            if file_size > max_size:
                flash(f'File too large. Maximum size is 50MB.', 'error')
                return redirect(url_for('submissions.submit_revision', draft_name=draft_name))

            # Save file
            filename = f"{submission_id}-{file.filename}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            # Calculate pages and words
            pages, words = calculate_pages_and_words(file_path, filename)

            # Create revision submission with file data
            submission = Submission(
                draft_name=submission_id,
                title=title,
                authors=authors_list,
                abstract=abstract,
                group=group,
                layer_id=revision_layer_id,
                filename=filename,
                file_path=file_path,
                submitted_by=get_current_user()['name'],
                sourceType='file',
                pages=pages,
                words=words,
                parent_draft_name=draft_name,
                revision_number=new_rev,
                what_changed=what_changed,
                is_revision=True
            )

        # Save to database
        db.session.add(submission)
        db.session.commit()

        # Log the action
        source_desc = f"from ordinal {submission.ordinalId}" if source_type == 'ordinal' else "via file upload"
        change_desc = f" Changes: {what_changed[:100]}" if what_changed else ""
        add_to_document_history(
            draft_name,
            "revision_submitted",
            get_current_user()['name'],
            f"Revision {new_rev} submitted {source_desc}.{change_desc}"
        )

        flash(f'Revision {new_rev} submitted successfully!', 'success')
        return redirect(url_for('submissions.submission_detail', submission_id=submission.draft_name or submission.id))

    # GET: Show form with pre-populated data
    # Generate workgroup options
    group_options = '<option value="">Select a Workgroup</option>'
    for grp in GROUPS:
        selected = 'selected' if grp['acronym'] == draft.get('group', '') else ''
        group_options += f'<option value="{grp["acronym"]}" {selected}>{grp["name"]}</option>'

    draft_detail_url = url_for('documents.draft_detail', draft_name=draft_name)
    revision_form = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="{url_for('pages.home')}">Home</a></li>
                <li class="breadcrumb-item"><a href="{draft_detail_url}">{display_id}</a></li>
                <li class="breadcrumb-item active">Submit Revision</li>
            </ol>
        </nav>

        <h1>Submit New Revision</h1>
        <p class="lead">Submit a new revision of {display_id}</p>

        <div class="alert alert-info">
            <i class="fas fa-info-circle me-2"></i>
            <strong>Current Revision:</strong> {draft.get('rev', '00')} → <strong>New Revision:</strong> {new_rev}
        </div>

        <form method="POST" enctype="multipart/form-data" id="revisionForm">
            <div class="mb-3">
                <label class="form-label">Draft Name</label>
                <input type="text" class="form-control" value="{display_id}" disabled>
                <input type="hidden" name="draft_name" value="{draft_name}">
                <small class="form-text text-muted">This field cannot be changed for revisions</small>
            </div>

            <div class="mb-3">
                <label class="form-label">Title *</label>
                <input type="text" class="form-control" name="title" value="{draft.get('title', '')}" required>
            </div>

            <div class="mb-3">
                <label class="form-label">Authors *</label>
                <input type="text" class="form-control" name="authors" value="{draft.get('authors', '')}" required>
                <small class="form-text text-muted">Comma-separated list</small>
            </div>

            <div class="mb-3">
                <label class="form-label">Abstract</label>
                <textarea class="form-control" name="abstract" rows="4">{draft.get('abstract', '')}</textarea>
            </div>

            <div class="mb-3">
                <label class="form-label">Workgroup</label>
                <select class="form-control" name="group">
                    {group_options}
                </select>
            </div>

            <div class="mb-3">
                <label class="form-label">What changed since the last revision?</label>
                <textarea class="form-control" name="what_changed" rows="3"
                          placeholder="Example: Clarified workgroup role in determining rough consensus; added glossary; no change to core governance principles."></textarea>
                <small class="form-text text-muted">
                    Optional but recommended. Briefly describe substantive changes so reviewers and future readers
                    can understand what evolved and why. Not required for minor or editorial edits.
                </small>
            </div>

            <ul class="nav nav-tabs" role="tablist">
                <li class="nav-item">
                    <a class="nav-link active" data-bs-toggle="tab" href="#upload" onclick="document.getElementById('sourceType').value='file'">Upload File</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" data-bs-toggle="tab" href="#ordinal" onclick="document.getElementById('sourceType').value='ordinal'">Bitcoin Ordinal</a>
                </li>
            </ul>

            <div class="tab-content mt-3">
                <div id="upload" class="tab-pane active">
                    <div class="mb-3">
                        <label class="form-label">Upload Document *</label>
                        <input type="file" class="form-control" name="file" accept=".txt,.pdf,.xml,.docx">
                        <small class="form-text text-muted">Supported formats: TXT, PDF, XML, DOCX</small>
                    </div>
                </div>

                <div id="ordinal" class="tab-pane">
                    <div class="mb-3">
                        <label class="form-label">Inscription ID *</label>
                        <input type="text" class="form-control" name="ordinalId" id="ordinalId"
                               placeholder="e.g., 6fb976ab49dcec017f1e201e84395983204ae1a7c2abf7ced0a85d692e442799i0">
                        <small class="form-text text-muted">The unique inscription ID from Bitcoin</small>
                    </div>

                    <div class="mb-3">
                        <button type="button" class="btn btn-secondary" onclick="previewOrdinal()">
                            <i class="fas fa-eye me-1"></i>Preview Ordinal
                        </button>
                    </div>

                    <div id="ordinalPreview" class="mb-3" style="display: none;">
                        <div class="card">
                            <div class="card-header">
                                <h6>Ordinal Preview</h6>
                            </div>
                            <div class="card-body">
                                <div id="ordinalContent"></div>
                                <input type="hidden" name="ordinalContentUrl" id="ordinalContentUrl">
                                <input type="hidden" name="ordinalContentType" id="ordinalContentType">
                                <input type="hidden" name="inscriptionNumber" id="inscriptionNumber">
                                <input type="hidden" name="blockHeight" id="blockHeight">
                                <input type="hidden" name="inscriptionTimestamp" id="inscriptionTimestamp">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <input type="hidden" name="sourceType" value="file" id="sourceType">

            <div class="mt-4">
                <button type="submit" class="btn btn-success btn-lg">
                    <i class="fas fa-upload me-2"></i>Submit Revision
                </button>
                <a href="{draft_detail_url}" class="btn btn-secondary btn-lg ms-2">Cancel</a>
            </div>
        </form>
    </div>

    <script>
    async function previewOrdinal() {{
        const inscriptionId = document.getElementById('ordinalId').value.trim();
        if (!inscriptionId) {{
            alert('Please enter an inscription ID');
            return;
        }}

        // Show loading
        const preview = document.getElementById('ordinalPreview');
        const content = document.getElementById('ordinalContent');
        content.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Loading ordinal...</div>';
        preview.style.display = 'block';

        try {{
            // Use our API endpoint to fetch ordinal metadata
            const response = await fetch('/api/ordinal/preview', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{ inscriptionId }})
            }});

            const data = await response.json();

            if (!data.success) {{
                content.innerHTML = `<div class="alert alert-danger">Error: ${{data.error}}</div>`;
                return;
            }}

            // Fill in hidden form fields
            document.getElementById('ordinalContentUrl').value = data.contentUrl;
            document.getElementById('ordinalContentType').value = data.contentType;
            document.getElementById('inscriptionNumber').value = data.inscriptionNumber || '';
            document.getElementById('blockHeight').value = data.blockHeight || '';
            document.getElementById('inscriptionTimestamp').value = data.timestamp || '';

            // Fetch and display content
            const contentResponse = await fetch(data.contentUrl);
            const contentText = await contentResponse.text();

            // Check if it's markdown
            const isMarkdown = data.contentType.includes('markdown') || data.contentType.includes('text/plain');

            if (isMarkdown) {{
                // Convert markdown to HTML
                const convertResponse = await fetch('/api/ordinal/convert-markdown', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ markdown: contentText }})
                }});

                const convertData = await convertResponse.json();

                if (convertData.success) {{
                    content.innerHTML = '';
                    const infoDiv = document.createElement('div');
                    infoDiv.className = 'alert alert-info mb-3';
                    infoDiv.innerHTML = `<strong>Preview:</strong> Inscription #${{data.inscriptionNumber}} | Block: ${{data.blockHeight}} | Size: ${{(data.contentSize / 1024).toFixed(2)}} KB`;
                    content.appendChild(infoDiv);
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'document-content';
                    contentDiv.style.cssText = 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 1em; line-height: 1.6; max-height: 600px; overflow-y: auto; padding: 20px; border: 1px solid var(--border-color); border-radius: 8px; background: var(--input-bg); color: var(--text-primary);';
                    contentDiv.innerHTML = convertData.html;
                    content.appendChild(contentDiv);
                    const images = contentDiv.querySelectorAll('img');
                    images.forEach(img => {{
                        img.style.maxWidth = '100%';
                        img.style.height = 'auto';
                        img.style.display = 'block';
                        img.style.margin = '1em 0';
                    }});
                }} else {{
                    content.innerHTML = `<div class="alert alert-danger">Conversion failed: ${{convertData.error}}</div>`;
                }}
            }} else {{
                content.innerHTML = `<pre style="max-height: 400px; overflow-y: auto; white-space: pre-wrap;">${{contentText.substring(0, 2000)}}</pre>`;
            }}

        }} catch (error) {{
            content.innerHTML = `<div class="alert alert-danger">Error loading ordinal: ${{error.message}}</div>`;
        }}
    }}
    </script>
    """

    return _format_base_template(title=f"Submit Revision - {display_id}", theme=current_theme, user_menu=user_menu, content=revision_form, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/submit/status/')
@require_auth
def submission_status():
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    # Get user's submissions
    user_name = get_current_user()['name']
    submissions = Submission.query.filter_by(submitted_by=user_name).order_by(Submission.submitted_at.desc()).all()

    # Format submissions for template
    submissions_html = ""
    for submission in submissions:
        status_badge = {
            'submitted': 'badge bg-warning text-dark',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger',
            'published': 'badge bg-info',
            'inscription_pending': 'badge bg-warning'
        }.get(submission.status, 'badge bg-secondary')

        # Get source type
        source_type = getattr(submission, 'sourceType', 'file')
        source_badge = '<span class="badge bg-info ms-2"><i class="bi bi-coin"></i> Ordinal</span>' if source_type == 'ordinal' else '<span class="badge bg-secondary ms-2"><i class="bi bi-file-earmark"></i> File</span>'

        # Get revision info
        is_revision = getattr(submission, 'is_revision', False)
        revision_number = getattr(submission, 'revision_number', '')
        parent_draft_name = getattr(submission, 'parent_draft_name', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''

        # Get source info (inscription number or filename)
        if source_type == 'ordinal':
            inscription_number = getattr(submission, 'inscriptionNumber', None)
            ordinal_id = getattr(submission, 'ordinalId', None)
            if inscription_number:
                source_info = f'<p class="mb-2"><strong>Inscription:</strong> #{inscription_number}</p>'
            elif ordinal_id:
                shortened_id = shorten_inscription_id(ordinal_id, 8)
                source_info = f'<p class="mb-2"><strong>Inscription:</strong> <a href="https://ordinals.com/inscription/{ordinal_id}" target="_blank" class="text-decoration-none"><code>{shortened_id}</code></a></p>'
            else:
                source_info = ''
        else:
            filename = getattr(submission, 'filename', None)
            source_info = f'<p class="mb-2"><strong>File:</strong> {filename}</p>' if filename else '<p class="mb-2 text-muted"><em>No file</em></p>'

        detail_url = url_for('submissions.submission_detail', submission_id=submission.id)
        draft_url = url_for('documents.draft_detail', draft_name=submission.id)
        submissions_html += f"""
        <div class="submission-item">
            <div class="card mb-3">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">
                        <a href="{detail_url}" class="text-decoration-none">
                            {submission.title}
                        </a>
                    </h6>
                    <div>
                        <span class="{status_badge}">{submission.status.title()}</span>
                        {source_badge}
                        {revision_badge}
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-8">
                            <p class="mb-2"><strong>Authors:</strong> {', '.join(submission.authors)}</p>
                            <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                            <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')}</p>
                            {source_info}
                            {f'<p class="mb-2"><strong>Abstract:</strong> {submission.abstract[:100]}...</p>' if submission.abstract else ''}
                        </div>
                        <div class="col-md-4 text-end">
                            <a href="{detail_url}" class="btn btn-sm btn-primary me-2">View Details</a>
                            <a href="{draft_url}" class="btn btn-sm btn-outline-primary">View Draft</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    home_url = url_for('pages.home')
    submit_url = url_for('submissions.submit_draft')
    doc_all_url = url_for('documents.all_documents')
    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="{home_url}">Home</a></li>
                <li class="breadcrumb-item"><a href="{submit_url}">Submit Draft</a></li>
                <li class="breadcrumb-item active">My Submissions</li>
            </ol>
        </nav>

        <h1>My Submissions</h1>

        {f'<div class="alert alert-info">You have {len(submissions)} submission(s).</div>' if submissions else '<div class="alert alert-info">You have no submissions yet.</div>'}

        {submissions_html}

        <div class="mt-4">
            <a href="{submit_url}" class="btn btn-primary">Submit Another Draft</a>
            <a href="{home_url}" class="btn btn-secondary ms-2">Back to Home</a>
        </div>
    </div>
    """

    return _format_base_template(title="My Submissions - MLGH", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/submit/status/<submission_id>/')
@require_auth
def submission_detail(submission_id):
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    from services.documents import MARKDOWN_SUPPORT

    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    current_user = get_current_user()

    submission = get_submission_by_ref(submission_id)
    if not submission:
        return "Submission not found", 404

    # Check if user owns this submission or is admin
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        return "Access denied", 403

    # Handle content preview based on source type
    file_content = "File preview not available"
    content_preview_html = ""
    source_type = getattr(submission, 'sourceType', 'file')

    if source_type == 'ordinal':
        # Ordinal content - generate preview HTML
        ordinal_content_type = getattr(submission, 'ordinalContentType', '')
        ordinal_content_url = getattr(submission, 'ordinalContentUrl', '')

        if ordinal_content_type.startswith('image/'):
            content_preview_html = f'<img src="{ordinal_content_url}" class="img-fluid" style="max-height: 400px;" alt="Ordinal content">'
        elif 'text/plain' in ordinal_content_type or 'text/javascript' in ordinal_content_type or 'application/json' in ordinal_content_type or 'application/javascript' in ordinal_content_type:
            # Fetch and display text-based content
            try:
                import markdown2
                import bleach
                import re
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                text_content = response.text

                # Check if content is markdown
                is_markdown = False
                if 'text/plain' in ordinal_content_type:
                    markdown_patterns = [
                        r'^#{1,6}\s+.+$', r'\*\*.+\*\*', r'\*.+\*', r'^\s*[-*+]\s+',
                        r'^\s*\d+\.\s+', r'\[.+\]\(.+\)', r'!\[.*\]\(.+\)'
                    ]
                    for pattern in markdown_patterns:
                        if re.search(pattern, text_content, re.MULTILINE):
                            is_markdown = True
                            break

                if is_markdown:
                    html_content = markdown2.markdown(text_content, extras=['fenced-code-blocks', 'tables', 'break-on-newline'])
                    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                    'ul', 'ol', 'li', 'a', 'img', 'code', 'pre', 'blockquote', 'table',
                                    'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div', 'span']
                    allowed_attrs = {'a': ['href', 'title', 'target'], 'img': ['src', 'alt', 'title', 'width', 'height']}
                    html_content = bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
                    html_content = re.sub(r'src="(/content/[^"]+)"', r'src="https://ordinals.com\1"', html_content)
                    content_preview_html = f'<div class="border p-3" style="max-height: 400px; overflow-y: auto;">{html_content}</div>'
                    file_content = ""
                else:
                    file_content = text_content[:2000] + "..." if len(text_content) > 2000 else text_content
            except Exception as e:
                current_app.logger.error(f"Error fetching ordinal text content: {e}")
                file_content = "Error loading ordinal text content"
        elif 'text/markdown' in ordinal_content_type:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(ordinal_content_url, headers=headers, timeout=10)
                markdown_text = response.text
                if MARKDOWN_SUPPORT:
                    import markdown2
                    html_content = markdown2.markdown(markdown_text, extras=['fenced-code-blocks', 'tables', 'break-on-newline'])
                    content_preview_html = f'<div class="border p-3" style="max-height: 400px; overflow-y: auto;">{html_content}</div>'
                else:
                    file_content = markdown_text[:2000] + ("..." if len(markdown_text) > 2000 else "")
            except Exception:
                file_content = "Error loading ordinal markdown content"
        elif 'text/html' in ordinal_content_type:
            content_preview_html = f'<iframe src="{ordinal_content_url}" sandbox="allow-same-origin" style="width: 100%; height: 400px; border: 1px solid var(--card-border);"></iframe>'
        else:
            file_content = f"Ordinal content type: {ordinal_content_type}\nPreview not available for this content type."

    elif submission.file_path and os.path.exists(submission.file_path):
        # File upload - extract text for preview
        _, ext = os.path.splitext(submission.filename.lower())
        try:
            if ext in ['.txt', '.xml']:
                with open(submission.file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    file_content = content[:2000] + "..." if len(content) > 2000 else content
            elif ext == '.docx':
                from docx import Document
                doc = Document(submission.file_path)
                content = ""
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content += paragraph.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                content += cell.text + "\n"
                if content.strip():
                    file_content = content[:2000] + "..." if len(content) > 2000 else content
                else:
                    file_content = "DOCX file appears to be empty or contains no extractable text."
            elif ext == '.pdf':
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                view_url = url_for('submissions.view_submission', submission_id=submission.id)
                download_url = url_for('submissions.download_submission', submission_id=submission.id)
                content_preview_html = f'''
                <div class="pdf-viewer-container">
                    <div class="alert alert-info mb-3">
                        <i class="bi bi-file-pdf"></i> PDF Document ({file_size_kb:.1f} KB) -
                        <a href="{download_url}" class="alert-link">Download PDF</a> for best viewing experience
                    </div>
                    <iframe src="{view_url}"
                            type="application/pdf"
                            style="width: 100%; height: 600px; border: 1px solid var(--card-border);"
                            title="PDF Preview">
                        <p>Your browser does not support PDF preview.
                           <a href="{download_url}">Download the PDF</a> to view it.</p>
                    </iframe>
                </div>
                '''
                file_content = ""
            elif ext == '.doc':
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                file_content = f"Legacy DOC file ({file_size_kb:.1f} KB)\nText extraction not supported for legacy .doc format.\nPlease convert to .docx for text preview."
            else:
                file_size = os.path.getsize(submission.file_path)
                file_size_kb = file_size / 1024
                file_content = f"Unsupported file type: {ext} ({file_size_kb:.1f} KB)\nPreview not available."
        except Exception as e:
            file_size = os.path.getsize(submission.file_path)
            file_size_kb = file_size / 1024
            file_content = f"Error extracting text from {ext[1:].upper()} file ({file_size_kb:.1f} KB): {str(e)}"

    # Prepare template variables
    parent_draft_name = getattr(submission, 'parent_draft_name', '')
    inscription_ts = getattr(submission, 'inscriptionTimestamp', None)
    template_vars = {
        'submission': submission,
        'current_user': current_user,
        'file_content': file_content,
        'content_preview_html': content_preview_html,
        'submission_id': submission.id,
        'submission_status': submission.status,
        'submission_status_title': submission.status.title(),
        'submission_title': submission.title or '',
        'submission_abstract': submission.abstract or '',
        'submission_authors': submission.authors,
        'submission_authors_joined': ', '.join(submission.authors) if submission.authors else '',
        'submission_draft_name': getattr(submission, 'draft_name', submission.id) or '',
        'submission_submitted_at': submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if submission.submitted_at else '',
        'submission_filename': submission.filename or '',
        'submission_approved_at': submission.approved_at.strftime('%Y-%m-%d %H:%M:%S') if submission.approved_at else '',
        'submission_rejected_at': submission.rejected_at.strftime('%Y-%m-%d %H:%M:%S') if submission.rejected_at else '',
        'is_admin': current_user and (current_user.get('role') in ['admin', 'editor'] or current_user['name'] in ['admin', 'Admin User']),
        'is_approved': submission.status == 'approved',
        'is_rejected': submission.status == 'rejected',
        'is_approved_or_rejected': submission.status in ['approved', 'rejected'],
        'is_submitted': submission.status == 'submitted',
        'source_type': source_type,
        'is_ordinal': source_type == 'ordinal',
        'is_file': source_type == 'file',
        'ordinal_id': getattr(submission, 'ordinalId', ''),
        'ordinal_id_short': shorten_inscription_id(getattr(submission, 'ordinalId', ''), 8),
        'ordinal_content_url': getattr(submission, 'ordinalContentUrl', ''),
        'ordinal_content_type': getattr(submission, 'ordinalContentType', ''),
        'inscription_number': getattr(submission, 'inscriptionNumber', None),
        'block_height': getattr(submission, 'blockHeight', None),
        'inscription_timestamp': inscription_ts.strftime('%Y-%m-%d %H:%M:%S') if inscription_ts else None,
        'ml_number': submission.ml_number,
        'is_revision': getattr(submission, 'is_revision', False),
        'parent_draft_name': parent_draft_name,
        'parent_draft_url': url_for('documents.draft_detail', draft_name=parent_draft_name) if parent_draft_name else '',
        'revision_number': getattr(submission, 'revision_number', ''),
        'what_changed': getattr(submission, 'what_changed', ''),
        'artifact_id': getattr(submission, 'artifact_id', None),
        'artifact_layer_slug': Layer.query.get(submission.layer_id).slug if submission.layer_id and getattr(submission, 'artifact_id', None) else None,
        'home_url': url_for('pages.home'),
        'submit_url': url_for('submissions.submit_draft'),
        'doc_all_url': url_for('documents.all_documents'),
        'approve_url': url_for('submissions.approve_submission', submission_id=submission.id),
        'reject_url': url_for('submissions.reject_submission', submission_id=submission.id),
        'download_url': url_for('submissions.download_submission', submission_id=submission.id),
    }

    rendered_content = render_template_string(SUBMISSION_STATUS_TEMPLATE, **template_vars)
    return _format_base_template(title=f"Submission {submission.id} - MLGH", theme=current_theme, user_menu=user_menu, content=rendered_content, build_number=BUILD_NUMBER, hypothesis_config="")


# ---------------------------------------------------------------------------
# API and admin routes
# ---------------------------------------------------------------------------

@bp.route('/api/layers/<layer_id>/submissions/', methods=['GET'])
def list_layer_submissions(layer_id):
    """List approved drafts (not RFCs) for a layer - eligible for voting."""
    Layer.query.get_or_404(layer_id)
    submissions = Submission.query.filter(
        Submission.layer_id == layer_id,
        Submission.status == 'approved',
        Submission.doc_type == 'draft'
    ).order_by(Submission.submitted_at.desc()).all()
    return jsonify({
        'submissions': [{
            'id': s.id,
            'public_id': s.public_id,
            'artifact_id': s.artifact_id,
            'title': s.title,
            'draft_name': s.draft_name,
            'ml_number': s.ml_number,
            'group': s.group,
            'status': s.status,
            'submitted_at': s.submitted_at.isoformat() if s.submitted_at else None
        } for s in submissions]
    })


@bp.route('/submit/approve/<submission_id>', methods=['POST'])
@require_role('admin')
def approve_submission(submission_id):
    submission = get_submission_by_ref(submission_id)
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('submissions.admin_submissions'))

    is_revision = getattr(submission, 'is_revision', False)
    revision_num = getattr(submission, 'revision_number', '')
    ml_num = submission.ml_number
    parent_draft_name = getattr(submission, 'parent_draft_name', '')

    if is_revision and revision_num and ml_num:
        existing_revision = Submission.query.filter(
            Submission.ml_number == ml_num,
            Submission.revision_number == revision_num,
            Submission.status == 'approved',
            Submission.id != submission_id
        ).first()
        if existing_revision:
            all_revisions = Submission.query.filter(
                Submission.ml_number == ml_num,
                Submission.status == 'approved',
                Submission.revision_number.isnot(None)
            ).all()
            existing_nums = []
            for rev in all_revisions:
                try:
                    existing_nums.append(int(rev.revision_number))
                except (ValueError, TypeError):
                    pass
            next_num = 1
            while next_num in existing_nums:
                next_num += 1
            submission.revision_number = f"{next_num:02d}"

    if is_revision and parent_draft_name:
        parent_submission = get_submission_by_ref(parent_draft_name)
        if parent_submission and parent_submission.ml_number:
            revision_num = getattr(submission, 'revision_number', '')
            if revision_num:
                existing_revision = Submission.query.filter(
                    Submission.ml_number == parent_submission.ml_number,
                    Submission.revision_number == revision_num,
                    Submission.status == 'approved',
                    Submission.id != submission_id
                ).first()
                if existing_revision:
                    all_revisions = Submission.query.filter(
                        Submission.ml_number == parent_submission.ml_number,
                        Submission.status == 'approved',
                        Submission.revision_number.isnot(None)
                    ).all()
                    existing_nums = []
                    for rev in all_revisions:
                        try:
                            existing_nums.append(int(rev.revision_number))
                        except (ValueError, TypeError):
                            pass
                    next_num = 1
                    while next_num in existing_nums:
                        next_num += 1
                    submission.revision_number = f"{next_num:02d}"
            submission.ml_number = parent_submission.ml_number
        elif not submission.ml_number:
            try:
                doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                submission.ml_number = get_next_ml_number(doc_type)
            except Exception:
                pass
    elif not submission.ml_number:
        try:
            doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
            submission.ml_number = get_next_ml_number(doc_type)
        except Exception:
            pass

    submission.status = 'approved'
    submission.approved_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to commit approval: {e}")
        db.session.rollback()
        flash(f'Failed to approve submission: {str(e)}', 'error')
        return redirect(url_for('submissions.admin_submissions'))

    admin_user = get_current_user()
    action_desc = f"Approved revision {submission.revision_number} of {parent_draft_name}" if is_revision else f"Approved submission: {submission.title}"
    add_to_document_history(f"submission-{submission.id}", "approved", admin_user['name'], action_desc)

    flash_msg = f'Revision {submission.id} approved! ML number: {submission.ml_number}' if is_revision else f'Submission {submission.id} approved! ML number: {submission.ml_number}'
    flash(flash_msg, 'success')
    return redirect(url_for('submissions.submission_detail', submission_id=submission_id))


@bp.route('/submit/reject/<submission_id>', methods=['POST'])
@require_role('admin')
def reject_submission(submission_id):
    submission = get_submission_by_ref(submission_id)
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('submissions.admin_submissions'))

    submission.status = 'rejected'
    submission.rejected_at = datetime.utcnow()
    db.session.commit()

    admin_user = get_current_user()
    add_to_document_history(f"submission-{submission.id}", "rejected", admin_user['name'],
                           f"Rejected submission: {submission.title}")

    flash(f'Submission {submission.id} rejected!', 'warning')
    return redirect(url_for('submissions.submission_detail', submission_id=submission_id))


@bp.route('/view/<submission_id>')
@require_auth
def view_submission(submission_id):
    """View a submission file inline (for PDFs and other viewable files)."""
    submission = get_submission_by_ref(submission_id)
    if not submission:
        return "Submission not found", 404

    current_user = get_current_user()
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        return "Access denied", 403

    if not submission.file_path or not os.path.exists(submission.file_path):
        return "File not found", 404

    return send_file(submission.file_path, as_attachment=False, download_name=submission.filename)


@bp.route('/download/<submission_id>')
@require_auth
def download_submission(submission_id):
    """Download a submission file."""
    submission = get_submission_by_ref(submission_id)
    if not submission:
        return "Submission not found", 404

    current_user = get_current_user()
    if submission.submitted_by != current_user['name'] and current_user.get('role') not in ['admin', 'editor']:
        return "Access denied", 403

    if not submission.file_path or not os.path.exists(submission.file_path):
        return "File not found", 404

    return send_file(submission.file_path, as_attachment=True, download_name=submission.filename)


@bp.route('/admin/submissions/')
@require_role('admin')
def admin_submissions():
    """Admin submission management page."""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER

    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    status_filter = request.args.get('status', 'submitted')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Submission.query
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)

    submissions = query.order_by(Submission.submitted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    submission_cards = ""
    for submission in submissions.items:
        status_badge = {
            'submitted': 'badge bg-warning text-dark',
            'approved': 'badge bg-success',
            'rejected': 'badge bg-danger',
            'published': 'badge bg-info',
            'inscription_pending': 'badge bg-warning'
        }.get(submission.status, 'badge bg-secondary')

        is_revision = getattr(submission, 'is_revision', False)
        revision_number = getattr(submission, 'revision_number', '')
        parent_draft_name = getattr(submission, 'parent_draft_name', '')
        revision_badge = f'<span class="badge bg-success ms-2">Revision {revision_number}</span>' if is_revision and revision_number else ''

        source_type = getattr(submission, 'sourceType', 'file')
        if source_type == 'ordinal':
            inscription_number = getattr(submission, 'inscriptionNumber', None)
            ordinal_id = getattr(submission, 'ordinalId', None)
            block_height = getattr(submission, 'blockHeight', None)
            if inscription_number:
                source_info = f'<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span> Inscription #{inscription_number}'
                if block_height:
                    source_info += f' (Block {block_height})'
            elif ordinal_id:
                source_info = f'<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span> {ordinal_id[:16]}...'
            else:
                source_info = '<span class="badge bg-info"><i class="bi bi-coin"></i> Ordinal</span>'
        else:
            file_size = "N/A"
            if submission.file_path and os.path.exists(submission.file_path):
                file_size = f"{os.path.getsize(submission.file_path) / 1024:.1f} KB"
            source_info = f'<span class="badge bg-secondary"><i class="bi bi-file-earmark"></i> File</span> {submission.filename} ({file_size})'

        action_buttons = ""
        if submission.status == 'submitted':
            action_buttons = f"""
            <button class="btn btn-success btn-sm me-2" onclick="approveSubmission('{submission.id}')">
                <i class="fas fa-check me-1"></i>Approve
            </button>
            <button class="btn btn-danger btn-sm me-2" onclick="rejectSubmission('{submission.id}')">
                <i class="fas fa-times me-1"></i>Reject
            </button>
            <button class="btn btn-info btn-sm" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            """
        elif submission.status == 'approved':
            action_buttons = f"""
            <button class="btn btn-info btn-sm me-2" onclick="publishAsRFC('{submission.id}')">
                <i class="fas fa-star me-1"></i>Publish as RFC
            </button>
            <button class="btn btn-warning btn-sm" onclick="unapproveSubmission('{submission.id}')">
                <i class="fas fa-undo me-1"></i>Unapprove
            </button>
            """

        revision_context = ""
        if is_revision and parent_draft_name:
            revision_context = f'<p class="mb-2"><strong>Revision of:</strong> <a href="/doc/draft/{parent_draft_name}/" class="text-decoration-none">{parent_draft_name}</a></p>'

        authors = submission.authors if isinstance(submission.authors, list) else [submission.authors] if submission.authors else []
        submission_cards += f"""
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <a href="/doc/draft/{submission.id}/" class="text-decoration-none">
                        {submission.title}
                    </a>
                </h6>
                <div>
                    <span class="{status_badge}">{submission.status.title()}</span>
                    {revision_badge}
                </div>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-8">
                        <p class="mb-2"><strong>Authors:</strong> {', '.join(authors)}</p>
                        <p class="mb-2"><strong>Group:</strong> {submission.group or 'None'}</p>
                        <p class="mb-2"><strong>Submitted:</strong> {submission.submitted_at.strftime('%Y-%m-%d %H:%M')} by {submission.submitted_by}</p>
                        <p class="mb-2"><strong>Source:</strong> {source_info}</p>
                        {revision_context}
                        {f'<p class="mb-2"><strong>Abstract:</strong> {submission.abstract[:200]}...</p>' if submission.abstract else ''}
                    </div>
                    <div class="col-md-4">
                        <div class="d-grid gap-2">
                            <a href="/doc/draft/{submission.id}/" class="btn btn-outline-primary btn-sm">
                                <i class="fas fa-eye me-1"></i>View Draft
                            </a>
                            {action_buttons}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

    status_options = f"""
    <option value="all" {'selected' if status_filter == 'all' else ''}>All Submissions</option>
    <option value="submitted" {'selected' if status_filter == 'submitted' else ''}>Pending Review</option>
    <option value="approved" {'selected' if status_filter == 'approved' else ''}>Approved</option>
    <option value="rejected" {'selected' if status_filter == 'rejected' else ''}>Rejected</option>
    <option value="published" {'selected' if status_filter == 'published' else ''}>Published</option>
    """

    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/admin/">Admin Dashboard</a></li>
                <li class="breadcrumb-item active">Submission Management</li>
            </ol>
        </nav>

        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Submission Management</h1>
            <div>
                <select class="form-select form-select-sm" onchange="changeStatusFilter(this.value)">
                    {status_options}
                </select>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{Submission.query.filter_by(status='submitted').count()}</h4>
                        <p class="mb-0 small">Pending Review</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{Submission.query.filter_by(status='approved').count()}</h4>
                        <p class="mb-0 small">Approved</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-danger">{Submission.query.filter_by(status='rejected').count()}</h4>
                        <p class="mb-0 small">Rejected</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{Submission.query.filter_by(status='published').count()}</h4>
                        <p class="mb-0 small">Published as RFC</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="submissions-container">
            {submission_cards}
        </div>

        {f'''
        <nav aria-label="Submission pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not submissions.has_prev else ""}"><a class="page-link" href="?page={submissions.prev_num}&status={status_filter}">Previous</a></li>' if submissions.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == submissions.page else ""}"><a class="page-link" href="?page={i}&status={status_filter}">{i}</a></li>' for i in (submissions.iter_pages() or [])])}
                {f'<li class="page-item {"disabled" if not submissions.has_next else ""}"><a class="page-link" href="?page={submissions.next_num}&status={status_filter}">Next</a></li>' if submissions.has_next else ''}
            </ul>
        </nav>
        ''' if submissions.pages and submissions.pages > 1 else ''}
    </div>

    <script>
        function changeStatusFilter(status) {{
            window.location.href = '?status=' + status;
        }}

        function approveSubmission(submissionId) {{
            if (confirm('Approve this draft submission? It will be marked as approved and ready for publication.')) {{
                updateSubmissionStatus(submissionId, 'approved');
            }}
        }}

        function rejectSubmission(submissionId) {{
            const reason = prompt('Reason for rejection (optional):');
            updateSubmissionStatus(submissionId, 'rejected', reason);
        }}

        function unapproveSubmission(submissionId) {{
            if (confirm('Remove approval for this submission?')) {{
                updateSubmissionStatus(submissionId, 'submitted');
            }}
        }}

        function publishAsRFC(submissionId) {{
            const rfcNumber = prompt('Enter RFC number:');
            if (rfcNumber && confirm('Publish as RFC ' + rfcNumber + '?')) {{
                updateSubmissionStatus(submissionId, 'published', null, rfcNumber);
            }}
        }}

        function updateSubmissionStatus(submissionId, status, reason = null, rfcNumber = null) {{
            const data = {{ status: status }};
            if (reason) data.reason = reason;
            if (rfcNumber) data.rfc_number = rfcNumber;

            fetch('/admin/submissions/' + submissionId + '/status', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(data)
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{ location.reload(); }}
                else {{ alert('Error: ' + data.message); }}
            }})
            .catch(error => {{
                console.error('Error:', error);
                alert('Error updating submission status');
            }});
        }}
    </script>
    """

    return _format_base_template(
        title="Submission Management - MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER, hypothesis_config="")


@bp.route('/admin/submissions/<submission_id>/status', methods=['POST'])
@require_role('admin')
def update_submission_status(submission_id):
    """Update submission status (approve, reject, publish, unapprove)."""
    data = request.get_json() or {}
    new_status = data.get('status', '')
    reason = data.get('reason', '')
    rfc_number = data.get('rfc_number', '')

    if new_status not in ['submitted', 'approved', 'rejected', 'published']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400

    submission = get_submission_by_ref(submission_id)
    if not submission:
        return jsonify({'success': False, 'message': 'Submission not found'}), 404

    old_status = submission.status
    submission.status = new_status

    if new_status == 'approved':
        is_revision = getattr(submission, 'is_revision', False)
        revision_num = getattr(submission, 'revision_number', '')
        ml_num = submission.ml_number

        if is_revision and revision_num and ml_num:
            existing_revision = Submission.query.filter(
                Submission.ml_number == ml_num,
                Submission.revision_number == revision_num,
                Submission.status == 'approved',
                Submission.id != submission_id
            ).first()

            if existing_revision:
                all_revisions = Submission.query.filter(
                    Submission.ml_number == ml_num,
                    Submission.status == 'approved',
                    Submission.revision_number.isnot(None)
                ).all()
                existing_nums = []
                for rev in all_revisions:
                    try:
                        existing_nums.append(int(rev.revision_number))
                    except (ValueError, TypeError):
                        pass
                next_num = 1
                while next_num in existing_nums:
                    next_num += 1
                submission.revision_number = f"{next_num:02d}"
                current_app.logger.warning(f"Duplicate revision detected for {ml_num}, auto-assigned {submission.revision_number}")

    if new_status == 'approved' and not submission.ml_number:
        is_revision = getattr(submission, 'is_revision', False)
        parent_draft_name = getattr(submission, 'parent_draft_name', '')

        if is_revision and parent_draft_name:
            parent_submission = get_submission_by_ref(parent_draft_name)
            if parent_submission and parent_submission.ml_number:
                revision_num = getattr(submission, 'revision_number', '')
                if revision_num:
                    existing_revision = Submission.query.filter(
                        Submission.ml_number == parent_submission.ml_number,
                        Submission.revision_number == revision_num,
                        Submission.status == 'approved',
                        Submission.id != submission_id
                    ).first()
                    if existing_revision:
                        all_revisions = Submission.query.filter(
                            Submission.ml_number == parent_submission.ml_number,
                            Submission.status == 'approved',
                            Submission.revision_number.isnot(None)
                        ).all()
                        existing_nums = []
                        for rev in all_revisions:
                            try:
                                existing_nums.append(int(rev.revision_number))
                            except (ValueError, TypeError):
                                pass
                        next_num = 1
                        while next_num in existing_nums:
                            next_num += 1
                        submission.revision_number = f"{next_num:02d}"
                submission.ml_number = parent_submission.ml_number
                submission.approved_at = datetime.utcnow()
            else:
                try:
                    doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                    ml_number = get_next_ml_number(doc_type)
                    submission.ml_number = ml_number
                    submission.approved_at = datetime.utcnow()
                except Exception as e:
                    current_app.logger.error(f"Failed to assign ML number: {e}")
        else:
            try:
                doc_type = getattr(submission, 'doc_type', 'draft') or 'draft'
                ml_number = get_next_ml_number(doc_type)
                submission.ml_number = ml_number
                submission.approved_at = datetime.utcnow()
            except Exception as e:
                current_app.logger.error(f"Failed to assign ML number: {e}")

    if new_status == 'rejected' and reason:
        submission.rejected_at = datetime.utcnow()

    if new_status == 'published':
        if rfc_number:
            try:
                submission.rfc_number = int(rfc_number)
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid RFC number'}), 400
        if submission.ml_number and submission.ml_number.startswith('ML-Draft-'):
            draft_num = submission.ml_number.split('-')[-1]
            submission.ml_number = f"ML-RFC-{draft_num}"
        submission.doc_type = 'rfc'

    db.session.commit()

    admin_user = get_current_user()
    action_details = f"Changed status from {old_status} to {new_status}"
    if reason:
        action_details += f" - Reason: {reason}"
    if rfc_number:
        action_details += f" - Published as RFC {rfc_number}"

    add_to_document_history(f"submission-{submission.id}", "status_changed",
                           admin_user['name'], action_details)

    return jsonify({'success': True, 'message': f'Status updated to {new_status}'})
