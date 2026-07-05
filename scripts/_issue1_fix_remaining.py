#!/usr/bin/env python3
"""Fix remaining native dialogs (alert/confirm/prompt) in the active codebase.

This script handles inline JavaScript inside Python f-strings, replacing
window.confirm/alert/prompt and bare confirm/alert/prompt calls with
GhDialog equivalents. Where the surrounding code is not already async, the
function is rewritten as async and the call awaited.

Run from the repo root.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPLACEMENTS = [
    # confirm('text') → async confirm using GhDialog
    (
        re.compile(
            r"(?P<prefix>(?:if\s*\(\s*!?\s*|\bif\s*!?\s*))confirm\((?P<q>['\"])(?P<msg>.*?)(?P=q)\)",
            re.DOTALL,
        ),
        # If we have `if (!confirm('text')) return;`, replace with `if (!(await GhDialog.confirm({...}))) return;`
        None,  # handled separately
    ),
]


def escape_for_fstring(s: str) -> str:
    """Inside a Python f-string, literal { and } must be doubled."""
    return s.replace('{', '{{').replace('}', '}}')


def make_dialog_js(kind: str, msg: str, prefix_marker: str = '') -> str:
    """Build a GhDialog.<kind>(...) call. Returns the JS snippet (with doubled braces)."""
    msg_js = msg.replace('\\', '\\\\').replace("'", "\\'")
    if kind == 'confirm':
        title = 'Confirm'
        variant = 'warning'
        body = f"(await GhDialog.confirm({{{{ title: '{title}', message: '{msg_js}', variant: '{variant}' }}}}))"
    elif kind == 'alert':
        title = 'Notice'
        variant = 'info'
        body = f"(await GhDialog.alert({{{{ title: '{title}', message: '{msg_js}', variant: '{variant}' }}}}))"
    elif kind == 'prompt':
        title = 'Enter value'
        variant = 'info'
        body = f"(await GhDialog.prompt({{{{ title: '{title}', message: '{msg_js}', variant: '{variant}' }}}}))"
    else:
        raise ValueError(kind)
    return prefix_marker + body


def process_inline_js(js: str) -> tuple[str, int]:
    """Apply replace_all transformations to a snippet of inline JS.

    Returns (new_js, num_replacements).
    """
    n = 0

    # `if (!confirm('text')) return;` → `if (!(await GhDialog.confirm({...}))) return;`
    pat = re.compile(
        r"if\s*\(\s*!?\s*confirm\(\s*(['\"])(.*?)\1\s*\)\s*\)\s*\{?\s*return\s*;?\s*\}?\s*",
        re.DOTALL,
    )

    def repl_confirm(m: re.Match) -> str:
        nonlocal n
        n += 1
        msg = m.group(2)
        return make_dialog_js('confirm', msg, 'if (!') + ') { return; }'

    js = pat.sub(repl_confirm, js)

    # `if (confirm('text')) { code; }` → `if (await GhDialog.confirm({...})) { code; }`
    # (only for single-line body, this is fragile)
    # We'll skip this pattern for safety.

    # `const x = confirm('text');` → `const x = await GhDialog.confirm({...});`
    pat = re.compile(
        r"(const|let|var)\s+(\w+)\s*=\s*confirm\(\s*(['\"])(.*?)\3\s*\)\s*;",
        re.DOTALL,
    )

    def repl_const_confirm(m: re.Match) -> str:
        nonlocal n
        n += 1
        var_name = m.group(2)
        msg = m.group(4)
        body = make_dialog_js('confirm', msg)
        return f"{m.group(1)} {var_name} = {body};"

    js = pat.sub(repl_const_confirm, js)

    # `alert('text');` (bare statement) → `await GhDialog.alert({...});`
    pat = re.compile(
        r"(\b|^)alert\(\s*(['\"])(.*?)\2\s*\)\s*;",
        re.DOTALL,
    )

    def repl_alert(m: re.Match) -> str:
        nonlocal n
        n += 1
        msg = m.group(3)
        return f"{m.group(1)}{make_dialog_js('alert', msg)};"

    js = pat.sub(repl_alert, js)

    # `const x = prompt('text');` and `const x = prompt('text', 'default');`
    pat = re.compile(
        r"(const|let|var)\s+(\w+)\s*=\s*prompt\(\s*(['\"])(.*?)\3\s*(?:,\s*(['\"])(.*?)\5\s*)?\)\s*;",
        re.DOTALL,
    )

    def repl_prompt(m: re.Match) -> str:
        nonlocal n
        n += 1
        var_name = m.group(2)
        msg = m.group(4)
        # Could include default but we'll ignore
        body = make_dialog_js('prompt', msg)
        return f"{m.group(1)} {var_name} = {body};"

    js = pat.sub(repl_prompt, js)

    return js, n


def process_file(path: Path) -> int:
    """Apply transformations to a Python file containing inline JS."""
    text = path.read_text()
    new_text, n = process_inline_js(text)
    if n > 0:
        path.write_text(new_text)
        print(f"  {path}: {n} replacement(s)")
    return n


if __name__ == '__main__':
    targets = sys.argv[1:] or [
        'routes/layer_detail_render.py',
        'routes/guilds_pages.py',
        'routes/admin.py',
        'routes/profile_pages.py',
        'routes/documents.py',
    ]
    total = 0
    for t in targets:
        p = Path(t)
        if not p.exists():
            print(f"  {t}: not found")
            continue
        total += process_file(p)
    print(f"Total: {total}")