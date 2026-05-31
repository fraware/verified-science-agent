"""HTML report renderer."""

from __future__ import annotations

import html
from typing import Any

from vsa.render.markdown import render_markdown


def render_html(report: dict[str, Any]) -> str:
    subject = report.get("subject", {})
    vr = report.get("validation_results", {})
    hr = report.get("human_review", {})
    prov = report.get("provenance", {})

    def esc(value: object) -> str:
        return html.escape(str(value))

    claims_rows = ""
    for claim in report.get("claims", []):
        boundary = claim.get("review_boundary", "")
        cls = "speculative" if boundary == "speculative" else "clinical" if "clinical" in boundary else ""
        claims_rows += f"""
        <tr class="{cls}">
          <td>{esc(claim.get('claim_id'))}</td>
          <td>{esc(claim.get('claim_type'))}</td>
          <td><span class="badge">{esc(boundary)}</span></td>
          <td>{esc(claim.get('confidence'))}</td>
          <td>{esc(claim.get('claim_text'))}</td>
          <td>{esc(', '.join(claim.get('evidence_ids', [])))}</td>
        </tr>"""

    evidence_rows = ""
    for ev in report.get("evidence", []):
        qs = ev.get("quality_score", {})
        evidence_rows += f"""
        <tr>
          <td>{esc(ev.get('evidence_id'))}</td>
          <td>{esc(ev.get('source_name'))}</td>
          <td>{esc(ev.get('source_type'))}</td>
          <td><a href="{esc(ev.get('retrieval_path'))}">{esc(ev.get('identifier'))}</a></td>
          <td>{esc(qs.get('score', '—'))}</td>
          <td>{esc(ev.get('summary'))}</td>
        </tr>"""

    conflict_section = ""
    for c in report.get("contradictions", []):
        conflict_section += f"""
        <div class="conflict">
          <strong>{esc(c.get('contradiction_id'))}</strong> ({esc(c.get('severity'))}):
          {esc(c.get('description'))}
        </div>"""
    if not conflict_section:
        conflict_section = "<p><em>No contradictions detected.</em></p>"

    checks = ""
    for check in vr.get("checks", []):
        checks += f"<li class='{esc(check.get('status'))}'>{esc(check.get('name'))}: {esc(check.get('message'))}</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Scientific Report — {esc(subject.get('display_name', 'Unknown'))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
    h1, h2 {{ border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.92rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    .badge {{ background: #eee; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.85rem; }}
    .conflict {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 0.75rem; margin: 0.5rem 0; }}
    tr.clinical {{ background: #fde8e8; }}
    tr.speculative {{ background: #f0f4ff; }}
    li.fail {{ color: #b00020; }}
    li.warn {{ color: #856404; }}
    code {{ background: #f5f5f5; padding: 0.1rem 0.3rem; }}
    .meta {{ color: #555; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Scientific Report: {esc(subject.get('display_name', 'Unknown'))}</h1>
  <p class="meta">Research infrastructure artifact. Human expert review required before clinical use.</p>

  <h2>Executive summary</h2>
  <ul>
    <li>Validation: <strong>{esc(vr.get('status'))}</strong></li>
    <li>Human review: {esc(hr.get('status'))} (required: {esc(hr.get('required'))})</li>
    <li>Claims: {len(report.get('claims', []))} | Evidence: {len(report.get('evidence', []))}</li>
  </ul>

  <h2>Evidence table</h2>
  <table>
    <thead><tr><th>ID</th><th>Source</th><th>Type</th><th>Identifier</th><th>Quality</th><th>Summary</th></tr></thead>
    <tbody>{evidence_rows}</tbody>
  </table>

  <h2>Claim table</h2>
  <table>
    <thead><tr><th>ID</th><th>Type</th><th>Boundary</th><th>Conf.</th><th>Claim</th><th>Evidence</th></tr></thead>
    <tbody>{claims_rows}</tbody>
  </table>

  <h2>Contradictions</h2>
  {conflict_section}

  <h2>Provenance</h2>
  <ul>
    <li>Report hash: <code>{esc(prov.get('report_hash'))}</code></li>
    <li>Evidence bundle hash: <code>{esc(prov.get('evidence_bundle_hash'))}</code></li>
  </ul>

  <h2>Validation checks</h2>
  <ul>{checks}</ul>
</body>
</html>"""
