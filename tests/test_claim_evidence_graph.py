"""Claim–evidence graph field and validation tests."""

from __future__ import annotations

import copy

from vsa.claims.normalize import build_claim_evidence_graph, finalize_claims, supporting_ids
from vsa.pipeline.build import build_report
from vsa.schema import validate_schema
from vsa.validate.engine import validate_report


def test_built_claims_have_graph_fields(brca1_evidence):
    report = build_report(
        {"question": "BRCA1 c.68_69del"},
        offline_evidence=copy.deepcopy(brca1_evidence),
        claim_mode="rule",
    )
    assert report.get("claim_evidence_graph")
    for claim in report["claims"]:
        assert "claim_text_normalized" in claim
        assert "supporting_evidence_ids" in claim
        assert "contradicting_evidence_ids" in claim
        assert "inference_method" in claim
        assert "confidence_semantics" in claim
        assert "validation_result" in claim
        assert "reviewer_status" in claim
        assert "source_spans" in claim
        if claim["review_boundary"] != "unsupported":
            assert supporting_ids(claim)
    assert not validate_schema(report), validate_schema(report)


def test_dangling_supporting_evidence_fails(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["claims"][0]["supporting_evidence_ids"] = ["E_MISSING"]
    report["claims"][0]["evidence_ids"] = ["E_MISSING"]
    result = validate_report(report, verify_hashes=False)
    assert not result.passed
    assert any("missing evidence" in e.lower() or "dangling" in e.lower() or "unresolved" in e.lower() or "E_MISSING" in e for e in result.errors + [c.message for c in result.checks])


def test_out_of_scope_evidence_fails(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["evidence"][0]["domain_metadata"] = {
        **(report["evidence"][0].get("domain_metadata") or {}),
        "subject_key": "TOTALLY_DIFFERENT_SUBJECT",
    }
    result = validate_report(report, verify_hashes=False)
    assert not result.passed
    assert any("scope" in e.lower() for e in result.errors)


def test_unsupported_must_have_empty_support(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["claims"][0]["review_boundary"] = "unsupported"
    report["claims"][0]["supporting_evidence_ids"] = [report["evidence"][0]["evidence_id"]]
    report["claims"][0]["evidence_ids"] = [report["evidence"][0]["evidence_id"]]
    result = validate_report(report, verify_hashes=False)
    assert not result.passed


def test_finalize_migrates_legacy_evidence_ids(brca1_evidence):
    claims = finalize_claims(
        [
            {
                "claim_id": "C001",
                "claim_type": "observation",
                "claim_text": "Legacy claim text long enough.",
                "evidence_ids": ["E001"],
                "confidence": 0.5,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium",
            }
        ],
        brca1_evidence,
        inference_method="rule",
    )
    assert claims[0]["supporting_evidence_ids"] == ["E001"]
    assert claims[0]["claim_text_normalized"]
    graph = build_claim_evidence_graph({"claims": claims, "evidence": brca1_evidence})
    assert graph["edges"]
    assert graph["digest"]
