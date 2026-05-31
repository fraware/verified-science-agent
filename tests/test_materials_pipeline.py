"""Materials pipeline tests."""

from vsa.pipeline.build import build_report
from vsa.pipeline.subject_parser import parse_question


def test_material_subject():
    s = parse_question("LiFePO4 cathode material")
    assert s["entity_type"] == "material"


def test_material_build_offline():
    import json
    from pathlib import Path

    ev = json.loads(
        (Path(__file__).resolve().parents[1] / "benchmarks/fixtures/materials_candidate_evidence.json").read_text()
    )
    report = build_report({"question": "LiFePO4 cathode material"}, offline_evidence=ev, claim_mode="rule")
    assert report["validation_results"]["status"] in ("pass", "warn")
    sources = {e["source_name"] for e in report["evidence"]}
    assert "Materials Project" in sources
