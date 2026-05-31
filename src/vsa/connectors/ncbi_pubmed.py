"""NCBI PubMed read-only connector via E-utilities."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class PubMedConnector(Connector):
    name = "PubMed"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, cache: EvidenceCache | None = None, client: Any | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        pmid = query.get("pmid")
        doi = query.get("doi")
        term = query.get("term") or query.get("display_name")

        if pmid:
            return self._fetch_by_pmid(str(pmid))
        if doi:
            return self._search(f"{doi}[doi]", cache_key={"doi": doi})
        if not term:
            return []
        return self._search(term, cache_key={"term": term})

    def _search(self, term: str, cache_key: dict[str, str]) -> list[NormalizedEvidence]:
        cached = self.cache.get(self.name, cache_key)
        if cached:
            pmid = cached.get("pmid")
        else:
            resp = self.client.get(
                self.ESEARCH,
                params={"db": "pubmed", "term": term, "retmode": "json", "retmax": 1},
            )
            resp.raise_for_status()
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []
            pmid = ids[0]
            self.cache.set(self.name, cache_key, {"pmid": pmid})
        return self._fetch_by_pmid(pmid)

    def _fetch_by_pmid(self, pmid: str) -> list[NormalizedEvidence]:
        cache_query = {"pmid": pmid}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            record = cached
        else:
            resp = self.client.get(
                self.ESUMMARY,
                params={"db": "pubmed", "id": pmid, "retmode": "json"},
            )
            resp.raise_for_status()
            result = resp.json().get("result", {})
            record = result.get(pmid, result)
            self.cache.set(self.name, cache_query, record)

        title = record.get("title", "Unknown title")
        authors = ", ".join(record.get("authors", [])[:5]) if isinstance(record.get("authors"), list) else record.get("authors", "")
        pubdate = record.get("pubdate", "")
        doi = ""
        for id_entry in record.get("articleids", []):
            if id_entry.get("idtype") == "doi":
                doi = id_entry.get("value", "")

        return [
            NormalizedEvidence(
                source_name="PubMed",
                source_type="publication",
                identifier=f"PMID:{pmid}",
                retrieval_path=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "authors": authors, "pubdate": pubdate, "doi": doi},
                    ["title", "authors", "pubdate", "doi"],
                ),
                raw_record=record,
                domain_metadata={"pmid": pmid, "doi": doi},
            )
        ]
