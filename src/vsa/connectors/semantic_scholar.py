"""Semantic Scholar read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class SemanticScholarConnector(Connector):
    name = "Semantic Scholar"
    BASE = "https://api.semanticscholar.org/graph/v1/paper"

    def __init__(self, cache: EvidenceCache | None = None, client: httpx.Client | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        doi = query.get("doi")
        if not doi:
            return []
        doi_clean = doi.replace("https://doi.org/", "").strip()
        cache_query = {"doi": doi_clean}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            record = cached
        else:
            resp = self.client.get(
                f"{self.BASE}/DOI:{doi_clean}",
                params={"fields": "title,authors,abstract,year,externalIds"},
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            record = resp.json()
            self.cache.set(self.name, cache_query, record)

        title = record.get("title", "Unknown")
        authors = ", ".join(a.get("name", "") for a in record.get("authors", [])[:5])
        abstract = (record.get("abstract") or "")[:800]
        content_level = "abstract" if abstract.strip() else "metadata"

        return [
            NormalizedEvidence(
                source_name="Semantic Scholar",
                source_type="publication",
                identifier=record.get("paperId") or doi_clean,
                retrieval_path=f"https://doi.org/{doi_clean}",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "authors": authors, "abstract": abstract},
                    ["title", "authors", "abstract"],
                ),
                raw_record=record,
                domain_metadata={
                    "doi": doi_clean,
                    "title": title,
                    "year": record.get("year"),
                    "content_level": content_level,
                    "abstract_snippet": abstract[:220] if abstract else "",
                },
            )
        ]
