"""LLM claim extraction tests (mocked — no live API calls)."""

from __future__ import annotations

import json

import httpx
import respx

from vsa.claims.llm_extraction import extract_claims_llm, sanitize_claim
from vsa.llm.providers import OpenAIProvider


def test_sanitize_rejects_unknown_evidence():
    assert sanitize_claim(
        {"claim_id": "C1", "claim_text": "Valid claim text here.", "evidence_ids": ["E999"]},
        {"E001"},
        1,
    ) is None


def test_sanitize_accepts_valid_claim():
    claim = sanitize_claim(
        {
            "claim_id": "C001",
            "claim_type": "classification",
            "claim_text": "BRCA1 variant is pathogenic per ClinVar.",
            "evidence_ids": ["E001"],
            "confidence": 0.9,
            "review_boundary": "requires_clinical_review",
            "uncertainty_level": "low",
        },
        {"E001"},
        1,
    )
    assert claim is not None
    assert claim["evidence_ids"] == ["E001"]


@respx.mock
def test_openai_llm_extraction(tmp_path, brca1_evidence):
    mock_response = {
        "claims": [
            {
                "claim_id": "C001",
                "claim_type": "classification",
                "claim_text": "BRCA1 c.68_69del is classified as pathogenic in ClinVar.",
                "evidence_ids": ["E001"],
                "confidence": 0.88,
                "review_boundary": "requires_clinical_review",
                "uncertainty_level": "low",
            }
        ]
    }
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(mock_response)}}]},
        )
    )
    import os

    os.environ["OPENAI_API_KEY"] = "test-key"
    provider = OpenAIProvider(client=httpx.Client(headers={"Authorization": "Bearer test-key"}))
    subject = {"entity_type": "variant", "gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"}
    claims = extract_claims_llm(subject, brca1_evidence, provider=provider)
    assert len(claims) >= 1
    assert all(eid in {"E001", "E002"} for eid in claims[0]["evidence_ids"])
