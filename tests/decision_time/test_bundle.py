"""Decision-time bundle cutoff, verify, compare, immutability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.cli import main
from vsa.decision_time.cutoff import apply_cutoff_filter
from vsa.decision_time.snapshot import build_decision_time_bundle, compute_bundle_hash
from vsa.decision_time.verify import compare_cutoffs, verify_decision_time_bundle

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"


@pytest.fixture
def source_report():
    return json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))


def test_cutoff_excludes_post_cutoff(source_report):
    included, excluded, errors = apply_cutoff_filter(
        source_report["evidence"], "2024-01-01T00:00:00Z", require_timestamps=True
    )
    assert not errors
    assert [e["evidence_id"] for e in included] == ["E001"]
    assert [e["evidence_id"] for e in excluded] == ["E002"]


def test_snapshot_digest_stability(source_report):
    a = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    b = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    assert a["integrity"]["bundle_hash"] == b["integrity"]["bundle_hash"]
    assert a["integrity"]["bundle_hash"] == compute_bundle_hash(a)


def test_no_invented_source_fields(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    orig = {e["evidence_id"]: e for e in source_report["evidence"]}
    for ev in bundle["included_evidence"]:
        src = orig[ev["evidence_id"]]
        assert ev["raw_record_hash"] == src["raw_record_hash"]
        assert ev["summary"] == src["summary"]
        assert ev["identifier"] == src["identifier"]


def test_claim_source_binding_under_cutoff(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    included_ids = {e["evidence_id"] for e in bundle["included_evidence"]}
    assert "E002" not in included_ids
    claim_ids = {c["claim_id"] for c in bundle["claims"]}
    assert "C001" in claim_ids
    assert "C002" not in claim_ids  # only supported by post-cutoff E002
    result = verify_decision_time_bundle(bundle)
    assert result.passed


def test_verify_valid_fixture():
    bundle = json.loads((EXAMPLES / "valid_pre_cutoff.json").read_text(encoding="utf-8"))
    assert verify_decision_time_bundle(bundle).passed


def test_verify_invalid_post_cutoff_included():
    bundle = json.loads(
        (EXAMPLES / "invalid_post_cutoff_included.json").read_text(encoding="utf-8")
    )
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(c["check_id"] == "cutoff_inclusion" and c["status"] == "fail" for c in result.checks)


def test_verify_invalid_missing_digest():
    bundle = json.loads((EXAMPLES / "invalid_missing_digest.json").read_text(encoding="utf-8"))
    result = verify_decision_time_bundle(bundle)
    assert not result.passed


def test_missing_digest_fail_closed(source_report):
    source_report["evidence"][0]["raw_record_hash"] = None
    with pytest.raises(ValueError, match="raw_record_hash"):
        build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")


def test_missing_timestamp_retrospective_fail(source_report):
    del source_report["evidence"][0]["retrieved_at"]
    del source_report["evidence"][0]["published_at"]
    with pytest.raises(ValueError, match="timestamp"):
        build_decision_time_bundle(
            source_report, cutoff="2024-01-01T00:00:00Z", mode="retrospective"
        )


def test_compare_cutoffs(source_report):
    early = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    late = build_decision_time_bundle(source_report, cutoff="2026-01-01T00:00:00Z")
    diff = compare_cutoffs(early, late)
    assert "E002" in diff["included_only_in_b"]
    assert diff["hash_match"] is False


def test_cli_snapshot_verify_compare(tmp_path, source_report):
    src = tmp_path / "src.json"
    out = tmp_path / "bundle.json"
    src.write_text(json.dumps(source_report), encoding="utf-8")
    assert (
        main(["snapshot-evidence", str(src), "--cutoff", "2024-01-01T00:00:00Z", "--out", str(out)])
        == 0
    )
    assert main(["verify-decision-time-bundle", str(out)]) == 0
    out2 = tmp_path / "bundle2.json"
    assert (
        main(
            ["snapshot-evidence", str(src), "--cutoff", "2026-01-01T00:00:00Z", "--out", str(out2)]
        )
        == 0
    )
    assert main(["compare-cutoffs", str(out), str(out2)]) == 0


def test_privacy_safe_metrics_shape_on_verify(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    result = verify_decision_time_bundle(bundle)
    assert any(
        c["check_id"] == "privacy_safe_metrics" and c["status"] == "pass" for c in result.checks
    )
    # Inject digest-like histogram key and rehash
    bundle["privacy_safe_metrics"]["contradiction_severity_histogram"]["a" * 64] = 1
    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(
        c["check_id"] == "privacy_safe_metrics" and c["status"] == "fail" for c in result.checks
    )
