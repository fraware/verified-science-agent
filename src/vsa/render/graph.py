"""Build Mermaid diagram for claim-evidence-source graph."""

from __future__ import annotations

from typing import Any


def evidence_graph_mermaid(report: dict[str, Any]) -> str:
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    lines = ["graph LR"]
    for claim in report.get("claims", []):
        cid = claim["claim_id"].replace("-", "_")
        lines.append(f'  {cid}["{claim["claim_id"]}<br/>{claim.get("claim_type", "")}"]')
        for eid in claim.get("evidence_ids", []):
            eid_safe = eid.replace("-", "_")
            ev = evidence_by_id.get(eid, {})
            src = ev.get("source_name", "?").replace('"', "'")
            lines.append(f'  {eid_safe}["{eid}<br/>{src}"]')
            lines.append(f"  {cid} --> {eid_safe}")
    for c in report.get("contradictions", []):
        for eid in c.get("evidence_ids", []):
            eid_safe = eid.replace("-", "_")
            lines.append(f"  {eid_safe} -. conflict .-> {eid_safe}")
    return "\n".join(lines)
