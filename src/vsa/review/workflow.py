"""Human review workflow for claim-by-claim approval with hash-linked events."""

from __future__ import annotations

from typing import Any

from vsa.provenance.hashchain import (
    REVIEW_CHAIN_GENESIS_DIGEST,
    digest_review_event,
    hash_review_chain,
    now_utc_iso,
    stamp_report,
    verify_review_event_links,
)


def _event_identity(event: dict[str, Any]) -> str:
    return str(event.get("reviewer_identity") or event.get("reviewer") or "")


def _build_event(
    *,
    reviewer_identity: str,
    decision: str,
    claim_ids: list[str] | None = None,
    rationale: str | None = None,
    corrections: list[str] | None = None,
    prior_event_digest: str,
    signature: str | None = None,
) -> dict[str, Any]:
    """Build a hash-linkable review event (signed or explicitly unsigned)."""
    event: dict[str, Any] = {
        "timestamp": now_utc_iso(),
        "reviewer_identity": reviewer_identity,
        "reviewer": reviewer_identity,  # legacy alias
        "decision": decision,
        "action": decision,  # legacy alias
        "claim_ids": list(claim_ids or []),
        "prior_event_digest": prior_event_digest,
    }
    if rationale:
        event["rationale"] = rationale
        event["notes"] = rationale  # legacy alias
    if corrections:
        event["corrections"] = corrections
    if signature:
        event["signature"] = signature
    else:
        event["unsigned_status"] = "unsigned"
    return event


def _prior_digest(events: list[dict[str, Any]]) -> str:
    if not events:
        return REVIEW_CHAIN_GENESIS_DIGEST
    return digest_review_event(events[-1])


def _append_event(
    report: dict[str, Any],
    *,
    reviewer_identity: str,
    action: str,
    claim_ids: list[str] | None = None,
    notes: str | None = None,
    corrections: list[str] | None = None,
    signature: str | None = None,
) -> dict[str, Any]:
    report = dict(report)
    hr = dict(report.get("human_review", {}))
    events = list(hr.get("review_events") or [])
    event = _build_event(
        reviewer_identity=reviewer_identity,
        decision=action,
        claim_ids=claim_ids,
        rationale=notes,
        corrections=corrections,
        prior_event_digest=_prior_digest(events),
        signature=signature,
    )
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
    signature: str | None = None,
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

    hr = dict(report.get("human_review", {}))
    events = list(hr.get("review_events") or [])
    event = _build_event(
        reviewer_identity=reviewer_identity,
        decision=action,
        claim_ids=approved,
        rationale=review_notes,
        prior_event_digest=_prior_digest(events),
        signature=signature,
    )
    events.append(event)

    hr.update(
        {
            "required": True,
            "status": status,
            "reviewer_identity": reviewer_identity,
            "review_timestamp": event["timestamp"],
            "review_decision": review_decision,
            "approved_claim_ids": approved,
            "required_corrections": required_corrections or hr.get("required_corrections", []),
            "review_events": events,
        }
    )
    report["human_review"] = hr

    prov = dict(report.get("provenance", {}))
    prov.setdefault("generated_by", {})["human_reviewer"] = reviewer_identity
    prov["review_event_hash"] = hash_review_chain([event])
    report["provenance"] = prov

    return stamp_report(report)


def verify_review_chain(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """Verify review event chain hashes and hash-linked integrity."""
    errors: list[str] = []
    provenance = report.get("provenance") or {}
    events = list((report.get("human_review") or {}).get("review_events") or [])

    if events and not provenance.get("review_chain_hash"):
        errors.append("review events present but provenance.review_chain_hash missing")
    elif events and provenance.get("review_chain_hash"):
        expected_chain = hash_review_chain(events)
        if provenance.get("review_chain_hash") != expected_chain:
            errors.append("provenance.review_chain_hash does not match review events")

    errors.extend(verify_review_event_links(events))

    hr = report.get("human_review") or {}
    if events:
        last_identity = _event_identity(events[-1])
        hr_identity = hr.get("reviewer_identity")
        if hr_identity and last_identity and hr_identity != last_identity:
            errors.append(
                "human_review.reviewer_identity does not match latest review event "
                "(reviewer substitution without new event)"
            )

    return not errors, errors
