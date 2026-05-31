"""Benchmark runner for evidence coverage and claim validity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vsa.pipeline.build import build_report
from vsa.pipeline.retrieval import retrieve_evidence_with_meta
from vsa.validate.engine import validate_report


def _benchmarks_dir() -> Path:
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = base / "benchmarks"
        if (candidate / "tasks.json").exists():
            return candidate
    return Path.cwd() / "benchmarks"


def _load_offline_evidence(task_id: str, fixtures_dir: Path) -> list[dict[str, Any]] | None:
    path = fixtures_dir / f"{task_id}_evidence.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def score_task(
    task: dict[str, Any],
    *,
    offline: bool = True,
    cache_dir: str = ".vsa_cache",
    fixtures_dir: Path | None = None,
) -> dict[str, Any]:
    from vsa.connectors.cache import EvidenceCache
    from vsa.pipeline.subject_parser import parse_question

    fixtures_dir = fixtures_dir or _benchmarks_dir() / "fixtures"
    subject = parse_question(task["input_question"])
    evidence: list[dict[str, Any]] | None = None
    warnings: list[str] = []

    if offline:
        evidence = _load_offline_evidence(task["task_id"], fixtures_dir)
        if evidence is None:
            return {
                "task_id": task["task_id"],
                "passed": False,
                "reason": "no offline fixture",
                "scores": {},
            }
    else:
        result = retrieve_evidence_with_meta(subject, cache=EvidenceCache(cache_dir))
        evidence = result.evidence
        warnings = result.warnings
        if not evidence:
            return {
                "task_id": task["task_id"],
                "passed": False,
                "reason": "live retrieval returned no evidence",
                "warnings": warnings,
                "scores": {},
            }

    report = build_report(
        {"question": task["input_question"], "evidence": evidence or []},
        offline_evidence=evidence,
        cache_dir=cache_dir,
        claim_mode="rule",
    )
    validation = validate_report(report)

    sources = {e.get("source_name") for e in report.get("evidence", [])}
    claim_types = {c.get("claim_type") for c in report.get("claims", [])}
    boundaries = {c.get("review_boundary") for c in report.get("claims", [])}

    expected_sources = set(task.get("expected_evidence_sources", []))
    expected_types = set(task.get("expected_claim_types", []))
    expected_flags = set(task.get("required_review_flags", []))

    source_coverage = len(sources & expected_sources) / max(len(expected_sources), 1)
    type_coverage = len(claim_types & expected_types) / max(len(expected_types), 1)
    flag_coverage = len(boundaries & expected_flags) / max(len(expected_flags), 1)
    validity = 1.0 if validation.passed else 0.0

    overall = (source_coverage + type_coverage + flag_coverage + validity) / 4

    return {
        "task_id": task["task_id"],
        "passed": overall >= 0.75 and validation.passed,
        "mode": "offline" if offline else "live",
        "warnings": warnings,
        "scores": {
            "source_coverage": round(source_coverage, 3),
            "type_coverage": round(type_coverage, 3),
            "flag_coverage": round(flag_coverage, 3),
            "validity": validity,
            "overall": round(overall, 3),
        },
        "validation_status": validation.status,
        "sources_found": sorted(sources),
    }


def run_benchmark(
    tasks_path: Path | None = None,
    *,
    offline: bool = True,
    cache_dir: str = ".vsa_cache",
    fixtures_dir: Path | None = None,
) -> dict[str, Any]:
    benchmarks = _benchmarks_dir()
    tasks_path = tasks_path or benchmarks / "tasks.json"
    fixtures_dir = fixtures_dir or benchmarks / "fixtures"
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    results = [
        score_task(t, offline=offline, cache_dir=cache_dir, fixtures_dir=fixtures_dir) for t in tasks
    ]
    passed = sum(1 for r in results if r["passed"])
    return {
        "mode": "offline" if offline else "live",
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
