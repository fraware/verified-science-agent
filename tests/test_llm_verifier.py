"""LLM verifier tests (mocked — no live API calls)."""

from __future__ import annotations

import json

import httpx
import respx

from vsa.llm.llm_verifier import (
    audit_report_llm,
    audit_report_with_llm,
    sanitize_claim_audit,
)
from vsa.llm.providers import OpenAIProvider
from vsa.llm.verifier import audit_report, audit_report_rule, merge_audit_results


def test_sanitize_claim_audit_rejects_unknown_claim():
    assert sanitize_claim_audit({"claim_id": "C999", "status": "supported"}, valid_claim_ids={"C001"}) is None


def test_sanitize_claim_audit_normalizes_fields():
    audit = sanitize_claim_audit(
        {
            "claim_id": "C001",
            "status": "partially_supported",
            "issues": ["overreach"],
            "missing_evidence": ["functional assay data"],
            "confidence_concerns": ["high confidence for weak evidence"],
            "notes": "Needs expert review.",
        },
        valid_claim_ids={"C001"},
    )
    assert audit is not None
    assert audit.status == "partially_supported"
    assert audit.missing_evidence == ["functional assay data"]


def test_merge_audit_results_is_conservative(brca1_report):
    rule = audit_report_rule(brca1_report)
    llm = audit_report_rule(brca1_report)
    for audit in llm.claim_audits:
        audit.status = "supported"
        audit.issues = []

    merged = merge_audit_results(rule, llm)
    assert merged.overall_status == rule.overall_status
    assert all(a.issues for a in merged.claim_audits if any(r.issues for r in rule.claim_audits if r.claim_id == a.claim_id))


def test_audit_report_rule_mode(brca1_report):
    result = audit_report(brca1_report, mode="rule")
    assert result.verifier_method == "rule-based"
    assert result.overall_status in ("passed", "partial", "review_required")


@respx.mock
def test_openai_llm_audit_hybrid(brca1_report):
    mock_response = {
        "claim_audits": [
            {
                "claim_id": "C001",
                "status": "human_review_required",
                "issues": ["clinical classification requires expert review"],
                "missing_evidence": [],
                "confidence_concerns": [],
                "notes": "ClinVar pathogenicity is context-dependent.",
            },
            {
                "claim_id": "C002",
                "status": "supported",
                "issues": [],
                "missing_evidence": [],
                "confidence_concerns": [],
                "notes": "",
            },
        ],
        "report_issues": [],
        "evidence_contradictions": [],
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
    llm_result = audit_report_llm(brca1_report, provider=provider)
    assert llm_result.verifier_method.startswith("llm/openai")
    assert any(a.claim_id == "C001" for a in llm_result.claim_audits)

    hybrid = audit_report_with_llm(brca1_report, mode="llm", llm_provider=provider)
    assert hybrid.verifier_method.startswith("hybrid(")
    payload = hybrid.to_dict()
    assert payload["verifier_method"].startswith("hybrid(")
    assert payload["claim_audits"][0]["missing_evidence"] is not None


def test_audit_auto_falls_back_without_keys(brca1_report, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = audit_report(brca1_report, mode="auto")
    assert result.verifier_method == "rule-based"
