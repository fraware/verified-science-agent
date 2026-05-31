"""UniProt read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class UniProtConnector(Connector):
    name = "UniProt"
    BASE = "https://rest.uniprot.org/uniprotkb"

    def __init__(self, cache: EvidenceCache | None = None, client: httpx.Client | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        accession = query.get("protein_accession") or query.get("accession")
        gene = query.get("gene_symbol")
        if not accession and gene:
            return self._search_by_gene(gene)
        if not accession:
            return []
        return self._fetch_accession(accession)

    def _fetch_accession(self, accession: str) -> list[NormalizedEvidence]:
        cache_query = {"accession": accession}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            record = cached
        else:
            resp = self.client.get(f"{self.BASE}/{accession}.json")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            record = resp.json()
            self.cache.set(self.name, cache_query, record)

        protein_name = (
            record.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", "Unknown protein")
        )
        gene = ""
        genes = record.get("genes", [])
        if genes:
            gene = genes[0].get("geneName", {}).get("value", "")

        entry_type = str(record.get("entryType", "")).lower()
        reviewed = "reviewed" in entry_type or "swiss-prot" in entry_type
        unreviewed = "unreviewed" in entry_type or "trembl" in entry_type

        return [
            NormalizedEvidence(
                source_name="UniProt",
                source_type="database",
                identifier=accession,
                retrieval_path=f"https://www.uniprot.org/uniprotkb/{accession}/entry",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {
                        "accession": accession,
                        "protein_name": protein_name,
                        "gene": gene,
                        "entry_type": "Swiss-Prot (reviewed)" if reviewed else "TrEMBL (unreviewed)",
                    },
                    ["accession", "protein_name", "gene", "entry_type"],
                ),
                raw_record=record,
                reliability="high" if reviewed else "medium",
                domain_metadata={
                    "accession": accession,
                    "gene_symbol": gene,
                    "entry_type": "reviewed" if reviewed else "unreviewed",
                    "protein_name": protein_name,
                },
            )
        ]

    def _search_by_gene(self, gene: str) -> list[NormalizedEvidence]:
        cache_query = {"gene": gene, "organism": "human"}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            results = cached
        else:
            resp = self.client.get(
                f"{self.BASE}/search",
                params={"query": f"gene:{gene} AND organism_id:9606", "format": "json", "size": 5},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            self.cache.set(self.name, cache_query, results)

        if not results:
            return []
        accessions = [r.get("primaryAccession") for r in results if r.get("primaryAccession")]
        ambiguous = len(accessions) > 1
        accession = accessions[0]
        if not accession:
            return []
        evidence = self._fetch_accession(accession)
        if evidence and ambiguous:
            item = evidence[0]
            item.reliability = "medium"
            item.domain_metadata = {
                **item.domain_metadata,
                "gene_search_ambiguous": True,
                "alternate_accessions": accessions[1:4],
                "candidate_count": len(accessions),
            }
            item.summary = (
                item.summary
                + f"; gene search ambiguous ({len(accessions)} human isoforms; using {accession})"
            )
        return evidence
