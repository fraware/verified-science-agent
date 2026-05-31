"""AlphaFold DB read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client


class AlphaFoldConnector(Connector):
    name = "AlphaFold DB"
    BASE = "https://alphafold.ebi.ac.uk/api/prediction"

    def __init__(self, cache: EvidenceCache | None = None, client: httpx.Client | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        accession = query.get("protein_accession") or query.get("accession")
        if not accession:
            return []

        cache_query = {"accession": accession}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            records = cached if isinstance(cached, list) else [cached]
        else:
            resp = self.client.get(f"{self.BASE}/{accession}")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            records = data if isinstance(data, list) else [data]
            self.cache.set(self.name, cache_query, records)

        if not records:
            return []

        record = records[0]
        uniprot = record.get("uniprotAccession", accession)
        organism = record.get("organismScientificName", "")
        model_url = record.get("pdbUrl") or f"https://alphafold.ebi.ac.uk/entry/{uniprot}"

        return [
            NormalizedEvidence(
                source_name="AlphaFold DB",
                source_type="structure",
                identifier=uniprot,
                retrieval_path=model_url,
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {
                        "uniprot": uniprot,
                        "organism": organism,
                        "model_version": record.get("latestVersion"),
                    },
                    ["uniprot", "organism", "model_version"],
                ),
                raw_record=record,
                domain_metadata={
                    "uniprot_accession": uniprot,
                    "model_version": record.get("latestVersion"),
                },
            )
        ]
