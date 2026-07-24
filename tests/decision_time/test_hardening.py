"""Contradiction / uncertainty hardening for decision-time path."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.decision_time.snapshot import build_decision_time_bundle
from vsa.decision_time.verify import verify_decision_time_bundle
from vsa.validate.contradictions import detect_contradictions
from vsa.validate.decision_time_checks import run_decision_time_checks

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"


def test_high_quality_contradiction_elevated():
    report = {
        "evidence": [
            {
                "evidence_id": "E1",
                "domain_metadata": {"clinical_significance": "pathogenic"},
                "summary": "pathogenic",
                "quality_score": {"score": 0.95},
            },
            {
                "evidence_id": "E2",
                "domain_metadata": {"clinical_significance": "benign"},
                "summary": "benign",
                "quality_score": {"score": 0.95},
            },
        ],
        "claims": [{"claim_id": "C1", "evidence_ids": ["E1", "E2"]}],
    }
    conflicts = detect_contradictions(report)
    assert conflicts
    assert conflicts[0]["severity"] == "high"


def test_computational_to_experimental_extrapolation():
    report = {
        "evidence": [
            {
                "evidence_id": "E1",
                "source_name": "AlphaFold DB",
                "domain_metadata": {"structure_type": "predicted"},
                "summary": "predicted structure",
            }
        ],
        "claims": [
            {
                "claim_id": "C1",
                "claim_text": "The experimental structure confirms folding.",
                "evidence_ids": ["E1"],
            }
        ],
    }
    conflicts = detect_contradictions(report)
    assert any(
        "computational" in c["description"].lower() or "predicted" in c["description"].lower()
        for c in conflicts
    )
    assert any(c["severity"] == "high" for c in conflicts)


def test_entity_ambiguity_check():
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    source["evidence"][0]["domain_metadata"]["retrieval_ambiguity"] = True
    source["claims"][0]["confidence"] = 0.95
    # Drop post-cutoff evidence for simpler bundle
    source["evidence"] = [source["evidence"][0]]
    source["claims"] = [source["claims"][0]]
    bundle = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z")
    checks = {c.check_id: c for c in run_decision_time_checks(bundle)}
    assert checks["dt_entity_ambiguity"].status == "fail"


def test_uncertainty_preserved():
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    bundle = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z")
    assert "claim_uncertainty" in bundle["uncertainty"]
    result = verify_decision_time_bundle(bundle)
    assert any(
        c["check_id"] == "dt_uncertainty_preserved" and c["status"] == "pass" for c in result.checks
    )


def test_metadata_only_warning():
    report = {
        "report_id": "meta-1",
        "schema_version": "1.2.0",
        "subject": {"entity_type": "paper", "display_name": "meta"},
        "claims": [
            {
                "claim_id": "C1",
                "claim_type": "identity",
                "claim_text": "Paper exists",
                "evidence_ids": ["E1"],
                "confidence": 0.5,
                "review_boundary": "safe_summary",
                "uncertainty_level": "high",
                "support_level": "low",
            }
        ],
        "evidence": [
            {
                "evidence_id": "E1",
                "source_name": "Crossref",
                "source_type": "publication",
                "identifier": "10.0/test",
                "retrieval_path": "https://example.test/doi",
                "retrieved_at": "2023-01-01T00:00:00Z",
                "summary": "title only",
                "raw_record_hash": "abababababababababababababababababababababababababababababababab",
                "domain_metadata": {"content_level": "metadata"},
            }
        ],
        "provenance": {
            "report_hash": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
            "generated_by": {},
        },
        "limitations": [],
    }
    bundle = build_decision_time_bundle(report, cutoff="2024-01-01T00:00:00Z")
    checks = {c.check_id: c for c in run_decision_time_checks(bundle)}
    assert checks["dt_metadata_only"].status == "warn"
