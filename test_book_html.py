from services.book_html import (
    load_book_html_for_reader,
    looks_like_html_document,
    prepare_book_html_fragment,
)


def test_looks_like_html_document():
    assert looks_like_html_document('<!DOCTYPE html><html><body>x</body></html>')
    assert not looks_like_html_document('# Hello\n\nPlain markdown')


def test_prepare_book_html_scopes_css_and_body():
    full = '''<!DOCTYPE html><html><head><style>
        body { max-width: 600px; color: #000; }
        img { max-width: 100%; }
        .heading1 { font-size: 28px; }
    </style></head><body><div class="heading1">Title</div></body></html>'''
    out = prepare_book_html_fragment(full)
    assert '<style' in out
    assert '.metaweb-book-chapter' in out
    assert 'body {' not in out
    assert '.metaweb-book-chapter img' in out
    assert '<div class="metaweb-book-chapter">' in out
    assert 'Title' in out
    assert 'background-color' not in out or 'body {' not in out


def test_rewrite_ordinals_content_urls():
    iid = 'a' * 64 + 'i0'
    html = f'<img src="/content/{iid}">'
    out = load_book_html_for_reader(
        '<!DOCTYPE html><html><head></head><body>' + html + '</body></html>'
    )
    assert f'https://ordinals.com/content/{iid}' in out
