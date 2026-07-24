"""JSON Schema loading for companion integration artifacts."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def companion_schema_path(name: str) -> Path:
    return Path(str(resources.files("vsa.schemas") / name))


def load_companion_schema(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(companion_schema_path(name).read_text(encoding="utf-8"))
    return data


def get_companion_validator(name: str) -> Draft202012Validator:
    schema = load_companion_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_companion(name: str, document: dict[str, Any]) -> list[str]:
    """Return JSON Schema validation errors (empty if valid)."""
    validator = get_companion_validator(name)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(document), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def schema_digest(name: str) -> str:
    from vsa.provenance.hashchain import sha256_hex

    return sha256_hex(companion_schema_path(name).read_text(encoding="utf-8"))
