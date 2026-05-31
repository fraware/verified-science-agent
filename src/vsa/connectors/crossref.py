"""Crossref read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class CrossrefConnector(Connector):
    name = "Crossref"
    BASE = "https://api.crossref.org/works"

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
            message = cached
        else:
            resp = self.client.get(f"{self.BASE}/{doi_clean}")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            message = resp.json().get("message", {})
            self.cache.set(self.name, cache_query, message)

        title = (message.get("title") or ["Unknown"])[0]
        authors = ", ".join(
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in message.get("author", [])[:5]
        )
        abstract = (message.get("abstract") or "")[:800]

        return [
            NormalizedEvidence(
                source_name="Crossref",
                source_type="publication",
                identifier=doi_clean,
                retrieval_path=f"https://doi.org/{doi_clean}",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "authors": authors, "abstract": abstract},
                    ["title", "authors", "abstract"],
                ),
                raw_record=message,
                domain_metadata={
                    "doi": doi_clean,
                    "title": title,
                    "publisher": message.get("publisher"),
                    "year": (message.get("published-print") or message.get("published-online") or {}).get(
                        "date-parts", [[None]]
                    )[0][0],
                    "content_level": "abstract" if abstract.strip() else "metadata",
                    "abstract_snippet": abstract[:220] if abstract else "",
                },
            )
        ]
