"""PCS-shaped portable evidence references (adapter only; does not redefine PCS core)."""

from __future__ import annotations

from typing import Any

from vsa.version import PCS_PORTABLE_REF_SCHEMA_ID


def build_portable_refs(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Emit PCS-shaped refs from existing evidence digests.

    Shape: content_digest, media_type, producer, retrieved_at, schema_id.
    Reuses raw_record_hash; does not invent a second hash kernel.
    """
    refs: list[dict[str, Any]] = []
    for item in evidence:
        digest = item.get("raw_record_hash")
        if not digest:
            continue
        refs.append(
            {
                "content_digest": str(digest),
                "media_type": "application/json",
                "producer": str(item.get("source_name") or "unknown"),
                "retrieved_at": str(item.get("retrieved_at") or ""),
                "schema_id": PCS_PORTABLE_REF_SCHEMA_ID,
                "evidence_id": item.get("evidence_id"),
            }
        )
    return refs


def verify_portable_refs(
    evidence: list[dict[str, Any]],
    portable_refs: list[dict[str, Any]] | None,
) -> list[str]:
    """Verify portable refs match included evidence digests.

    Fail closed when included evidence has digests but refs are missing/empty.
    """
    by_id = {
        str(e["evidence_id"]): e
        for e in evidence
        if e.get("evidence_id") and e.get("raw_record_hash")
    }
    if by_id and not portable_refs:
        return ["portable_refs missing or empty while included evidence has digests (fail closed)"]
    if portable_refs is None:
        return []
    errors: list[str] = []
    for ref in portable_refs:
        eid = ref.get("evidence_id")
        digest = ref.get("content_digest")
        if not digest:
            errors.append("portable ref missing content_digest")
            continue
        if ref.get("schema_id") != PCS_PORTABLE_REF_SCHEMA_ID:
            errors.append(f"portable ref schema_id mismatch for {eid or digest}")
        if eid and eid in by_id:
            expected = by_id[eid].get("raw_record_hash")
            if expected != digest:
                errors.append(f"portable ref digest mismatch for {eid}")
        elif eid and eid not in by_id:
            errors.append(f"portable ref evidence_id not in included evidence: {eid}")
    # Every included evidence with a hash should have a ref when refs are present
    ref_ids = {r.get("evidence_id") for r in portable_refs if r.get("evidence_id")}
    for eid, ev in by_id.items():
        if eid not in ref_ids:
            errors.append(f"included evidence missing portable ref: {eid}")
        else:
            matching = [r for r in portable_refs if r.get("evidence_id") == eid]
            if matching and matching[0].get("content_digest") != ev.get("raw_record_hash"):
                errors.append(f"portable ref content_digest != raw_record_hash for {eid}")
    return errors
