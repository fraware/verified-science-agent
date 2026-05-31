"""OpenAlex connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.openalex import OpenAlexConnector


@respx.mock
def test_openalex_fetch_doi():
    respx.get("https://api.openalex.org/works/https://doi.org/10.1038/nature12373").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W123",
                "title": "Example Nature paper",
                "doi": "https://doi.org/10.1038/nature12373",
                "publication_year": 2013,
                "authorships": [{"author": {"display_name": "A Author"}}],
            },
        )
    )
    conn = OpenAlexConnector()
    results = conn.fetch({"doi": "10.1038/nature12373"})
    assert len(results) == 1
    assert results[0].source_name == "OpenAlex"
    assert results[0].source_type == "publication"
    assert "Example Nature paper" in results[0].summary
