"""Europe PMC read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class EuropePMCConnector(Connector):
    name = "Europe PMC"
    BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def __init__(self, cache: EvidenceCache | None = None, client: httpx.Client | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        doi = query.get("doi")
        pmid = query.get("pmid")
        term = f"DOI:{doi}" if doi else f"EXT_ID:{pmid}" if pmid else query.get("term")
        if not term:
            return []

        cache_query = {"term": term}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            results = cached
        else:
            resp = self.client.get(self.BASE, params={"query": term, "format": "json", "pageSize": 1})
            resp.raise_for_status()
            results = resp.json().get("resultList", {}).get("result", [])
            self.cache.set(self.name, cache_query, results)

        if not results:
            return []

        record = results[0]
        title = record.get("title", "Unknown")
        authors = record.get("authorString", "")
        abstract = (record.get("abstractText") or "")[:500]

        return [
            NormalizedEvidence(
                source_name="Europe PMC",
                source_type="publication",
                identifier=record.get("id") or record.get("pmid") or term,
                retrieval_path=f"https://europepmc.org/article/MED/{record.get('pmid', record.get('id', ''))}",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "authors": authors, "abstract": abstract},
                    ["title", "authors", "abstract"],
                ),
                raw_record=record,
                domain_metadata={"pmid": record.get("pmid"), "doi": record.get("doi")},
            )
        ]
