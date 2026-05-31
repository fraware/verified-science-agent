"""Evidence quality scoring with explainable reasons."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_AUTHORITY: dict[str, float] = {
    "ClinVar": 0.95,
    "UniProt": 0.92,
    "AlphaFold DB": 0.88,
    "PubMed": 0.85,
    "Europe PMC": 0.85,
    "OpenAlex": 0.82,
    "Crossref": 0.80,
    "Semantic Scholar": 0.78,
    "Materials Project": 0.90,
}

SOURCE_TYPE_WEIGHT: dict[str, float] = {
    "database": 0.95,
    "publication": 0.85,
    "structure": 0.88,
    "guideline": 0.90,
    "experiment": 0.80,
    "benchmark": 0.75,
    "preprint": 0.65,
}


def _parse_dt(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (TypeError, ValueError):
        return None


def score_evidence(item: dict[str, Any]) -> dict[str, Any]:
    """Score a single evidence item; returns quality_score dict."""
    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.5

    source_name = str(item.get("source_name", ""))
    source_type = str(item.get("source_type", ""))
    identifier = str(item.get("identifier", ""))
    retrieval_path = str(item.get("retrieval_path", ""))
    raw_hash = str(item.get("raw_record_hash", ""))

    authority = SOURCE_AUTHORITY.get(source_name, 0.7)
    score += authority * 0.25
    reasons.append(f"source authority for {source_name}: {authority:.2f}")

    type_weight = SOURCE_TYPE_WEIGHT.get(source_type, 0.6)
    score += type_weight * 0.20
    reasons.append(f"source type {source_type}: {type_weight:.2f}")

    if identifier and len(identifier) >= 3:
        score += 0.10
        reasons.append("identifier is specific")
    else:
        warnings.append("identifier lacks specificity")
        score -= 0.05

    if retrieval_path.startswith(("http://", "https://")):
        score += 0.08
        reasons.append("retrieval path is a reproducible URL")
    elif retrieval_path:
        score += 0.05
        reasons.append("retrieval path present (non-URL)")
    else:
        warnings.append("missing retrieval path")
        score -= 0.10

    if raw_hash and len(raw_hash) == 64:
        score += 0.12
        reasons.append("raw record hash enables reproducibility")
    else:
        warnings.append("missing or invalid raw_record_hash")
        score -= 0.10

    retrieved_at = _parse_dt(str(item.get("retrieved_at", "")))
    if retrieved_at:
        age_days = (datetime.now(timezone.utc) - retrieved_at).days
        if age_days <= 365:
            score += 0.10
            reasons.append(f"retrieved recently ({age_days} days ago)")
        elif age_days <= 1825:
            score += 0.05
            reasons.append(f"retrieved within 5 years ({age_days} days ago)")
        else:
            warnings.append(f"evidence retrieved {age_days} days ago; may be stale")
    else:
        warnings.append("retrieved_at missing or invalid")

    role = item.get("evidence_role")
    if role == "contradicts":
        reasons.append("marked as contradicting evidence (included for conflict resolution)")

    score = max(0.0, min(1.0, score))
    if score < 0.5:
        warnings.append("low-quality evidence; consider additional sources")

    return {"score": round(score, 3), "reasons": reasons, "warnings": warnings}


def apply_quality_scores(report: dict[str, Any]) -> dict[str, Any]:
    report = dict(report)
    evidence = []
    for item in report.get("evidence", []):
        item = dict(item)
        item["quality_score"] = score_evidence(item)
        evidence.append(item)
    report["evidence"] = evidence
    return report
