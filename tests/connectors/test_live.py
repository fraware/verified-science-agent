"""Optional live connector integration tests (network required)."""

from __future__ import annotations

import pytest

from vsa.connectors.clinvar import ClinVarConnector
from vsa.connectors.openalex import OpenAlexConnector
from vsa.connectors.uniprot import UniProtConnector

pytestmark = pytest.mark.live


@pytest.mark.timeout(60)
def test_live_uniprot_accession():
    results = UniProtConnector().fetch({"protein_accession": "P38398"})
    assert results, "UniProt returned no results for P38398"
    assert results[0].source_name == "UniProt"


@pytest.mark.timeout(60)
def test_live_openalex_doi():
    results = OpenAlexConnector().fetch({"doi": "10.1038/nature12373"})
    assert results, "OpenAlex returned no results for nature DOI"
    assert results[0].source_type == "publication"


@pytest.mark.timeout(90)
def test_live_clinvar_gene_variant():
    results = ClinVarConnector().fetch({"gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"})
    assert results, "ClinVar returned no candidates"
    assert results[0].domain_metadata.get("candidate_rank") == 1
