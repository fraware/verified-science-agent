"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.pipeline.build import build_report

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
FIXTURES = ROOT / "benchmarks" / "fixtures"


@pytest.fixture
def brca1_evidence():
    return json.loads((FIXTURES / "brca1_variant_evidence.json").read_text(encoding="utf-8"))


@pytest.fixture
def brca1_report(brca1_evidence):
    return build_report(
        {"question": "BRCA1 c.68_69del", "report_id": "test-brca1"},
        offline_evidence=brca1_evidence,
        claim_mode="rule",
    )


@pytest.fixture(autouse=True)
def _no_llm_in_tests(monkeypatch):
    """Prevent tests from calling live LLM APIs when .env keys are present."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MATERIALS_PROJECT_API_KEY", raising=False)


@pytest.fixture
def brca1_input_path():
    return EXAMPLES / "brca1_input.json"
