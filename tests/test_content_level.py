"""Publication content level helpers."""

from __future__ import annotations

from vsa.connectors.content_level import abstract_snippet, has_abstract_content, infer_content_level


def test_infer_content_level_from_metadata():
    ev = {"domain_metadata": {"content_level": "abstract"}, "summary": "title: x"}
    assert infer_content_level(ev) == "abstract"


def test_infer_content_level_from_summary():
    ev = {"summary": "title: x; abstract: Long abstract body text here for testing purposes."}
    assert infer_content_level(ev) == "abstract"
    assert has_abstract_content(ev)


def test_abstract_snippet_prefers_domain_metadata():
    ev = {
        "domain_metadata": {"abstract_snippet": "Preferred snippet from metadata."},
        "summary": "abstract: fallback",
    }
    assert abstract_snippet(ev).startswith("Preferred snippet")
