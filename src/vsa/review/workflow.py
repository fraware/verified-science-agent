"""Human review workflow for claim-by-claim approval."""

from __future__ import annotations

from typing import Any

from vsa.provenance.hashchain import now_utc_iso, stamp_report


def apply_review(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    review_decision: str,
    approved_claim_ids: list[str] | None = None,
    required_corrections: list[str] | None = None,
    reject: bool = False,
    review_notes: str | None = None,
) -> dict[str, Any]:
    """Apply a human review event and update report metadata."""
    report = dict(report)
    claims = report.get("claims", [])
    valid_ids = {c["claim_id"] for c in claims}
    approved = [cid for cid in (approved_claim_ids or []) if cid in valid_ids]

    clinical_claims = {
        c["claim_id"]
        for c in claims
        if c.get("review_boundary") == "requires_clinical_review"
    }
    unapproved_clinical = clinical_claims - set(approved)

    if reject:
        status = "rejected"
    elif unapproved_clinical and review_decision == "approved":
        status = "in_progress"
        review_decision = "partial_approval"
    elif approved and len(approved) == len(claims):
        status = "approved"
    elif approved:
        status = "in_progress"
    else:
        status = "in_progress"

    event = {
        "timestamp": now_utc_iso(),
        "reviewer": reviewer_identity,
        "action": review_decision,
        "claim_ids": approved,
    }
    if review_notes:
        event["notes"] = review_notes

    hr = dict(report.get("human_review", {}))
    hr.update(
        {
            "required": True,
            "status": status,
            "reviewer_identity": reviewer_identity,
            "review_timestamp": now_utc_iso(),
            "review_decision": review_decision,
            "approved_claim_ids": approved,
            "required_corrections": required_corrections or hr.get("required_corrections", []),
        }
    )
    events = list(hr.get("review_events") or [])
    events.append(event)
    hr["review_events"] = events
    report["human_review"] = hr

    prov = dict(report.get("provenance", {}))
    prov.setdefault("generated_by", {})["human_reviewer"] = reviewer_identity
    prov["review_event_hash"] = _review_event_hash(event)
    report["provenance"] = prov

    report = stamp_report(report)
    return report


def _review_event_hash(event: dict[str, Any]) -> str:
    from vsa.provenance.hashchain import sha256_hex
    from vsa.utils import canonical_json

    return sha256_hex(canonical_json(event))
