"""Schema migration tests."""

from __future__ import annotations

import copy

from vsa.migrate.schema import migrate_schema
from vsa.provenance.hashchain import stamp_report
from vsa.schema import validate_schema
from vsa.version import SCHEMA_VERSION


def _legacy_report(brca1_report):
    legacy = copy.deepcopy(brca1_report)
    legacy["schema_version"] = "1.0.0"
    for key in (
        "input_question",
        "domain",
        "retrieval_plan",
        "retrieval_warnings",
        "evidence_selection_method",
        "claim_generation_method",
        "review_policy",
        "limitations",
    ):
        legacy.pop(key, None)
    return legacy


def test_migrate_1_0_to_current(brca1_report):
    legacy = _legacy_report(brca1_report)
    migrated = migrate_schema(legacy, target=SCHEMA_VERSION)
    assert migrated["schema_version"] == SCHEMA_VERSION
    assert migrated.get("input_question")
    assert migrated.get("limitations")
    migrated = stamp_report(migrated)
    assert not validate_schema(migrated), validate_schema(migrated)


def test_migrate_1_1_to_1_2(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["schema_version"] = "1.1.0"
    report.pop("domain", None)
    report.pop("source_records", None)
    report.pop("claim_evidence_graph", None)
    for claim in report.get("claims") or []:
        for key in (
            "claim_text_normalized",
            "supporting_evidence_ids",
            "contradicting_evidence_ids",
            "source_spans",
            "inference_method",
            "confidence_semantics",
            "validation_result",
            "reviewer_status",
        ):
            claim.pop(key, None)
    migrated = migrate_schema(report, target="1.2.0")
    assert migrated["schema_version"] == "1.2.0"
    assert migrated.get("domain") == "genomics"


def test_migrate_1_2_to_1_3(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["schema_version"] = "1.2.0"
    report.pop("source_records", None)
    report.pop("claim_evidence_graph", None)
    for claim in report.get("claims") or []:
        for key in (
            "claim_text_normalized",
            "supporting_evidence_ids",
            "contradicting_evidence_ids",
            "source_spans",
            "inference_method",
            "confidence_semantics",
            "validation_result",
            "reviewer_status",
        ):
            claim.pop(key, None)
        # leave legacy evidence_ids
    migrated = migrate_schema(report, target="1.3.0")
    assert migrated["schema_version"] == "1.3.0"
    assert migrated.get("source_records")
    assert migrated["claims"][0].get("supporting_evidence_ids") is not None
    assert migrated.get("claim_evidence_graph")
