"""UniProt connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.uniprot import UniProtConnector


@respx.mock
def test_uniprot_fetch_accession_reviewed():
    respx.get("https://rest.uniprot.org/uniprotkb/P38398.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "primaryAccession": "P38398",
                "entryType": "UniProtKB reviewed (Swiss-Prot)",
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "Breast cancer type 1 susceptibility protein"}}
                },
                "genes": [{"geneName": {"value": "BRCA1"}}],
            },
        )
    )
    conn = UniProtConnector()
    results = conn.fetch({"protein_accession": "P38398"})
    assert len(results) == 1
    assert results[0].domain_metadata["entry_type"] == "reviewed"
    assert results[0].reliability == "high"
