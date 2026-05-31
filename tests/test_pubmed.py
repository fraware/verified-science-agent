"""PubMed connector tests."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.cache import EvidenceCache
from vsa.connectors.ncbi_pubmed import PubMedConnector


@respx.mock
def test_pubmed_fetch_by_pmid(tmp_path):
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "12345": {
                        "title": "Test article",
                        "authors": ["Author A"],
                        "pubdate": "2024",
                        "articleids": [{"idtype": "doi", "value": "10.1/test"}],
                    }
                }
            },
        )
    )
    cache = EvidenceCache(tmp_path)
    results = PubMedConnector(cache).fetch({"pmid": "12345"})
    assert results[0].source_name == "PubMed"
    assert "12345" in results[0].retrieval_path
