"""Compare two ScientificReport artifacts."""

from __future__ import annotations

from typing import Any


def compare_reports(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Diff two reports on claims, evidence, hashes, and validation."""
    claims_a = {c["claim_id"]: c for c in a.get("claims", [])}
    claims_b = {c["claim_id"]: c for c in b.get("claims", [])}
    evidence_a = {e["evidence_id"]: e for e in a.get("evidence", [])}
    evidence_b = {e["evidence_id"]: e for e in b.get("evidence", [])}

    claim_ids_a = set(claims_a)
    claim_ids_b = set(claims_b)
    evidence_ids_a = set(evidence_a)
    evidence_ids_b = set(evidence_b)

    changed_claims = []
    for cid in claim_ids_a & claim_ids_b:
        if claims_a[cid].get("claim_text") != claims_b[cid].get("claim_text"):
            changed_claims.append(cid)

    hash_a = a.get("provenance", {}).get("report_hash")
    hash_b = b.get("provenance", {}).get("report_hash")

    return {
        "report_a": a.get("report_id"),
        "report_b": b.get("report_id"),
        "hash_match": hash_a == hash_b,
        "report_hash_a": hash_a,
        "report_hash_b": hash_b,
        "claims_only_in_a": sorted(claim_ids_a - claim_ids_b),
        "claims_only_in_b": sorted(claim_ids_b - claim_ids_a),
        "changed_claims": changed_claims,
        "evidence_only_in_a": sorted(evidence_ids_a - evidence_ids_b),
        "evidence_only_in_b": sorted(evidence_ids_b - evidence_ids_a),
        "validation_a": a.get("validation_results", {}).get("status"),
        "validation_b": b.get("validation_results", {}).get("status"),
        "contradictions_a": len(a.get("contradictions", [])),
        "contradictions_b": len(b.get("contradictions", [])),
    }


def format_compare(diff: dict[str, Any]) -> str:
    lines = [
        f"Comparing {diff.get('report_a')} vs {diff.get('report_b')}",
        f"Hash match: {diff.get('hash_match')}",
        f"  A: {diff.get('report_hash_a')}",
        f"  B: {diff.get('report_hash_b')}",
        "",
        f"Validation: {diff.get('validation_a')} vs {diff.get('validation_b')}",
        f"Contradictions: {diff.get('contradictions_a')} vs {diff.get('contradictions_b')}",
        "",
    ]
    if diff.get("claims_only_in_a"):
        lines.append(f"Claims only in A: {diff['claims_only_in_a']}")
    if diff.get("claims_only_in_b"):
        lines.append(f"Claims only in B: {diff['claims_only_in_b']}")
    if diff.get("changed_claims"):
        lines.append(f"Changed claims: {diff['changed_claims']}")
    if diff.get("evidence_only_in_a"):
        lines.append(f"Evidence only in A: {diff['evidence_only_in_a']}")
    if diff.get("evidence_only_in_b"):
        lines.append(f"Evidence only in B: {diff['evidence_only_in_b']}")
    if len(lines) == 8:
        lines.append("Reports are structurally identical on claims and evidence IDs.")
    return "\n".join(lines)
