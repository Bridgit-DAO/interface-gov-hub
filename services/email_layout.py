"""Shared HTML shell and display-name helper for outbound notification emails."""
from __future__ import annotations

import html
from typing import Optional


def email_shell(title: str, body_html: str) -> str:
    """Wrap ``body_html`` in the standard Gov Hub notification email chrome."""
    return f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#222;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#667eea;margin-top:0;">{html.escape(title)}</h2>
{body_html}
<p style="font-size:12px;color:#888;margin-top:32px;">Gov Hub · Interface Governance Hub</p>
</body></html>"""


def user_display(user, fallback: str = 'Someone') -> str:
    """Best available display name for a user, falling back when absent."""
    if not user:
        return fallback
    return user.displayName or user.name or user.username or fallback
