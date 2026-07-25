"""Sanitize untrusted source/report text before HTML or PDF rendering."""

from __future__ import annotations

import html
import re

# Strip executable / active markup that must never reach render sinks raw.
_SCRIPT_TAG = re.compile(r"<\s*script\b[^>]*>.*?<\s*/\s*script\s*>", re.I | re.S)
_EVENT_HANDLER = re.compile(r"\son\w+\s*=\s*(['\"]).*?\1", re.I | re.S)
_EVENT_HANDLER_UNQUOTED = re.compile(r"\son\w+\s*=\s*[^\s>]+", re.I)
_JS_URI = re.compile(r"javascript\s*:", re.I)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_render_text(value: object) -> str:
    """Return text safe for insertion into HTML (escaped) or PDF (tag-stripped).

    Always escapes HTML entities so ``<script>`` and similar never execute when
    embedded in HTML. Also strips script blocks, inline handlers, and javascript:
    URIs before escaping so PDF/plain sinks do not carry raw markup payloads.
    """
    text = _CONTROL_CHARS.sub("", str(value if value is not None else ""))
    text = _SCRIPT_TAG.sub("", text)
    text = _EVENT_HANDLER.sub("", text)
    text = _EVENT_HANDLER_UNQUOTED.sub("", text)
    text = _JS_URI.sub("", text)
    return html.escape(text, quote=True)


def sanitize_pdf_text(value: object) -> str:
    """PDF-safe text: strip active markup then unescape entities for glyph output."""
    escaped = sanitize_render_text(value)
    # fpdf writes literal glyphs; unescape so &lt;script&gt; is visible as text, not markup.
    return html.unescape(escaped)
