"""Export report artifacts (audit, provenance, review bundles)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vsa import __version__
from vsa.llm.verifier import AuditResult, audit_report
from vsa.provenance.attestation import build_slsa_attestation
from vsa.provenance.hashchain import now_utc_iso
from vsa.render import render
from vsa.version import SCHEMA_VERSION, VALIDATION_VERSION


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_sources(report: dict[str, Any], sources_dir: Path) -> list[str]:
    sources_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for ev in report.get("evidence", []):
        eid = ev.get("evidence_id", "unknown")
        payload = {
            "evidence_id": eid,
            "source_name": ev.get("source_name"),
            "source_type": ev.get("source_type"),
            "identifier": ev.get("identifier"),
            "retrieval_path": ev.get("retrieval_path"),
            "retrieved_at": ev.get("retrieved_at"),
            "summary": ev.get("summary"),
            "domain_metadata": ev.get("domain_metadata"),
            "raw_record_hash": ev.get("raw_record_hash"),
            "reliability": ev.get("reliability"),
        }
        path = sources_dir / f"{eid}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(str(path))
    return written


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
    """Write canonical artifact bundle to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    created_at = now_utc_iso()

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["report"] = str(report_path)

    report_md_path = out_dir / "report.md"
    report_md_path.write_text(render(report, "markdown"), encoding="utf-8")
    paths["report_md"] = str(report_md_path)

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

    sources_dir = out_dir / "sources"
    source_files = _write_sources(report, sources_dir)
    if source_files:
        paths["sources"] = str(sources_dir)

    if include_attestation:
        attestation_path = out_dir / "attestation.json"
        attestation = build_slsa_attestation(report, subject_name="report.json")
        attestation_path.write_text(json.dumps(attestation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths["attestation"] = str(attestation_path)

    artifact_entries: dict[str, dict[str, str]] = {}
    for name, path in paths.items():
        p = Path(path)
        if p.is_dir():
            for child in sorted(p.glob("*.json")):
                key = f"sources/{child.name}"
                artifact_entries[key] = {"path": f"sources/{child.name}", "sha256": _sha256_file(child)}
        else:
            artifact_entries[name] = {"path": p.name, "sha256": _sha256_file(p)}

    manifest = {
        "bundle_version": "1.1.0",
        "created_at": created_at,
        "generator": f"verified-science-agent/{__version__}",
        "schema_version": SCHEMA_VERSION,
        "validation_version": VALIDATION_VERSION,
        "report_id": report.get("report_id"),
        "report_hash": (report.get("provenance") or {}).get("report_hash"),
        "artifacts": artifact_entries,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths["manifest"] = str(manifest_path)

    return paths
