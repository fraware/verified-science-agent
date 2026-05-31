"""Semantic Scholar connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.semantic_scholar import SemanticScholarConnector


@respx.mock
def test_semantic_scholar_fetch_doi_with_abstract():
    respx.get("https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373").mock(
        return_value=httpx.Response(
            200,
            json={
                "paperId": "abc123",
                "title": "Semantic Scholar example",
                "authors": [{"name": "Jane Doe"}],
                "abstract": "Example abstract for testing content level.",
                "year": 2024,
            },
        )
    )
    conn = SemanticScholarConnector()
    results = conn.fetch({"doi": "10.1038/nature12373"})
    assert len(results) == 1
    assert results[0].domain_metadata["content_level"] == "abstract"
    assert "Semantic Scholar example" in results[0].summary
