"""Paper claim extraction tests."""

from __future__ import annotations

from vsa.claims.extraction import extract_claims


def test_paper_claims_with_abstract():
    subject = {"entity_type": "paper", "doi": "10.1038/nature12373", "display_name": "10.1038/nature12373"}
    evidence = [
        {
            "evidence_id": "E001",
            "source_name": "OpenAlex",
            "summary": "title: Sample; abstract: Sample abstract for claim extraction test.",
            "domain_metadata": {"content_level": "abstract", "abstract_snippet": "Sample abstract"},
        }
    ]
    claims = extract_claims(subject, evidence)
    assert len(claims) >= 2
    assert claims[0]["claim_type"] == "identity"
    assert claims[1]["claim_type"] == "observation"
    assert all(c.get("evidence_ids") for c in claims)


def test_paper_claims_metadata_only():
    subject = {"entity_type": "paper", "doi": "10.1000/xyz", "display_name": "10.1000/xyz"}
    evidence = [
        {
            "evidence_id": "E001",
            "source_name": "Crossref",
            "summary": "title: Metadata only paper; authors: A B",
            "domain_metadata": {"content_level": "metadata"},
        }
    ]
    claims = extract_claims(subject, evidence)
    assert any(
        "SCIENTIFIC CREDIBILITY WARNING" in c["claim_text"]
        or "CONTENT WARNING" in c["claim_text"]
        or "metadata" in c["claim_text"].lower()
        for c in claims
    )
