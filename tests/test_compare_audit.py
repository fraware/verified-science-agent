"""Audit comparison tests."""

from __future__ import annotations

from vsa.compare_audit import compare_audits, format_compare_audits


def test_compare_audits_detects_status_change():
    a = {
        "overall_status": "passed",
        "report_hash": "abc",
        "claim_audits": [{"claim_id": "C001", "status": "supported"}],
    }
    b = {
        "overall_status": "partial",
        "report_hash": "abc",
        "claim_audits": [{"claim_id": "C001", "status": "needs_review"}],
    }
    diff = compare_audits(a, b)
    assert diff["overall_changed"] is True
    assert diff["status_changes"][0]["claim_id"] == "C001"
    text = format_compare_audits(diff)
    assert "C001" in text
