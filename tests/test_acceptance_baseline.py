"""Acceptance skip registry and baseline artifact tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.acceptance.skip_registry import (
    LIVE_CONNECTOR_NAMES,
    build_acceptance_baseline,
    skipped_live_connectors,
    write_acceptance_baseline,
)
from vsa.connectors import default_connectors


def test_live_connector_registry_covers_default_connectors():
    names = {c.name for c in default_connectors()}
    assert names == set(LIVE_CONNECTOR_NAMES)
    assert len(LIVE_CONNECTOR_NAMES) == 9


def test_skipped_live_when_network_disallowed():
    rows = skipped_live_connectors(allow_network=False)
    assert len(rows) == 9
    assert all(r["status"] == "skipped_live" for r in rows)


def test_eligible_when_network_allowed():
    rows = skipped_live_connectors(allow_network=True)
    assert all(r["status"] == "eligible_live" for r in rows)


def test_write_acceptance_baseline(tmp_path: Path):
    out = write_acceptance_baseline(
        tmp_path / "acceptance_baseline.json",
        command_exit_codes={"make_test": 0, "vsa_benchmark": 0},
        extras=["dev"],
        allow_network=False,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["command_exit_codes"]["make_test"] == 0
    assert payload["python_version"]
    assert payload["git_sha"]
    assert len(payload["skipped_live_connectors"]) == 9
    assert payload["network_allowed"] is False


def test_build_baseline_shape():
    payload = build_acceptance_baseline(allow_network=False)
    assert "timestamp" in payload
    assert "skipped_live_connectors" in payload
    assert "extras_installed" in payload
