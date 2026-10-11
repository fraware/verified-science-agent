"""ClinVar connector tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
import respx

from vsa.connectors.clinvar import ClinVarConnector


@respx.mock
def test_clinvar_fetch_by_id():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "12345": {
                        "title": "BRCA1 c.68_69del",
                        "clinical_significance": {"description": "Pathogenic"},
                    }
                }
            },
        )
    )
    conn = ClinVarConnector()
    results = conn.fetch({"clinvar_id": "12345", "gene_symbol": "BRCA1"})
    assert len(results) == 1
    ev = results[0]
    assert ev.source_name == "ClinVar"
    assert ev.reliability == "high"
    assert ev.domain_metadata["match_score"] == 1.0
    assert ev.raw_record["title"] == "BRCA1 c.68_69del"


@respx.mock
def test_clinvar_search_returns_ranked_candidates():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["111", "222"]}})
    )

    def summary(request):
        uid = request.url.params.get("id")
        titles = {"111": "BRCA1 c.68_69del", "222": "BRCA1 other variant"}
        return httpx.Response(
            200,
            json={"result": {uid: {"title": titles[uid], "clinical_significance": "Pathogenic"}}},
        )

    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(side_effect=summary)

    conn = ClinVarConnector()
    results = conn.fetch({"gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"})
    assert len(results) >= 1
    assert results[0].domain_metadata["candidate_rank"] == 1
    assert "match_score" in results[0].domain_metadata


@respx.mock
def test_clinvar_ambiguous_lowers_reliability():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": ["111", "222"]}})
    )

    def summary(request):
        uid = request.url.params.get("id")
        titles = {"111": "BRCA1 c.68_69del", "222": "BRCA1 c.68_69del alt"}
        return httpx.Response(
            200,
            json={"result": {uid: {"title": titles[uid], "clinical_significance": "Pathogenic"}}},
        )

    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(side_effect=summary)

    conn = ClinVarConnector()
    results = conn.fetch({"gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"})
    top = results[0]
    if top.domain_metadata.get("retrieval_ambiguity"):
        assert top.reliability == "low"

@respx.mock
def test_clinvar_retries_rate_limit_without_discarding_evidence(monkeypatch: pytest.MonkeyPatch):
    delays: list[float] = []
    monkeypatch.setattr("vsa.connectors.clinvar.time.sleep", delays.append)
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "2"}),
            httpx.Response(
                200,
                json={"result": {"12345": {"title": "BRCA1 c.68_69del"}}},
            ),
        ]
    )
    endpoint = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi")
    endpoint.mock(side_effect=lambda request: next(responses))

    results = ClinVarConnector().fetch({"clinvar_id": "12345"})
    assert endpoint.call_count == 2
    assert any(delay >= 2 for delay in delays)
    assert results[0].raw_record["title"] == "BRCA1 c.68_69del"


@respx.mock
def test_clinvar_exhausted_rate_limit_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("vsa.connectors.clinvar.time.sleep", lambda _: None)
    endpoint = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi")
    endpoint.mock(return_value=httpx.Response(429))

    with pytest.raises(httpx.HTTPStatusError) as error:
        ClinVarConnector().fetch({"clinvar_id": "12345"})

    assert error.value.response.status_code == 429
    assert endpoint.call_count == 4

