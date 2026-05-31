"""LLM-backed scientific report verification with structured output."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from vsa.llm.providers import LLMProvider, get_provider
from vsa.llm.verifier import (
    VERIFIER_PROMPT_VERSION,
    AuditResult,
    ClaimAudit,
    audit_report_rule,
    merge_audit_results,
)

VALID_STATUSES = frozenset(
    {"supported", "partially_supported", "unsupported", "human_review_required"}
)


def load_verifier_prompt() -> str:
    return (resources.files("vsa.prompts") / "verifier_prompt_v1.md").read_text(encoding="utf-8")


def _evidence_for_audit(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": evidence["evidence_id"],
        "source_name": evidence.get("source_name"),
        "source_type": evidence.get("source_type"),
        "identifier": evidence.get("identifier"),
        "retrieval_path": evidence.get("retrieval_path"),
        "summary": evidence.get("summary"),
        "evidence_role": evidence.get("evidence_role"),
        "domain_metadata": evidence.get("domain_metadata", {}),
    }


def _report_payload_for_llm(report: dict[str, Any]) -> dict[str, Any]:
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    claims_payload: list[dict[str, Any]] = []

    for claim in report.get("claims", []):
        cited = [
            _evidence_for_audit(evidence_by_id[eid])
            for eid in claim.get("evidence_ids", [])
            if eid in evidence_by_id
        ]
        claims_payload.append(
            {
                "claim_id": claim.get("claim_id"),
                "claim_type": claim.get("claim_type"),
                "claim_text": claim.get("claim_text"),
                "evidence_ids": claim.get("evidence_ids", []),
                "confidence": claim.get("confidence"),
                "review_boundary": claim.get("review_boundary"),
                "uncertainty_level": claim.get("uncertainty_level"),
                "support_level": claim.get("support_level"),
                "cited_evidence": cited,
            }
        )

    prov = report.get("provenance", {})
    validation = report.get("validation_results", {})
    return {
        "subject": report.get("subject", {}),
        "claims": claims_payload,
        "contradictions": report.get("contradictions", []),
        "provenance_summary": {
            "report_hash": prov.get("report_hash"),
            "evidence_bundle_hash": prov.get("evidence_bundle_hash"),
            "validation_status": validation.get("status"),
            "schema_version": report.get("schema_version"),
        },
        "human_review": report.get("human_review", {}),
    }


def sanitize_claim_audit(
    raw: dict[str, Any],
    *,
    valid_claim_ids: set[str],
) -> ClaimAudit | None:
    claim_id = str(raw.get("claim_id", "")).strip()
    if not claim_id or claim_id not in valid_claim_ids:
        return None

    status = str(raw.get("status", "partially_supported")).strip()
    if status not in VALID_STATUSES:
        status = "partially_supported"

    def _string_list(key: str) -> list[str]:
        value = raw.get(key, [])
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    return ClaimAudit(
        claim_id=claim_id,
        status=status,
        issues=_string_list("issues"),
        missing_evidence=_string_list("missing_evidence"),
        confidence_concerns=_string_list("confidence_concerns"),
        notes=str(raw.get("notes", "")).strip(),
    )


def _parse_llm_audit(
    result: dict[str, Any],
    *,
    valid_claim_ids: set[str],
) -> AuditResult:
    raw_claim_audits = result.get("claim_audits", [])
    claim_audits: list[ClaimAudit] = []

    if isinstance(raw_claim_audits, list):
        for raw in raw_claim_audits:
            if not isinstance(raw, dict):
                continue
            cleaned = sanitize_claim_audit(raw, valid_claim_ids=valid_claim_ids)
            if cleaned:
                claim_audits.append(cleaned)

    report_issues: list[str] = []
    if isinstance(result.get("report_issues"), list):
        report_issues = [str(item).strip() for item in result["report_issues"] if str(item).strip()]

    contradictions: list[str] = []
    if isinstance(result.get("evidence_contradictions"), list):
        contradictions = [str(item).strip() for item in result["evidence_contradictions"] if str(item).strip()]
    report_issues.extend(contradictions)

    overall = _overall_from_claim_audits(claim_audits, report_issues)
    return AuditResult(
        overall_status=overall,
        claim_audits=claim_audits,
        report_issues=report_issues,
        verifier_method="llm-pending",
    )


def _overall_from_claim_audits(claim_audits: list[ClaimAudit], report_issues: list[str]) -> str:
    unsupported = [a for a in claim_audits if a.status == "unsupported"]
    review_needed = [a for a in claim_audits if a.status == "human_review_required"]

    if unsupported:
        return "failed"
    if report_issues or review_needed:
        return "review_required"
    if any(a.status == "partially_supported" for a in claim_audits):
        return "partial"
    if claim_audits:
        return "passed"
    return "partial"


def audit_report_llm(
    report: dict[str, Any],
    *,
    provider: LLMProvider | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> AuditResult:
    """Run LLM verification; caller should merge with rule audit for production use."""
    valid_claim_ids = {c["claim_id"] for c in report.get("claims", []) if c.get("claim_id")}
    if not valid_claim_ids:
        return AuditResult(
            overall_status="partial",
            claim_audits=[],
            report_issues=["no claims to audit"],
            verifier_method="llm/skipped",
        )

    system = load_verifier_prompt()
    payload = _report_payload_for_llm(report)
    user = (
        "Audit the scientific report below. Return JSON matching the output schema in the system prompt.\n\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )

    llm = provider or get_provider(provider_name, model)
    result = llm.complete_json(system, user)
    if not isinstance(result, dict):
        raise RuntimeError("LLM verifier returned non-object JSON")

    parsed = _parse_llm_audit(result, valid_claim_ids=valid_claim_ids)
    stack = f"llm/{provider_name or llm.name}"
    if model or getattr(llm, "model", None):
        stack += f"/{model or llm.model}"
    parsed.verifier_method = stack
    parsed.verifier_version = VERIFIER_PROMPT_VERSION
    return parsed


def audit_report_with_llm(
    report: dict[str, Any],
    *,
    mode: str = "auto",
    provider: str | None = None,
    model: str | None = None,
    llm_provider: LLMProvider | None = None,
) -> AuditResult:
    """
    Audit with rule baseline plus optional LLM semantic review (conservative merge).
    """
    from vsa.config import llm_available

    rule_result = audit_report_rule(report)
    rule_result.verifier_method = "rule-based"
    rule_result.verifier_version = VERIFIER_PROMPT_VERSION

    mode = mode.lower()
    if mode == "rule":
        return rule_result

    use_llm = mode == "llm" or (mode == "auto" and llm_available())
    if not use_llm:
        return rule_result

    try:
        llm_result = audit_report_llm(
            report,
            provider=llm_provider,
            provider_name=provider,
            model=model,
        )
    except Exception as exc:
        if mode == "llm":
            raise RuntimeError(
                f"LLM audit failed ({exc}). "
                "Try --audit-mode auto for rule fallback, or check network/TLS (.env VSA_SSL_VERIFY)."
            ) from exc
        rule_result.verifier_method = "rule-based (llm fallback)"
        rule_result.report_issues = list(rule_result.report_issues) + [f"llm audit unavailable: {exc}"]
        return rule_result

    merged = merge_audit_results(rule_result, llm_result)
    merged.verifier_method = f"hybrid({rule_result.verifier_method}+{llm_result.verifier_method})"
    merged.verifier_version = VERIFIER_PROMPT_VERSION
    return merged
