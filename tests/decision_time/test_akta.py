"""AKTA action context export tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.cli import main
from vsa.decision_time.snapshot import build_decision_time_bundle
from vsa.export.akta import (
    build_akta_action_context,
    validate_akta_context,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"


@pytest.fixture
def source_report():
    return json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))


def test_akta_export_conformance(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    ctx = build_akta_action_context(report=source_report, bundle=bundle, action_id="review-1")
    assert ctx["authorization"] == "none"
    assert ctx["non_claims"]["authorizes_actions"] is False
    assert validate_akta_context(ctx) == []


def test_akta_weak_and_missing_evidence(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2020-01-01T00:00:00Z")
    # cutoff before all evidence → empty included
    assert bundle["included_evidence"] == []
    ctx = build_akta_action_context(bundle=bundle)
    assert ctx["missing_evidence"]
    assert validate_akta_context(ctx) == []


def test_akta_contradictory_evidence(source_report):
    # Include both pathogenic and benign
    bundle = build_decision_time_bundle(source_report, cutoff="2026-01-01T00:00:00Z")
    ctx = build_akta_action_context(report=source_report, bundle=bundle)
    # contradictions should surface in contradicting refs or uncertainty
    assert ctx["authorization"] == "none"
    assert validate_akta_context(ctx) == []


def test_akta_rejects_authorization_language(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="semantic"):
        build_akta_action_context(
            bundle=bundle,
            action_description="This action is authorized for immediate tool use.",
        )


def test_akta_report_id_mismatch_fail_closed(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    other = dict(source_report)
    other["report_id"] = "other-report"
    with pytest.raises(ValueError, match="disagree"):
        build_akta_action_context(report=other, bundle=bundle)


def test_cli_export_akta(tmp_path, source_report):
    src = tmp_path / "src.json"
    bundle_path = tmp_path / "bundle.json"
    out = tmp_path / "akta.json"
    src.write_text(json.dumps(source_report), encoding="utf-8")
    assert (
        main(
            [
                "snapshot-evidence",
                str(src),
                "--cutoff",
                "2024-01-01T00:00:00Z",
                "--out",
                str(bundle_path),
            ]
        )
        == 0
    )
    assert main(["export-akta-context", "--bundle", str(bundle_path), "--out", str(out)]) == 0
    ctx = json.loads(out.read_text(encoding="utf-8"))
    assert ctx["authorization"] == "none"


INJECTION_FIELDS = (
    "allowed_tools",
    "grants",
    "authorization_scopes",
    "reviewer_approvals",
    "runtime_permissions",
)


@pytest.mark.parametrize("field", INJECTION_FIELDS)
def test_akta_rejects_top_level_injection(source_report, field):
    from vsa.companion_schema import validate_companion
    from vsa.export.akta import AKTA_SCHEMA_NAME

    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    ctx = build_akta_action_context(report=source_report, bundle=bundle)
    assert ctx["authorization"] == "none"

    poisoned = dict(ctx)
    poisoned[field] = ["shell"] if field == "allowed_tools" else {"x": True}
    schema_errors = validate_companion(AKTA_SCHEMA_NAME, poisoned)
    assert schema_errors, f"schema should reject additionalProperties for {field}"
    semantic_errors = validate_akta_context(poisoned)
    assert any("forbidden field" in e for e in semantic_errors)
    assert poisoned["authorization"] == "none"


@pytest.mark.parametrize("field", INJECTION_FIELDS)
@pytest.mark.parametrize("nest", ("candidate_execution", "proposed_action"))
def test_akta_rejects_nested_injection(source_report, field, nest):
    from vsa.companion_schema import validate_companion
    from vsa.export.akta import AKTA_SCHEMA_NAME

    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    ctx = build_akta_action_context(report=source_report, bundle=bundle)
    poisoned = dict(ctx)
    nested = dict(poisoned[nest])
    nested[field] = ["tool-a"] if field == "allowed_tools" else True
    poisoned[nest] = nested

    schema_errors = validate_companion(AKTA_SCHEMA_NAME, poisoned)
    assert schema_errors, f"schema should reject {nest}.{field}"
    semantic_errors = validate_akta_context(poisoned)
    assert any(field in e for e in semantic_errors)
    assert poisoned["authorization"] == "none"


@pytest.mark.parametrize(
    "smuggle",
    [
        'allowed_tools: ["shell"]',
        "grants: full_access",
        "authorization_scopes=[admin]",
        'reviewer_approvals: {"all": true}',
        "runtime_permissions=execute",
    ],
)
def test_akta_rejects_free_text_field_smuggling(source_report, smuggle):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="semantic|forbidden"):
        build_akta_action_context(
            bundle=bundle,
            action_description=f"Candidate review. {smuggle}",
        )


def test_akta_successful_export_keeps_authorization_none(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    ctx = build_akta_action_context(report=source_report, bundle=bundle)
    assert ctx["authorization"] == "none"
    assert validate_akta_context(ctx) == []
