"""Scientific report audit / verification layer (rule-based + LLM hybrid)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

VERIFIER_PROMPT_VERSION = "verifier_prompt_v1"

VALID_STATUSES = frozenset(
    {"supported", "partially_supported", "unsupported", "human_review_required"}
)

STATUS_SEVERITY = {
    "supported": 1,
    "partially_supported": 2,
    "human_review_required": 3,
    "unsupported": 4,
}


@dataclass
class ClaimAudit:
    claim_id: str
    status: str
    issues: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    confidence_concerns: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AuditResult:
    overall_status: str
    claim_audits: list[ClaimAudit] = field(default_factory=list)
    report_issues: list[str] = field(default_factory=list)
    verifier_method: str = "rule-based"
    verifier_version: str = VERIFIER_PROMPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "verifier_version": self.verifier_version,
            "verifier_method": self.verifier_method,
            "claim_audits": [
                {
                    "claim_id": c.claim_id,
                    "status": c.status,
                    "issues": c.issues,
                    "missing_evidence": c.missing_evidence,
                    "confidence_concerns": c.confidence_concerns,
                    "notes": c.notes,
                }
                for c in self.claim_audits
            ],
            "report_issues": self.report_issues,
        }


def _merge_status(left: str, right: str) -> str:
    left = left if left in VALID_STATUSES else "partially_supported"
    right = right if right in VALID_STATUSES else "partially_supported"
    return left if STATUS_SEVERITY[left] >= STATUS_SEVERITY[right] else right


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _merge_claim_audit(rule: ClaimAudit, llm: ClaimAudit | None) -> ClaimAudit:
    if llm is None:
        return rule
    return ClaimAudit(
        claim_id=rule.claim_id,
        status=_merge_status(rule.status, llm.status),
        issues=_dedupe_strings(rule.issues + llm.issues),
        missing_evidence=_dedupe_strings(rule.missing_evidence + llm.missing_evidence),
        confidence_concerns=_dedupe_strings(rule.confidence_concerns + llm.confidence_concerns),
        notes=llm.notes or rule.notes,
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


def merge_audit_results(rule_result: AuditResult, llm_result: AuditResult) -> AuditResult:
    """Conservative merge: rule structural checks cannot be overridden by LLM."""
    llm_by_id = {audit.claim_id: audit for audit in llm_result.claim_audits}
    merged_claims = [_merge_claim_audit(audit, llm_by_id.get(audit.claim_id)) for audit in rule_result.claim_audits]

    for claim_id, llm_audit in llm_by_id.items():
        if claim_id not in {c.claim_id for c in rule_result.claim_audits}:
            merged_claims.append(llm_audit)

    report_issues = _dedupe_strings(rule_result.report_issues + llm_result.report_issues)
    overall = _overall_from_claim_audits(merged_claims, report_issues)
    return AuditResult(
        overall_status=overall,
        claim_audits=merged_claims,
        report_issues=report_issues,
        verifier_method=rule_result.verifier_method,
        verifier_version=VERIFIER_PROMPT_VERSION,
    )


def audit_report_rule(report: dict[str, Any]) -> AuditResult:
    """Deterministic rule audit implementing verifier_prompt.md responsibilities."""
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    evidence_ids = set(evidence_by_id)
    claim_audits: list[ClaimAudit] = []
    report_issues: list[str] = []

    prov = report.get("provenance", {})
    if not prov.get("report_hash"):
        report_issues.append("missing provenance.report_hash")
    if not prov.get("evidence_bundle_hash"):
        report_issues.append("missing provenance.evidence_bundle_hash")

    validation_status = (report.get("validation_results") or {}).get("status")
    if validation_status == "fail":
        report_issues.append("validation_results.status is fail")

    for claim in report.get("claims", []):
        cid = claim.get("claim_id", "?")
        issues: list[str] = []
        missing_evidence: list[str] = []
        confidence_concerns: list[str] = []
        refs = claim.get("evidence_ids", [])
        dangling: list[str] = []

        if not refs:
            issues.append("no evidence_ids")
            missing_evidence.append("at least one supporting evidence item required")
        else:
            dangling = [r for r in refs if r not in evidence_ids]
            if dangling:
                issues.append(f"dangling evidence refs: {dangling}")

        for eid in refs:
            ev = evidence_by_id.get(eid)
            if not ev:
                continue
            if not ev.get("retrieval_path"):
                issues.append(f"{eid} missing retrieval_path")
            if not ev.get("source_type"):
                issues.append(f"{eid} missing source_type")

        text = str(claim.get("claim_text", ""))
        if len(text) < 20:
            issues.append("claim_text too short for independent review")

        boundary = claim.get("review_boundary", "")
        if boundary == "unsupported":
            issues.append("marked unsupported")
        if boundary == "speculative" and claim.get("uncertainty_level") == "low":
            issues.append("speculative claim with low uncertainty")
            confidence_concerns.append("speculative boundary conflicts with low uncertainty")

        confidence = claim.get("confidence")
        if isinstance(confidence, (int, float)):
            if confidence >= 0.85 and boundary in ("speculative", "requires_domain_review"):
                confidence_concerns.append("high confidence with cautious review boundary")
            if confidence <= 0.35 and boundary == "safe_summary":
                confidence_concerns.append("low confidence with safe_summary boundary")

        clinical_terms = ("pathogenic", "diagnosis", "prognosis", "therapy", "treatment")
        if any(t in text.lower() for t in clinical_terms) and boundary not in (
            "requires_clinical_review",
            "speculative",
            "unsupported",
        ):
            issues.append("clinical language without requires_clinical_review boundary")

        if not issues:
            status = "supported"
        elif boundary == "unsupported" or (refs and dangling):
            status = "unsupported"
        elif boundary in ("requires_clinical_review", "requires_domain_review"):
            status = "human_review_required"
        else:
            status = "partially_supported"

        claim_audits.append(
            ClaimAudit(
                claim_id=cid,
                status=status,
                issues=issues,
                missing_evidence=missing_evidence,
                confidence_concerns=confidence_concerns,
            )
        )

    high_conflicts = [c for c in report.get("contradictions", []) if c.get("severity") == "high"]
    if high_conflicts:
        report_issues.append(f"{len(high_conflicts)} high-severity contradiction(s)")

    overall = _overall_from_claim_audits(claim_audits, report_issues)
    return AuditResult(
        overall_status=overall,
        claim_audits=claim_audits,
        report_issues=report_issues,
        verifier_method="rule-based",
        verifier_version=VERIFIER_PROMPT_VERSION,
    )


def audit_report(
    report: dict[str, Any],
    *,
    mode: str = "auto",
    provider: str | None = None,
    model: str | None = None,
) -> AuditResult:
    """Audit report with rule baseline and optional LLM semantic review."""
    from vsa.llm.llm_verifier import audit_report_with_llm

    return audit_report_with_llm(report, mode=mode, provider=provider, model=model)
