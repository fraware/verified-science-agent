"""Scientific credibility policies for evidence and report warnings."""

from __future__ import annotations

from typing import Any

PREDICTED_STRUCTURE_PHRASE = "predicted structure"
METADATA_ONLY_WARNING = (
    "SCIENTIFIC CREDIBILITY WARNING: All publication evidence is metadata-only. "
    "Claims must not exceed bibliographic facts; abstract or full-text evidence is required "
    "for substantive scientific conclusions."
)
CLINVAR_AMBIGUITY_WARNING = (
    "CLINVAR AMBIGUITY ALERT: One or more ClinVar records were retrieved from an ambiguous "
    "query (multiple closely scored candidates). Do not treat clinical significance as definitive "
    "without expert review and exact variant ID confirmation."
)
GENERIC_AMBIGUITY_WARNING = (
    "RETRIEVAL AMBIGUITY ALERT: Evidence marked ambiguous must not support high-confidence "
    "clinical or classification claims without human review."
)
ALPHAFOLD_WARNING = (
    "STRUCTURE WARNING: AlphaFold coordinates are computationally predicted, not experimentally "
    "determined. Do not cite as experimental structure evidence."
)
MATERIALS_PROJECT_SKIP = "Materials Project: skipped (MATERIALS_PROJECT_API_KEY not configured)"


def _is_ambiguous(item: dict[str, Any]) -> bool:
    meta = item.get("domain_metadata") or {}
    return bool(meta.get("retrieval_ambiguity") or meta.get("gene_search_ambiguous"))


def _cap_reliability(reliability: str) -> str:
    rank = {"high": 3, "medium": 2, "low": 1}
    return "low" if rank.get(reliability, 2) > 1 else reliability


def harden_evidence(evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply credibility caps and emit retrieval warnings that cannot be ignored."""
    warnings: list[str] = []
    hardened: list[dict[str, Any]] = []

    for item in evidence:
        ev = dict(item)
        meta = dict(ev.get("domain_metadata") or {})
        source = ev.get("source_name", "")

        if _is_ambiguous(ev):
            prev = ev.get("reliability", "medium")
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "ambiguous_retrieval"
            if prev == "high":
                warnings.append(
                    f"AMBIGUITY ALERT {source}:{ev.get('identifier')}: reliability reduced "
                    f"from high to low (match_score={meta.get('match_score')})"
                )
            else:
                warnings.append(
                    f"AMBIGUITY ALERT {source}:{ev.get('identifier')}: ambiguous retrieval "
                    f"(match_score={meta.get('match_score')}, rank={meta.get('candidate_rank')})"
                )

        if source == "AlphaFold DB":
            meta.setdefault("structure_type", "predicted")
            summary = str(ev.get("summary", ""))
            if PREDICTED_STRUCTURE_PHRASE not in summary.lower():
                ev["summary"] = f"Predicted structure — {summary}".strip()
            ev["reliability"] = _cap_reliability(str(ev.get("reliability", "medium")))
            if ev["reliability"] != "low":
                ev["reliability"] = "medium"
            warnings.append(
                f"AlphaFold {ev.get('identifier')}: predicted structure only — not experimental"
            )

        ev["domain_metadata"] = meta
        hardened.append(ev)

    return hardened, warnings


def build_credibility_limitations(
    evidence: list[dict[str, Any]],
    *,
    metadata_only_publications: bool = False,
) -> list[str]:
    """Return limitation strings for high-visibility report warnings."""
    limitations: list[str] = []

    if any(e.get("source_name") == "ClinVar" and _is_ambiguous(e) for e in evidence):
        limitations.append(CLINVAR_AMBIGUITY_WARNING)

    if any(_is_ambiguous(e) for e in evidence):
        limitations.append(GENERIC_AMBIGUITY_WARNING)

    if any(e.get("source_name") == "AlphaFold DB" for e in evidence):
        limitations.append(ALPHAFOLD_WARNING)

    if metadata_only_publications:
        limitations.append(METADATA_ONLY_WARNING)

    return limitations
