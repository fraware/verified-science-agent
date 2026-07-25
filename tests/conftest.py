"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vsa.pipeline.build import build_report

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
DEV_FIXTURES = ROOT / "benchmarks" / "fixtures" / "dev"
HOLDOUT_FIXTURES = ROOT / "benchmarks" / "fixtures" / "holdout"
# Unit tests and local iteration must use the dev suite only.
FIXTURES = DEV_FIXTURES

_EXTRACTOR_TEST_MARKERS = (
    "extraction",
    "extract_claims",
    "test_pipeline",
    "test_paper_claims",
    "test_claim",
)


def assert_not_holdout_fixture(path: Path | str) -> None:
    """Raise if a path resolves under the holdout fixture tree."""
    resolved = Path(path).resolve()
    holdout = HOLDOUT_FIXTURES.resolve()
    try:
        resolved.relative_to(holdout)
    except ValueError:
        return
    raise RuntimeError(
        f"Holdout fixture import forbidden in unit tests: {resolved}. "
        "Use benchmarks/fixtures/dev/ for local iteration and extractor tests."
    )


def load_dev_fixture(name: str) -> object:
    """Load a JSON fixture from the dev suite (never holdout)."""
    path = DEV_FIXTURES / name
    assert_not_holdout_fixture(path)
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def brca1_evidence():
    path = FIXTURES / "brca1_variant_evidence.json"
    assert_not_holdout_fixture(path)
    return json.loads(path.read_text(encoding="utf-8"))


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


@pytest.fixture(autouse=True)
def _forbid_holdout_in_extractor_tests(request, monkeypatch):
    """Path guard: extractor unit tests must not import holdout fixtures."""
    nodeid = getattr(request.node, "nodeid", "") or ""
    if not any(marker in nodeid for marker in _EXTRACTOR_TEST_MARKERS):
        return

    holdout = HOLDOUT_FIXTURES.resolve()

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args, **kwargs):
        resolved = self.resolve()
        try:
            resolved.relative_to(holdout)
        except ValueError:
            return original_read_text(self, *args, **kwargs)
        raise RuntimeError(
            f"Holdout fixture import forbidden in extractor unit tests: {resolved}. "
            "Use benchmarks/fixtures/dev/."
        )

    monkeypatch.setattr(Path, "read_text", guarded_read_text)


@pytest.fixture
def brca1_input_path():
    return EXAMPLES / "brca1_input.json"
