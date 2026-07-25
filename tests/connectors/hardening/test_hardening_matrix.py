"""Per-connector offline hardening matrix (VSA-04)."""

from __future__ import annotations

import httpx
import pytest
import respx

from vsa.connectors.base import NormalizedEvidence
from vsa.connectors.cache import EvidenceCache
from vsa.connectors.dedup import dedupe_evidence_with_meta
from vsa.connectors.outcomes import (
    CONNECTOR_FAILURE,
    CONNECTOR_RATE_LIMITED,
    CONNECTOR_TIMEOUT,
    EMPTY_RESULT,
    MALFORMED_RESPONSE,
    SCHEMA_DRIFT,
    classify_exception,
    looks_schema_drifted,
)

from tests.connectors.hardening.harness import (
    CONNECTOR_SPECS,
    ConnectorSpec,
    assert_source_record,
    load_fixture,
    run_connector_via_retrieval,
)


@pytest.fixture(params=CONNECTOR_SPECS, ids=[s.key for s in CONNECTOR_SPECS])
def spec(request: pytest.FixtureRequest) -> ConnectorSpec:
    return request.param


@respx.mock
def test_fixture_offline_success(spec: ConnectorSpec, tmp_path, monkeypatch):
    body = load_fixture(spec.fixture_dir, "success.json")
    spec.mock_success(body)
    cache = EvidenceCache(tmp_path / "cache")
    if spec.name == "Materials Project":
        monkeypatch.setattr(
            "vsa.connectors.materials_project.materials_project_api_key", lambda: "test-key"
        )
    conn = spec.factory(cache)
    results = conn.fetch(spec.success_query)
    assert results, f"{spec.name}: expected NormalizedEvidence from success fixture"
    assert all(isinstance(r, NormalizedEvidence) for r in results)
    for item in results:
        assert_source_record(item, spec.success_query)
        assert item.raw_record is not None
        sr = item.to_source_record(spec.success_query)
        assert sr.raw_response_retention == "retained"
        assert sr.content_digest


@respx.mock
def test_schema_drift_warns_and_degrades(spec: ConnectorSpec, tmp_path, monkeypatch):
    body = load_fixture(spec.fixture_dir, "schema_drift.json")
    spec.mock_schema_drift(body)
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    joined = " ".join(result.warnings)
    # Must not be a silent empty success
    assert result.evidence or SCHEMA_DRIFT in joined or EMPTY_RESULT in joined
    if result.evidence:
        assert SCHEMA_DRIFT in joined or any(
            (e.get("domain_metadata") or {}).get("schema_drift") for e in result.evidence
        )
        assert result.retrieval_status in {"partial", "failed", "complete"}
        if any((e.get("domain_metadata") or {}).get("schema_drift") for e in result.evidence):
            assert result.retrieval_status == "partial"
            assert any(o.status == "schema_drift" for o in result.connector_outcomes)


@respx.mock
def test_malformed_response_not_empty_success(spec: ConnectorSpec, tmp_path, monkeypatch):
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, text="{not-json"))
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    joined = " ".join(result.warnings)
    assert MALFORMED_RESPONSE in joined or CONNECTOR_FAILURE in joined
    assert result.retrieval_status in {"partial", "failed"}
    # Failure must not look like clean empty evidence pass
    assert not (
        result.retrieval_status == "complete"
        and not result.evidence
        and not result.warnings
    )


@respx.mock
def test_timeout_distinct_warning(spec: ConnectorSpec, tmp_path, monkeypatch):
    respx.get(url__regex=r".*").mock(side_effect=httpx.TimeoutException("connect timeout"))
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    joined = " ".join(result.warnings)
    assert CONNECTOR_TIMEOUT in joined
    assert result.retrieval_status == "failed"
    assert not result.evidence


@respx.mock
def test_rate_limit_429_distinct_warning(spec: ConnectorSpec, tmp_path, monkeypatch):
    request = httpx.Request("GET", spec.mock_route_url)
    response = httpx.Response(429, request=request, text="rate limited")
    respx.get(url__regex=r".*").mock(
        side_effect=httpx.HTTPStatusError("429", request=request, response=response)
    )
    # Most connectors call raise_for_status; simulate via Response that raises
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(429, text="rate limited"))
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    joined = " ".join(result.warnings)
    assert CONNECTOR_RATE_LIMITED in joined
    assert result.retrieval_status == "failed"


