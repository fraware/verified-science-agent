"""Human review workflow for claim-by-claim approval."""

from __future__ import annotations

from typing import Any

from vsa.provenance.hashchain import hash_review_chain, now_utc_iso, stamp_report


def _append_event(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    action: str,
    claim_ids: list[str] | None = None,
    notes: str | None = None,
    corrections: list[str] | None = None,
) -> dict[str, Any]:
    report = dict(report)
    hr = dict(report.get("human_review", {}))
    event: dict[str, Any] = {
        "timestamp": now_utc_iso(),
        "reviewer": reviewer_identity,
        "action": action,
        "claim_ids": claim_ids or [],
    }
    if notes:
        event["notes"] = notes
    if corrections:
        event["corrections"] = corrections

    events = list(hr.get("review_events") or [])
    events.append(event)
    hr["review_events"] = events
    hr["reviewer_identity"] = reviewer_identity
    hr["review_timestamp"] = event["timestamp"]
    hr["required"] = True
    report["human_review"] = hr

    prov = dict(report.get("provenance", {}))
    prov.setdefault("generated_by", {})["human_reviewer"] = reviewer_identity
    prov["review_event_hash"] = hash_review_chain([event])
    report["provenance"] = prov
    return report


def start_review(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    review_notes: str | None = None,
) -> dict[str, Any]:
    """Begin human review session for a report."""
    report = _append_event(
        report,
        reviewer_identity=reviewer_identity,
        action="start",
        notes=review_notes,
    )
    hr = dict(report["human_review"])
    hr.update(
        {
            "status": "in_progress",
            "review_decision": "in_progress",
            "approved_claim_ids": hr.get("approved_claim_ids") or [],
            "required_corrections": hr.get("required_corrections") or [],
        }
    )
    report["human_review"] = hr
    return stamp_report(report)


def approve_claims(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    claim_ids: list[str],
    review_notes: str | None = None,
) -> dict[str, Any]:
    """Approve one or more claims (merges with prior approvals)."""
    return apply_review(
        report,
        reviewer_identity=reviewer_identity,
        review_decision="partial_approval",
        approved_claim_ids=_merge_approved(report, claim_ids),
        review_notes=review_notes,
    )


def request_corrections(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    corrections: list[str],
    review_notes: str | None = None,
) -> dict[str, Any]:
    """Record required corrections without approving claims."""
    report = _append_event(
        report,
        reviewer_identity=reviewer_identity,
        action="request_corrections",
        corrections=corrections,
        notes=review_notes,
    )
    hr = dict(report["human_review"])
    existing = list(hr.get("required_corrections") or [])
    hr["required_corrections"] = existing + [c for c in corrections if c not in existing]
    hr["status"] = "needs_revision"
    hr["review_decision"] = "needs_revision"
    report["human_review"] = hr
    return stamp_report(report)


def reject_review(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    review_notes: str | None = None,
) -> dict[str, Any]:
    """Reject the report."""
    return apply_review(
        report,
        reviewer_identity=reviewer_identity,
        review_decision="rejected",
        approved_claim_ids=[],
        reject=True,
        review_notes=review_notes,
    )


def _merge_approved(report: dict[str, Any], claim_ids: list[str]) -> list[str]:
    claims = report.get("claims", [])
    valid = {c["claim_id"] for c in claims}
    existing = set((report.get("human_review") or {}).get("approved_claim_ids") or [])
    merged = existing | {cid for cid in claim_ids if cid in valid}
    return sorted(merged)


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
        action = "reject"
    elif unapproved_clinical and review_decision == "approved":
        status = "in_progress"
        review_decision = "partial_approval"
        action = "partial_approval"
    elif approved and len(approved) == len(claims):
        status = "approved"
        action = "approve"
    elif approved:
        status = "in_progress"
        action = "approve_claim"
    else:
        status = "in_progress"
        action = review_decision

    event = {
        "timestamp": now_utc_iso(),
        "reviewer": reviewer_identity,
        "action": action,
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
    prov["review_event_hash"] = hash_review_chain([event])
    report["provenance"] = prov

    report = stamp_report(report)
    return report


def verify_review_chain(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """Verify review event chain hashes in provenance."""
    from vsa.provenance.hashchain import verify_provenance_hashes

    errors = [e for e in verify_provenance_hashes(report) if "review" in e.lower()]
    events = (report.get("human_review") or {}).get("review_events") or []
    if events and not (report.get("provenance") or {}).get("review_chain_hash"):
        errors.append("review events present but provenance.review_chain_hash missing")
    return not errors, errors
