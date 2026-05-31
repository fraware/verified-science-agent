"""CLI smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

from vsa.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_help():
    with __import__("pytest").raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_validate_good_report(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    assert main(["validate", str(path)]) == 0


def test_validate_bad_report(tmp_path):
    bad = ROOT / "examples" / "bad_unsupported_claim.json"
    assert main(["validate", str(bad), "--skip-hash-check"]) == 1


def test_render_markdown(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    out = tmp_path / "out.md"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    assert main(["render", str(path), "--format", "markdown", "--out", str(out)]) == 0
    assert "Scientific Report" in out.read_text(encoding="utf-8")


def test_hash_command(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    assert main(["hash", str(path)]) == 0


def test_inspect_command(tmp_path, brca1_report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(brca1_report), encoding="utf-8")
    assert main(["inspect", str(path)]) == 0


def test_build_command(tmp_path, brca1_input_path):
    out = tmp_path / "built.json"
    code = main(["build", str(brca1_input_path), "--out", str(out)])
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.1.0"
    assert len(report["evidence"]) >= 1
