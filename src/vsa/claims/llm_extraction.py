"""LLM-based claim extraction with strict evidence-ID enforcement."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from vsa.claims.extraction import PROMPT_TEMPLATE_VERSION, extract_claims as extract_claims_rule
from vsa.llm.providers import LLMProvider, get_provider

ALLOWED_CLAIM_KEYS = {
    "claim_id",
    "claim_type",
    "claim_text",
    "evidence_ids",
    "confidence",
    "review_boundary",
    "uncertainty_level",
    "support_level",
}

VALID_BOUNDARIES = {
    "safe_summary",
    "requires_domain_review",
    "requires_clinical_review",
    "speculative",
    "unsupported",
}

VALID_CLAIM_TYPES = {
    "identity",
    "classification",
    "observation",
    "mechanism",
    "comparison",
    "hypothesis",
    "summary",
    "structure",
    "property",
}


def load_prompt_template() -> str:
    return (resources.files("vsa.prompts") / "claim_extraction_v1.md").read_text(encoding="utf-8")


def _evidence_for_prompt(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip heavy/raw fields — LLM sees only what it needs to cite evidence IDs."""
    return [
        {
            "evidence_id": e["evidence_id"],
            "source_name": e.get("source_name"),
            "source_type": e.get("source_type"),
            "identifier": e.get("identifier"),
            "summary": e.get("summary"),
            "evidence_role": e.get("evidence_role"),
            "domain_metadata": e.get("domain_metadata", {}),
        }
        for e in evidence
    ]


def sanitize_claim(raw: dict[str, Any], evidence_ids: set[str], index: int) -> dict[str, Any] | None:
    """Keep only allowed fields; reject claims referencing unknown evidence."""
    eids = raw.get("evidence_ids") or []
    if not eids or not all(eid in evidence_ids for eid in eids):
        return None

    boundary = raw.get("review_boundary", "requires_domain_review")
    if boundary not in VALID_BOUNDARIES:
        boundary = "requires_domain_review"

    claim_type = raw.get("claim_type", "observation")
    if claim_type not in VALID_CLAIM_TYPES:
        claim_type = "observation"

    confidence = raw.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    text = str(raw.get("claim_text", "")).strip()
    if len(text) < 10:
        return None

    claim: dict[str, Any] = {
        "claim_id": raw.get("claim_id") or f"C{index:03d}",
        "claim_type": claim_type,
        "claim_text": text,
        "evidence_ids": list(eids),
        "confidence": confidence,
        "review_boundary": boundary,
        "uncertainty_level": raw.get("uncertainty_level", "medium"),
        "support_level": raw.get("support_level", "medium"),
    }
    if claim["uncertainty_level"] not in ("low", "medium", "high", "unknown"):
        claim["uncertainty_level"] = "medium"
    if claim["support_level"] not in ("high", "medium", "low", "insufficient"):
        claim["support_level"] = "medium"
    return claim


def extract_claims_llm(
    subject: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    provider: LLMProvider | None = None,
    provider_name: str | None = None,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract claims via LLM. Model may ONLY reference provided evidence IDs.
    Falls back to rule-based extraction if LLM output is invalid.
    """
    if not evidence:
        return []

    evidence_ids = {e["evidence_id"] for e in evidence}
    system = load_prompt_template()
    user_payload = {
        "subject": subject,
        "evidence": _evidence_for_prompt(evidence),
        "allowed_evidence_ids": sorted(evidence_ids),
    }
    user = (
        "Extract atomic scientific claims from the subject and evidence below. "
        "Return JSON: {\"claims\": [...]}. "
        "Each claim MUST use only evidence_ids from allowed_evidence_ids.\n\n"
        + json.dumps(user_payload, indent=2, ensure_ascii=False)
    )

    llm = provider or get_provider(provider_name, model)
    result = llm.complete_json(system, user)
    raw_claims = result.get("claims", [])
    if not isinstance(raw_claims, list):
        return extract_claims_rule(subject, evidence)

    claims: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_claims, start=1):
        if not isinstance(raw, dict):
            continue
        cleaned = sanitize_claim(raw, evidence_ids, i)
        if cleaned:
            claims.append(cleaned)

    if not claims:
        return extract_claims_rule(subject, evidence)
    return claims


def extract_claims(
    subject: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    mode: str = "auto",
    provider: str | None = None,
    model: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Extract claims using rule, llm, or auto mode.
    Returns (claims, method_description).
    """
    from vsa.config import llm_available

    mode = mode.lower()
    if mode == "rule":
        return extract_claims_rule(subject, evidence), "rule-based"

    if mode == "llm" or (mode == "auto" and llm_available()):
        try:
            claims = extract_claims_llm(subject, evidence, provider_name=provider, model=model)
            from vsa.config import default_llm_provider
            stack = f"llm/{provider or default_llm_provider()}"
            if model:
                stack += f"/{model}"
            return claims, stack
        except Exception as exc:
            if mode == "llm":
                raise RuntimeError(
                    f"LLM claim extraction failed ({exc}). "
                    "Try --claim-mode auto for rule-based fallback, or check network/TLS (.env VSA_SSL_VERIFY)."
                ) from exc
            return extract_claims_rule(subject, evidence), "rule-based (llm fallback)"

    return extract_claims_rule(subject, evidence), "rule-based"
