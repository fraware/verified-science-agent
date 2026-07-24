"""AktaActionContext builder and non-authorization semantic validation."""

from __future__ import annotations

import re
import uuid
from typing import Any

from vsa.companion_schema import schema_digest, validate_companion
from vsa.version import AKTA_ACTION_CONTEXT_SCHEMA_VERSION

AKTA_SCHEMA_NAME = "akta_action_context.schema.json"

FORBIDDEN_AUTH_PATTERNS = [
    re.compile(r"\bis\s+authorized\b", re.I),
    re.compile(r"\bauthorization\s*[:=]\s*(?!none\b)\w+", re.I),
    re.compile(r"\bgrants?\s+(permission|access|execution)\b", re.I),
    re.compile(r"\bpermission\s+granted\b", re.I),
    re.compile(r"\bapprove[sd]?\s+for\s+execution\b", re.I),
    re.compile(r"\btool\s+may\s+run\b", re.I),
    re.compile(r"\bcertified\s+correct\b", re.I),
    re.compile(r"\bscientifically\s+proven\b", re.I),
    re.compile(r"\baction\s+is\s+approved\b", re.I),
    re.compile(r"\bexecution\s+allowed\b", re.I),
    re.compile(r"\bmay\s+execute\b", re.I),
    re.compile(r"\bclearance\s+to\s+(run|execute)\b", re.I),
]

NON_CLAIMS = {
    "authorizes_actions": False,
    "executes_tools": False,
    "issues_grants": False,
    "certifies_scientific_correctness": False,
}


def _scan_forbidden(text: str) -> list[str]:
    hits = []
    for pat in FORBIDDEN_AUTH_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def semantic_validate_akta_context(context: dict[str, Any]) -> list[str]:
    """Reject exports that imply authorization, execution, or correctness certification."""
    errors: list[str] = []
    if context.get("authorization") != "none":
        errors.append("authorization must be 'none'")
    nc = context.get("non_claims") or {}
    for key, expected in NON_CLAIMS.items():
        if nc.get(key) is not expected:
            errors.append(f"non_claims.{key} must be {expected}")

    blobs = [
        str((context.get("proposed_action") or {}).get("description") or ""),
        str((context.get("candidate_execution") or {}).get("note") or ""),
        str((context.get("uncertainty") or {}).get("summary") or ""),
        " ".join(context.get("suggested_next_evidence_steps") or []),
        " ".join(context.get("known_domain_limits") or []),
    ]
    for blob in blobs:
        hits = _scan_forbidden(blob)
        if hits:
            errors.append(f"forbidden authorization/execution language matched: {hits}")

    digests = context.get("digests") or {}
    if not digests.get("report_hash") and not digests.get("bundle_hash"):
        errors.append("digests must include report_hash and/or bundle_hash")
    # Reject any accidental grant-like fields that might be injected
    for banned in ("grant", "grants", "permission", "permissions", "approved", "executable"):
        if banned in context:
            errors.append(f"forbidden field present on AktaActionContext: {banned}")
    candidate = context.get("candidate_execution") or {}
    if candidate.get("authorization") not in (None, "none"):
        errors.append("candidate_execution.authorization must be absent or 'none'")
    return errors


