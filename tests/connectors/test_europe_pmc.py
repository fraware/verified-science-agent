"""Europe PMC connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.pubmed import EuropePMCConnector


@respx.mock
def test_europe_pmc_fetch_doi_with_fulltext_flag():
    respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [
                        {
                            "id": "PMC123",
                            "pmid": "12345",
                            "doi": "10.1038/nature12373",
                            "title": "Europe PMC example",
                            "authorString": "Author A",
                            "abstractText": "Example abstract body.",
                            "hasFullText": "Y",
                            "isOpenAccess": "Y",
                        }
                    ]
                }
            },
        )
    )
    conn = EuropePMCConnector()
    results = conn.fetch({"doi": "10.1038/nature12373"})
    assert len(results) == 1
    assert results[0].domain_metadata["content_level"] == "fulltext"
    assert results[0].domain_metadata["has_fulltext"] is True
