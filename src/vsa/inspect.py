"""Report inspection utilities."""

from __future__ import annotations

from typing import Any


def inspect_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return a structured summary for CLI inspect."""
    subject = report.get("subject", {})
    claims = report.get("claims", [])
    evidence = report.get("evidence", [])
    vr = report.get("validation_results", {})
    prov = report.get("provenance", {})

    boundaries: dict[str, int] = {}
    for c in claims:
        b = c.get("review_boundary", "unknown")
        boundaries[b] = boundaries.get(b, 0) + 1

    sources: dict[str, int] = {}
    for e in evidence if isinstance(evidence, list) else []:
        s = e.get("source_name", "unknown")
        sources[s] = sources.get(s, 0) + 1

    failed_checks = [c for c in vr.get("checks", []) if c.get("status") == "fail"]
    warn_checks = [c for c in vr.get("checks", []) if c.get("status") == "warn"]

    return {
        "report_id": report.get("report_id"),
        "schema_version": report.get("schema_version"),
        "subject": {
            "entity_type": subject.get("entity_type"),
            "display_name": subject.get("display_name"),
        },
        "counts": {
            "claims": len(claims),
            "evidence": len(evidence) if isinstance(evidence, list) else 0,
            "contradictions": len(report.get("contradictions", [])),
        },
        "review_boundaries": boundaries,
        "evidence_sources": sources,
        "validation_status": vr.get("status"),
        "failed_checks": failed_checks,
        "warnings": warn_checks,
        "provenance": {
            "report_hash": prov.get("report_hash"),
            "evidence_bundle_hash": prov.get("evidence_bundle_hash"),
        },
        "human_review": report.get("human_review", {}),
    }


def format_inspect(summary: dict[str, Any]) -> str:
    lines = [
        f"Report: {summary.get('report_id')} (schema {summary.get('schema_version')})",
        f"Subject: {summary.get('subject', {}).get('display_name')} [{summary.get('subject', {}).get('entity_type')}]",
        "",
        "Counts:",
        f"  claims: {summary['counts']['claims']}",
        f"  evidence: {summary['counts']['evidence']}",
        f"  contradictions: {summary['counts']['contradictions']}",
        "",
        f"Validation: {summary.get('validation_status')}",
        f"Report hash: {summary.get('provenance', {}).get('report_hash')}",
        "",
        "Review boundaries:",
    ]
    for k, v in summary.get("review_boundaries", {}).items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Evidence sources:")
    for k, v in summary.get("evidence_sources", {}).items():
        lines.append(f"  {k}: {v}")
    if summary.get("failed_checks"):
        lines.append("")
        lines.append("Failed checks:")
        for c in summary["failed_checks"]:
            lines.append(f"  - {c.get('name')}: {c.get('message')}")
    if summary.get("warnings"):
        lines.append("")
        lines.append("Warnings:")
        for c in summary["warnings"]:
            lines.append(f"  - {c.get('name')}: {c.get('message')}")
    return "\n".join(lines)
