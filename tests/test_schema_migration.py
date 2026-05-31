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
    migrated = migrate_schema(report, target="1.2.0")
    assert migrated["schema_version"] == "1.2.0"
    assert migrated.get("domain") == "genomics"
