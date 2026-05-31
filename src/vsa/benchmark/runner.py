"""Benchmark runner for evidence coverage and claim validity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vsa.pipeline.build import build_report
from vsa.pipeline.retrieval import retrieve_evidence_with_meta
from vsa.provenance.hashchain import build_provenance
from vsa.validate.engine import validate_report


def _benchmarks_dir() -> Path:
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = base / "benchmarks"
        if (candidate / "tasks.json").exists():
            return candidate
    return Path.cwd() / "benchmarks"


def _load_offline_evidence(task: dict[str, Any], fixtures_dir: Path) -> list[dict[str, Any]] | None:
    fixture_id = task.get("fixture_task_id") or task["task_id"]
    path = fixtures_dir / f"{fixture_id}_evidence.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if task.get("allow_missing_fixture"):
        return []
    return None


def _citation_integrity(report: dict[str, Any]) -> float:
    evidence_ids = {e["evidence_id"] for e in report.get("evidence", [])}
    claims = report.get("claims", [])
    if not claims:
        return 0.0
    ok = sum(1 for c in claims if all(eid in evidence_ids for eid in c.get("evidence_ids", [])))
    return ok / len(claims)


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
        evidence = _load_offline_evidence(task, fixtures_dir)
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
        if not evidence and not task.get("allow_empty_evidence"):
            return {
                "task_id": task["task_id"],
                "passed": False,
                "reason": "live retrieval returned no evidence",
                "warnings": warnings,
                "scores": {},
            }

    input_payload = {"question": task["input_question"], "evidence": evidence or []}
    report = build_report(input_payload, offline_evidence=evidence, cache_dir=cache_dir, claim_mode="rule")
    validation = validate_report(report)

    if task.get("check_hash_stable"):
        report2 = build_report(
            {**input_payload, "report_id": report["report_id"]},
            offline_evidence=evidence,
            cache_dir=cache_dir,
            claim_mode="rule",
        )
        h1 = build_provenance(report)["report_hash"]
        h2 = build_provenance(report2)["report_hash"]
        hash_stable = h1 == h2
    else:
        hash_stable = True

    sources = {e.get("source_name") for e in report.get("evidence", [])}
    claim_types = {c.get("claim_type") for c in report.get("claims", [])}
    boundaries = {c.get("review_boundary") for c in report.get("claims", [])}
    contradictions = report.get("contradictions", [])

    expected_sources = set(task.get("expected_evidence_sources", []))
    expected_types = set(task.get("expected_claim_types", []))
    expected_flags = set(task.get("required_review_flags", []))

    source_coverage = len(sources & expected_sources) / max(len(expected_sources), 1)
    type_coverage = len(claim_types & expected_types) / max(len(expected_types), 1)
    flag_coverage = len(boundaries & expected_flags) / max(len(expected_flags), 1)
    validity = 1.0 if validation.passed else 0.0
    citation = _citation_integrity(report)
    contradiction_score = 1.0
    if task.get("expect_contradictions"):
        contradiction_score = 1.0 if contradictions else 0.0
    elif task.get("expect_no_contradictions"):
        contradiction_score = 1.0 if not contradictions else 0.0

    gold = task.get("gold_labels") or {}
    gold_score = 1.0
    if gold.get("min_claims") is not None:
        gold_score *= 1.0 if len(report.get("claims", [])) >= gold["min_claims"] else 0.0
    if gold.get("min_evidence") is not None:
        gold_score *= 1.0 if len(report.get("evidence", [])) >= gold["min_evidence"] else 0.0
    if gold.get("required_claim_ids"):
        claim_ids = {c.get("claim_id") for c in report.get("claims", [])}
        needed = set(gold["required_claim_ids"])
        gold_score *= len(claim_ids & needed) / max(len(needed), 1)

    overall = (
        source_coverage + type_coverage + flag_coverage + validity + citation + contradiction_score + gold_score
    ) / 7

    expect_pass = task.get("expect_pass", True)
    task_passed = (overall >= 0.7 and validation.passed) if expect_pass else (not validation.passed or overall < 0.5)
    if task.get("check_hash_stable") and not hash_stable:
        task_passed = False

    return {
        "task_id": task["task_id"],
        "passed": task_passed,
        "mode": "offline" if offline else "live",
        "warnings": warnings,
        "scores": {
            "source_coverage": round(source_coverage, 3),
            "type_coverage": round(type_coverage, 3),
            "flag_coverage": round(flag_coverage, 3),
            "validity": validity,
            "citation_integrity": round(citation, 3),
            "contradiction_score": round(contradiction_score, 3),
            "gold_label_score": round(gold_score, 3),
            "hash_stable": hash_stable,
            "overall": round(overall, 3),
        },
        "validation_status": validation.status,
        "sources_found": sorted(sources),
        "contradictions_found": len(contradictions),
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
