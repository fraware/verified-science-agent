"""Review workflow and CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.cli import main
from vsa.review.workflow import (
    approve_claims,
    reject_review,
    request_corrections,
    start_review,
    verify_review_chain,
)


def test_start_and_approve_claim(brca1_report):
    started = start_review(brca1_report, reviewer_identity="reviewer@example.com")
    assert started["human_review"]["status"] == "in_progress"
    assert started["human_review"]["review_events"][-1]["action"] == "start"

    approved = approve_claims(
        started,
        reviewer_identity="reviewer@example.com",
        claim_ids=["C002"],
    )
    assert "C002" in approved["human_review"]["approved_claim_ids"]
    ok, errors = verify_review_chain(approved)
    assert ok, errors


def test_request_corrections(brca1_report):
    updated = request_corrections(
        brca1_report,
        reviewer_identity="reviewer@example.com",
        corrections=["Fix clinical wording on C003"],
    )
    assert updated["human_review"]["status"] == "needs_revision"
    assert "Fix clinical wording on C003" in updated["human_review"]["required_corrections"]


def test_reject_review(brca1_report):
    updated = reject_review(brca1_report, reviewer_identity="reviewer@example.com")
    assert updated["human_review"]["status"] == "rejected"


def test_review_cli_legacy(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    out = tmp_path / "reviewed.json"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    code = main(
        [
            "review",
            str(path),
            "--reviewer",
            "reviewer@example.com",
            "--approve",
            "C002",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    reviewed = json.loads(out.read_text(encoding="utf-8"))
    assert "C002" in reviewed["human_review"]["approved_claim_ids"]


def test_review_subcommand_approve_claim(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    out = tmp_path / "reviewed.json"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    main(["review", "start", str(path), "--reviewer", "reviewer@example.com", "--out", str(path)])
    code = main(
        [
            "review",
            "approve-claim",
            str(path),
            "--reviewer",
            "reviewer@example.com",
            "--claim",
            "C001",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    reviewed = json.loads(out.read_text(encoding="utf-8"))
    assert "C001" in reviewed["human_review"]["approved_claim_ids"]
    assert main(["review", "verify", str(out)]) == 0
