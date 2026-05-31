"""Rendering tests."""

from __future__ import annotations

from vsa.render import render


def test_markdown_contains_sections(brca1_report):
    md = render(brca1_report, "markdown")
    for section in ["Executive summary", "Evidence table", "Claim table", "Provenance", "Validation checks"]:
        assert section in md


def test_html_renders(brca1_report):
    html = render(brca1_report, "html")
    assert "<html" in html
    assert "Scientific Report" in html


def test_json_render_roundtrip(brca1_report):
    text = render(brca1_report, "json")
    assert brca1_report["report_id"] in text
