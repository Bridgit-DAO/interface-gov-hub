"""Document services: draft data, comments, follow, notification controls, pages/words calculation."""
import os
import re
from datetime import datetime, timedelta
from html import escape

from sqlalchemy import or_

from extensions import db
from models import Comment, CommentLike, Submission, User
from models.db_types import comment_is_deleted
from services.csrf import csrf_form_field

from services.event_subscriptions import (
    DRAFT_SUBSCRIPTION_ROWS,
    get_draft_subscription_matrix,
    user_follows_draft,
)

# Optional file processing libraries
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    import docx
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False

try:
    import markdown2
    import bleach
    MARKDOWN_SUPPORT = True
except ImportError:
    MARKDOWN_SUPPORT = False

# Legacy in-memory store (kept for test_core_features compatibility)
COMMENTS = {}

EDIT_DELETE_TIME_MINUTES = 15

_ML_DIGITS_RE = re.compile(r'\d+')


def draft_ml_number_sort_tuple(draft: dict) -> tuple:
    """
    Sort key for /doc/all/ lists: higher ML draft/RFC numbers first (reverse sort).
    Drafts without ml_number use -1 so they appear after numbered items.
    """
    ml = (draft.get('ml_number') or '').strip()
    found = _ML_DIGITS_RE.findall(ml)
    num = int(found[-1]) if found else -1
    tie_break = draft.get('name') or ''
    return (num, tie_break)


def sort_documents_by_ml_number_desc(documents: list) -> list:
    return sorted(documents, key=draft_ml_number_sort_tuple, reverse=True)


# Query-string values accepted by the `collection=` param on /doc/all/ (see
# filter_documents_by_collection). Unknown/garbage values are ignored so the
# route always degrades to the full, unfiltered list.
DOC_COLLECTION_DESIRABLE_PROPERTIES = 'desirable-properties'

# Title of the ML-Draft that isn't itself a numbered "DPn" draft but belongs
# in the same external deep-link collection as the DP1..DPn drafts.
DESIRABLE_PROPERTIES_META_LAYER_TITLE = 'The Layered Web: The Desirable Properties of a Meta-Layer'
_DESIRABLE_PROPERTIES_META_LAYER_LEGACY_TITLES = frozenset({
    'The Desirable Properties of a Meta-Layer',
})


def is_desirable_properties_collection_document(title: str) -> bool:
    """True for the DP1..DPn drafts plus the Meta-Layer overview draft they anchor."""
    from services.workgroup_links import extract_dp_number_from_title

    t = (title or '').strip()
    if extract_dp_number_from_title(t) is not None:
        return True
    known_titles = {DESIRABLE_PROPERTIES_META_LAYER_TITLE.casefold()} | {
        legacy.casefold() for legacy in _DESIRABLE_PROPERTIES_META_LAYER_LEGACY_TITLES
    }
    return t.casefold() in known_titles


def filter_documents_by_collection(documents: list, collection: str) -> list:
    """
    Server-side filter for the /doc/all/?collection= query param, used to deep-link
    external sites (e.g. desirableproperties.org) to a curated subset of documents.
    Unrecognized values fall back to the full, unfiltered list rather than erroring.
    """
    key = (collection or '').strip().lower()
    if key == DOC_COLLECTION_DESIRABLE_PROPERTIES:
        return [
            d for d in documents
            if is_desirable_properties_collection_document(d.get('title'))
        ]
    return documents


def load_draft_data():
    """Load draft data from test files. Returns empty list - test documents removed."""
    return []


# Module-level cache for routes (loaded on first import)
DRAFTS = load_draft_data()


def extract_text_from_file(file_path, filename, max_size_mb=50):
    """
    Extract plain text from an uploaded draft file for word count / content hashing.
    Returns empty string when extraction fails or format is unsupported.
    """
    try:
        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            return ''

        _, ext = os.path.splitext(filename.lower())
        content = ''

        if ext in ['.txt', '.xml', '.md', '.markdown']:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

        elif ext == '.docx' and DOCX_SUPPORT:
            doc = docx.Document(file_path)
            content_parts = [p.text for p in doc.paragraphs if p.text.strip()]
            content = '\n\n'.join(content_parts)

        elif ext == '.pdf' and PDF_SUPPORT:
            reader = PyPDF2.PdfReader(file_path)
            content_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    content_parts.append(text)
            content = '\n\n'.join(content_parts)

        return content or ''
    except Exception as e:
        print(f"[WARNING] Failed to extract text from {filename}: {e}")
        return ''


