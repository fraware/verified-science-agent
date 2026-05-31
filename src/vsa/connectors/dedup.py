"""Cross-connector evidence deduplication."""

from __future__ import annotations

import re
from typing import Any

from vsa.connectors.base import NormalizedEvidence

PAPER_SOURCES = frozenset({"OpenAlex", "Crossref", "PubMed", "Europe PMC", "Semantic Scholar"})


def _normalize_doi(value: str) -> str:
    return value.lower().strip().removeprefix("https://doi.org/").removeprefix("doi:")


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())[:120]


def _paper_keys(item: NormalizedEvidence) -> set[str]:
    keys: set[str] = set()
    meta = item.domain_metadata or {}
    raw = item.raw_record or {}
    doi = meta.get("doi") or raw.get("DOI") or raw.get("doi")
    if doi:
        keys.add(f"doi:{_normalize_doi(str(doi))}")
    pmid = meta.get("pmid") or raw.get("pmid") or raw.get("PMID")
    if pmid:
        keys.add(f"pmid:{str(pmid).strip()}")
    title = meta.get("title") or raw.get("title") or item.summary
    year = meta.get("year") or raw.get("publication_year") or raw.get("year")
    if title:
        keys.add(f"title:{_normalize_title(str(title))}|{year or ''}")
    return keys


def _prefer(a: NormalizedEvidence, b: NormalizedEvidence) -> bool:
    rank = {"high": 3, "medium": 2, "low": 1}
    ra = rank.get(a.reliability, 0)
    rb = rank.get(b.reliability, 0)
    if ra != rb:
        return ra > rb
    sa = float((a.domain_metadata or {}).get("match_score", 0))
    sb = float((b.domain_metadata or {}).get("match_score", 0))
    return sa >= sb


def dedupe_evidence(items: list[NormalizedEvidence]) -> list[NormalizedEvidence]:
    """Merge duplicate publication records; preserve first-seen order."""
    key_to_index: dict[str, int] = {}
    output: list[NormalizedEvidence] = []

    for item in items:
        if item.source_name in PAPER_SOURCES:
            keys = _paper_keys(item) or {f"{item.source_name}:{item.identifier}"}
            existing_idx = next((key_to_index[k] for k in keys if k in key_to_index), None)
            if existing_idx is not None:
                if _prefer(item, output[existing_idx]):
                    output[existing_idx] = item
                continue
            idx = len(output)
            output.append(item)
            for key in keys:
                key_to_index[key] = idx
        else:
            key = f"{item.source_name}:{item.identifier}"
            if key in key_to_index:
                continue
            key_to_index[key] = len(output)
            output.append(item)

    return output


def collect_ambiguity_warnings(evidence: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for ev in evidence:
        meta = ev.get("domain_metadata") or {}
        if meta.get("retrieval_ambiguity"):
            warnings.append(
                f"{ev.get('source_name')}:{ev.get('identifier')}: ambiguous retrieval "
                f"(match_score={meta.get('match_score')}, rank={meta.get('candidate_rank')})"
            )
        if meta.get("entry_type") == "unreviewed":
            warnings.append(f"UniProt {ev.get('identifier')}: TrEMBL (unreviewed) entry")
        if meta.get("structure_type") == "predicted":
            warnings.append(f"AlphaFold {ev.get('identifier')}: predicted structure, not experimental")
    return warnings
