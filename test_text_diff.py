"""Word-level diff rendering used by the patches list page."""
from services.text_diff import build_diff_html, change_counts


def test_unchanged_text_has_no_diff_markup():
    assert build_diff_html('same text', 'same text') == 'same text'


def test_replacement_marks_deletion_and_insertion():
    html = build_diff_html('the quick fox', 'the slow fox')

    assert '<del class="dp-diff-del">quick</del>' in html
    assert '<mark class="dp-diff-ins">slow</mark>' in html
    assert html.startswith('the ')
    assert html.endswith(' fox')


def test_pure_insertion_keeps_surrounding_text_unmarked():
    html = build_diff_html('trust collapses.', 'trust visibly collapses.')

    assert '<del' not in html
    assert '<mark class="dp-diff-ins">' in html
    assert 'trust' in html and 'collapses.' in html


def test_html_in_source_text_is_escaped():
    html = build_diff_html('a <script>x</script> b', 'a <b>y</b> b')

    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_missing_original_marks_everything_as_inserted_and_escaped():
    assert build_diff_html('', '<b>hi</b>') == (
        '<mark class="dp-diff-ins">&lt;b&gt;hi&lt;/b&gt;</mark>'
    )


def test_change_counts_reports_added_and_removed_characters():
    added, removed = change_counts('the quick fox', 'the slow fox')

    assert added == len('slow')
    assert removed == len('quick')


def test_oversized_input_falls_back_to_plain_proposed_text():
    huge = 'word ' * 5000

    assert build_diff_html(huge, huge + 'tail') == (huge + 'tail')
