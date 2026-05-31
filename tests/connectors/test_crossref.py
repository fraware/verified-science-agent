"""Crossref connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.crossref import CrossrefConnector


@respx.mock
def test_crossref_fetch_doi():
    respx.get("https://api.crossref.org/works/10.1038/nature12373").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "DOI": "10.1038/nature12373",
                    "title": ["Crossref example title"],
                    "author": [{"given": "Jane", "family": "Doe"}],
                }
            },
        )
    )
    conn = CrossrefConnector()
    results = conn.fetch({"doi": "10.1038/nature12373"})
    assert len(results) == 1
    assert results[0].source_name == "Crossref"
    assert "Crossref example title" in results[0].summary