@respx.mock
def test_empty_result_distinct_from_failure(spec: ConnectorSpec, tmp_path, monkeypatch):
    spec.mock_empty()
    result = run_connector_via_retrieval(
        spec, query=spec.empty_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    joined = " ".join(result.warnings)
    assert EMPTY_RESULT in joined
    assert CONNECTOR_FAILURE not in joined
    assert CONNECTOR_TIMEOUT not in joined
    assert result.retrieval_status == "partial"
    codes = {o.code for o in result.connector_outcomes}
    assert EMPTY_RESULT in codes


@respx.mock
def test_ambiguous_query_scored(spec: ConnectorSpec):
    if spec.ambiguous_setup is None:
        pytest.skip(f"{spec.name}: no ambiguous-query pattern")
    results = spec.ambiguous_setup()
    assert results
    top = results[0]
    meta = top.domain_metadata or {}
    assert meta.get("retrieval_ambiguity") or meta.get("gene_search_ambiguous")
    assert top.reliability == "low"


def test_duplicate_results_keep_dropped_provenance():
    a = NormalizedEvidence(
        source_name="OpenAlex",
        source_type="publication",
        identifier="W1",
        retrieval_path="https://openalex.org/W1",
        retrieved_at="2024-01-01T00:00:00Z",
        summary="Same paper",
        raw_record={"doi": "10.1/xyz", "title": "Same paper"},
        reliability="medium",
        domain_metadata={"doi": "10.1/xyz", "title": "Same paper", "year": 2020},
    )
    b = NormalizedEvidence(
        source_name="Crossref",
        source_type="publication",
        identifier="10.1/xyz",
        retrieval_path="https://doi.org/10.1/xyz",
        retrieved_at="2024-01-01T00:00:00Z",
        summary="Same paper",
        raw_record={"DOI": "10.1/xyz", "title": ["Same paper"]},
        reliability="high",
        domain_metadata={"doi": "10.1/xyz", "title": "Same paper", "year": 2020},
    )
    dedupe = dedupe_evidence_with_meta([a, b])
    assert len(dedupe.items) == 1
    assert dedupe.dropped_ids
    assert dedupe.dropped[0]["kept_id"]
    assert dedupe.dropped[0]["dropped_id"]


@respx.mock
def test_provenance_retention_on_success(spec: ConnectorSpec, tmp_path, monkeypatch):
    body = load_fixture(spec.fixture_dir, "success.json")
    spec.mock_success(body)
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    assert result.source_records
    for sr in result.source_records:
        assert sr.get("content_digest")
        assert sr.get("raw_response_retention") in {"retained", "digest_only", "unavailable"}
        assert sr.get("connector") == spec.name


@respx.mock
def test_explicit_degradation_visible_on_build_path(spec: ConnectorSpec, tmp_path, monkeypatch):
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(429, text="slow down"))
    result = run_connector_via_retrieval(
        spec, query=spec.success_query, cache=EvidenceCache(tmp_path / "cache"), monkeypatch=monkeypatch
    )
    assert result.retrieval_status in {"partial", "failed"}
    assert result.warnings
    assert any(
        CONNECTOR_RATE_LIMITED in w or CONNECTOR_FAILURE in w or "partial_retrieval" in w
        for w in result.warnings
    )


def test_classify_exception_codes():
    assert classify_exception(httpx.TimeoutException("t"))[1] == CONNECTOR_TIMEOUT
    req = httpx.Request("GET", "https://example.com")
    resp = httpx.Response(429, request=req)
    assert classify_exception(httpx.HTTPStatusError("x", request=req, response=resp))[1] == (
        CONNECTOR_RATE_LIMITED
    )
    assert looks_schema_drifted(
        NormalizedEvidence(
            source_name="OpenAlex",
            source_type="publication",
            identifier="",
            retrieval_path="x",
            retrieved_at="2024-01-01T00:00:00Z",
            summary="Unknown",
            raw_record={},
        )
    )


@respx.mock
def test_timeout_never_clean_empty_pass(tmp_path, monkeypatch):
    """Injected timeout must not produce clean empty-evidence pass without failure warning."""
    for spec in CONNECTOR_SPECS:
        respx.clear()
        respx.get(url__regex=r".*").mock(side_effect=httpx.TimeoutException("boom"))
        result = run_connector_via_retrieval(
            spec,
            query=spec.success_query,
            cache=EvidenceCache(tmp_path / spec.key),
            monkeypatch=monkeypatch,
        )
        assert CONNECTOR_TIMEOUT in " ".join(result.warnings)
        assert result.retrieval_status != "complete"
