"""Benchmark task governance: schema validation and suite path helpers."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

VALID_SUITES = frozenset({"holdout", "dev"})
DEFAULT_SUITE = "holdout"
MIN_EVALUATION_TASKS = 50

FLAG_KEYS = (
    "ambiguity",
    "contradiction",
    "metadata_only",
    "source_substitution",
    "unavailable_source",
    "temporal_cutoff",
)


def task_schema_path() -> Path:
    return Path(resources.files("vsa.schemas") / "benchmark_task.schema.json")


def load_task_schema() -> dict[str, Any]:
    return json.loads(task_schema_path().read_text(encoding="utf-8"))


def get_task_validator() -> Draft202012Validator:
    schema = load_task_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_tasks_document(doc: dict[str, Any]) -> list[str]:
    """Return governance schema errors for a tasks.json document (empty if valid)."""
    validator = get_task_validator()
    errors: list[str] = []
    for error in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{path}: {error.message}")
    return errors


def validate_tasks_file(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return validate_tasks_document(doc)


def normalize_suite(suite: str | None) -> str:
    name = (suite or DEFAULT_SUITE).strip().lower()
    if name not in VALID_SUITES:
        raise ValueError(f"unknown benchmark suite {suite!r}; expected one of {sorted(VALID_SUITES)}")
    return name


def fixtures_dir_for_suite(benchmarks_dir: Path, suite: str | None = None) -> Path:
    return benchmarks_dir / "fixtures" / normalize_suite(suite)


def empty_flags() -> dict[str, bool]:
    return {k: False for k in FLAG_KEYS}


def flags_from_categories(categories: list[str]) -> dict[str, bool]:
    flags = empty_flags()
    cats = set(categories)
    if "ambiguity" in cats:
        flags["ambiguity"] = True
    if "contradiction" in cats:
        flags["contradiction"] = True
    if "metadata_only_paper" in cats:
        flags["metadata_only"] = True
    if "source_substitution" in cats:
        flags["source_substitution"] = True
    if "unavailable_source" in cats:
        flags["unavailable_source"] = True
    if "temporal_cutoff" in cats:
        flags["temporal_cutoff"] = True
    return flags


def governance_signal_text(report: dict[str, Any]) -> str:
    """Aggregate warning and provenance signals used by governance expect_* checks."""
    parts: list[str] = []
    for key in ("limitations", "retrieval_warnings"):
        for item in report.get(key) or []:
            parts.append(str(item))
    for sr in report.get("source_records") or []:
        if not isinstance(sr, dict):
            continue
        avail = str(sr.get("source_availability") or "")
        if avail == "substituted":
            parts.append("SOURCE_SUBSTITUTION")
        elif avail == "unavailable":
            parts.append("UNAVAILABLE_SOURCE")
        retention = str(sr.get("raw_response_retention") or "")
        if retention == "unavailable":
            parts.append("UNAVAILABLE_SOURCE")
    for ev in report.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        meta = ev.get("domain_metadata") or {}
        if not isinstance(meta, dict):
            continue
        avail = str(meta.get("source_availability") or "")
        if avail == "substituted" or meta.get("source_substituted"):
            parts.append("SOURCE_SUBSTITUTION")
        if avail == "unavailable" or meta.get("source_unavailable"):
            parts.append("UNAVAILABLE_SOURCE")
        if (
            meta.get("temporal_cutoff")
            or meta.get("post_cutoff")
            or meta.get("beyond_temporal_cutoff")
            or meta.get("temporal_cutoff_violation")
        ):
            parts.append("TEMPORAL_CUTOFF")
    return " ".join(parts).upper()
