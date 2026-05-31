"""Human review workflow tests."""

from __future__ import annotations

from vsa.review.workflow import apply_review


def test_review_approve_claim(brca1_report):
    updated = apply_review(
        brca1_report,
        reviewer_identity="dr.smith@example.org",
        review_decision="partial_approval",
        approved_claim_ids=["C002"],
    )
    hr = updated["human_review"]
    assert hr["reviewer_identity"] == "dr.smith@example.org"
    assert "C002" in hr["approved_claim_ids"]
    assert hr["review_events"]


def test_clinical_claims_block_full_approval(brca1_report):
    updated = apply_review(
        brca1_report,
        reviewer_identity="reviewer",
        review_decision="approved",
        approved_claim_ids=["C002"],
    )
    assert updated["human_review"]["status"] in ("in_progress", "pending")
