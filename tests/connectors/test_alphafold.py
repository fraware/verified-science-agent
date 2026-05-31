"""AlphaFold connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.alphafold import AlphaFoldConnector


@respx.mock
def test_alphafold_predicted_structure_warning():
    respx.get("https://alphafold.ebi.ac.uk/api/prediction/P38398").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "uniprotAccession": "P38398",
                    "organismScientificName": "Homo sapiens",
                    "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P38398-F1-model_v4.pdb",
                    "latestVersion": 4,
                }
            ],
        )
    )
    conn = AlphaFoldConnector()
    results = conn.fetch({"protein_accession": "P38398"})
    assert len(results) == 1
    assert results[0].domain_metadata.get("structure_type") == "predicted"
    assert "not experimental" in results[0].summary.lower()
    assert results[0].reliability == "medium"
