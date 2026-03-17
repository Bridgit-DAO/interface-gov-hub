"""Ordinals.com API helpers: reinscription resolution, meta-domain fetch, markdown processing."""
import re
import time
import requests

try:
    import markdown2
    import bleach
    _MARKDOWN_SUPPORT = True
except ImportError:
    _MARKDOWN_SUPPORT = False


def process_ordinal_markdown(markdown_text):
    """Process ordinal markdown content into HTML. Used by API and draft_detail page."""
    if not _MARKDOWN_SUPPORT:
        import html
        return html.escape(markdown_text).replace('\n', '<br>')

    def replace_figure_image(match):
        alt_text = match.group(1) if match.group(1) else ''
        image_url = match.group(2)
        caption = match.group(3) if len(match.groups()) >= 3 and match.group(3) else ''
        html = '<figure class="figure">\n'
        html += f'  <img src="{image_url}" alt="{alt_text}" class="img-fluid figure-img">\n'
        if caption:
            html += f'  <figcaption class="figure-caption"><small>{caption}</small></figcaption>\n'
        html += '</figure>'
        return html

    markdown_text = re.sub(
        r'<figure[^>]*>\s*!\[([^\]]*)\]\(([^\)]+)\)\s*(?:<figcaption[^>]*>(.*?)</figcaption>)?\s*</figure>',
        replace_figure_image,
        markdown_text,
        flags=re.MULTILINE | re.DOTALL
    )
    html_content = markdown2.markdown(markdown_text, extras=['fenced-code-blocks', 'tables'])
    html_content = re.sub(r'src="(/content/[^"]+)"', r'src="https://ordinals.com\1"', html_content)
    html_content = re.sub(
        r'src="(?:[^"]*/)??([a-f0-9]{64}i\d+)"',
        r'src="https://ordinals.com/content/\1"',
        html_content
    )
    html_content = re.sub(r'<img(?![^>]*class=)([^>]*)>', r'<img class="img-fluid"\1>', html_content)
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img',
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'figure', 'figcaption', 'small', 'hr', 'div', 'span'
    ]
    allowed_attrs = {
        'a': ['href', 'title', 'target'],
        'img': ['src', 'alt', 'title', 'class'],
        'code': ['class'],
        'figure': ['class'],
        'figcaption': ['class']
    }
    html_content = bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs, strip=True)
    return html_content


def shorten_inscription_id(inscription_id, chars_each_side=8):
    """
    Shorten an inscription ID to show first N chars...last N chars.
    Example: 8e24de51....7615bi0 (with chars_each_side=8).
    """
    if not inscription_id:
        return ''
    if len(inscription_id) <= (chars_each_side * 2 + 4):
        return inscription_id
    start = inscription_id[:chars_each_side]
    end = inscription_id[-chars_each_side:]
    return f'{start}....{end}'


def _ordinals_fetch_json(url, retry=False):
    """
    Fetch JSON from ordinals.com. Retries once with timestamp query param on failure.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if not retry:
            ts = int(time.time() / (60 * 10))
            return _ordinals_fetch_json(f"{url}?timestamp={ts}", retry=True)
        raise


def get_last_inscription_for_sat(sat):
    """
    Retrieve the last (most recent) inscription on a given sat.
    Uses ordinals.com /r/sat/{sat}/at/-1 for reinscription resolution.
    Returns inscription ID or None.
    """
    if sat is None:
        return None
    try:
        url = f"https://ordinals.com/r/sat/{sat}/at/-1"
        data = _ordinals_fetch_json(url)
        return data.get("id")
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(f"get_last_inscription_for_sat sat={sat}: {e}")
        except RuntimeError:
            pass
        return None


def fetch_meta_domain_from_inscription(inscription_id):
    """
    Fetch meta-domain string from ordinal inscription content.
    If content is a sat number, resolve reinscription via get_last_inscription_for_sat.
    Returns domain string or None.
    """
    if not inscription_id:
        return None
    try:
        url = f"https://ordinals.com/content/{inscription_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/plain,application/octet-stream,*/*',
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        content = r.text.strip()
        try:
            sat = int(content)
            resolved_id = get_last_inscription_for_sat(sat)
            if resolved_id:
                r2 = requests.get(f"https://ordinals.com/content/{resolved_id}", headers=headers, timeout=15)
                r2.raise_for_status()
                content = r2.text.strip()
        except (ValueError, TypeError):
            pass
        return content if content else None
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(f"fetch_meta_domain_from_inscription {inscription_id}: {e}")
        except RuntimeError:
            pass
        return None
