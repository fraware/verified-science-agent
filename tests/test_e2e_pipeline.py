"""End-to-end pipeline: build → validate → audit → attest → export."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.artifacts.export import export_report_bundle
from vsa.llm.verifier import audit_report
from vsa.pipeline.build import build_report
from vsa.provenance.attestation import build_slsa_attestation, verify_attestation
from vsa.validate.engine import validate_report


def test_e2e_pipeline_offline(tmp_path: Path):
    fixture = Path("benchmarks/fixtures/brca1_variant_evidence.json")
    evidence = json.loads(fixture.read_text(encoding="utf-8"))
    report = build_report(
        {"question": "BRCA1 c.68_69del", "evidence": evidence},
        offline_evidence=evidence,
        claim_mode="rule",
    )
    validation = validate_report(report)
    assert validation.passed

    audit = audit_report(report, mode="rule")
    assert audit.overall_status in ("passed", "partial")

    attestation = build_slsa_attestation(report, subject_name="report.json")
    ok, msg = verify_attestation(attestation, report, subject_name="report.json")
    assert ok, msg

    out_dir = tmp_path / "bundle"
    paths = export_report_bundle(report, out_dir, audit_mode="rule")
    assert Path(paths["manifest"]).exists()
    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
    assert manifest["report_id"] == report["report_id"]
