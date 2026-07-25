"""Domain pack loading and build selection (VSA-10)."""

from __future__ import annotations

import copy

import pytest

from vsa.domain_packs import list_packs, load_pack, resolve_pack_name, routing_for_pack
from vsa.pipeline.build import build_report
from vsa.pipeline.retrieval import select_connectors


def test_list_packs_includes_pilots():
    packs = list_packs()
    assert "clinical_genetics" in packs
    assert "materials" in packs


def test_clinical_genetics_routing():
    pack = load_pack("clinical_genetics")
    assert pack.name == "clinical_genetics"
    assert "variant" in pack.entity_types
    routing = routing_for_pack("clinical_genetics")
    assert routing["variant"][0] == "ClinVar"
    assert "ClinVar" in routing["gene"]
    names = [c.name for c in select_connectors({"entity_type": "variant"}, domain_pack="clinical_genetics")]
    assert names == routing["variant"]


def test_materials_routing():
    pack = load_pack("materials")
    assert pack.warning_policy.get("require_api_key_notice") is True
    routing = routing_for_pack("materials")
    assert routing["material"][0] == "Materials Project"
    assert "Crossref" in routing["material"]
    names = [c.name for c in select_connectors({"entity_type": "material"}, domain_pack="materials")]
    assert names == routing["material"]


def test_unknown_pack_raises():
    with pytest.raises(KeyError):
        load_pack("no_such_pack")
    assert resolve_pack_name(None) is None


def test_build_selects_domain_pack(brca1_evidence, tmp_path):
    report = build_report(
        {"question": "BRCA1 c.68_69del", "report_id": "domain-pack-1"},
        offline_evidence=copy.deepcopy(brca1_evidence),
        claim_mode="rule",
        cache_dir=str(tmp_path / "cache"),
        domain_pack="clinical_genetics",
    )
    assert report.get("domain_pack") == "clinical_genetics"
    assert report.get("retrieval_status") == "complete"


def test_materials_pack_selectable_on_build(tmp_path):
    from vsa.connectors.base import NormalizedEvidence, now_utc

    ne = NormalizedEvidence(
        source_name="Materials Project",
        source_type="database",
        identifier="mp-19017",
        retrieval_path="https://materialsproject.org/materials/mp-19017",
        retrieved_at=now_utc(),
        summary="material_id: mp-19017; formula: LiFePO4",
        raw_record={"material_id": "mp-19017", "formula_pretty": "LiFePO4"},
        domain_metadata={"material_id": "mp-19017", "formula": "LiFePO4"},
    )
    sr = ne.to_source_record({"entity_type": "material", "formula": "LiFePO4"})
    evidence = [ne.to_dict("E001", source_id=sr.source_id)]
    report = build_report(
        {
            "question": "LiFePO4 cathode material",
            "report_id": "domain-pack-mat-1",
            "subject": {
                "entity_type": "material",
                "display_name": "LiFePO4",
                "formula": "LiFePO4",
            },
            "source_records": [sr.to_dict()],
        },
        offline_evidence=evidence,
        claim_mode="rule",
        cache_dir=str(tmp_path / "cache"),
        domain_pack="materials",
    )
    assert report.get("domain_pack") == "materials"