def build_akta_action_context(
    *,
    report: dict[str, Any] | None = None,
    bundle: dict[str, Any] | None = None,
    action_id: str = "candidate-action",
    action_class: str = "evidence_review",
    action_description: str | None = None,
    tool_or_execution_class: str = "none",
) -> dict[str, Any]:
    """Build AktaActionContext from ScientificReport and/or DecisionTimeEvidenceBundle.

    Fail closed if both report and bundle hashes disagree when both are provided.
    """
    if report is None and bundle is None:
        raise ValueError("build_akta_action_context requires report and/or bundle")

    report = report or {}
    bundle = bundle or {}

    report_hash = (report.get("provenance") or {}).get("report_hash")
    bundle_hash = (bundle.get("integrity") or {}).get("bundle_hash")

    # Prefer bundle claims/evidence when present
    claims = list(bundle.get("claims") or report.get("claims") or [])
    contradictions = list(bundle.get("contradictions") or report.get("contradictions") or [])
    evidence = list(bundle.get("included_evidence") or report.get("evidence") or [])

    contradicting_claim_ids: set[str] = set()
    for c in contradictions:
        for cid in c.get("claim_ids") or []:
            contradicting_claim_ids.add(str(cid))

    supporting = [
        str(c["claim_id"])
        for c in claims
        if c.get("claim_id") and str(c["claim_id"]) not in contradicting_claim_ids
    ]
    contradicting = sorted(contradicting_claim_ids)

    evidence_levels = [
        {
            "claim_id": str(c.get("claim_id")),
            "support_level": str(c.get("support_level") or "unspecified"),
            "confidence": float(c.get("confidence") if c.get("confidence") is not None else 0.0),
            "uncertainty_level": c.get("uncertainty_level"),
        }
        for c in claims
        if c.get("claim_id")
    ]

    missing = list((bundle.get("uncertainty") or {}).get("missing_evidence") or [])
    if not evidence:
        missing.append("no evidence available at decision time")

    unc_items = [
        f"{c.get('claim_id')}: uncertainty={c.get('uncertainty_level')}"
        for c in claims
        if c.get("uncertainty_level")
    ]
    for w in bundle.get("source_quality_warnings") or []:
        unc_items.append(str(w))

    domain_limits = list(report.get("limitations") or [])[:20]
    domain_limits.append(
        "VSA exports evidence context only; AKTA must perform its own admissibility decisions."
    )

    next_steps = [
        "Gather additional pre-cutoff primary sources with digests where evidence is missing.",
        "Resolve contradictions via domain review before any downstream action decision.",
    ]
    if missing:
        next_steps.append(
            "Address disclosed missing_evidence items before relying on this context."
        )

    description = action_description or (
        "Candidate action under review using decision-time scientific evidence context. "
        "This export is evidence context only; it is not an action approval."
    )

    context_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"vsa:akta|{report.get('report_id') or ''}|{bundle.get('bundle_id') or ''}|{action_id}",
        )
    )

    context: dict[str, Any] = {
        "schema_version": AKTA_ACTION_CONTEXT_SCHEMA_VERSION,
        "context_id": context_id,
        "evidence_report_id": report.get("report_id") or bundle.get("evidence_report_id"),
        "bundle_id": bundle.get("bundle_id"),
        "decision_time_cutoff": bundle.get("decision_time_cutoff"),
        "proposed_action": {
            "action_id": action_id,
            "action_class": action_class,
            "description": description,
        },
        "supporting_claim_refs": supporting,
        "contradicting_claim_refs": contradicting,
        "evidence_levels": evidence_levels,
        "uncertainty": {
            "summary": (
                "Uncertainty and missing evidence are disclosed; "
                "VSA does not certify scientific correctness."
            ),
            "items": unc_items,
        },
        "missing_evidence": missing,
        "digests": {
            "report_hash": report_hash,
            "bundle_hash": bundle_hash,
            "schema_digest": schema_digest(AKTA_SCHEMA_NAME),
        },
        "known_domain_limits": domain_limits,
        "suggested_next_evidence_steps": next_steps,
        "candidate_execution": {
            "tool_or_execution_class": tool_or_execution_class,
            "note": (
                "authorization: none — VSA never issues execution rights or runs tools; "
                "class is informational for AKTA only."
            ),
        },
        "authorization": "none",
        "non_claims": dict(NON_CLAIMS),
    }

    if report and bundle:
        if (
            bundle.get("evidence_report_id")
            and report.get("report_id")
            and bundle.get("evidence_report_id") != report.get("report_id")
        ):
            raise ValueError(
                "fail closed: bundle.evidence_report_id disagrees with report.report_id"
            )
        # Fail closed when report_hash and an explicit expected hash disagree
        expected = (bundle.get("producer") or {}).get("expected_report_hash")
        if expected and report_hash and expected != report_hash:
            raise ValueError("fail closed: bundle/report digests disagree")
        # Fail closed when both digests present and included evidence hashes diverge
        if report_hash and bundle_hash:
            report_ev = {
                str(e.get("evidence_id")): e.get("raw_record_hash")
                for e in (report.get("evidence") or [])
                if isinstance(e, dict) and e.get("evidence_id")
            }
            mismatches = []
            for ev in bundle.get("included_evidence") or []:
                if not isinstance(ev, dict):
                    continue
                eid = str(ev.get("evidence_id") or "")
                if not eid:
                    continue
                if eid in report_ev and report_ev[eid] != ev.get("raw_record_hash"):
                    mismatches.append(eid)
            if mismatches:
                raise ValueError(
                    f"fail closed: bundle/report evidence digests disagree for {mismatches}"
                )

    schema_errors = validate_companion(AKTA_SCHEMA_NAME, context)
    if schema_errors:
        raise ValueError("AktaActionContext schema validation failed: " + "; ".join(schema_errors))

    semantic_errors = semantic_validate_akta_context(context)
    if semantic_errors:
        raise ValueError(
            "AktaActionContext semantic validation failed: " + "; ".join(semantic_errors)
        )

    return context


def validate_akta_context(context: dict[str, Any]) -> list[str]:
    version = context.get("schema_version")
    if version != AKTA_ACTION_CONTEXT_SCHEMA_VERSION:
        return [
            f"akta schema_version unsupported: {version!r}; "
            f"supported: {AKTA_ACTION_CONTEXT_SCHEMA_VERSION}"
        ]
    errors = validate_companion(AKTA_SCHEMA_NAME, context)
    errors.extend(semantic_validate_akta_context(context))
    return errors
