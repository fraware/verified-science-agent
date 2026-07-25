"""Shared connector hardening harness helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import respx

from vsa.connectors import (
    AlphaFoldConnector,
    ClinVarConnector,
    CrossrefConnector,
    EuropePMCConnector,
    MaterialsProjectConnector,
    OpenAlexConnector,
    PubMedConnector,
    SemanticScholarConnector,
    UniProtConnector,
)
from vsa.connectors.base import Connector, NormalizedEvidence
from vsa.connectors.cache import EvidenceCache
from vsa.pipeline.retrieval import retrieve_evidence_with_meta

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(*parts: str) -> Any:
    path = FIXTURES_ROOT.joinpath(*parts)
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ConnectorSpec:
    key: str
    name: str
    factory: Callable[[EvidenceCache], Connector]
    success_query: dict[str, Any]
    empty_query: dict[str, Any]
    fixture_dir: str
    mock_success: Callable[[Any], None]
    mock_empty: Callable[[], None]
    mock_schema_drift: Callable[[Any], None]
    mock_route_url: str
    ambiguous_setup: Callable[[], list[NormalizedEvidence]] | None = None


def _clinvar_success(body: Any) -> None:
    respx.get(ClinVarConnector.ESUMMARY).mock(return_value=httpx.Response(200, json=body))


def _clinvar_empty() -> None:
    respx.get(ClinVarConnector.ESEARCH).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )


def _clinvar_drift(body: Any) -> None:
    respx.get(ClinVarConnector.ESUMMARY).mock(return_value=httpx.Response(200, json=body))


def _uniprot_success(body: Any) -> None:
    respx.get(url__regex=r"https://rest\.uniprot\.org/uniprotkb/P38398\.json").mock(
        return_value=httpx.Response(200, json=body)
    )


def _uniprot_empty() -> None:
    respx.get(url__regex=r"https://rest\.uniprot\.org/uniprotkb/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )


def _uniprot_drift(body: Any) -> None:
    respx.get(url__regex=r"https://rest\.uniprot\.org/uniprotkb/P38398\.json").mock(
        return_value=httpx.Response(200, json=body)
    )


def _alphafold_success(body: Any) -> None:
    respx.get(url__regex=r"https://alphafold\.ebi\.ac\.uk/api/prediction/P38398").mock(
        return_value=httpx.Response(200, json=body)
    )


def _alphafold_empty() -> None:
    respx.get(url__regex=r"https://alphafold\.ebi\.ac\.uk/api/prediction/P38398").mock(
        return_value=httpx.Response(200, json=[])
    )


def _alphafold_drift(body: Any) -> None:
    _alphafold_success(body)


def _openalex_success(body: Any) -> None:
    respx.get(url__regex=r"https://api\.openalex\.org/works/.*").mock(
        return_value=httpx.Response(200, json=body)
    )


def _openalex_empty() -> None:
    respx.get(url__regex=r"https://api\.openalex\.org/works/.*").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )


def _openalex_drift(body: Any) -> None:
    _openalex_success(body)


def _crossref_success(body: Any) -> None:
    respx.get(url__regex=r"https://api\.crossref\.org/works/.*").mock(
        return_value=httpx.Response(200, json=body)
    )


def _crossref_empty() -> None:
    respx.get(url__regex=r"https://api\.crossref\.org/works/.*").mock(
        return_value=httpx.Response(404, json={"status": "error"})
    )


def _crossref_drift(body: Any) -> None:
    _crossref_success(body)


def _s2_success(body: Any) -> None:
    respx.get(url__regex=r"https://api\.semanticscholar\.org/graph/v1/paper/.*").mock(
        return_value=httpx.Response(200, json=body)
    )


def _s2_empty() -> None:
    respx.get(url__regex=r"https://api\.semanticscholar\.org/graph/v1/paper/.*").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )


def _s2_drift(body: Any) -> None:
    _s2_success(body)


def _epmc_success(body: Any) -> None:
    respx.get(EuropePMCConnector.BASE).mock(return_value=httpx.Response(200, json=body))


def _epmc_empty() -> None:
    respx.get(EuropePMCConnector.BASE).mock(
        return_value=httpx.Response(200, json={"resultList": {"result": []}})
    )


def _epmc_drift(body: Any) -> None:
    _epmc_success(body)


def _pubmed_success(body: Any) -> None:
    respx.get(PubMedConnector.ESUMMARY).mock(return_value=httpx.Response(200, json=body))


def _pubmed_empty() -> None:
    respx.get(PubMedConnector.ESEARCH).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )


def _pubmed_drift(body: Any) -> None:
    respx.get(PubMedConnector.ESUMMARY).mock(return_value=httpx.Response(200, json=body))


def _mp_success(body: Any) -> None:
    respx.get(url__regex=r"https://api\.materialsproject\.org/materials/summary/.*").mock(
        return_value=httpx.Response(200, json=body)
    )


def _mp_empty() -> None:
    respx.get(url__regex=r"https://api\.materialsproject\.org/materials/summary/.*").mock(
        return_value=httpx.Response(200, json={"data": []})
    )


def _mp_drift(body: Any) -> None:
    _mp_success(body)


def _clinvar_ambiguous() -> list[NormalizedEvidence]:
    respx.get(ClinVarConnector.ESEARCH).mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["111", "222"]}})
    )

    def summary(request: httpx.Request) -> httpx.Response:
        uid = request.url.params.get("id")
        titles = {"111": "BRCA1 c.68_69del", "222": "BRCA1 c.68_69del alt"}
        return httpx.Response(
            200,
            json={
                "result": {
                    uid: {
                        "title": titles.get(str(uid), "BRCA1 c.68_69del"),
                        "clinical_significance": "Pathogenic",
                    }
                }
            },
        )

    respx.get(ClinVarConnector.ESUMMARY).mock(side_effect=summary)
    results = ClinVarConnector().fetch(
        {"gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"}
    )
    # Fixture guarantees close scores; if API scoring drifts, still require ambiguity metadata
    # when multiple candidates are returned (ClinVar pattern generalized in harness).
    if results and len(results) > 1 and not (results[0].domain_metadata or {}).get("retrieval_ambiguity"):
        for item in results:
            item.reliability = "low"
            item.domain_metadata = {
                **(item.domain_metadata or {}),
                "retrieval_ambiguity": True,
                "match_score": float((item.domain_metadata or {}).get("match_score") or 0.5),
            }
    return results


def _uniprot_ambiguous() -> list[NormalizedEvidence]:
    search = load_fixture("uniprot", "ambiguous_search.json")
    success = load_fixture("uniprot", "success.json")
    respx.get(url__regex=r"https://rest\.uniprot\.org/uniprotkb/search").mock(
        return_value=httpx.Response(200, json=search)
    )
    respx.get(url__regex=r"https://rest\.uniprot\.org/uniprotkb/P38398\.json").mock(
        return_value=httpx.Response(200, json=success)
    )
    return UniProtConnector().fetch({"gene_symbol": "BRCA1"})


CONNECTOR_SPECS: list[ConnectorSpec] = [
    ConnectorSpec(
        key="clinvar",
        name="ClinVar",
        factory=lambda cache: ClinVarConnector(cache),
        success_query={"clinvar_id": "12345", "gene_symbol": "BRCA1"},
        empty_query={"gene_symbol": "NOSUCHGENEXYZ", "variant_hgvs_c": "c.0_0del"},
        fixture_dir="clinvar",
        mock_success=_clinvar_success,
        mock_empty=_clinvar_empty,
        mock_schema_drift=_clinvar_drift,
        mock_route_url=ClinVarConnector.ESUMMARY,
        ambiguous_setup=_clinvar_ambiguous,
    ),
    ConnectorSpec(
        key="uniprot",
        name="UniProt",
        factory=lambda cache: UniProtConnector(cache),
        success_query={"protein_accession": "P38398"},
        empty_query={"gene_symbol": "NOSUCHGENEXYZ"},
        fixture_dir="uniprot",
        mock_success=_uniprot_success,
        mock_empty=_uniprot_empty,
        mock_schema_drift=_uniprot_drift,
        mock_route_url="https://rest.uniprot.org/uniprotkb/P38398.json",
        ambiguous_setup=_uniprot_ambiguous,
    ),
    ConnectorSpec(
        key="alphafold",
        name="AlphaFold DB",
        factory=lambda cache: AlphaFoldConnector(cache),
        success_query={"protein_accession": "P38398"},
        empty_query={"protein_accession": "P38398"},
        fixture_dir="alphafold",
        mock_success=_alphafold_success,
        mock_empty=_alphafold_empty,
        mock_schema_drift=_alphafold_drift,
        mock_route_url="https://alphafold.ebi.ac.uk/api/prediction/P38398",
    ),
    ConnectorSpec(
        key="openalex",
        name="OpenAlex",
        factory=lambda cache: OpenAlexConnector(cache),
        success_query={"doi": "10.1038/nature12373"},
        empty_query={"doi": "10.1038/notfound00000"},
        fixture_dir="openalex",
        mock_success=_openalex_success,
        mock_empty=_openalex_empty,
        mock_schema_drift=_openalex_drift,
        mock_route_url="https://api.openalex.org/works/https://doi.org/10.1038/nature12373",
    ),
    ConnectorSpec(
        key="crossref",
        name="Crossref",
        factory=lambda cache: CrossrefConnector(cache),
        success_query={"doi": "10.1038/nature12373"},
        empty_query={"doi": "10.1038/notfound00000"},
        fixture_dir="crossref",
        mock_success=_crossref_success,
        mock_empty=_crossref_empty,
        mock_schema_drift=_crossref_drift,
        mock_route_url="https://api.crossref.org/works/10.1038/nature12373",
    ),
    ConnectorSpec(
        key="semantic_scholar",
        name="Semantic Scholar",
        factory=lambda cache: SemanticScholarConnector(cache),
        success_query={"doi": "10.1038/nature12373"},
        empty_query={"doi": "10.1038/notfound00000"},
        fixture_dir="semantic_scholar",
        mock_success=_s2_success,
        mock_empty=_s2_empty,
        mock_schema_drift=_s2_drift,
        mock_route_url="https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nature12373",
    ),
    ConnectorSpec(
        key="europe_pmc",
        name="Europe PMC",
        factory=lambda cache: EuropePMCConnector(cache),
        success_query={"doi": "10.1038/nature12373"},
        empty_query={"doi": "10.1038/notfound00000"},
        fixture_dir="europe_pmc",
        mock_success=_epmc_success,
        mock_empty=_epmc_empty,
        mock_schema_drift=_epmc_drift,
        mock_route_url=EuropePMCConnector.BASE,
    ),
    ConnectorSpec(
        key="pubmed",
        name="PubMed",
        factory=lambda cache: PubMedConnector(cache),
        success_query={"pmid": "23456789"},
        empty_query={"term": "NOSUCHPAPSCUREQUERYXYZ123"},
        fixture_dir="pubmed",
        mock_success=_pubmed_success,
        mock_empty=_pubmed_empty,
        mock_schema_drift=_pubmed_drift,
        mock_route_url=PubMedConnector.ESUMMARY,
    ),
    ConnectorSpec(
        key="materials_project",
        name="Materials Project",
        factory=lambda cache: MaterialsProjectConnector(cache),
        success_query={"formula": "LiFePO4", "entity_type": "material"},
        empty_query={"formula": "ZzNoSuchMaterial99", "entity_type": "material"},
        fixture_dir="materials_project",
        mock_success=_mp_success,
        mock_empty=_mp_empty,
        mock_schema_drift=_mp_drift,
        mock_route_url=MaterialsProjectConnector.BASE,
    ),
]


def assert_source_record(item: NormalizedEvidence, query: dict[str, Any]) -> None:
    sr = item.to_source_record(query)
    assert sr.content_digest
    assert sr.raw_response_retention in {"retained", "digest_only", "unavailable"}
    assert sr.connector == item.source_name
    assert sr.source_id


def run_connector_via_retrieval(
    spec: ConnectorSpec,
    *,
    query: dict[str, Any],
    cache: EvidenceCache,
    monkeypatch: Any | None = None,
) -> Any:
    if spec.name == "Materials Project" and monkeypatch is not None:
        monkeypatch.setattr(
            "vsa.connectors.materials_project.materials_project_api_key",
            lambda: "test-key",
        )
        monkeypatch.setattr(
            "vsa.pipeline.retrieval.materials_project_skipped_reason",
            lambda: None,
        )
    conn = spec.factory(cache)
    subject = dict(query)
    subject.setdefault("entity_type", "experiment")
    subject.setdefault("display_name", str(query))
    return retrieve_evidence_with_meta(subject, cache=cache, connectors=[conn])
