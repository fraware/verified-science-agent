"""Pipeline and claim extraction tests."""

from __future__ import annotations

from vsa.claims.extraction import extract_claims as extract_claims_rule
from vsa.pipeline.build import build_report
from vsa.pipeline.subject_parser import parse_question


def test_parse_brca1_variant():
    subject = parse_question("BRCA1 c.68_69del")
    assert subject["gene_symbol"] == "BRCA1"
    assert subject["entity_type"] == "variant"


def test_parse_doi():
    subject = parse_question("10.1038/nature12373")
    assert subject["entity_type"] == "paper"
    assert "10.1038" in subject["doi"]


def test_extract_claims_use_evidence_ids_only(brca1_evidence):
    subject = {"entity_type": "variant", "gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"}
    claims = extract_claims_rule(subject, brca1_evidence)
    evidence_ids = {e["evidence_id"] for e in brca1_evidence}
    for claim in claims:
        assert all(eid in evidence_ids for eid in claim["evidence_ids"])
        assert claim["review_boundary"] != "unsupported"


def test_build_offline(brca1_evidence):
    report = build_report({"question": "BRCA1 c.68_69del"}, offline_evidence=brca1_evidence, claim_mode="rule")
    assert report["validation_results"]["status"] in ("pass", "warn")
