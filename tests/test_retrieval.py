"""Retrieval cache propagation tests."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.cache import EvidenceCache
from vsa.pipeline.retrieval import retrieve_evidence_with_meta


@respx.mock
def test_cache_dir_used_by_connectors(tmp_path):
    respx.get("https://rest.uniprot.org/uniprotkb/P38398.json").mock(
        return_value=httpx.Response(
            200,
            json={"primaryAccession": "P38398", "genes": [{"geneName": {"value": "BRCA1"}}]},
        )
    )
    cache = EvidenceCache(tmp_path / "custom_cache")
    subject = {"entity_type": "protein", "protein_accession": "P38398", "display_name": "P38398"}
    result = retrieve_evidence_with_meta(subject, cache=cache)
    assert result.evidence
    assert (tmp_path / "custom_cache" / "UniProt").exists()
