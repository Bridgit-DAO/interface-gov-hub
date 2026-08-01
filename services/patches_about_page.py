"""Public explainer: what patches are and how they enable collaborative documents."""
from __future__ import annotations

import html as html_mod

from services.directory_ui import gh_breadcrumb, gh_living_module, gh_page_close, gh_page_header, gh_page_open
from services.proposal_modes import is_mode_enabled


def render_patches_about_html(*, patches_enabled: bool) -> str:
    """Body HTML for /patches/about/ (inside render_page shell)."""
    hero_section = ''
    if patches_enabled:
        hero_section = '''
        <section class="dp-challenge-hero living-module mb-4" aria-label="How to propose a patch">
            <div class="dp-challenge-hero-banner">
                <img src="/static/images/doc-patch-light.png" alt="" width="1024" height="576"
                    loading="eager" class="dp-challenge-hero-img dp-challenge-hero-img--light" />
                <img src="/static/images/doc-patch-dark.png" alt="" width="1024" height="576"
                    loading="eager" class="dp-challenge-hero-img dp-challenge-hero-img--dark" aria-hidden="true" />
            </div>
        </section>'''

    cta_block = ''
    if patches_enabled:
        cta_block = '''
        <div class="d-flex flex-wrap gap-2 mt-4">
            <a href="/doc/all/" class="btn btn-primary">
                <i class="fas fa-file-alt me-1"></i>Browse documents
            </a>
            <a href="/suggest-edit/" class="btn btn-outline-primary">
                <i class="fas fa-pen-fancy me-1"></i>Propose a patch
            </a>
            <a href="/dp-challenge/" class="btn btn-outline-secondary">
                <i class="fas fa-highlighter me-1"></i>DP Challenge
            </a>
        </div>'''
    else:
        cta_block = '''
        <div class="d-flex flex-wrap gap-2 mt-4">
            <a href="/doc/all/" class="btn btn-primary">
                <i class="fas fa-file-alt me-1"></i>Browse documents
            </a>
        </div>
        <p class="text-muted small mt-3 mb-0">
            Patch proposals are not available on this site yet. You can still read and follow documents.
        </p>'''

    what_body = '''
        <p class="mb-3">
            A <strong>patch</strong> is a suggested change to a specific passage in a living document.
            Instead of editing the document directly, you select the text you want to improve and
            propose clearer wording. Each patch stays tied to that passage so everyone can see
            exactly what you mean.
        </p>
        <p class="mb-0 text-muted small">
            Patches are passage-level only&mdash;there are no whole-document patches. This keeps
            review focused and makes it easy to accept good ideas one sentence at a time.
        </p>'''

    how_body = '''
        <ol class="gh-patch-steps mb-0">
            <li class="mb-3">
                <strong>Propose.</strong> Open a document, select the text you want to change,
                and submit your patched wording with a short rationale.
            </li>
            <li class="mb-3">
                <strong>Review.</strong> Others read your suggestion alongside the original passage.
                Comments and additional patches can stack on the same text.
            </li>
            <li class="mb-0">
                <strong>Merge.</strong> Document stewards accept patches that improve the text.
                Accepted patches become part of the document&rsquo;s living history.
            </li>
        </ol>'''

    start_body = f'''
        <p class="mb-0">
            Pick a document, read it in the Gov Hub reader, and look for the
            <strong>Propose a patch</strong> option when you select text. You can also browse
            existing patches on any document from its <strong>Patches</strong> tab.
        </p>
        {cta_block}'''

    return f'''
    <link rel="stylesheet" href="/static/css/dp-challenge.css?v=9">
    {gh_page_open()}
    {gh_page_header(
        'Patches',
        'A simple way to improve living documents together on the Meta-Layer.',
        'fa-code-branch',
        breadcrumb_html=gh_breadcrumb([('Participate', None), ('Patches', None)]),
    )}
    {hero_section}
    <div class="row g-4">
        <div class="col-lg-6">
            {gh_living_module('What is a patch?', what_body, 'fa-question-circle')}
        </div>
        <div class="col-lg-6">
            {gh_living_module('How collaboration works', how_body, 'fa-people-arrows')}
        </div>
        <div class="col-12">
            {gh_living_module('Start patching', start_body, 'fa-play-circle')}
        </div>
    </div>
    {gh_page_close()}'''


def patches_about_page_title() -> str:
    return 'Patches – GovHub'
