"""JSON Schema loading and validation for ScientificReport artifacts."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from vsa.version import SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS


def schema_path() -> Path:
    return Path(resources.files("vsa.schemas") / "scientific_report.schema.json")


def load_schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def get_validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(report: dict[str, Any]) -> list[str]:
    """Return JSON Schema validation errors (empty if valid)."""
    validator = get_validator()
    errors: list[str] = []
    for error in sorted(validator.iter_errors(report), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def assert_schema_version(report: dict[str, Any]) -> list[str]:
    version = report.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        return [
            f"schema_version unsupported: {version!r}; "
            f"supported: {', '.join(SUPPORTED_SCHEMA_VERSIONS)}"
        ]
    return []
