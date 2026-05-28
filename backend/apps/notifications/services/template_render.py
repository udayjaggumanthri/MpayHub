"""
Render admin email templates with {{variable}} placeholders.
"""
from __future__ import annotations

import html
import re
from typing import Any

_VAR_PATTERN = re.compile(r'\{\{\s*([a-zA-Z0-9_]+)\s*\}\}')


def render_template(template: str, context: dict[str, Any], *, escape_html: bool = False) -> str:
    if not template:
        return ''

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        val = context.get(key, '')
        if val is None:
            val = ''
        text = str(val)
        return html.escape(text) if escape_html else text

    return _VAR_PATTERN.sub(_replace, template)


def strip_html_to_plain(html_body: str) -> str:
    if not html_body:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', html_body, flags=re.I)
    text = re.sub(r'</p\s*>', '\n\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
