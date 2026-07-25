"""Tamper-evident hash-linked review chain integrity tests (VSA-07)."""

from __future__ import annotations

import copy
import json

from vsa.cli import main
from vsa.provenance.hashchain import (
    REVIEW_CHAIN_GENESIS_DIGEST,
    digest_review_event,
)
from vsa.review.workflow import (
    approve_claims,
    start_review,
    verify_review_chain,
)


def _reviewed_report(brca1_report):
    started = start_review(brca1_report, reviewer_identity="alice@example.com")
    return approve_claims(
        started,
        reviewer_identity="alice@example.com",
        claim_ids=["C002"],
        review_notes="Looks consistent with evidence",
    )


def test_intact_chain_passes(brca1_report):
    report = _reviewed_report(brca1_report)
    events = report["human_review"]["review_events"]
    assert len(events) >= 2
    assert events[0]["prior_event_digest"] == REVIEW_CHAIN_GENESIS_DIGEST
    assert events[1]["prior_event_digest"] == digest_review_event(events[0])
    assert events[0]["unsigned_status"] == "unsigned"
    assert events[0]["decision"] == "start"
    assert "rationale" in events[1] or events[1].get("notes")
    ok, errors = verify_review_chain(report)
    assert ok, errors


def test_delete_event_fails(brca1_report):
    report = _reviewed_report(brca1_report)
    events = list(report["human_review"]["review_events"])
    assert len(events) >= 2
    del events[0]
    report = copy.deepcopy(report)
    report["human_review"]["review_events"] = events
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any("prior_event_digest" in e for e in errors)


def test_reorder_events_fails(brca1_report):
    report = _reviewed_report(brca1_report)
    events = list(report["human_review"]["review_events"])
    assert len(events) >= 2
    reordered = [events[1], events[0]] + events[2:]
    report = copy.deepcopy(report)
    report["human_review"]["review_events"] = reordered
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any("prior_event_digest" in e for e in errors)


def test_duplicate_event_fails(brca1_report):
    """Replaying an earlier event (exact bytes) breaks prior linking and/or uniqueness."""
    report = _reviewed_report(brca1_report)
    events = list(report["human_review"]["review_events"])
    assert len(events) >= 2
    # Insert a byte-identical copy of the first event after the second
    events = [events[0], events[1], copy.deepcopy(events[0])]
    report = copy.deepcopy(report)
    report["human_review"]["review_events"] = events
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any(
        "duplicate event digest" in e or "prior_event_digest" in e for e in errors
    )


def test_exact_duplicate_append_fails(brca1_report):
    """Appending an unmodified copy of the last event breaks prior link or uniqueness."""
    report = _reviewed_report(brca1_report)
    events = list(report["human_review"]["review_events"])
    events.append(copy.deepcopy(events[-1]))
    report = copy.deepcopy(report)
    report["human_review"]["review_events"] = events
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any(
        "duplicate event digest" in e or "prior_event_digest" in e for e in errors
    )


def test_reviewer_substitution_on_event_fails(brca1_report):
    report = _reviewed_report(brca1_report)
    report = copy.deepcopy(report)
    events = report["human_review"]["review_events"]
    events[-1]["reviewer_identity"] = "attacker@evil.example"
    events[-1]["reviewer"] = "attacker@evil.example"
    # Keep human_review.reviewer_identity as the original reviewer
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any(
        "substitution" in e or "review_chain_hash" in e for e in errors
    )


def test_reviewer_identity_header_substitution_fails(brca1_report):
    report = _reviewed_report(brca1_report)
    report = copy.deepcopy(report)
    report["human_review"]["reviewer_identity"] = "attacker@evil.example"
    ok, errors = verify_review_chain(report)
    assert not ok
    assert any("substitution" in e for e in errors)


def test_needs_revision_status_in_schema(brca1_report):
    from vsa.review.workflow import request_corrections
    from vsa.schema import load_schema
    import jsonschema

    updated = request_corrections(
        brca1_report,
        reviewer_identity="alice@example.com",
        corrections=["Clarify claim wording"],
    )
    assert updated["human_review"]["status"] == "needs_revision"
    schema = load_schema()
    status_enum = schema["$defs"]["HumanReview"]["properties"]["status"]["enum"]
    assert "needs_revision" in status_enum
    # Validate HumanReview with root $defs so ReviewEvent $ref resolves
    fragment_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema["$defs"],
        **schema["$defs"]["HumanReview"],
    }
    jsonschema.validate(updated["human_review"], fragment_schema)
    ok, errors = verify_review_chain(updated)
    assert ok, errors


def test_cli_review_verify_detects_tamper(tmp_path, brca1_report):
    report = _reviewed_report(brca1_report)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert main(["review", "verify", str(path)]) == 0

    tampered = copy.deepcopy(report)
    del tampered["human_review"]["review_events"][0]
    path.write_text(json.dumps(tampered), encoding="utf-8")
    assert main(["review", "verify", str(path)]) == 1
