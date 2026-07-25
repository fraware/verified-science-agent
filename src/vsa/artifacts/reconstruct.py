"""Reconstruct report hashes from retained SourceRecords + config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vsa.provenance.hashchain import stamp_report, verify_provenance_hashes
from vsa.provenance.source_record import SourceRecord


class ReconstructError(ValueError):
    """Raised when reconstruction cannot proceed from retained sources."""


def _load_source_artifacts(sources_dir: Path) -> list[dict[str, Any]]:
    if not sources_dir.is_dir():
        raise ReconstructError(f"sources directory missing: {sources_dir}")
    artifacts: list[dict[str, Any]] = []
    for path in sorted(sources_dir.glob("*.json")):
        artifacts.append(json.loads(path.read_text(encoding="utf-8")))
    if not artifacts:
        raise ReconstructError(f"no source artifacts in {sources_dir}")
    return artifacts


def _source_record_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    if "source_record" in artifact and isinstance(artifact["source_record"], dict):
        return artifact["source_record"]
    if "content_digest" in artifact and "connector" in artifact:
        return {k: v for k, v in artifact.items() if k not in ("raw_response", "evidence_view")}
    raise ReconstructError("source artifact missing source_record fields")


def assert_retained_for_rebuild(source_records: list[dict[str, Any]]) -> None:
    """Fail closed when any SourceRecord cannot support full rebuild."""
    for sr in source_records:
        retention = sr.get("raw_response_retention")
        if retention in ("digest_only", "unavailable"):
            raise ReconstructError(
                f"source {sr.get('source_id')!r} has retention={retention!r}; "
                "full rebuild requires raw_response_retention=retained"
            )
        SourceRecord.from_dict(sr)


def rebuild_evidence_from_sources(
    artifacts: list[dict[str, Any]],
    *,
    preferred_order: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rebuild evidence views from export source artifacts (authority = SourceRecord)."""
    by_eid: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if "evidence_view" not in artifact:
            continue
        sr = _source_record_from_artifact(artifact)
        view = artifact.get("evidence_view")
        if not isinstance(view, dict):
            raise ReconstructError(
                f"source {sr.get('source_id')!r} missing evidence_view required for rebuild"
            )
        if view.get("raw_record_hash") and view["raw_record_hash"] != sr["content_digest"]:
            raise ReconstructError(
                f"evidence_view digest mismatch for {sr.get('source_id')!r}"
            )
        rebuilt = dict(view)
        rebuilt["source_id"] = sr["source_id"]
        rebuilt["raw_record_hash"] = sr["content_digest"]
        rebuilt["retrieval_path"] = sr.get("canonical_url") or rebuilt.get("retrieval_path")
        rebuilt["source_name"] = sr.get("connector") or rebuilt.get("source_name")
        rebuilt["identifier"] = sr.get("accession") or rebuilt.get("identifier")
        rebuilt["retrieved_at"] = sr.get("retrieved_at") or rebuilt.get("retrieved_at")
        eid = str(rebuilt.get("evidence_id") or "")
        by_eid[eid] = rebuilt
    if not by_eid:
        raise ReconstructError("no evidence_view entries found in sources/")
    if preferred_order:
        ordered = [by_eid[eid] for eid in preferred_order if eid in by_eid]
        # append any extras
        seen = set(preferred_order)
        ordered.extend(v for k, v in by_eid.items() if k not in seen)
        return ordered
    return [by_eid[k] for k in sorted(by_eid)]


def reconstruct_report_from_bundle(
    bundle_dir: Path | str,
    *,
    require_retained: bool = True,
) -> dict[str, Any]:
    """Rebuild report evidence from retained sources and restamp provenance hashes.

    Fails if any SourceRecord used for rebuild is digest_only/unavailable when
    require_retained=True. Preserves claim/config sections from the stored report.
    """
    bundle_dir = Path(bundle_dir)
    report_path = bundle_dir / "report.json"
    if not report_path.exists():
        raise ReconstructError("report.json not found in bundle")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    artifacts = _load_source_artifacts(bundle_dir / "sources")
    artifact_records = [_source_record_from_artifact(a) for a in artifacts]

    if require_retained:
        # Only require retention on artifacts that carry evidence views
        rebuild_records = [
            _source_record_from_artifact(a) for a in artifacts if "evidence_view" in a
        ]
        assert_retained_for_rebuild(rebuild_records)
        # Also require raw_response present for honest retention
        for artifact in artifacts:
            if "evidence_view" not in artifact:
                continue
            sr = _source_record_from_artifact(artifact)
            if "raw_response" not in artifact:
                raise ReconstructError(
                    f"source {sr.get('source_id')!r} marked retained but raw_response missing"
                )
        evidence = rebuild_evidence_from_sources(
            artifacts,
            preferred_order=[
                str(e.get("evidence_id"))
                for e in (report.get("evidence") or [])
                if isinstance(e, dict) and e.get("evidence_id")
            ],
        )
        report = dict(report)
        report["evidence"] = evidence
        # Keep report source_records if present; otherwise use artifact records
        if not report.get("source_records"):
            report["source_records"] = artifact_records
    else:
        report = dict(report)
        if not report.get("source_records"):
            report["source_records"] = artifact_records

    return stamp_report(report)


def verify_reconstructed_hash(
    bundle_dir: Path | str,
    *,
    require_retained: bool = True,
) -> tuple[bool, str, list[str]]:
    """Reconstruct and compare report_hash to the bundle's stored report.

    Returns (ok, reconstructed_hash, errors).
    """
    bundle_dir = Path(bundle_dir)
    try:
        original = json.loads((bundle_dir / "report.json").read_text(encoding="utf-8"))
        reconstructed = reconstruct_report_from_bundle(
            bundle_dir, require_retained=require_retained
        )
    except ReconstructError as exc:
        return False, "", [str(exc)]

    expected = (original.get("provenance") or {}).get("report_hash")
    actual = (reconstructed.get("provenance") or {}).get("report_hash")
    errors: list[str] = []
    if expected != actual:
        errors.append(
            f"report_hash mismatch: stored={expected!r} reconstructed={actual!r}"
        )
    errors.extend(verify_provenance_hashes(reconstructed))
    return not errors, actual or "", errors
