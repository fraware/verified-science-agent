"""Export bundle tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.artifacts.export import export_report_bundle


def test_export_bundle_includes_manifest_and_attestation(brca1_report, tmp_path: Path):
    paths = export_report_bundle(brca1_report, tmp_path, audit_mode="rule")
    assert "manifest" in paths
    assert "attestation" in paths
    assert "report_md" in paths
    assert Path(paths["sources"]).exists()
    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
    assert manifest["bundle_version"] == "1.1.0"
    assert manifest.get("schema_version")
    assert manifest.get("validation_version")
    assert manifest.get("created_at")
    assert set(manifest["artifacts"]) >= {"report", "audit", "provenance", "review", "attestation", "report_md"}
