"""Validation engine tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.validate.contradictions import detect_contradictions
from vsa.validate.engine import validate_report

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_good_report_passes(brca1_report):
    result = validate_report(brca1_report)
    assert result.passed
    assert result.status in ("pass", "warn")


def test_unsupported_claim_fails():
    report = json.loads((EXAMPLES / "bad_unsupported_claim.json").read_text(encoding="utf-8"))
    result = validate_report(report, verify_hashes=False)
    assert not result.passed
    assert any("unsupported" in e.lower() for e in result.errors)


def test_missing_evidence_ref_fails():
    report = json.loads((EXAMPLES / "bad_missing_evidence_ref.json").read_text(encoding="utf-8"))
    result = validate_report(report, verify_hashes=False)
    assert not result.passed


def test_contradiction_detection():
    report = {
        "evidence": [
            {
                "evidence_id": "E1",
                "domain_metadata": {"clinical_significance": "pathogenic"},
                "summary": "pathogenic",
            },
            {
                "evidence_id": "E2",
                "domain_metadata": {"clinical_significance": "uncertain significance"},
                "summary": "VUS",
            },
        ],
        "claims": [{"claim_id": "C1", "evidence_ids": ["E1", "E2"]}],
    }
    conflicts = detect_contradictions(report)
    assert len(conflicts) >= 1
    assert conflicts[0]["severity"] == "high"


def test_confidence_bounds(brca1_report):
    brca1_report["claims"][0]["confidence"] = 1.5
    result = validate_report(brca1_report)
    assert not result.passed
