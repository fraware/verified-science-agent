"""Export report artifacts (audit, provenance, review bundles)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vsa import __version__
from vsa.llm.verifier import AuditResult, audit_report
from vsa.provenance.attestation import build_slsa_attestation


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_audit_artifact(
    report: dict[str, Any],
    out_path: Path,
    *,
    mode: str = "auto",
    provider: str | None = None,
    model: str | None = None,
    result: AuditResult | None = None,
) -> dict[str, Any]:
    result = result or audit_report(report, mode=mode, provider=provider, model=model)
    payload = {
        "report_id": report.get("report_id"),
        "report_hash": (report.get("provenance") or {}).get("report_hash"),
        "audited_at": report.get("created_at"),
        **result.to_dict(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def export_report_bundle(
    report: dict[str, Any],
    out_dir: Path,
    *,
    audit_mode: str = "rule",
    include_attestation: bool = True,
) -> dict[str, str]:
    """Write report.json, audit.json, provenance.json, review.json, manifest.json to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["report"] = str(report_path)

    audit_path = out_dir / "audit.json"
    write_audit_artifact(report, audit_path, mode=audit_mode)
    paths["audit"] = str(audit_path)

    prov_path = out_dir / "provenance.json"
    prov_path.write_text(
        json.dumps(report.get("provenance", {}), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["provenance"] = str(prov_path)

    review_path = out_dir / "review.json"
    review_path.write_text(
        json.dumps(report.get("human_review", {}), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["review"] = str(review_path)

    if include_attestation:
        attestation_path = out_dir / "attestation.json"
        attestation = build_slsa_attestation(report, subject_name="report.json")
        attestation_path.write_text(json.dumps(attestation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths["attestation"] = str(attestation_path)

    manifest = {
        "bundle_version": "1.0.0",
        "generator": f"verified-science-agent/{__version__}",
        "report_id": report.get("report_id"),
        "report_hash": (report.get("provenance") or {}).get("report_hash"),
        "artifacts": {
            name: {"path": Path(path).name, "sha256": _sha256_file(Path(path))}
            for name, path in paths.items()
        },
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["manifest"] = str(manifest_path)

    return paths
