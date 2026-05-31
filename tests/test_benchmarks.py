"""Benchmark tests."""

from __future__ import annotations

from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.run_benchmark import run_benchmark


def test_benchmark_offline():
    summary = run_benchmark(Path(__file__).resolve().parents[1] / "benchmarks" / "tasks.json")
    assert summary["total"] >= 40
    assert summary["passed"] >= summary["total"] - 1, summary
    for category, minimum in summary["category_gaps"].items():
        assert summary["category_gaps"][category] == 0, f"missing {category} tasks: need {minimum} more"
