"""Verify bundle tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.artifacts.export import export_report_bundle
from vsa.artifacts.verify import verify_bundle


def test_verify_bundle_passes(brca1_report, tmp_path: Path):
    export_report_bundle(brca1_report, tmp_path, audit_mode="rule")
    ok, errors = verify_bundle(tmp_path)
    assert ok, errors


def test_verify_bundle_fails_on_tamper(brca1_report, tmp_path: Path):
    export_report_bundle(brca1_report, tmp_path, audit_mode="rule")
    audit_path = tmp_path / "audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["overall_status"] = "tampered"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    ok, errors = verify_bundle(tmp_path)
    assert not ok
    assert any("sha256" in e.lower() for e in errors)
