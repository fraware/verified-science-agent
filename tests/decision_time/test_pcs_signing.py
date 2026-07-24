"""PCS-shaped portable refs and signed bundle verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.decision_time.pcs import verify_portable_refs
from vsa.decision_time.signing import verify_bundle_signature
from vsa.decision_time.snapshot import build_decision_time_bundle
from vsa.decision_time.verify import verify_decision_time_bundle
from vsa.provenance.signing import generate_keypair
from vsa.version import PCS_PORTABLE_REF_SCHEMA_ID

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "decision_time"
PCS_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "pcs"


@pytest.fixture
def source_report():
    return json.loads((EXAMPLES / "source_report.json").read_text(encoding="utf-8"))


def test_portable_refs_shape(source_report):
    bundle = build_decision_time_bundle(source_report, cutoff="2024-01-01T00:00:00Z")
    refs = bundle["portable_refs"]
    assert refs
    assert refs[0]["schema_id"] == PCS_PORTABLE_REF_SCHEMA_ID
    assert refs[0]["content_digest"] == source_report["evidence"][0]["raw_record_hash"]
    assert verify_portable_refs(bundle["included_evidence"], refs) == []


def test_signed_bundle_verify(tmp_path, source_report):
    key = tmp_path / "key"
    generate_keypair(str(key))
    bundle = build_decision_time_bundle(
        source_report, cutoff="2024-01-01T00:00:00Z", sign=True, key_path=str(key)
    )
    ok, msg = verify_bundle_signature(bundle)
    assert ok, msg
    result = verify_decision_time_bundle(bundle, require_signature=True)
    assert result.passed


def test_pcs_fixture_checksums():
    manifest = json.loads((PCS_FIXTURES / "CHECKSUMS.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        path = PCS_FIXTURES / name
        from vsa.provenance.hashchain import sha256_hex

        actual = sha256_hex(path.read_text(encoding="utf-8"))
        assert actual == expected, f"checksum mismatch for {name}"
