"""Benchmark suite for evidence coverage and claim validity."""

from vsa.benchmark.governance import validate_tasks_document, validate_tasks_file
from vsa.benchmark.runner import REQUIRED_CATEGORY_MINIMUMS, run_benchmark, score_task

__all__ = [
    "REQUIRED_CATEGORY_MINIMUMS",
    "run_benchmark",
    "score_task",
    "validate_tasks_document",
    "validate_tasks_file",
]
