"""Scientific credibility policy tests."""

from __future__ import annotations

from vsa.pipeline.build import build_report
from vsa.scientific.credibility import harden_evidence
from vsa.validate.engine import validate_report


def test_harden_evidence_caps_ambiguous_reliability():
    evidence = [
        {
            "evidence_id": "E001",
            "source_name": "ClinVar",
            "source_type": "database",
            "identifier": "VCV1",
            "retrieval_path": "https://example.com/1",
            "retrieved_at": "2026-05-30T12:00:00Z",
            "summary": "ambiguous variant",
            "raw_record_hash": "a" * 64,
            "reliability": "high",
            "domain_metadata": {"retrieval_ambiguity": True, "match_score": 0.51},
        }
    ]
    hardened, warnings = harden_evidence(evidence)
    assert hardened[0]["reliability"] == "low"
    assert any("AMBIGUITY ALERT" in w for w in warnings)


def test_build_surfaces_clinvar_ambiguity_limitations():
    evidence = [
        {
            "evidence_id": "E001",
            "source_name": "ClinVar",
            "source_type": "database",
            "identifier": "VCV1",
            "retrieval_path": "https://example.com/1",
            "retrieved_at": "2026-05-30T12:00:00Z",
            "summary": "title: BRCA1; clinical_significance: pathogenic",
            "raw_record_hash": "a" * 64,
            "reliability": "low",
            "domain_metadata": {
                "retrieval_ambiguity": True,
                "clinical_significance": "pathogenic",
                "candidate_rank": 1,
                "match_score": 0.51,
            },
        }
    ]
    report = build_report({"question": "BRCA1 c.68_69del", "evidence": evidence}, claim_mode="rule")
    joined = " ".join(report.get("limitations", []) + report.get("retrieval_warnings", []))
    assert "CLINVAR AMBIGUITY" in joined.upper() or "AMBIGUITY ALERT" in joined.upper()
    validation = validate_report(report)
    assert validation.passed


def test_alphafold_summary_declares_predicted_structure():
    evidence = [
        {
            "evidence_id": "E001",
            "source_name": "AlphaFold DB",
            "source_type": "structure",
            "identifier": "P38398",
            "retrieval_path": "https://alphafold.ebi.ac.uk/entry/P38398",
            "retrieved_at": "2026-05-30T12:00:00Z",
            "summary": "model for P38398",
            "raw_record_hash": "b" * 64,
            "reliability": "high",
            "domain_metadata": {},
        }
    ]
    hardened, _ = harden_evidence(evidence)
    assert "predicted" in hardened[0]["summary"].lower()
    validation = validate_report(
        {
            "schema_version": "1.2.0",
            "report_id": "test",
            "created_at": "2026-05-30T12:00:00Z",
            "subject": {"entity_type": "protein", "display_name": "P38398"},
            "claims": [],
            "evidence": hardened,
            "provenance": {},
            "validation_results": {"status": "pass", "checks": []},
            "human_review": {"required": False, "status": "not_required"},
        },
        verify_hashes=False,
    )
    assert not [e for e in validation.errors if "alphafold" in e.lower()]
