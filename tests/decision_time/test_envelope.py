"""Tests for IntegrationEnvelope companion schema and builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.identity.envelope import build_envelope, validate_envelope
from vsa.version import ENVELOPE_SCHEMA_VERSION

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_envelope_from_1_0_report():
    report = json.loads((EXAMPLES / "tp53_report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0.0"
    env = build_envelope(report, cutoff="2024-01-01T00:00:00Z", candidate_action_id="act-1")
    assert env["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert env["evidence_report_id"] == report["report_id"]
    assert env["digests"]["report_hash"] == report["provenance"]["report_hash"]
    assert env["non_claims"]["authorizes_actions"] is False
    assert validate_envelope(env) == []


def test_envelope_round_trip_schema(brca1_report):
    env = build_envelope(brca1_report)
    assert validate_envelope(env) == []
    # Old report unchanged / still valid without envelope
    assert "integration_envelope" not in brca1_report


def test_envelope_fail_closed_unknown_version(brca1_report):
    env = build_envelope(brca1_report)
    env["schema_version"] = "9.9.9"
    errs = validate_envelope(env)
    assert errs
    assert "unsupported" in errs[0].lower() or "9.9.9" in errs[0]


def test_envelope_requires_report_id():
    with pytest.raises(ValueError, match="report_id"):
        build_envelope({"schema_version": "1.2.0", "claims": [], "evidence": []})
