"""Schema validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.schema import assert_schema_version, get_validator, load_schema, validate_schema

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_schema_loads():
    schema = load_schema()
    assert schema["title"] == "ScientificReport"
    assert schema["properties"]["schema_version"]["pattern"]


def test_validator_accepts_built_report(brca1_report):
    errors = validate_schema(brca1_report)
    assert errors == [], errors


def test_schema_version_check(brca1_report):
    assert assert_schema_version(brca1_report) == []


def test_bad_examples_fail_schema_or_validation():
    bad_files = list(EXAMPLES.glob("bad_*.json"))
    assert bad_files, "expected bad example files"
    for path in bad_files:
        report = json.loads(path.read_text(encoding="utf-8"))
        # Bad examples may pass schema but must fail semantic validation
        from vsa.validate.engine import validate_report

        result = validate_report(report, verify_hashes=False)
        assert not result.passed, f"{path.name} should fail validation"
