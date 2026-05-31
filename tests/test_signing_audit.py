"""Signing and audit tests."""

from __future__ import annotations

import json

from vsa.llm.verifier import audit_report
from vsa.provenance.hashchain import stamp_report
from vsa.provenance.signing import generate_keypair, sign_report, verify_signature
from vsa.review.workflow import apply_review
from vsa.schema import validate_schema


def test_audit_passes_good_report(brca1_report):
    result = audit_report(brca1_report)
    assert result.overall_status in ("passed", "partial", "review_required")


def test_sign_and_verify(tmp_path, brca1_report):
    key_path = tmp_path / "test.key"
    generate_keypair(str(key_path))
    signed = sign_report(brca1_report, key_path=str(key_path))
    ok, msg = verify_signature(signed)
    assert ok, msg


def test_review_preserves_chain_hash(brca1_report):
    reviewed = apply_review(
        brca1_report,
        reviewer_identity="test@example.org",
        review_decision="partial_approval",
        approved_claim_ids=["C002"],
        review_notes="Approved safe summary claim.",
    )
    reviewed = stamp_report(reviewed)
    assert reviewed["provenance"].get("review_chain_hash")
    errors = validate_schema(reviewed)
    assert not errors, errors
