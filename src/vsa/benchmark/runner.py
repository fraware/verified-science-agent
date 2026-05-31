"""Benchmark runner for evidence coverage and claim validity."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from vsa.llm.verifier import audit_report
from vsa.pipeline.build import build_report
from vsa.pipeline.retrieval import retrieve_evidence_with_meta
from vsa.provenance.hashchain import build_provenance
from vsa.validate.contradictions import detect_contradictions
from vsa.validate.engine import validate_report

CRITICAL_MIN_PASS_RATE = 1.0

REQUIRED_CATEGORY_MINIMUMS = {
    "adversarial": 10,
    "ambiguity": 5,
    "contradiction": 5,
    "metadata_only_paper": 5,
    "no_evidence": 5,
}


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


def _load_fixture_report(task: dict[str, Any], fixtures_dir: Path) -> dict[str, Any] | None:
    fixture_id = task.get("fixture_report_id") or task.get("fixture_task_id") or task["task_id"]
    path = fixtures_dir / f"{fixture_id}_report.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _citation_integrity(report: dict[str, Any]) -> float:
    evidence_ids = {e["evidence_id"] for e in report.get("evidence", [])}
    claims = report.get("claims", [])
    if not claims:
        return 1.0
    ok = sum(1 for c in claims if all(eid in evidence_ids for eid in c.get("evidence_ids", [])))
    return ok / len(claims)


def _evidence_id_validity(report: dict[str, Any]) -> float:
    evidence = report.get("evidence", [])
    claims = report.get("claims", [])
    if not evidence and not claims:
        return 1.0
    with_ids = sum(1 for e in evidence if e.get("evidence_id"))
    id_coverage = with_ids / len(evidence) if evidence else 1.0
    if not claims:
        return id_coverage
    evidence_ids = {e.get("evidence_id") for e in evidence if e.get("evidence_id")}
    valid_claims = sum(
        1 for c in claims if c.get("evidence_ids") and all(eid in evidence_ids for eid in c["evidence_ids"])
    )
    return (id_coverage + valid_claims / len(claims)) / 2


def _claim_atomicity(report: dict[str, Any]) -> float:
    claims = report.get("claims", [])
    if not claims:
        return 0.0
    ok = sum(
        1
        for c in claims
        if c.get("claim_type")
        and c.get("claim_text")
        and c.get("evidence_ids")
        and c.get("review_boundary")
    )
    return ok / len(claims)


def _evidence_recall(report: dict[str, Any], expected_sources: set[str]) -> float:
    if not expected_sources:
        return 1.0
    sources = {e.get("source_name") for e in report.get("evidence", [])}
    return len(sources & expected_sources) / len(expected_sources)


def _evidence_precision(report: dict[str, Any], expected_sources: set[str]) -> float:
    sources = {e.get("source_name") for e in report.get("evidence", [])}
    if not sources:
        return 1.0 if not expected_sources else 0.0
    if not expected_sources:
        return 1.0
    return len(sources & expected_sources) / len(sources)


def _review_boundary_correctness(report: dict[str, Any], expected_flags: set[str]) -> float:
    if not expected_flags:
        return 1.0
    boundaries = {c.get("review_boundary") for c in report.get("claims", [])}
    return len(boundaries & expected_flags) / len(expected_flags)


def _audit_stability(report: dict[str, Any]) -> float:
    a1 = audit_report(report, mode="rule")
    a2 = audit_report(report, mode="rule")
    return 1.0 if a1.overall_status == a2.overall_status else 0.0


def _bundle_reproducibility(report: dict[str, Any]) -> float:
    from vsa.artifacts.export import export_report_bundle

    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        export_report_bundle(report, Path(tmp1), audit_mode="rule")
        export_report_bundle(report, Path(tmp2), audit_mode="rule")
        m1 = json.loads((Path(tmp1) / "manifest.json").read_text(encoding="utf-8"))
        m2 = json.loads((Path(tmp2) / "manifest.json").read_text(encoding="utf-8"))
        a1 = {k: v["sha256"] for k, v in m1.get("artifacts", {}).items()}
        a2 = {k: v["sha256"] for k, v in m2.get("artifacts", {}).items()}
        return 1.0 if a1 == a2 else 0.0


def _task_categories(task: dict[str, Any]) -> list[str]:
    if task.get("task_categories"):
        return list(task["task_categories"])
    if task.get("task_category"):
        return [task["task_category"]]
    if task.get("task_class"):
        return [task["task_class"]]
    return ["standard"]


def _report_warning_text(report: dict[str, Any]) -> str:
    return " ".join(str(x) for x in report.get("limitations", []) + report.get("retrieval_warnings", []))


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
    warnings: list[str] = []
    hash_stable = True
    bundle_stable = 1.0
    fixture_report = _load_fixture_report(task, fixtures_dir) if task.get("use_fixture_report") else None

    if fixture_report is not None:
        report = dict(fixture_report)
        if task.get("expect_contradictions") and not report.get("contradictions"):
            report["contradictions"] = detect_contradictions(report)
        validation = validate_report(report, verify_hashes=task.get("verify_hashes", False))
        if task.get("check_bundle_reproducible"):
            bundle_stable = _bundle_reproducibility(report)
    else:
        subject = parse_question(task["input_question"])
        evidence: list[dict[str, Any]] | None = None

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

        bundle_stable = _bundle_reproducibility(report) if task.get("check_bundle_reproducible") else 1.0

    sources = {e.get("source_name") for e in report.get("evidence", [])}
    claim_types = {c.get("claim_type") for c in report.get("claims", [])}
    contradictions = report.get("contradictions") or detect_contradictions(report)

    expected_sources = set(task.get("expected_evidence_sources", []))
    expected_types = set(task.get("expected_claim_types", []))
    expected_flags = set(task.get("required_review_flags", []))

    source_recall = _evidence_recall(report, expected_sources)
    source_precision = _evidence_precision(report, expected_sources)
    type_coverage = len(claim_types & expected_types) / max(len(expected_types), 1)
    review_boundary_accuracy = _review_boundary_correctness(report, expected_flags)
    validity = 1.0 if validation.passed else 0.0
    citation_integrity = _citation_integrity(report)
    evidence_id_validity = _evidence_id_validity(report)
    atomicity = _claim_atomicity(report)
    contradiction_detection = 1.0
    if task.get("expect_contradictions"):
        contradiction_detection = 1.0 if contradictions else 0.0
    elif task.get("expect_no_contradictions"):
        contradiction_detection = 1.0 if not contradictions else 0.0

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

    audit_stable = _audit_stability(report) if task.get("check_audit_stable") else 1.0
    bundle_reproducibility = bundle_stable if task.get("check_bundle_reproducible") else (
        1.0 if hash_stable else 0.0
    )

    core_metrics = [
        source_recall,
        source_precision,
        citation_integrity,
        evidence_id_validity,
        review_boundary_accuracy,
        contradiction_detection,
        bundle_reproducibility,
    ]
    auxiliary_metrics = [type_coverage, validity, atomicity, gold_score, audit_stable]
    overall = sum(core_metrics + auxiliary_metrics) / (len(core_metrics) + len(auxiliary_metrics))

    expect_pass = task.get("expect_pass", True)
    task_passed = (overall >= 0.7 and validation.passed) if expect_pass else (not validation.passed or overall < 0.5)
    if task.get("check_hash_stable") and not hash_stable:
        task_passed = False
    if task.get("check_bundle_reproducible") and bundle_reproducibility < 1.0:
        task_passed = False
    if task.get("expect_validation_fail") and validation.passed:
        task_passed = False

    warning_text = _report_warning_text(report).upper()
    if task.get("expect_ambiguity_surfaced") and "AMBIGUITY" not in warning_text:
        task_passed = False
    if task.get("expect_metadata_warning") and "METADATA-ONLY" not in warning_text and "METADATA ONLY" not in warning_text:
        task_passed = False
    if task.get("expect_predicted_structure_label"):
        alphafold_ok = all(
            "PREDICTED" in str(e.get("summary", "")).upper()
            for e in report.get("evidence", [])
            if e.get("source_name") == "AlphaFold DB"
        )
        if not alphafold_ok:
            task_passed = False

    return {
        "task_id": task["task_id"],
        "task_categories": _task_categories(task),
        "passed": task_passed,
        "mode": "offline" if offline else "live",
        "warnings": warnings,
        "scores": {
            "source_recall": round(source_recall, 3),
            "source_precision": round(source_precision, 3),
            "citation_integrity": round(citation_integrity, 3),
            "evidence_id_validity": round(evidence_id_validity, 3),
            "review_boundary_accuracy": round(review_boundary_accuracy, 3),
            "contradiction_detection": round(contradiction_detection, 3),
            "bundle_reproducibility": round(bundle_reproducibility, 3),
            "evidence_recall": round(source_recall, 3),
            "evidence_precision": round(source_precision, 3),
            "review_boundary_correctness": round(review_boundary_accuracy, 3),
            "type_coverage": round(type_coverage, 3),
            "validity": validity,
            "claim_atomicity": round(atomicity, 3),
            "gold_label_score": round(gold_score, 3),
            "hash_reproducibility": hash_stable,
            "audit_stability": round(audit_stable, 3),
            "overall": round(overall, 3),
        },
        "validation_status": validation.status,
        "sources_found": sorted(sources),
        "contradictions_found": len(contradictions),
    }


def category_coverage(tasks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        for category in _task_categories(task):
            counts[category] = counts.get(category, 0) + 1
    return counts


def run_benchmark(
    tasks_path: Path | None = None,
    *,
    offline: bool = True,
    cache_dir: str = ".vsa_cache",
    fixtures_dir: Path | None = None,
    min_pass_rate: float | None = CRITICAL_MIN_PASS_RATE,
) -> dict[str, Any]:
    benchmarks = _benchmarks_dir()
    tasks_path = tasks_path or benchmarks / "tasks.json"
    fixtures_dir = fixtures_dir or benchmarks / "fixtures"
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))["tasks"]
    coverage = category_coverage(tasks)
    category_gaps = {
        name: max(0, minimum - coverage.get(name, 0))
        for name, minimum in REQUIRED_CATEGORY_MINIMUMS.items()
    }
    results = [
        score_task(t, offline=offline, cache_dir=cache_dir, fixtures_dir=fixtures_dir) for t in tasks
    ]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    pass_rate = passed / total if total else 0.0
    regression = pass_rate < (min_pass_rate or 0.0) or any(category_gaps.values())
    return {
        "mode": "offline" if offline else "live",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 3),
        "regression": regression,
        "min_pass_rate": min_pass_rate,
        "category_coverage": coverage,
        "category_gaps": category_gaps,
        "results": results,
    }
