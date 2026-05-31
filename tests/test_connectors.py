"""Connector unit tests with mocked HTTP."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.alphafold import AlphaFoldConnector
from vsa.connectors.cache import EvidenceCache
from vsa.connectors.clinvar import ClinVarConnector
from vsa.connectors.openalex import OpenAlexConnector
from vsa.connectors.uniprot import UniProtConnector


@respx.mock
def test_uniprot_fetch(tmp_path):
    respx.get("https://rest.uniprot.org/uniprotkb/P38398.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "primaryAccession": "P38398",
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "BRCA1 protein"}}
                },
                "genes": [{"geneName": {"value": "BRCA1"}}],
            },
        )
    )
    cache = EvidenceCache(tmp_path)
    results = UniProtConnector(cache).fetch({"protein_accession": "P38398"})
    assert len(results) == 1
    assert results[0].source_name == "UniProt"
    assert len(results[0].raw_record_hash()) == 64


@respx.mock
def test_clinvar_fetch_by_id(tmp_path):
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "17662": {
                        "title": "BRCA1 c.68_69del",
                        "clinical_significance": "Pathogenic",
                    }
                }
            },
        )
    )
    cache = EvidenceCache(tmp_path)
    results = ClinVarConnector(cache).fetch({"clinvar_id": "17662"})
    assert results[0].source_name == "ClinVar"


@respx.mock
def test_openalex_fetch(tmp_path):
    respx.get("https://api.openalex.org/works/https://doi.org/10.1038/nature12373").mock(
        return_value=httpx.Response(
            200,
            json={"id": "https://openalex.org/W1", "title": "Test paper", "authorships": []},
        )
    )
    cache = EvidenceCache(tmp_path)
    results = OpenAlexConnector(cache).fetch({"doi": "10.1038/nature12373"})
    assert results[0].source_type == "publication"


@respx.mock
def test_alphafold_fetch(tmp_path):
    respx.get("https://alphafold.ebi.ac.uk/api/prediction/P38398").mock(
        return_value=httpx.Response(
            200,
            json=[{"uniprotAccession": "P38398", "organismScientificName": "Homo sapiens"}],
        )
    )
    cache = EvidenceCache(tmp_path)
    results = AlphaFoldConnector(cache).fetch({"protein_accession": "P38398"})
    assert results[0].source_type == "structure"


def test_cache_roundtrip(tmp_path):
    cache = EvidenceCache(tmp_path)
    cache.set("Test", {"q": 1}, {"data": "value"})
    assert cache.get("Test", {"q": 1}) == {"data": "value"}
