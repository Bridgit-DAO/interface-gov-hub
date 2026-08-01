"""Public patch explainer and landing routes."""
from __future__ import annotations

from flask import Blueprint, redirect, session

from services.patches_about_page import patches_about_page_title, render_patches_about_html
from services.proposal_modes import is_mode_enabled
from services.rendering import generate_user_menu, render_page

bp = Blueprint('patches_pages', __name__)


@bp.route('/patches/')
@bp.route('/patches')
def patches_index():
    return redirect('/patches/about/', code=302)


@bp.route('/patches/about/')
@bp.route('/patches/about')
def patches_about():
    content = render_patches_about_html(patches_enabled=is_mode_enabled('document'))
    return render_page(
        patches_about_page_title(),
        content,
        theme=session.get('theme', 'dark'),
        user_menu=generate_user_menu(),
    )
