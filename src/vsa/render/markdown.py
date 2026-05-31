"""Markdown report renderer."""

from __future__ import annotations

from typing import Any


def render_markdown(report: dict[str, Any]) -> str:
    subject = report.get("subject", {})
    lines: list[str] = []

    lines.append(f"# Scientific Report: {subject.get('display_name', 'Unknown subject')}")
    lines.append("")
    lines.append("> Research infrastructure artifact. Human expert review required before clinical use.")
    lines.append("")

    # Executive summary
    lines.append("## Executive summary")
    lines.append("")
    vr = report.get("validation_results", {})
    hr = report.get("human_review", {})
    lines.append(f"- **Validation status:** {vr.get('status', 'unknown')}")
    lines.append(f"- **Human review:** {hr.get('status', 'unknown')} (required: {hr.get('required', True)})")
    lines.append(f"- **Claims:** {len(report.get('claims', []))}")
    lines.append(f"- **Evidence items:** {len(report.get('evidence', []))}")
    lines.append(f"- **Contradictions:** {len(report.get('contradictions', []))}")
    lines.append("")

    # Subject
    lines.append("## Subject")
    lines.append("")
    for key, value in subject.items():
        if value:
            lines.append(f"- **{key}:** {value}")
    lines.append("")

    # Evidence table
    lines.append("## Evidence table")
    lines.append("")
    lines.append("| ID | Source | Type | Identifier | Quality | Summary |")
    lines.append("|---|---|---|---|---|---|")
    for ev in report.get("evidence", []):
        qs = ev.get("quality_score", {})
        score = qs.get("score", "—")
        summary = str(ev.get("summary", "")).replace("|", "/")[:80]
        lines.append(
            f"| {ev.get('evidence_id')} | {ev.get('source_name')} | {ev.get('source_type')} "
            f"| {ev.get('identifier')} | {score} | {summary} |"
        )
    lines.append("")

    # Claim table
    lines.append("## Claim table")
    lines.append("")
    lines.append("| ID | Type | Boundary | Confidence | Claim | Evidence |")
    lines.append("|---|---|---|---|---|---|")
    for claim in report.get("claims", []):
        text = str(claim.get("claim_text", "")).replace("|", "/")[:100]
        eids = ", ".join(claim.get("evidence_ids", []))
        lines.append(
            f"| {claim.get('claim_id')} | {claim.get('claim_type')} | {claim.get('review_boundary')} "
            f"| {claim.get('confidence')} | {text} | {eids} |"
        )
    lines.append("")

    # Contradictions
    contradictions = report.get("contradictions", [])
    lines.append("## Contradictions")
    lines.append("")
    if contradictions:
        for c in contradictions:
            lines.append(f"- **{c.get('contradiction_id')}** ({c.get('severity')}): {c.get('description')}")
            lines.append(f"  - Claims: {c.get('claim_ids')}; Evidence: {c.get('evidence_ids')}")
    else:
        lines.append("_No contradictions detected._")
    lines.append("")

    # Review status
    lines.append("## Review status")
    lines.append("")
    lines.append(f"- Required: {hr.get('required')}")
    lines.append(f"- Status: {hr.get('status')}")
    if hr.get("reviewer_identity"):
        lines.append(f"- Reviewer: {hr.get('reviewer_identity')}")
    if hr.get("approved_claim_ids"):
        lines.append(f"- Approved claims: {hr.get('approved_claim_ids')}")
    lines.append("")

    # Provenance
    prov = report.get("provenance", {})
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Report hash: `{prov.get('report_hash', '—')}`")
    lines.append(f"- Evidence bundle hash: `{prov.get('evidence_bundle_hash', '—')}`")
    lines.append(f"- Validation version: {prov.get('validation_version')}")
    lines.append(f"- Renderer version: {prov.get('renderer_version')}")
    lines.append("")

    # Reproducibility
    repro = prov.get("reproducibility", {})
    lines.append("## Reproducibility instructions")
    lines.append("")
    lines.append(f"- Input hash: `{repro.get('input_hash', '—')}`")
    lines.append(f"- Cache directory: `{repro.get('cache_dir', '.vsa_cache')}`")
    lines.append(f"- {repro.get('instructions', 'Re-run build with same input and cache.')}")
    lines.append("")

    # Validation checks
    lines.append("## Validation checks")
    lines.append("")
    for check in vr.get("checks", []):
        icon = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(check.get("status"), "?")
        lines.append(f"- [{icon}] {check.get('name')}: {check.get('message')}")
    lines.append("")

    return "\n".join(lines)
