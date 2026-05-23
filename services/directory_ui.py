"""Shared directory page chrome (Living Layer design system)."""
from __future__ import annotations

import html as html_mod


def gh_page_open(extra_class: str = '') -> str:
    extra = f' {extra_class.strip()}' if extra_class.strip() else ''
    return f'<div class="gh-page container mt-4{extra}">'


def gh_page_close() -> str:
    return '</div>'


def gh_page_header(
    title: str,
    lead: str = '',
    icon: str = 'fa-compass',
    actions_html: str = '',
    breadcrumb_html: str = '',
) -> str:
    icon_html = (
        f'<div class="gh-page-header-icon"><i class="fas {html_mod.escape(icon)}"></i></div>'
        if icon
        else ''
    )
    lead_html = (
        f'<p class="gh-page-lead">{html_mod.escape(lead)}</p>' if lead else ''
    )
    actions = (
        f'<div class="gh-page-header-actions">{actions_html}</div>'
        if actions_html
        else ''
    )
    return (
        f'{breadcrumb_html}'
        f'<header class="gh-page-header">'
        f'<div class="gh-page-header-main">{icon_html}'
        f'<div><h1 class="gh-page-title">{html_mod.escape(title)}</h1>{lead_html}</div></div>'
        f'{actions}'
        f'</header>'
    )


def gh_filter_row(cols_html: str) -> str:
    return f'<div class="gh-filter-bar row g-3 mb-4">{cols_html}</div>'


def gh_filter_col(label: str, field_html: str, col_class: str = 'col-md-4') -> str:
    return (
        f'<div class="{col_class}">'
        f'<label class="form-label gh-filter-label">{html_mod.escape(label)}</label>'
        f'{field_html}</div>'
    )


def gh_directory_grid(
    container_id: str,
    grid_class: str = 'row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-3',
) -> str:
    return (
        f'<div id="{html_mod.escape(container_id)}" class="{grid_class}">'
        f'<div class="col-12 text-center py-5">'
        f'<div class="spinner-border text-primary" role="status">'
        f'<span class="visually-hidden">Loading...</span></div></div></div>'
    )


def gh_living_module(
    title: str,
    body_html: str,
    icon: str = 'fa-layer-group',
    extra_class: str = 'mb-4',
    header_actions: str = '',
) -> str:
    actions = f'<div class="ms-auto">{header_actions}</div>' if header_actions else ''
    return (
        f'<div class="living-module {extra_class.strip()}">'
        f'<div class="living-module-header">'
        f'<div class="living-module-icon"><i class="fas {html_mod.escape(icon)}"></i></div>'
        f'<h5 class="living-module-title">{html_mod.escape(title)}</h5>'
        f'{actions}'
        f'</div>'
        f'<div class="living-module-body">{body_html}</div>'
        f'</div>'
    )


def gh_breadcrumb(items: list) -> str:
    """items: sequence of (label, href) — href None for active crumb."""
    parts = ['<nav aria-label="breadcrumb" class="gh-detail-breadcrumb mb-3"><ol class="breadcrumb">']
    for i, item in enumerate(items):
        label, href = item[0], item[1] if len(item) > 1 else None
        if href:
            parts.append(
                f'<li class="breadcrumb-item"><a href="{html_mod.escape(href)}">'
                f'{html_mod.escape(label)}</a></li>'
            )
        else:
            parts.append(f'<li class="breadcrumb-item active">{html_mod.escape(label)}</li>')
    parts.append('</ol></nav>')
    return ''.join(parts)


def gh_auth_panel(title: str, body_html: str, icon: str = 'fa-sign-in-alt') -> str:
    return (
        f'{gh_page_open()}'
        f'{gh_page_header(title, "", icon)}'
        f'<div class="row justify-content-center"><div class="col-md-6 col-lg-5">'
        f'{gh_living_module(title, body_html, icon, extra_class="mb-0")}'
        f'</div></div>'
        f'{gh_page_close()}'
    )
