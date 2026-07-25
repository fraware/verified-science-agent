"""Adversarial / negative-path tests for decision-time hardening."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vsa.decision_time.cutoff import apply_cutoff_filter, evidence_effective_timestamp
from vsa.decision_time.pcs import verify_portable_refs
from vsa.decision_time.signing import sign_bundle, verify_bundle_signature
from vsa.decision_time.snapshot import build_decision_time_bundle, compute_bundle_hash
from vsa.decision_time.verify import verify_decision_time_bundle
from vsa.export.akta import build_akta_action_context
from vsa.outcome.links import build_outcome_link
from vsa.provenance.signing import generate_keypair

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"


@pytest.fixture
def source_report():
    return json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))


def test_cutoff_precedence_source_timestamp_wins(source_report):
    ev = source_report["evidence"][0]
    ev["source_timestamp"] = "2020-01-01T00:00:00Z"
    ev["published_at"] = "2025-01-01T00:00:00Z"
    ev["retrieved_at"] = "2025-06-01T00:00:00Z"
    effective, field = evidence_effective_timestamp(ev)
    assert field == "source_timestamp"
    assert effective is not None
    assert effective.year == 2020
    included, excluded, errors = apply_cutoff_filter(
        [ev], "2021-01-01T00:00:00Z", require_timestamps=True
    )
    assert not errors
    assert included and not excluded


def test_tampered_bundle_hash_fails(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    bundle["integrity"]["bundle_hash"] = "0" * 64
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(c["check_id"] == "bundle_hash" and c["status"] == "fail" for c in result.checks)


def test_mutated_included_evidence_fails_hash(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    bundle["included_evidence"][0]["summary"] = "tampered summary"
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(c["check_id"] == "bundle_hash" and c["status"] == "fail" for c in result.checks)


def test_missing_portable_refs_fail_closed(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    errs = verify_portable_refs(bundle["included_evidence"], None)
    assert errs
    bundle["portable_refs"] = []
    # Recompute hash so only portable_refs integrity fails (hash includes refs)
    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(c["check_id"] == "portable_refs" and c["status"] == "fail" for c in result.checks)


def test_non_claims_corruption_fails(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    bundle["non_claims"]["authorizes_actions"] = True
    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    # schema const:false and/or non_claims check
    assert any(
        c["check_id"] in ("non_claims", "schema") and c["status"] == "fail" for c in result.checks
    )


def test_forged_signature_fails(tmp_path, source_report):
    key_a = tmp_path / "key_a"
    key_b = tmp_path / "key_b"
    generate_keypair(str(key_a))
    generate_keypair(str(key_b))
    bundle = build_decision_time_bundle(
        source_report, cutoff="2024-01-01T00:00:00Z", sign=True, key_path=str(key_a)
    )
    # Replace signature with one from a different key over same hash
    forged = sign_bundle(copy.deepcopy(bundle), key_path=str(key_b))
    bundle["integrity"]["signature"] = forged["integrity"]["signature"]
    # Keep original public key claim but wrong signature bytes — or use forged fully
    ok, msg = verify_bundle_signature(bundle)
    # Fully replaced sig from key_b should still verify cryptographically...
    # So instead corrupt the signature bytes:
    sig = dict(bundle["integrity"]["signature"])
    sig["signature_b64"] = sig["signature_b64"][:-4] + "AAAA"
    bundle["integrity"]["signature"] = sig
    ok, msg = verify_bundle_signature(bundle)
    assert not ok
    result = verify_decision_time_bundle(bundle, require_signature=True)
    assert not result.passed


def test_signature_rejects_mutated_material(tmp_path, source_report):
    key = tmp_path / "key"
    generate_keypair(str(key))
    bundle = build_decision_time_bundle(
        source_report, cutoff="2024-01-01T00:00:00Z", sign=True, key_path=str(key)
    )
    bundle["claims"][0]["claim_text"] = "mutated after sign"
    ok, msg = verify_bundle_signature(bundle)
    assert not ok
    assert "mismatch" in msg.lower() or "invalid" in msg.lower()


def test_outcome_link_rejects_mutated_bundle(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    bundle["integrity"]["bundle_hash"] = "1" * 64
    with pytest.raises(ValueError, match="bundle_hash mismatch"):
        build_outcome_link(bundle, outcome_ref="outcome://x")


def test_akta_evidence_digest_mismatch_fail_closed(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    other = copy.deepcopy(source_report)
    other["evidence"][0]["raw_record_hash"] = "c" * 64
    with pytest.raises(ValueError, match="evidence digests disagree"):
        build_akta_action_context(report=other, bundle=bundle)


def test_akta_rejects_execution_allowed_language(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="semantic"):
        build_akta_action_context(
            bundle=bundle,
            action_description="Clearance to execute the tool pipeline now.",
        )


def test_unknown_bundle_schema_version_fail_closed(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    bundle["schema_version"] = "9.9.9"
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(c["check_id"] == "schema_version" and c["status"] == "fail" for c in result.checks)


def test_included_excluded_overlap_fail_closed(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    assert bundle["excluded_post_cutoff"]
    # Smuggle an excluded id into included (and rehash so only partition fails)
    smuggled = copy.deepcopy(source_report["evidence"][1])
    bundle["included_evidence"].append(smuggled)
    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)
    bundle["integrity"]["source_record_hashes"] = {
        e["evidence_id"]: e["raw_record_hash"] for e in bundle["included_evidence"]
    }
    from vsa.decision_time.pcs import build_portable_refs

    bundle["portable_refs"] = build_portable_refs(bundle["included_evidence"])
    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)
    result = verify_decision_time_bundle(bundle)
    assert not result.passed
    assert any(
        c["check_id"] == "evidence_id_partition" and c["status"] == "fail" for c in result.checks
    )


def test_duplicate_evidence_id_build_fail_closed(source_report):
    dup = copy.deepcopy(source_report["evidence"][0])
    source_report["evidence"].append(dup)
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")


def test_trusted_key_pin_rejects_untrusted(tmp_path, source_report):
    key_a = tmp_path / "key_a"
    key_b = tmp_path / "key_b"
    generate_keypair(str(key_a))
    info_b = generate_keypair(str(key_b))
    bundle = build_decision_time_bundle(
        source_report, cutoff="2024-01-01T00:00:00Z", sign=True, key_path=str(key_a)
    )
    pk_b = info_b["public_key_b64"]
    ok, msg = verify_bundle_signature(bundle, trusted_public_keys_b64=[pk_b])
    assert not ok
    assert "trusted" in msg.lower()
    result = verify_decision_time_bundle(bundle, trusted_public_keys_b64=[pk_b])
    assert not result.passed


def test_trusted_key_pin_accepts_matching(tmp_path, source_report):
    key = tmp_path / "key"
    info = generate_keypair(str(key))
    bundle = build_decision_time_bundle(
        source_report, cutoff="2024-01-01T00:00:00Z", sign=True, key_path=str(key)
    )
    result = verify_decision_time_bundle(bundle, trusted_public_keys_b64=[info["public_key_b64"]])
    assert result.passed


def test_privacy_metrics_reject_digest_keys(source_report):
    from vsa.decision_time.metrics import assert_privacy_safe_metrics

    bad = {
        "included_source_count": 1,
        "excluded_source_count": 0,
        "contradiction_severity_histogram": {"a" * 64: 1},
        "uncertainty_distribution": {},
    }
    errs = assert_privacy_safe_metrics(bad)
    assert errs


def test_missing_timestamp_all_modes_fail_closed(source_report):
    del source_report["evidence"][0]["retrieved_at"]
    del source_report["evidence"][0]["published_at"]
    for mode in ("retrospective", "shadow", "read_only"):
        with pytest.raises(ValueError, match="timestamp"):
            build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z", mode=mode)


def test_akta_rejects_forbidden_execution_class(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="execution"):
        build_akta_action_context(bundle=bundle, tool_or_execution_class="authorized")


def test_cli_compare_fail_on_verify(tmp_path, source_report):
    from vsa.cli import main

    src = tmp_path / "src.json"
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    src.write_text(json.dumps(source_report), encoding="utf-8")
    assert (
        main(
            ["snapshot-evidence", str(src), "--cutoff", "2024-01-01T00:00:00Z", "--out", str(good)]
        )
        == 0
    )
    bundle = json.loads(good.read_text(encoding="utf-8"))
    bundle["integrity"]["bundle_hash"] = "0" * 64
    bad.write_text(json.dumps(bundle), encoding="utf-8")
    assert main(["compare-cutoffs", str(good), str(bad)]) == 0
    assert main(["compare-cutoffs", str(good), str(bad), "--fail-on-verify"]) == 1


def test_cli_load_missing_file_exits_one():
    from vsa.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["verify-decision-time-bundle", "does-not-exist-dt-bundle.json"])
    assert exc.value.code == 1


def test_independent_reconstruction_matches_fixture(source_report):
    rebuilt = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    fixture = json.loads((EXAMPLES / "valid_pre_cutoff.json").read_text(encoding="utf-8"))
    assert rebuilt["integrity"]["bundle_hash"] == fixture["integrity"]["bundle_hash"]
    assert verify_decision_time_bundle(rebuilt).passed
