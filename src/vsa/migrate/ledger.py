"""Migrate legacy claim-ledger JSON to ScientificReport format."""

from __future__ import annotations

from typing import Any

from vsa.version import SCHEMA_VERSION


def is_ledger(data: dict[str, Any]) -> bool:
    return "ledger_id" in data and "claims" in data and "schema_version" not in data


def migrate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    """Convert claim-ledger format to ScientificReport (draft — requires rebuild for full provenance)."""
    evidence_registry: dict[str, dict[str, Any]] = {}
    claims_out: list[dict[str, Any]] = []

    for claim in ledger.get("claims", []):
        eids: list[str] = []
        for ev in claim.get("evidence", []):
            eid = ev.get("evidence_id", f"E{len(evidence_registry)+1:03d}")
            if eid not in evidence_registry:
                raw_hash = ev.get("raw_record_hash") or ("0" * 64)
                evidence_registry[eid] = {
                    "evidence_id": eid,
                    "source_name": ev.get("source_name", "unknown"),
                    "source_type": ev.get("source_type", "database"),
                    "identifier": ev.get("identifier", eid),
                    "retrieval_path": ev.get("retrieval_path", ""),
                    "retrieved_at": ev.get("accessed_at_utc", ev.get("retrieved_at", "1970-01-01T00:00:00Z")),
                    "summary": ev.get("quoted_or_structured_evidence", ev.get("summary", "")),
                    "raw_record_hash": raw_hash if len(str(raw_hash)) == 64 else "0" * 64,
                }
            eids.append(eid)

        boundary = "requires_domain_review"
        status = (claim.get("verification") or {}).get("status", "")
        if status == "unsupported":
            boundary = "unsupported"
        elif status == "human_review_required":
            boundary = "requires_clinical_review"

        claims_out.append(
            {
                "claim_id": claim.get("claim_id", f"C{len(claims_out)+1:03d}"),
                "claim_type": claim.get("claim_type", "observation"),
                "claim_text": claim.get("claim_text", ""),
                "evidence_ids": eids,
                "confidence": claim.get("confidence", 0.5),
                "review_boundary": boundary,
                "uncertainty_level": "medium",
                "support_level": claim.get("support_level", "medium"),
            }
        )

    subject = ledger.get("subject", {})
    if "display_name" not in subject:
        subject = {
            **subject,
            "display_name": subject.get("gene_symbol") or subject.get("entity_type") or "migrated-subject",
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": ledger.get("ledger_id", "migrated-report"),
        "created_at": ledger.get("created_at_utc", "1970-01-01T00:00:00Z"),
        "subject": subject,
        "claims": claims_out or [{"claim_id": "C001", "claim_text": "placeholder", "evidence_ids": [], "claim_type": "observation", "confidence": 0, "review_boundary": "unsupported", "uncertainty_level": "unknown"}],
        "evidence": list(evidence_registry.values()) or [],
        "methods": [{"method_id": "M000", "name": "ledger_migration", "version": "1.0.0"}],
        "provenance": {},
        "validation_results": {"status": "pending", "checks": []},
        "human_review": {"required": True, "status": "pending"},
        "generated_outputs": {"formats_available": ["json"]},
        "_migration_note": "Run vsa build or re-stamp to refresh provenance hashes",
    }
