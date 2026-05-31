"""OpenAlex read-only connector for scholarly works."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class OpenAlexConnector(Connector):
    name = "OpenAlex"
    BASE = "https://api.openalex.org"

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
            url = f"{self.BASE}/works/https://doi.org/{doi_clean}"
            resp = self.client.get(url)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            record = resp.json()
            self.cache.set(self.name, cache_query, record)

        title = record.get("title") or "Unknown title"
        authors = ", ".join(
            a.get("author", {}).get("display_name", "")
            for a in record.get("authorships", [])[:5]
        )
        abstract = record.get("abstract_inverted_index")
        abstract_text = ""
        if isinstance(abstract, dict):
            words = [""] * (max(abstract.keys(), key=int) + 1 if abstract else 0)
            for word, positions in abstract.items():
                for pos in positions:
                    if pos < len(words):
                        words[pos] = word
            abstract_text = " ".join(words).strip()[:500]

        return [
            NormalizedEvidence(
                source_name="OpenAlex",
                source_type="publication",
                identifier=record.get("id", doi_clean),
                retrieval_path=record.get("id") or f"https://doi.org/{doi_clean}",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "authors": authors, "abstract": abstract_text},
                    ["title", "authors", "abstract"],
                ),
                raw_record=record,
                domain_metadata={
                    "doi": doi_clean,
                    "publication_year": record.get("publication_year"),
                    "type": record.get("type"),
                },
            )
        ]
