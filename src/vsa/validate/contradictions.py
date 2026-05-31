"""Contradiction detection across evidence and claims."""

from __future__ import annotations

from typing import Any


def _clinical_significance(evidence: dict[str, Any]) -> str | None:
    meta = evidence.get("domain_metadata") or {}
    sig = meta.get("clinical_significance") or meta.get("significance")
    if sig:
        return str(sig).lower()
    summary = str(evidence.get("summary", "")).lower()
    for term in ("pathogenic", "likely pathogenic", "benign", "likely benign", "uncertain significance", "vus"):
        if term in summary:
            return term
    return None


def _sig_category(sig: str) -> str:
    if "pathogenic" in sig and "likely" not in sig:
        return "pathogenic"
    if "likely pathogenic" in sig:
        return "likely_pathogenic"
    if "benign" in sig:
        return "benign"
    if "uncertain" in sig or "vus" in sig:
        return "vus"
    return "other"


def detect_contradictions(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect explicit contradictions in evidence and claims."""
    contradictions: list[dict[str, Any]] = []
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    claims = report.get("claims", [])

    sig_map: dict[str, list[str]] = {}
    for eid, ev in evidence_by_id.items():
        sig = _clinical_significance(ev)
        if sig:
            sig_map.setdefault(_sig_category(sig), []).append(eid)

    conflict_pairs = [
        ("pathogenic", "vus", "high"),
        ("pathogenic", "benign", "high"),
        ("likely_pathogenic", "vus", "high"),
        ("likely_pathogenic", "benign", "medium"),
    ]
    seen: set[tuple[str, str]] = set()
    for cat_a, cat_b, severity in conflict_pairs:
        ids_a = sig_map.get(cat_a, [])
        ids_b = sig_map.get(cat_b, [])
        if ids_a and ids_b:
            key = tuple(sorted([cat_a, cat_b]))
            if key in seen:
                continue
            seen.add(key)
            related_claims = [
                c["claim_id"]
                for c in claims
                if set(c.get("evidence_ids", [])) & (set(ids_a) | set(ids_b))
            ]
            contradictions.append(
                {
                    "contradiction_id": f"CONFLICT-{len(contradictions) + 1:03d}",
                    "claim_ids": related_claims,
                    "evidence_ids": ids_a + ids_b,
                    "description": (
                        f"Conflicting clinical significance categories: {cat_a!r} vs {cat_b!r} "
                        f"across evidence {ids_a} and {ids_b}."
                    ),
                    "severity": severity,
                }
            )

    # Predicted structure vs experimental claim language
    for claim in claims:
        text = str(claim.get("claim_text", "")).lower()
        if "experimental structure" in text or "experimentally determined" in text:
            for eid in claim.get("evidence_ids", []):
                ev = evidence_by_id.get(eid)
                if ev and (ev.get("domain_metadata") or {}).get("structure_type") == "predicted":
                    contradictions.append(
                        {
                            "contradiction_id": f"CONFLICT-{len(contradictions) + 1:03d}",
                            "claim_ids": [claim["claim_id"]],
                            "evidence_ids": [eid],
                            "description": (
                                f"Claim {claim['claim_id']} implies experimental structure but "
                                f"{eid} is a predicted AlphaFold model."
                            ),
                            "severity": "medium",
                        }
                    )

    # Evidence explicitly marked as contradicts
    for claim in claims:
        for eid in claim.get("evidence_ids", []):
            ev = evidence_by_id.get(eid)
            if ev and ev.get("evidence_role") == "contradicts":
                contradictions.append(
                    {
                        "contradiction_id": f"CONFLICT-{len(contradictions) + 1:03d}",
                        "claim_ids": [claim["claim_id"]],
                        "evidence_ids": [eid],
                        "description": f"Evidence {eid} explicitly contradicts claim {claim['claim_id']}.",
                        "severity": "medium",
                    }
                )

    # Ambiguous ClinVar with high-confidence classification claim
    for claim in claims:
        if claim.get("claim_type") != "classification":
            continue
        for eid in claim.get("evidence_ids", []):
            ev = evidence_by_id.get(eid)
            meta = (ev or {}).get("domain_metadata") or {}
            if meta.get("retrieval_ambiguity") and float(claim.get("confidence", 0)) >= 0.8:
                contradictions.append(
                    {
                        "contradiction_id": f"CONFLICT-{len(contradictions) + 1:03d}",
                        "claim_ids": [claim["claim_id"]],
                        "evidence_ids": [eid],
                        "description": (
                            f"High-confidence classification claim {claim['claim_id']} cites "
                            f"ambiguous ClinVar evidence {eid}."
                        ),
                        "severity": "medium",
                    }
                )

    return contradictions
