"""Pilot modes, privacy-safe metrics, outcome append links."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.cli import main
from vsa.decision_time.snapshot import build_decision_time_bundle, compute_bundle_hash
from vsa.outcome.links import build_outcome_link, write_outcome_link

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"


def test_retrospective_shadow_and_read_only_modes():
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    retro = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z", mode="retrospective")
    shadow = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z", mode="shadow")
    read_only = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z", mode="read_only")
    assert retro["mode"] == "retrospective"
    assert shadow["mode"] == "shadow"
    assert read_only["mode"] == "read_only"
    assert retro["non_claims"]["executes_tools"] is False
    assert read_only["non_claims"]["authorizes_actions"] is False


def test_privacy_safe_metrics_no_payloads():
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    bundle = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z")
    metrics = bundle["privacy_safe_metrics"]
    blob = json.dumps(metrics)
    assert (
        "aaaaaaaa" not in blob
    )  # no raw hashes as partner payload stand-in in metrics values beyond counts
    assert metrics["included_source_count"] == 1
    assert metrics["excluded_source_count"] == 1
    assert "contradiction_severity_histogram" in metrics


def test_outcome_link_does_not_mutate_bundle(tmp_path):
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    bundle = build_decision_time_bundle(source, cutoff="2024-01-01T00:00:00Z")
    before = compute_bundle_hash(bundle)
    before_bytes = json.dumps(bundle, sort_keys=True)
    link = build_outcome_link(bundle, outcome_ref="outcome://demo/1", link_kind="calibration")
    after = compute_bundle_hash(bundle)
    assert before == after
    assert json.dumps(bundle, sort_keys=True) == before_bytes
    assert link["bundle_hash"] == before
    assert link["non_claims"]["mutates_bundle"] is False

    out = tmp_path / "link.json"
    write_outcome_link(bundle, out, outcome_ref="outcome://demo/2")
    assert compute_bundle_hash(bundle) == before


def test_cli_link_outcome(tmp_path):
    source = json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))
    bundle_path = tmp_path / "bundle.json"
    link_path = tmp_path / "link.json"
    src = tmp_path / "src.json"
    src.write_text(json.dumps(source), encoding="utf-8")
    assert (
        main(
            [
                "snapshot-evidence",
                str(src),
                "--cutoff",
                "2024-01-01T00:00:00Z",
                "--out",
                str(bundle_path),
                "--mode",
                "shadow",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "link-outcome",
                str(bundle_path),
                "--outcome-ref",
                "outcome://pilot/1",
                "--out",
                str(link_path),
            ]
        )
        == 0
    )
    # Bundle file bytes unchanged vs re-hash
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert compute_bundle_hash(bundle) == bundle["integrity"]["bundle_hash"]
