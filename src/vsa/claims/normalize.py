"""Claim field normalization for the claim–evidence graph (schema 1.3+)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from vsa.utils import canonical_json

INFERENCE_METHODS = frozenset(
    {"direct_extract", "rule", "llm", "aggregation", "human", "unknown"}
)
REVIEWER_STATUSES = frozenset({"unreviewed", "approved", "rejected", "needs_revision"})

DEFAULT_CONFIDENCE_SEMANTICS = {
    "scale": "unit_interval",
    "min": 0.0,
    "max": 1.0,
    "interpretation": (
        "Heuristic extractor confidence on [0,1]; not a calibrated probability "
        "of scientific truth."
    ),
}


def normalize_claim_text(text: str) -> str:
    """Normalize claim text for stable comparison (whitespace + case)."""
    collapsed = re.sub(r"\s+", " ", (text or "").strip().lower())
    return collapsed


def quote_hash(quote: str) -> str:
    return hashlib.sha256(quote.encode("utf-8")).hexdigest()


def cited_evidence_ids(claim: dict[str, Any]) -> list[str]:
    """Union of supporting, contradicting, and legacy evidence_ids (order-preserving)."""
    seen: set[str] = set()
    out: list[str] = []
    for key in ("supporting_evidence_ids", "contradicting_evidence_ids", "evidence_ids"):
        for eid in claim.get(key) or []:
            if eid not in seen:
                seen.add(eid)
                out.append(str(eid))
    return out


def supporting_ids(claim: dict[str, Any]) -> list[str]:
    if "supporting_evidence_ids" in claim:
        return [str(x) for x in (claim.get("supporting_evidence_ids") or [])]
    # Legacy: evidence_ids are treated as supporting unless boundary is unsupported
    if claim.get("review_boundary") == "unsupported":
        return []
    return [str(x) for x in (claim.get("evidence_ids") or [])]


def contradicting_ids(claim: dict[str, Any]) -> list[str]:
    return [str(x) for x in (claim.get("contradicting_evidence_ids") or [])]


def finalize_claim(
    claim: dict[str, Any],
    *,
    inference_method: str = "rule",
    evidence_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Enrich a claim with 1.3 graph fields; keep evidence_ids in sync for compatibility."""
    out = dict(claim)
    text = str(out.get("claim_text") or "")
    out["claim_text_normalized"] = out.get("claim_text_normalized") or normalize_claim_text(text)

    support = supporting_ids(out)
    contradict = contradicting_ids(out)
    boundary = out.get("review_boundary")

    if boundary == "unsupported":
        support = []
    elif not support and out.get("evidence_ids"):
        support = [str(x) for x in out["evidence_ids"]]

    out["supporting_evidence_ids"] = support
    out["contradicting_evidence_ids"] = contradict
    # Compatibility: evidence_ids = supporting ∪ contradicting (supporting first)
    merged = list(support)
    for eid in contradict:
        if eid not in merged:
            merged.append(eid)
    out["evidence_ids"] = merged

    if "source_spans" not in out:
        out["source_spans"] = []
        if evidence_by_id:
            for eid in support:
                ev = evidence_by_id.get(eid) or {}
                summary = str(ev.get("summary") or "")
                if not summary:
                    continue
                out["source_spans"].append(
                    {
                        "source_id": ev.get("source_id") or "",
                        "evidence_id": eid,
                        "start": 0,
                        "end": min(len(summary), 200),
                        "quote_hash": quote_hash(summary[:200]),
                    }
                )

    method = out.get("inference_method") or inference_method
    if method not in INFERENCE_METHODS:
        method = "unknown"
    out["inference_method"] = method

    if not isinstance(out.get("confidence_semantics"), dict):
        out["confidence_semantics"] = dict(DEFAULT_CONFIDENCE_SEMANTICS)

    if not isinstance(out.get("validation_result"), dict):
        out["validation_result"] = {"status": "pending", "check_ids": []}

    status = out.get("reviewer_status") or "unreviewed"
    if status not in REVIEWER_STATUSES:
        status = "unreviewed"
    out["reviewer_status"] = status

    return out


def finalize_claims(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]] | None = None,
    *,
    inference_method: str = "rule",
) -> list[dict[str, Any]]:
    by_id = {e["evidence_id"]: e for e in (evidence or []) if e.get("evidence_id")}
    return [
        finalize_claim(c, inference_method=inference_method, evidence_by_id=by_id) for c in claims
    ]


def build_claim_evidence_graph(report: dict[str, Any]) -> dict[str, Any]:
    """First-class claim–evidence graph used by validation (not render-only)."""
    claims = report.get("claims") or []
    evidence = report.get("evidence") or []
    evidence_ids = {e.get("evidence_id") for e in evidence if isinstance(e, dict)}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        nodes.append(
            {
                "id": ev.get("evidence_id"),
                "kind": "evidence",
                "source_id": ev.get("source_id"),
                "source_name": ev.get("source_name"),
            }
        )

    for claim in claims:
        if not isinstance(claim, dict):
            continue
        cid = claim.get("claim_id")
        nodes.append(
            {
                "id": cid,
                "kind": "claim",
                "review_boundary": claim.get("review_boundary"),
                "reviewer_status": claim.get("reviewer_status"),
            }
        )
        for eid in supporting_ids(claim):
            edges.append(
                {
                    "from": cid,
                    "to": eid,
                    "relation": "supports",
                    "resolves": eid in evidence_ids,
                }
            )
        for eid in contradicting_ids(claim):
            edges.append(
                {
                    "from": cid,
                    "to": eid,
                    "relation": "contradicts",
                    "resolves": eid in evidence_ids,
                }
            )

    return {
        "schema": "claim_evidence_graph/1.0",
        "nodes": nodes,
        "edges": edges,
        "digest": hashlib.sha256(canonical_json({"nodes": nodes, "edges": edges}).encode()).hexdigest(),
    }
