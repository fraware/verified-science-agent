"""PDF report renderer (optional fpdf2 dependency)."""

from __future__ import annotations

from typing import Any


def render_pdf(report: dict[str, Any]) -> bytes:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("PDF rendering requires: pip install verified-science-agent[pdf]") from exc

    subject = report.get("subject", {})
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Scientific Report: {subject.get('display_name', 'Unknown')}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, "Research infrastructure artifact. Human expert review required before clinical use.")
    pdf.ln(4)

    vr = report.get("validation_results", {})
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Executive summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Validation: {vr.get('status', '?')} | Claims: {len(report.get('claims', []))} | Evidence: {len(report.get('evidence', []))}", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Claims", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for claim in report.get("claims", []):
        text = (
            f"[{claim.get('claim_id')}] ({claim.get('review_boundary')}) "
            f"{claim.get('claim_text', '')[:300]}"
        )
        pdf.multi_cell(0, 5, text)
        pdf.ln(1)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Evidence", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for ev in report.get("evidence", []):
        line = f"{ev.get('evidence_id')} | {ev.get('source_name')} | {ev.get('summary', '')[:200]}"
        pdf.multi_cell(0, 5, line)
        pdf.ln(1)

    prov = report.get("provenance", {})
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Provenance", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, f"Report hash: {prov.get('report_hash', '?')}")
    pdf.multi_cell(0, 5, f"Evidence bundle hash: {prov.get('evidence_bundle_hash', '?')}")

    return pdf.output()
