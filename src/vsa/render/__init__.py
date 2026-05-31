from __future__ import annotations

from typing import Any

from vsa.render.graph import evidence_graph_mermaid
from vsa.render.html import render_html
from vsa.render.json_renderer import render_json
from vsa.render.markdown import render_markdown

RENDERERS = {
    "markdown": render_markdown,
    "md": render_markdown,
    "html": render_html,
    "json": render_json,
}


def render(report: dict[str, Any], fmt: str = "markdown") -> str | bytes:
    fmt = fmt.lower()
    if fmt == "pdf":
        from vsa.render.pdf import render_pdf

        return render_pdf(report)
    fn = RENDERERS.get(fmt)
    if not fn:
        raise ValueError(f"Unknown format: {fmt}. Choose from: {', '.join(list(RENDERERS) + ['pdf'])}")
    return fn(report)
