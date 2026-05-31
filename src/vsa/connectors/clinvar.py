"""ClinVar read-only connector via NCBI E-utilities."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class ClinVarConnector(Connector):
    name = "ClinVar"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, cache: EvidenceCache | None = None, client: Any | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        gene = query.get("gene_symbol")
        variant = query.get("variant_hgvs_c") or query.get("variant")
        clinvar_id = query.get("clinvar_id")

        if clinvar_id:
            return self._fetch_by_id(str(clinvar_id))

        if not gene and not variant:
            return []

        term_parts = []
        if gene:
            term_parts.append(f"{gene}[gene]")
        if variant:
            term_parts.append(variant)
        term = " AND ".join(term_parts)

        cache_query = {"term": term}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            uid = cached.get("uid")
        else:
            resp = self.client.get(
                self.ESEARCH,
                params={"db": "clinvar", "term": term, "retmode": "json", "retmax": 1},
            )
            resp.raise_for_status()
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []
            uid = ids[0]
            self.cache.set(self.name, cache_query, {"uid": uid})

        return self._fetch_by_id(uid)

    def _fetch_by_id(self, uid: str) -> list[NormalizedEvidence]:
        cache_query = {"uid": uid}
        cached = self.cache.get(self.name, f"summary_{uid}")
        if cached:
            record = cached
        else:
            resp = self.client.get(
                self.ESUMMARY,
                params={"db": "clinvar", "id": uid, "retmode": "json"},
            )
            resp.raise_for_status()
            result = resp.json().get("result", {})
            record = result.get(uid, result)
            self.cache.set(self.name, f"summary_{uid}", record)

        title = record.get("title", "ClinVar variant")
        significance = record.get("clinical_significance") or record.get("description", "")
        if isinstance(significance, dict):
            significance = significance.get("description", str(significance))
        if isinstance(significance, list):
            significance = "; ".join(str(s) for s in significance)

        return [
            NormalizedEvidence(
                source_name="ClinVar",
                source_type="database",
                identifier=f"VCV{uid}" if not str(uid).startswith("VCV") else str(uid),
                retrieval_path=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "clinical_significance": significance},
                    ["title", "clinical_significance"],
                ),
                raw_record=record,
                domain_metadata={"clinical_significance": str(significance).lower()},
            )
        ]
