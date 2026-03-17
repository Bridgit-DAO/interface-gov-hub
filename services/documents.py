"""Document services: draft data, comments, follow, notification controls, pages/words calculation."""
import os
import signal
from datetime import datetime, timedelta

from extensions import db
from models import Comment, UserFollow, User

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

# In-memory store for comment likes (no DB model yet)
COMMENT_LIKES = {}

# Legacy in-memory store (kept for test_core_features compatibility)
COMMENTS = {}

EDIT_DELETE_TIME_MINUTES = 15


def load_draft_data():
    """Load draft data from test files. Returns empty list - test documents removed."""
    return []


# Module-level cache for routes (loaded on first import)
DRAFTS = load_draft_data()


def calculate_pages_and_words(file_path, filename, max_size_mb=50, timeout_seconds=30):
    """
    Calculate pages and words from a file.
    Returns: (pages, words) tuple
    Defaults to (1, 0) if calculation fails

    Security features:
    - File size limit (default 50MB)
    - Processing timeout (default 30s)
    - Safe error handling
    """
    try:
        # Check file size (security: prevent memory exhaustion)
        file_size = os.path.getsize(file_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            print(f"[WARNING] File too large: {file_size} bytes (max {max_size_bytes})")
            return (1, 0)

        _, ext = os.path.splitext(filename.lower())
        words = 0
        pages = 1

        def timeout_handler(signum, frame):
            raise TimeoutError("File processing timeout")

        # Set timeout alarm (if supported)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

        try:
            if ext in ['.txt', '.xml']:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                words = len(content.split())
                pages = max(1, (words + 499) // 500)  # ~500 words per page

            elif ext == '.docx' and DOCX_SUPPORT:
                doc = docx.Document(file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = max(1, (words + 499) // 500)

            elif ext == '.pdf' and PDF_SUPPORT:
                reader = PyPDF2.PdfReader(file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = len(reader.pages) if reader.pages else max(1, (words + 499) // 500)
        finally:
            # Cancel timeout alarm
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)

        return (pages, words)

    except TimeoutError:
        print(f"[WARNING] File processing timeout for {filename}")
        return (1, 0)
    except Exception as e:
        print(f"[WARNING] Failed to calculate pages/words for {filename}: {e}")
        return (1, 0)  # Default fallback


def toggle_comment_like(draft_name, comment_id, user):
    """Toggle like on a comment."""
    like_key = f"{draft_name}:{comment_id}"
    if like_key not in COMMENT_LIKES:
        COMMENT_LIKES[like_key] = set()

    if user in COMMENT_LIKES[like_key]:
        COMMENT_LIKES[like_key].remove(user)
        return False  # Unliked
    else:
        COMMENT_LIKES[like_key].add(user)
        return True  # Liked


def get_comment_likes(draft_name, comment_id):
    """Get like count for a comment."""
    like_key = f"{draft_name}:{comment_id}"
    return len(COMMENT_LIKES.get(like_key, set()))


def is_comment_liked(draft_name, comment_id, user):
    """Check if user has liked a comment."""
    like_key = f"{draft_name}:{comment_id}"
    return user in COMMENT_LIKES.get(like_key, set())


def is_user_following_draft(draft_name, user):
    """Check if a user is following a specific draft."""
    if not user:
        return False
    return UserFollow.query.filter_by(user_id=user['id'], draft_name=draft_name).first() is not None


def get_user_follow(draft_name, user):
    """Get the UserFollow object for a user and draft."""
    if not user:
        return None
    return UserFollow.query.filter_by(user_id=user['id'], draft_name=draft_name).first()


def get_notification_controls(draft_name, user):
    """Generate HTML for notification level controls."""
    if not user:
        return ''

    follow = get_user_follow(draft_name, user)
    if not follow:
        return ''

    current_level = follow.notification_level
    options = []
    for level, description in UserFollow.NOTIFICATION_LEVELS.items():
        selected = 'selected' if level == current_level else ''
        options.append(f'<option value="{level}" {selected}>{description}</option>')

    return f'''
    <form method="post" action="/doc/draft/{draft_name}/update-notification/" class="mt-2">
        <label class="form-label small">Notification Level:</label>
        <select name="notification_level" class="form-select form-select-sm mb-1">
            {''.join(options)}
        </select>
        <button type="submit" class="btn btn-outline-secondary btn-sm w-100">Update Notifications</button>
    </form>
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
    all_comments = Comment.query.filter_by(draft_name=draft_name).order_by(Comment.timestamp).all()

    comment_dict = {}
    for comment in all_comments:
        comment_dict[comment.id] = {
            'id': str(comment.id),
            'author': comment.author,
            'date': comment.timestamp.strftime('%Y-%m-%d %H:%M'),
            'comment': comment.text if not comment.is_deleted else '[Deleted]',
            'avatar': ''.join([word[0].upper() for word in comment.author.split()[:2]]),
            'replies': [],
            'timestamp': comment.timestamp,
            'edited_at': comment.edited_at,
            'is_deleted': comment.is_deleted,
            'original_text': comment.original_text
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
    if comment['author'] != current_user['name']:
        return False
    if comment.get('is_deleted', False):
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
        is_liked = is_comment_liked_fn(draft_name, comment_id, current_user['name']) if current_user else False
        can_edit_delete = can_edit_delete_comment(comment, current_user)
        is_deleted = comment.get('is_deleted', False)
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
                        {deleted_badge}
                    </div>
                </div>
                <p class="mb-2" style="font-size: {font_size}px; {deleted_style}">{comment['comment']}</p>
                <div class="d-flex gap-2 align-items-center">
                    {like_button}
                    {reply_button}
                    {edit_delete_buttons}
                </div>

                <!-- Reply form (hidden by default) -->
                <div id="reply-form-{comment_id}" class="mt-3" style="display: none;">
                    <form method="POST" class="d-flex gap-2">
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
