"""Verify exported report artifact bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vsa.provenance.attestation import verify_attestation


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(bundle_dir: Path, *, verify_attestation_digest: bool = True) -> tuple[bool, list[str]]:
    """Verify manifest hashes, report provenance, and optional attestation."""
    errors: list[str] = []
    bundle_dir = Path(bundle_dir)

    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json not found"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts: dict[str, Any] = manifest.get("artifacts") or {}

    for name, meta in artifacts.items():
        if name == "manifest":
            continue
        rel = meta.get("path")
        expected_hash = meta.get("sha256")
        if not rel or not expected_hash:
            errors.append(f"artifact {name}: missing path or sha256 in manifest")
            continue
        artifact_path = bundle_dir / rel
        if not artifact_path.exists():
            errors.append(f"artifact {name}: missing file {rel}")
            continue
        actual = _sha256_file(artifact_path)
        if actual != expected_hash:
            errors.append(f"artifact {name}: sha256 mismatch (expected {expected_hash[:12]}…, got {actual[:12]}…)")

    report_path = bundle_dir / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest_hash = manifest.get("report_hash")
        report_hash = (report.get("provenance") or {}).get("report_hash")
        if manifest_hash and report_hash and manifest_hash != report_hash:
            errors.append("manifest report_hash does not match report.json provenance")
        if manifest.get("report_id") and report.get("report_id") != manifest.get("report_id"):
            errors.append("manifest report_id does not match report.json")

    if verify_attestation_digest:
        attestation_path = bundle_dir / "attestation.json"
        if attestation_path.exists() and report_path.exists():
            attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            ok, msg = verify_attestation(attestation, report, subject_name="report.json")
            if not ok:
                errors.append(f"attestation verification failed: {msg}")

    return not errors, errors
