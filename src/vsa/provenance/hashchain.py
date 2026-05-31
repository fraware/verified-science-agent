"""Provenance hashchain for ScientificReport artifacts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from vsa.utils import canonical_json
from vsa.version import RENDERER_VERSION, VALIDATION_VERSION


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def hash_evidence_bundle(evidence: list[dict[str, Any]]) -> str:
    ordered = sorted(evidence, key=lambda e: e.get("evidence_id", ""))
    return sha256_hex(canonical_json(ordered))


def hash_claim(claim: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(claim))


def hash_source_records(evidence: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(item["evidence_id"]): str(item["raw_record_hash"])
        for item in evidence
        if item.get("evidence_id") and item.get("raw_record_hash")
    }


def hash_review_chain(events: list[dict[str, Any]]) -> str:
    return sha256_hex(canonical_json(events))


def build_provenance(
    report: dict[str, Any],
    *,
    input_hash: str | None = None,
    cache_dir: str | None = None,
) -> dict[str, Any]:
    evidence = report.get("evidence", [])
    claims = report.get("claims", [])
    prev = report.get("provenance") or {}

    source_record_hashes = hash_source_records(evidence)
    evidence_bundle_hash = hash_evidence_bundle(evidence)
    claim_hashes = {str(c["claim_id"]): hash_claim(c) for c in claims if c.get("claim_id")}

    report_core = {
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
        "subject": report.get("subject"),
        "claims": claims,
        "evidence": evidence,
        "contradictions": report.get("contradictions", []),
        "human_review": report.get("human_review", {}),
    }
    report_hash = sha256_hex(canonical_json(report_core))

    generated_by = dict(prev.get("generated_by", {}))
    if not generated_by and report.get("provenance", {}).get("generated_by"):
        generated_by = dict(report["provenance"]["generated_by"])

    provenance: dict[str, Any] = {
        "source_record_hashes": source_record_hashes,
        "evidence_bundle_hash": evidence_bundle_hash,
        "claim_hashes": claim_hashes,
        "report_hash": report_hash,
        "validation_version": VALIDATION_VERSION,
        "renderer_version": RENDERER_VERSION,
        "generated_by": generated_by,
        "reproducibility": {
            "input_hash": input_hash or prev.get("reproducibility", {}).get("input_hash", ""),
            "cache_dir": cache_dir or prev.get("reproducibility", {}).get("cache_dir", ".vsa_cache"),
            "instructions": (
                "Re-run `vsa build <input.json> --out <report.json>` with the same input and "
                "connector cache to reproduce evidence retrieval and hashes."
            ),
        },
    }

    review_events = (report.get("human_review") or {}).get("review_events") or []
    if review_events:
        provenance["review_chain_hash"] = hash_review_chain(review_events)
        provenance["review_event_hash"] = hash_review_chain([review_events[-1]])

    if prev.get("signature"):
        provenance["signature"] = prev["signature"]

    return provenance


def verify_provenance_hashes(report: dict[str, Any]) -> list[str]:
    """Verify stored provenance hashes match recomputed values."""
    errors: list[str] = []
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        return ["provenance section missing or invalid"]

    evidence = report.get("evidence", [])
    claims = report.get("claims", [])

    expected_source = hash_source_records(evidence)
    if provenance.get("source_record_hashes") != expected_source:
        errors.append("provenance.source_record_hashes do not match evidence records")

    expected_bundle = hash_evidence_bundle(evidence)
    if provenance.get("evidence_bundle_hash") != expected_bundle:
        errors.append("provenance.evidence_bundle_hash does not match evidence bundle")

    expected_claims = {str(c["claim_id"]): hash_claim(c) for c in claims if c.get("claim_id")}
    if provenance.get("claim_hashes") != expected_claims:
        errors.append("provenance.claim_hashes do not match claims")

    report_core = {
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
        "subject": report.get("subject"),
        "claims": claims,
        "evidence": evidence,
        "contradictions": report.get("contradictions", []),
        "human_review": report.get("human_review", {}),
    }
    expected_report = sha256_hex(canonical_json(report_core))
    if provenance.get("report_hash") != expected_report:
        errors.append("provenance.report_hash does not match report content")

    review_events = (report.get("human_review") or {}).get("review_events") or []
    if review_events and provenance.get("review_chain_hash"):
        expected_chain = hash_review_chain(review_events)
        if provenance.get("review_chain_hash") != expected_chain:
            errors.append("provenance.review_chain_hash does not match review events")

    return errors


def stamp_report(report: dict[str, Any], *, input_hash: str | None = None) -> dict[str, Any]:
    """Attach or refresh provenance on a report, preserving review/signature metadata."""
    report = dict(report)
    cache_dir = report.get("provenance", {}).get("reproducibility", {}).get("cache_dir")
    report["provenance"] = build_provenance(report, input_hash=input_hash, cache_dir=cache_dir)
    return report


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
