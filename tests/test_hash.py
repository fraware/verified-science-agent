"""Provenance hashchain tests."""

from __future__ import annotations

from vsa.provenance.hashchain import build_provenance, hash_claim, stamp_report, verify_provenance_hashes


def test_same_input_same_hash(brca1_report):
    h1 = build_provenance(brca1_report)["report_hash"]
    h2 = build_provenance(brca1_report)["report_hash"]
    assert h1 == h2


def test_changed_claim_changes_hash(brca1_report):
    original = build_provenance(brca1_report)["report_hash"]
    brca1_report["claims"][0]["claim_text"] = "Modified claim text for hash test."
    modified = build_provenance(brca1_report)["report_hash"]
    assert original != modified


def test_provenance_verification(brca1_report):
    stamped = stamp_report(brca1_report)
    assert verify_provenance_hashes(stamped) == []


def test_claim_hash_stable(brca1_report):
    claim = brca1_report["claims"][0]
    assert hash_claim(claim) == hash_claim(dict(claim))