def calculate_pages_and_words(file_path, filename, max_size_mb=50, timeout_seconds=30):
    """
    Calculate pages and words from a file.
    Returns: (pages, words) tuple
    Defaults to (1, 0) if calculation fails

    Security: file size limit (default 50MB) to reduce memory exhaustion risk.

    Note: SIGALRM-based timeouts were removed – Flask's threaded request workers
    are not the main interpreter thread, so signal handlers raise and every
    listing/detail ended up as (1, 0) words.
    """
    del timeout_seconds  # retained for call-site compatibility
    try:
        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            print(f"[WARNING] File too large: {file_size} bytes (max {max_size_bytes})")
            return (1, 0)

        content = extract_text_from_file(file_path, filename, max_size_mb=max_size_mb)
        if content:
            words = len(content.split())
            pages = max(1, (words + 499) // 500)
            return (pages, words)

        _, ext = os.path.splitext(filename.lower())
        if ext == '.pdf' and PDF_SUPPORT:
            reader = PyPDF2.PdfReader(file_path)
            pages = len(reader.pages) if reader.pages else 1
            return (pages, 0)

        return (1, 0)

    except Exception as e:
        print(f"[WARNING] Failed to calculate pages/words for {filename}: {e}")
        return (1, 0)  # Default fallback


def revision_notes_to_safe_html(text) -> str:
    """
    Plain-text revision notes → safe HTML: blank-line boundaries become paragraphs;
    single newlines inside a paragraph become <br />.
    """
    if text is None:
        return ''
    raw = str(text).strip()
    if not raw:
        return ''
    normalized = raw.replace('\r\n', '\n').replace('\r', '\n')
    blocks = [b.strip() for b in re.split(r'\n\s*\n', normalized) if b.strip()]
    if not blocks:
        return ''
    parts = []
    n = len(blocks)
    for i, block in enumerate(blocks):
        inner = escape(block).replace('\n', '<br />\n')
        margin = 'mb-2' if i < n - 1 else 'mb-0'
        parts.append(f'<p class="{margin}">{inner}</p>')
    return ''.join(parts)


def _config_upload_folder():
    """UPLOAD_FOLDER from Flask config when in app context; else None."""
    try:
        from flask import current_app

        return current_app.config.get('UPLOAD_FOLDER')
    except RuntimeError:
        return None


def _resolve_submission_disk_path(file_path, filename, upload_folder):
    """Use stored path if present; else try upload dir + basename (path drift on deploy)."""
    if file_path and os.path.isfile(file_path):
        return file_path
    if upload_folder and filename:
        cand = os.path.join(upload_folder, os.path.basename(filename))
        if os.path.isfile(cand):
            return cand
    if upload_folder and file_path:
        cand = os.path.join(upload_folder, os.path.basename(file_path))
        if os.path.isfile(cand):
            return cand
    return None


def _ordinal_text_word_page_count_from_url(url, ctype_raw):
    """(pages, words) from an inscription content URL; None if not applicable or fetch fails."""
    ctype = (ctype_raw or '').lower()
    if not url or not ('text/' in ctype or 'application/json' in ctype):
        return None
    try:
        import requests

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return None
        wc = len(r.text.split())
        pc = max(1, (wc + 499) // 500)
        return (pc, wc)
    except Exception:
        return None


def _ordinal_text_word_page_count(submission):
    """(pages, words) from ordinal URL for text/json inscriptions; None if not applicable or fetch fails."""
    return _ordinal_text_word_page_count_from_url(
        getattr(submission, 'ordinalContentUrl', None),
        getattr(submission, 'ordinalContentType', None),
    )


def submission_file_pages_words(submission):
    """
    Pages/word count for UI: prefer calculating from upload file when possible;
    for text ordinals with 0 words in DB, fetch inscription body (listing/detail).
    """
    if submission is None:
        return 1, 0
    st = (getattr(submission, 'sourceType', None) or 'file').strip().lower()
    fp = getattr(submission, 'file_path', None) or None
    fn = getattr(submission, 'filename', None) or None
    try:
        fallback_pages = max(1, int(submission.pages or 1))
    except (TypeError, ValueError):
        fallback_pages = 1
    try:
        fallback_words = int(submission.words or 0)
    except (TypeError, ValueError):
        fallback_words = 0

    if st == 'file' and fn:
        dbs = (getattr(submission, 'displayBodySource', None) or 'file').strip().lower()
        if dbs == 'ordinal':
            du = getattr(submission, 'displayOrdinalContentUrl', None)
            dct = getattr(submission, 'displayOrdinalContentType', None)
            got = _ordinal_text_word_page_count_from_url(du, dct)
            if got:
                return got
        resolved = _resolve_submission_disk_path(fp, fn, _config_upload_folder())
        if resolved:
            pages, words = calculate_pages_and_words(resolved, fn)
            return pages, words

    if st == 'ordinal' and fallback_words == 0:
        got = _ordinal_text_word_page_count(submission)
        if got:
            return got

    return fallback_pages, fallback_words


def _comment_like_user_id(user) -> str:
    if isinstance(user, dict):
        return str(user.get('id') or '').strip()
    return str(user or '').strip()


def toggle_comment_like(draft_name, comment_id, user):
    """Toggle like on a draft comment (persisted). Returns True if now liked."""
    user_id = _comment_like_user_id(user)
    if not user_id:
        return False

    existing = CommentLike.query.filter_by(comment_id=comment_id, user_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return False

    comment = Comment.query.filter_by(id=comment_id, draft_name=draft_name).first()
    if not comment or comment_is_deleted(comment.is_deleted):
        return False

    db.session.add(CommentLike(comment_id=comment_id, user_id=user_id))

    layer_id = None
    sub = (
        Submission.query.filter(
            or_(
                Submission.draft_name == draft_name,
                Submission.parent_draft_name == draft_name,
            ),
            Submission.status == 'approved',
        )
        .order_by(Submission.submitted_at.desc().nullslast())
        .first()
    )
    if sub:
        layer_id = sub.layer_id

    from services.events import emit_event

    emit_event(
        'draft_comment_liked',
        actor_type='user',
        actor_id=user_id,
        subject_type='comment',
        subject_id=str(comment_id),
        layer_id=layer_id,
        payload={
            'draft_name': draft_name,
            'ml_number': getattr(sub, 'ml_number', None) if sub else None,
            'comment_author': comment.author,
            'comment_preview': (comment.text or '')[:120],
        },
    )
    db.session.commit()
    return True


def get_comment_likes(draft_name, comment_id):
    """Get like count for a comment."""
    del draft_name  # scoped by comment_id
    return CommentLike.query.filter_by(comment_id=comment_id).count()


def is_comment_liked(draft_name, comment_id, user):
    """Check if user has liked a comment."""
    del draft_name
    user_id = _comment_like_user_id(user)
    if not user_id:
        return False
    return CommentLike.query.filter_by(comment_id=comment_id, user_id=user_id).first() is not None


def is_user_following_draft(draft_name, user):
    """Check if a user is following a specific draft (UserEventSubscription rows)."""
    if not user:
        return False
    return user_follows_draft(user['id'], draft_name)


def render_draft_subscription_form_html(
    draft_name,
    user,
    *,
    compact=False,
    next_url=None,
    show_hub_link=True,
):
    """HTML for per-event in-app / email toggles; POST to /doc/draft/.../subscriptions/."""
    if not user:
        return ''

    from html import escape

    matrix = get_draft_subscription_matrix(user['id'], draft_name)
    any_on = any(ia or em for ia, em in matrix.values())

    rows_html = []
    for et, label in DRAFT_SUBSCRIPTION_ROWS:
        ia, em = matrix.get(et, (False, False))
        ia_chk = ' checked' if ia else ''
        em_chk = ' checked' if em else ''
        rows_html.append(
            f'<tr>'
            f'<td class="small">{escape(label)}</td>'
            f'<td class="text-center"><input type="checkbox" class="form-check-input" name="in_app_{escape(et)}" value="1"{ia_chk}></td>'
            f'<td class="text-center"><input type="checkbox" class="form-check-input" name="email_{escape(et)}" value="1"{em_chk}></td>'
            f'</tr>'
        )

    intro = (
        '<p class="small text-muted mb-2">Choose which events notify you for this draft. Requires at least one channel on one row. '
        'Email also needs account email opt-in under profile.</p>'
        if not compact
        else '<p class="small text-muted mb-2">Per-event in-app and email.</p>'
    )
    status_badge = (
        '<span class="badge bg-secondary">Not subscribed</span>'
        if not any_on
        else '<span class="badge bg-success">Subscribed</span>'
    )
    next_hidden = ''
    if next_url:
        next_hidden = f'<input type="hidden" name="next" value="{escape(next_url)}">'

    wrap_cls = 'gh-draft-notifications border-top pt-2 mt-2' if not compact else 'gh-draft-notifications'
    heading = (
        '<h6 class="text-muted mb-2"><i class="fas fa-bell me-1"></i>Notifications</h6>'
        if not compact
        else '<h6 class="text-muted mb-2 small">Events &amp; channels</h6>'
    )
    hub_link_html = (
        '<p class="small text-muted mb-0"><a href="/notifications/">Open notifications hub</a></p>'
        if show_hub_link
        else ''
    )
    panel_id = 'gh-draft-notif-' + re.sub(r'[^\w-]', '-', draft_name or 'draft')

    details_html = f'''
            {intro}
            <form method="post" action="/doc/draft/{escape(draft_name)}/subscriptions/">
                {next_hidden}
                <div class="table-responsive">
                    <table class="table table-sm table-borderless mb-2 small">
                        <thead><tr><th>Event</th><th class="text-center">In-app</th><th class="text-center">Email</th></tr></thead>
                        <tbody>{''.join(rows_html)}</tbody>
                    </table>
                </div>
                <button type="submit" class="btn btn-primary btn-sm w-100 mb-1"><i class="fas fa-save me-1"></i>Save subscriptions</button>
            </form>
            <form method="post" action="/doc/draft/{escape(draft_name)}/subscriptions/" class="mt-1">
                {next_hidden}
                <input type="hidden" name="clear_all" value="1">
                <button type="submit" class="btn btn-outline-warning btn-sm w-100">Remove all for this draft</button>
            </form>
            {hub_link_html}
    '''

    return f'''
    <div class="{wrap_cls}">
        {heading}
        <div class="d-flex align-items-center gap-2 gh-draft-notif-summary">
            {status_badge}
            <button type="button" class="btn btn-link btn-sm p-0 text-muted gh-draft-notif-toggle"
                data-bs-toggle="collapse" data-bs-target="#{panel_id}"
                aria-expanded="false" aria-controls="{panel_id}"
                aria-label="Show notification options">
                <i class="fas fa-chevron-down" aria-hidden="true"></i>
            </button>
        </div>
        <div class="collapse pt-2" id="{panel_id}">
            {details_html}
        </div>
    </div>
    '''


def add_comment_reply(draft_name, parent_comment_id, reply_text, user):
    """Add a reply to a comment."""
    reply = Comment(
        draft_name=draft_name,
        text=reply_text,
        author=user['name'],
        parent_id=parent_comment_id
    )
    db.session.add(reply)
    db.session.commit()
    return reply


def build_comment_tree(draft_name):
    """Build a tree structure of comments with nested replies."""
    from services.document_reader_comments import comment_query_for_draft_ref

    all_comments = comment_query_for_draft_ref(draft_name).order_by(Comment.timestamp).all()

    comment_dict = {}
    for comment in all_comments:
        deleted = comment_is_deleted(comment.is_deleted)
        from urllib.parse import quote

        from services.dp_proposals import submission_draft_ref
        from services.read_navigation import read_page_url
        from services.submissions import get_submission_by_ref

        anchor_hash = (comment.anchor_hash or '').strip()
        scope = getattr(comment, 'comment_scope', None) or 'document'
        excerpt = (comment.passage_excerpt or comment.original_text or '').strip()
        sub = None
        if comment.submission_id:
            sub = Submission.query.get(comment.submission_id)
        if not sub and comment.draft_name:
            sub = get_submission_by_ref(comment.draft_name)
        read_ref = submission_draft_ref(sub) if sub else draft_name
        passage_href = None
        if anchor_hash:
            passage_href = read_page_url(read_ref) + '#gh-anchor-' + quote(anchor_hash, safe='')

        comment_dict[comment.id] = {
            'id': str(comment.id),
            'author': comment.author,
            'author_user_id': comment.author_user_id,
            'date': comment.timestamp.strftime('%Y-%m-%d %H:%M'),
            'comment': '[Deleted]' if deleted else (comment.text or ''),
            'avatar': ''.join([word[0].upper() for word in comment.author.split()[:2]]),
            'replies': [],
            'timestamp': comment.timestamp,
            'edited_at': comment.edited_at,
            'is_deleted': deleted,
            'original_text': comment.original_text,
            'comment_scope': scope,
            'passage_excerpt': excerpt,
            'anchor_hash': anchor_hash or None,
            'passage_href': passage_href,
        }

    top_level_comments = []
    for comment in all_comments:
        if comment.parent_id is None:
            top_level_comments.append(comment_dict[comment.id])
        else:
            if comment.parent_id in comment_dict:
                comment_dict[comment.parent_id]['replies'].append(comment_dict[comment.id])

    return top_level_comments


def can_edit_delete_comment(comment, current_user):
    """Check if current user can edit/delete this comment."""
    if not current_user:
        return False
    if comment_is_deleted(comment.get('is_deleted')):
        return False
    uid = current_user.get('id')
    author_user_id = comment.get('author_user_id')
    if author_user_id and uid:
        owned = author_user_id == uid
    else:
        owned = comment.get('author') == current_user.get('name')
    if not owned:
        return False

    comment_time = comment.get('timestamp')
    if comment_time:
        time_diff = datetime.utcnow() - comment_time
        time_limit = timedelta(minutes=EDIT_DELETE_TIME_MINUTES)
        return time_diff <= time_limit
    return False


def render_comment_tree(comments, draft_name, get_current_user_fn, get_comment_likes_fn, is_comment_liked_fn, level=0):
    """Recursively render comments and their nested replies."""
    if not comments:
        return ""

    indent_class = f"ms-{level * 4}" if level > 0 else ""
    html = f'<div class="{indent_class} mt-2">' if level > 0 else '<div class="mt-2">'

    for comment in comments:
        comment_id = comment.get('id', 'unknown')
        like_count = get_comment_likes_fn(draft_name, comment_id)
        current_user = get_current_user_fn()
        is_liked = is_comment_liked_fn(draft_name, comment_id, current_user) if current_user else False
        can_edit_delete = can_edit_delete_comment(comment, current_user)
        is_deleted = comment_is_deleted(comment.get('is_deleted'))
        edited_at = comment.get('edited_at')
        edited_text = f" (edited {edited_at.strftime('%Y-%m-%d %H:%M')})" if edited_at else ""

        like_btn_class = "btn-outline-danger" if is_liked else "btn-outline-secondary"
        like_icon = "❤️" if is_liked else "🤍"

        avatar_size = max(30 - level * 5, 20)
        font_size = max(14 - level * 2, 12)
        card_class = "mb-2" if level > 0 else "mb-3"

        edit_delete_buttons = ""
        if can_edit_delete:
            edit_click = f"editComment('{comment_id}')"
            delete_click = f"deleteComment('{comment_id}')"
            edit_delete_buttons = f"""
                    <button class="btn btn-sm btn-outline-warning" onclick="{edit_click}" style="font-size: {font_size - 2}px;">
                        Edit
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="{delete_click}" style="font-size: {font_size - 2}px;">
                        Delete
                    </button>
            """

        like_click = f"toggleLike('{comment_id}')"
        reply_click = f"toggleReply('{comment_id}')"
        like_button = f'<button class="btn btn-sm {like_btn_class}" onclick="{like_click}" style="font-size: {font_size - 2}px;">{like_icon} {like_count}</button>' if not is_deleted else ''
        reply_button = f'<button class="btn btn-sm btn-outline-primary" onclick="{reply_click}" style="font-size: {font_size - 2}px;">Reply</button>' if not is_deleted else ''
        deleted_badge = '<small class="text-muted ms-2" style="font-style: italic;">[Deleted]</small>' if is_deleted else ''
        deleted_style = 'opacity: 0.5; font-style: italic;' if is_deleted else ''
        comment_body = escape(comment['comment'] or '')
        passage_block = ''
        passage_badge = ''
        is_passage = comment.get('comment_scope') == 'passage' or bool(comment.get('anchor_hash'))
        href = comment.get('passage_href')
        excerpt = (comment.get('passage_excerpt') or comment.get('original_text') or '').strip()
        if not is_deleted and is_passage:
            badge_style = f'font-size: {font_size - 3}px;'
            if href:
                passage_badge = (
                    f'<a href="{escape(href)}" class="badge bg-info text-dark ms-2 '
                    f'gh-passage-comment-link" style="{badge_style}" '
                    f'title="Open highlighted passage in the document">'
                    f'<i class="fas fa-highlighter me-1" aria-hidden="true"></i>Passage comment</a>'
                )
            else:
                passage_badge = (
                    f'<span class="badge bg-info text-dark ms-2" style="{badge_style}">'
                    f'Passage comment</span>'
                )
            if excerpt:
                excerpt_html = f'<em>&ldquo;{escape(excerpt)}&rdquo;</em>'
                passage_block = (
                    f'<div class="gh-comment-passage small mb-2 p-2 rounded" '
                    f'style="background: var(--bg-tertiary); border-left: 3px solid var(--bs-info); '
                    f'color: var(--text-primary, inherit);">'
                    f'<div class="text-muted mb-1"><i class="fas fa-highlighter me-1"></i>'
                    f'Comment on this passage</div>'
                    f'{excerpt_html}'
                    f'</div>'
                )

        html += f"""
        <div class="card {card_class}" id="comment-{comment_id}">
            <div class="card-body py-2">
                <div class="d-flex align-items-center mb-1">
                    <div class="avatar bg-{"secondary" if level > 0 else "primary"} text-white rounded-circle me-2" style="width: {avatar_size}px; height: {avatar_size}px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: {font_size - 2}px;">
                        {comment['avatar']}
                    </div>
                    <div>
                        <strong style="font-size: {font_size}px;">{comment['author']}</strong>
                        <small class="text-muted ms-2">{comment['date']}{edited_text}</small>
                        {passage_badge}
                        {deleted_badge}
                    </div>
                </div>
                {passage_block}
                <p class="mb-2 gh-comment-body" style="font-size: {font_size}px; white-space: pre-wrap; word-wrap: break-word; {deleted_style}">{comment_body}</p>
                <div class="d-flex gap-2 align-items-center">
                    {like_button}
                    {reply_button}
                    {edit_delete_buttons}
                </div>

                <!-- Reply form (hidden by default) -->
                <div id="reply-form-{comment_id}" class="mt-3" style="display: none;">
                    <form method="POST" class="d-flex gap-2">
                        {csrf_form_field()}
                        <input type="hidden" name="action" value="reply">
                        <input type="hidden" name="parent_comment_id" value="{comment_id}">
                        <input type="text" name="reply_text" class="form-control" placeholder="Write a reply..." required style="font-size: {font_size}px;">
                        <button type="submit" class="btn btn-primary btn-sm" style="font-size: {font_size - 2}px;">Reply</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="{reply_click}" style="font-size: {font_size - 2}px;">Cancel</button>
                    </form>
                </div>

                <!-- Nested replies -->
                {render_comment_tree(comment.get('replies', []), draft_name, get_current_user_fn, get_comment_likes_fn, is_comment_liked_fn, level + 1)}
            </div>
        </div>
        """

    html += '</div>'
    return html
