"""Benchmark tests."""

from __future__ import annotations

from pathlib import Path

from vsa.benchmark.runner import REQUIRED_CATEGORY_MINIMUMS, run_benchmark


def test_benchmark_offline_holdout():
    summary = run_benchmark(
        Path(__file__).resolve().parents[1] / "benchmarks" / "tasks.json",
        suite="holdout",
    )
    assert summary["suite"] == "holdout"
    assert summary["total"] >= 50
    assert summary["passed"] == summary["total"], {
        "failed": [r["task_id"] for r in summary["results"] if not r["passed"]],
        "governance_errors": summary.get("governance_errors"),
        "category_gaps": summary.get("category_gaps"),
    }
    assert not summary["regression"]
    for category, missing in summary["category_gaps"].items():
        assert missing == 0, f"missing {category} tasks: need {missing} more (minima={REQUIRED_CATEGORY_MINIMUMS})"
