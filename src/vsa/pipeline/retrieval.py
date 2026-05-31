"""Evidence retrieval pipeline: question → connectors → ranked evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from vsa.connectors import Connector, EvidenceCache, default_connectors
from vsa.connectors.base import NormalizedEvidence
from vsa.connectors.dedup import collect_ambiguity_warnings, dedupe_evidence
from vsa.connectors.materials_project import materials_project_skipped_reason
from vsa.pipeline.subject_parser import parse_input, parse_question
from vsa.telemetry import span
from vsa.scoring.evidence_quality import score_evidence

logger = logging.getLogger(__name__)

CONNECTOR_ROUTING: dict[str, list[str]] = {
    "variant": ["ClinVar", "UniProt", "PubMed", "Europe PMC"],
    "gene": ["UniProt", "ClinVar", "PubMed"],
    "protein": ["UniProt", "AlphaFold DB"],
    "paper": ["OpenAlex", "Crossref", "PubMed", "Europe PMC", "Semantic Scholar"],
    "target": ["UniProt", "OpenAlex", "PubMed"],
    "material": ["Materials Project", "OpenAlex", "PubMed"],
    "chemical": ["PubMed", "OpenAlex"],
    "experiment": ["OpenAlex", "PubMed", "Europe PMC"],
}


@dataclass
class RetrievalResult:
    evidence: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    retrieval_plan: list[str] = field(default_factory=list)


def _rank_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        if "quality_score" not in item:
            item["quality_score"] = score_evidence(item)
    return sorted(items, key=lambda e: e.get("quality_score", {}).get("score", 0), reverse=True)


def select_connectors(
    subject: dict[str, Any],
    connectors: list[Connector] | None = None,
    *,
    cache: EvidenceCache | None = None,
) -> list[Connector]:
    all_connectors = connectors or default_connectors(cache)
    by_name = {c.name: c for c in all_connectors}
    entity_type = subject.get("entity_type", "experiment")
    names = CONNECTOR_ROUTING.get(entity_type, ["OpenAlex", "UniProt"])
    return [by_name[n] for n in names if n in by_name]


def retrieve_evidence(
    subject_or_question: dict[str, Any] | str,
    *,
    cache: EvidenceCache | None = None,
    connectors: list[Connector] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve normalized evidence for a subject or question."""
    result = retrieve_evidence_with_meta(subject_or_question, cache=cache, connectors=connectors)
    return result.evidence


def retrieve_evidence_with_meta(
    subject_or_question: dict[str, Any] | str,
    *,
    cache: EvidenceCache | None = None,
    connectors: list[Connector] | None = None,
) -> RetrievalResult:
    """Retrieve evidence and collect connector warnings."""
    if isinstance(subject_or_question, str):
        subject = parse_question(subject_or_question)
    elif "question" in subject_or_question:
        subject = parse_input(subject_or_question)
    elif "subject" in subject_or_question:
        subject = subject_or_question["subject"]
    else:
        subject = subject_or_question

    with span("retrieve_evidence", entity_type=subject.get("entity_type")):
        cache = cache or EvidenceCache()
        selected = select_connectors(subject, connectors, cache=cache)
        query = dict(subject)
        normalized: list[NormalizedEvidence] = []
        warnings: list[str] = []
        plan = [c.name for c in selected]

        for connector in selected:
            try:
                if connector.name == "Materials Project":
                    skip = materials_project_skipped_reason()
                    if skip:
                        warnings.append(skip)
                        continue
                results = connector.fetch(query)
            except Exception as exc:
                msg = f"{connector.name}: {exc}"
                warnings.append(msg)
                logger.warning("Connector failed: %s", msg)
                continue
            if not results:
                warnings.append(f"{connector.name}: no results for query")
            normalized.extend(results)

        normalized = dedupe_evidence(normalized)
        evidence_items: list[dict[str, Any]] = []
        for idx, item in enumerate(normalized, start=1):
            eid = f"E{idx:03d}"
            evidence_items.append(item.to_dict(eid))

        ranked = _rank_evidence(evidence_items)
        warnings.extend(collect_ambiguity_warnings(ranked))
        return RetrievalResult(evidence=ranked, warnings=warnings, retrieval_plan=plan)


def retrieve(question: str, *, cache_dir: str = ".vsa_cache") -> dict[str, Any]:
    """High-level retrieve returning subject + evidence + warnings."""
    cache = EvidenceCache(cache_dir)
    subject = parse_question(question)
    result = retrieve_evidence_with_meta(subject, cache=cache)
    return {
        "subject": subject,
        "evidence": result.evidence,
        "warnings": result.warnings,
        "retrieval_plan": result.retrieval_plan,
    }
