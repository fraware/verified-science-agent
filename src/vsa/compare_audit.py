"""Compare audit artifacts across runs."""

from __future__ import annotations

from typing import Any


def compare_audits(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Diff two audit JSON artifacts."""
    audits_a = {c.get("claim_id"): c for c in a.get("claim_audits", []) if c.get("claim_id")}
    audits_b = {c.get("claim_id"): c for c in b.get("claim_audits", []) if c.get("claim_id")}

    status_changes: list[dict[str, str]] = []
    for cid in sorted(set(audits_a) & set(audits_b)):
        sa = audits_a[cid].get("status")
        sb = audits_b[cid].get("status")
        if sa != sb:
            status_changes.append({"claim_id": cid, "status_a": sa, "status_b": sb})

    return {
        "overall_status_a": a.get("overall_status"),
        "overall_status_b": b.get("overall_status"),
        "overall_changed": a.get("overall_status") != b.get("overall_status"),
        "verifier_method_a": a.get("verifier_method"),
        "verifier_method_b": b.get("verifier_method"),
        "report_hash_a": a.get("report_hash"),
        "report_hash_b": b.get("report_hash"),
        "report_hash_match": a.get("report_hash") == b.get("report_hash"),
        "claims_only_in_a": sorted(set(audits_a) - set(audits_b)),
        "claims_only_in_b": sorted(set(audits_b) - set(audits_a)),
        "status_changes": status_changes,
        "report_issues_a": a.get("report_issues", []),
        "report_issues_b": b.get("report_issues", []),
    }


def format_compare_audits(diff: dict[str, Any]) -> str:
    lines = [
        f"Audit overall: {diff.get('overall_status_a')} -> {diff.get('overall_status_b')}",
        f"Report hash match: {diff.get('report_hash_match')}",
        f"  A: {diff.get('report_hash_a')}",
        f"  B: {diff.get('report_hash_b')}",
        "",
    ]
    if diff.get("status_changes"):
        lines.append("Claim status changes:")
        for row in diff["status_changes"]:
            lines.append(f"  {row['claim_id']}: {row['status_a']} -> {row['status_b']}")
    if diff.get("claims_only_in_a"):
        lines.append(f"Claims only in A: {diff['claims_only_in_a']}")
    if diff.get("claims_only_in_b"):
        lines.append(f"Claims only in B: {diff['claims_only_in_b']}")
    if len(lines) == 4:
        lines.append("Audits are identical on claim statuses.")
    return "\n".join(lines)
