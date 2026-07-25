"""Focused tests for benchmark governance (VSA-05)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.benchmark.governance import (
    DEFAULT_SUITE,
    MIN_EVALUATION_TASKS,
    fixtures_dir_for_suite,
    flags_from_categories,
    governance_signal_text,
    validate_tasks_document,
    validate_tasks_file,
)
from vsa.benchmark.runner import REQUIRED_CATEGORY_MINIMUMS, category_coverage, score_task

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "benchmarks" / "tasks.json"
HOLDOUT = ROOT / "benchmarks" / "fixtures" / "holdout"
DEV = ROOT / "benchmarks" / "fixtures" / "dev"


def test_tasks_json_validates_against_governance_schema():
    errors = validate_tasks_file(TASKS_PATH)
    assert not errors, errors[:5]


def test_required_governance_fields_present_on_every_task():
    doc = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    required = ("provenance", "license", "expected_outputs", "scoring_rationale", "domain", "flags")
    flag_keys = (
        "ambiguity",
        "contradiction",
        "metadata_only",
        "source_substitution",
        "unavailable_source",
        "temporal_cutoff",
    )
    for task in doc["tasks"]:
        for key in required:
            assert key in task, f"{task['task_id']} missing {key}"
        for fk in flag_keys:
            assert fk in task["flags"], f"{task['task_id']} missing flag {fk}"
        assert task["provenance"].get("origin")
        assert task["provenance"].get("curator")
        assert task["provenance"].get("date")
        assert task["expected_outputs"].get("summary")
        assert task["scoring_rationale"]


def test_category_minima_include_new_governance_categories():
    for name in ("source_substitution", "unavailable_source", "temporal_cutoff"):
        assert name in REQUIRED_CATEGORY_MINIMUMS
        assert REQUIRED_CATEGORY_MINIMUMS[name] >= 5


def test_holdout_suite_meets_minima_and_floor():
    doc = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    tasks = doc["tasks"]
    assert len(tasks) >= MIN_EVALUATION_TASKS
    coverage = category_coverage(tasks)
    for name, minimum in REQUIRED_CATEGORY_MINIMUMS.items():
        assert coverage.get(name, 0) >= minimum, f"{name}: {coverage.get(name, 0)} < {minimum}"


def test_default_suite_is_holdout():
    assert DEFAULT_SUITE == "holdout"
    assert fixtures_dir_for_suite(ROOT / "benchmarks") == HOLDOUT
    assert fixtures_dir_for_suite(ROOT / "benchmarks", "dev") == DEV


def test_holdout_and_dev_fixture_trees_exist():
    assert HOLDOUT.is_dir()
    assert DEV.is_dir()
    assert (HOLDOUT / "brca1_variant_evidence.json").exists()
    assert (DEV / "brca1_variant_evidence.json").exists()
    for stem in (
        "source_substitution_1_evidence",
        "unavailable_source_1_evidence",
        "temporal_cutoff_1_evidence",
    ):
        assert (HOLDOUT / f"{stem}.json").exists()


def test_governance_signal_text_from_evidence_metadata():
    report = {
        "limitations": [],
        "retrieval_warnings": [],
        "source_records": [{"source_availability": "substituted"}],
        "evidence": [
            {"domain_metadata": {"source_unavailable": True}},
            {"domain_metadata": {"post_cutoff": True}},
        ],
    }
    text = governance_signal_text(report)
    assert "SUBSTITUT" in text
    assert "UNAVAILABLE" in text
    assert "TEMPORAL_CUTOFF" in text


def test_flags_from_categories():
    flags = flags_from_categories(["ambiguity", "source_substitution", "temporal_cutoff"])
    assert flags["ambiguity"] is True
    assert flags["source_substitution"] is True
    assert flags["temporal_cutoff"] is True
    assert flags["unavailable_source"] is False


@pytest.mark.parametrize(
    "task_id,expect_key",
    [
        ("source_substitution_1", "expect_source_substitution"),
        ("unavailable_source_1", "expect_unavailable_source"),
        ("temporal_cutoff_1", "expect_temporal_cutoff"),
    ],
)
def test_new_category_tasks_score_on_holdout(task_id: str, expect_key: str):
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))["tasks"]
    task = next(t for t in tasks if t["task_id"] == task_id)
    assert task.get(expect_key) is True
    result = score_task(task, fixtures_dir=HOLDOUT)
    assert result["passed"], result


def test_invalid_tasks_document_fails_governance_schema():
    errors = validate_tasks_document({"tasks": [{"task_id": "x"}]})
    assert errors


def test_conftest_holdout_guard_rejects_holdout_path():
    from tests.conftest import assert_not_holdout_fixture

    with pytest.raises(RuntimeError, match="Holdout fixture import forbidden"):
        assert_not_holdout_fixture(HOLDOUT / "brca1_variant_evidence.json")
    assert_not_holdout_fixture(DEV / "brca1_variant_evidence.json")
