#!/usr/bin/env python3
"""Render a compact Markdown report from a claim ledger."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def render(ledger: dict[str, Any]) -> str:
    subject = ledger["subject"]
    lines: list[str] = []
    lines.append(f"# Generated evidence report: {subject.get('gene_symbol', 'Unknown')} {subject.get('variant_hgvs_c', '')}")
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append("Research demo only. Human expert review is required before any clinical or operational use.")
    lines.append("")
    lines.append("## Subject")
    lines.append("")
    for key in ["gene_symbol", "transcript", "variant_hgvs_c", "variant_hgvs_p", "protein_accession", "condition_or_context"]:
        value = subject.get(key)
        if value:
            lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Claims")
    lines.append("")
    lines.append("| ID | Type | Claim | Support | Verification |")
    lines.append("|---|---|---|---|---|")
    for claim in ledger["claims"]:
        status = claim.get("verification", {}).get("status", "unknown")
        text = str(claim.get("claim_text", "")).replace("|", " ")
        lines.append(f"| {claim['claim_id']} | {claim.get('claim_type', '')} | {text} | {claim.get('support_level', '')} | {status} |")
    lines.append("")
    lines.append("## Evidence register")
    lines.append("")
    for claim in ledger["claims"]:
        lines.append(f"### {claim['claim_id']}")
        for ev in claim.get("evidence", []):
            lines.append(f"- {ev['source_name']} ({ev['source_type']}): {ev['retrieval_path']}")
            lines.append(f"  - Role: {ev['evidence_role']}")
            lines.append(f"  - Evidence: {ev['quoted_or_structured_evidence']}")
        lines.append("")
    assessment = ledger.get("report_level_assessment", {})
    lines.append("## Report-level assessment")
    lines.append("")
    lines.append(f"- Overall status: {assessment.get('overall_status', 'unknown')}")
    lines.append(f"- Human review required: {assessment.get('human_review_required', True)}")
    lines.append(f"- Blocking issues: {assessment.get('blocking_issues', [])}")
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Markdown report from a claim ledger.")
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = render(load_json(args.ledger))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
