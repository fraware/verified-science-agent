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


def detect_contradictions(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect explicit contradictions in evidence and claims."""
    contradictions: list[dict[str, Any]] = []
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    claims = report.get("claims", [])

    # Clinical significance conflicts across evidence
    sig_map: dict[str, list[str]] = {}
    for eid, ev in evidence_by_id.items():
        sig = _clinical_significance(ev)
        if sig:
            sig_map.setdefault(sig, []).append(eid)

    conflict_pairs = [
        ("pathogenic", "uncertain significance"),
        ("pathogenic", "benign"),
        ("likely pathogenic", "uncertain significance"),
        ("likely pathogenic", "benign"),
    ]
    seen: set[tuple[str, str]] = set()
    for sig_a, sig_b in conflict_pairs:
        ids_a = sig_map.get(sig_a, [])
        ids_b = sig_map.get(sig_b, [])
        if ids_a and ids_b:
            key = tuple(sorted([sig_a, sig_b]))
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
                        f"Conflicting clinical significance: {sig_a!r} vs {sig_b!r} "
                        f"across sources {ids_a} and {ids_b}."
                    ),
                    "severity": "high",
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

    return contradictions
