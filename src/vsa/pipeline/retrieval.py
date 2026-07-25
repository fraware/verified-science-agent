"""Evidence retrieval pipeline: question → connectors → ranked evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from vsa.connectors import Connector, EvidenceCache, default_connectors
from vsa.connectors.base import NormalizedEvidence
from vsa.connectors.dedup import collect_ambiguity_warnings, dedupe_evidence_with_meta
from vsa.connectors.materials_project import materials_project_skipped_reason
from vsa.connectors.outcomes import (
    CONNECTOR_SKIPPED,
    DUPLICATE_DROPPED,
    EMPTY_RESULT,
    OUTCOME_DEGRADED,
    OUTCOME_EMPTY,
    OUTCOME_SCHEMA_DRIFT,
    OUTCOME_SKIPPED,
    OUTCOME_SUCCESS,
    PARTIAL_RETRIEVAL,
    SCHEMA_DRIFT,
    ConnectorOutcome,
    aggregate_retrieval_status,
    classify_exception,
    looks_schema_drifted,
)
from vsa.pipeline.subject_parser import parse_input, parse_question
from vsa.scoring.evidence_quality import score_evidence
from vsa.telemetry import span

logger = logging.getLogger(__name__)

# Fallback routing when no domain pack is selected (entity_type → connector names).
# Domain packs under vsa.domain_packs override/extend this map.
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
    source_records: list[dict[str, Any]] = field(default_factory=list)
    retrieval_status: str = "complete"
    connector_outcomes: list[ConnectorOutcome] = field(default_factory=list)
    dropped_duplicates: list[dict[str, Any]] = field(default_factory=list)
    domain_pack: str | None = None

    def outcomes_as_dicts(self) -> list[dict[str, Any]]:
        return [o.to_dict() for o in self.connector_outcomes]


def _rank_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        if "quality_score" not in item:
            item["quality_score"] = score_evidence(item)
    return sorted(items, key=lambda e: e.get("quality_score", {}).get("score", 0), reverse=True)


def _routing_table(domain_pack: str | None = None) -> dict[str, list[str]]:
    if not domain_pack:
        return dict(CONNECTOR_ROUTING)
    from vsa.domain_packs import routing_for_pack

    return routing_for_pack(domain_pack)


def select_connectors(
    subject: dict[str, Any],
    connectors: list[Connector] | None = None,
    *,
    cache: EvidenceCache | None = None,
    domain_pack: str | None = None,
) -> list[Connector]:
    explicit = connectors is not None
    all_connectors = connectors if explicit else default_connectors(cache)
    by_name = {c.name: c for c in all_connectors}
    entity_type = subject.get("entity_type", "experiment")
    routing = _routing_table(domain_pack)
    names = routing.get(entity_type, routing.get("experiment", ["OpenAlex", "UniProt"]))
    selected = [by_name[n] for n in names if n in by_name]
    # Explicit connector pools (tests / single-connector injection) must not
    # silently become an empty plan when entity routing excludes them.
    if explicit and not selected:
        return list(all_connectors)
    return selected


def _mark_schema_drift(results: list[NormalizedEvidence]) -> tuple[list[NormalizedEvidence], bool]:
    drifted = False
    for item in results:
        if looks_schema_drifted(item):
            drifted = True
            meta = dict(item.domain_metadata or {})
            meta["schema_drift"] = True
            item.domain_metadata = meta
            if item.reliability == "high":
                item.reliability = "low"
    return results, drifted


def retrieve_evidence(
    subject_or_question: dict[str, Any] | str,
    *,
    cache: EvidenceCache | None = None,
    connectors: list[Connector] | None = None,
    domain_pack: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve normalized evidence for a subject or question."""
    result = retrieve_evidence_with_meta(
        subject_or_question, cache=cache, connectors=connectors, domain_pack=domain_pack
    )
    return result.evidence


def retrieve_evidence_with_meta(
    subject_or_question: dict[str, Any] | str,
    *,
    cache: EvidenceCache | None = None,
    connectors: list[Connector] | None = None,
    domain_pack: str | None = None,
) -> RetrievalResult:
    """Retrieve evidence and collect typed connector outcomes / warnings."""
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
        selected = select_connectors(subject, connectors, cache=cache, domain_pack=domain_pack)
        query = dict(subject)
        normalized: list[NormalizedEvidence] = []
        warnings: list[str] = []
        outcomes: list[ConnectorOutcome] = []
        plan = [c.name for c in selected]

        for connector in selected:
            if connector.name == "Materials Project":
                skip = materials_project_skipped_reason()
                if skip:
                    outcome = ConnectorOutcome(
                        connector=connector.name,
                        status=OUTCOME_SKIPPED,
                        code=CONNECTOR_SKIPPED,
                        warning=skip,
                    )
                    outcomes.append(outcome)
                    formatted = outcome.format_warning()
                    if formatted:
                        warnings.append(formatted)
                    continue
            try:
                results = connector.fetch(query)
            except Exception as exc:
                status, code, message = classify_exception(exc)
                outcome = ConnectorOutcome(
                    connector=connector.name,
                    status=status,
                    code=code,
                    warning=message,
                )
                outcomes.append(outcome)
                formatted = outcome.format_warning()
                if formatted:
                    warnings.append(formatted)
                logger.warning("Connector failed (%s): %s", code, formatted)
                continue

            if not results:
                outcome = ConnectorOutcome(
                    connector=connector.name,
                    status=OUTCOME_EMPTY,
                    code=EMPTY_RESULT,
                    evidence_count=0,
                    warning="no results for query",
                )
                outcomes.append(outcome)
                formatted = outcome.format_warning()
                if formatted:
                    warnings.append(formatted)
                continue

            results, drifted = _mark_schema_drift(results)
            if drifted:
                outcome = ConnectorOutcome(
                    connector=connector.name,
                    status=OUTCOME_SCHEMA_DRIFT,
                    code=SCHEMA_DRIFT,
                    evidence_count=len(results),
                    warning="response missing expected fields; degraded reliability",
                )
                outcomes.append(outcome)
                formatted = outcome.format_warning()
                if formatted:
                    warnings.append(formatted)
            else:
                ambiguous = any(
                    (r.domain_metadata or {}).get("retrieval_ambiguity")
                    or (r.domain_metadata or {}).get("gene_search_ambiguous")
                    for r in results
                )
                outcomes.append(
                    ConnectorOutcome(
                        connector=connector.name,
                        status=OUTCOME_DEGRADED if ambiguous else OUTCOME_SUCCESS,
                        code=None,
                        evidence_count=len(results),
                        details={"ambiguous": ambiguous} if ambiguous else {},
                    )
                )
            normalized.extend(results)

        dedupe = dedupe_evidence_with_meta(normalized)
        for drop in dedupe.dropped:
            warnings.append(
                f"{DUPLICATE_DROPPED}: kept {drop.get('kept_source')}:{drop.get('kept_id')} "
                f"dropped {drop.get('dropped_source')}:{drop.get('dropped_id')}"
            )

        evidence_items: list[dict[str, Any]] = []
        source_records: list[dict[str, Any]] = []
        seen_source_ids: set[str] = set()
        for idx, item in enumerate(dedupe.items, start=1):
            eid = f"E{idx:03d}"
            source_rec = item.to_source_record(query)
            sid = source_rec.source_id
            evidence_items.append(item.to_dict(eid, source_id=sid))
            if sid not in seen_source_ids:
                source_records.append(source_rec.to_dict())
                seen_source_ids.add(sid)
            if item.raw_record:
                cache.set_by_digest(source_rec.content_digest, item.raw_record)

        ranked = _rank_evidence(evidence_items)
        from vsa.scientific.credibility import harden_evidence

        ranked, credibility_warnings = harden_evidence(ranked)
        warnings.extend(credibility_warnings)
        warnings.extend(collect_ambiguity_warnings(ranked))

        retrieval_status = aggregate_retrieval_status(outcomes)
        if retrieval_status in {"partial", "failed"}:
            warnings.append(
                f"{PARTIAL_RETRIEVAL}: retrieval_status={retrieval_status} "
                f"(connectors={len(outcomes)}, evidence={len(ranked)})"
            )

        return RetrievalResult(
            evidence=ranked,
            warnings=warnings,
            retrieval_plan=plan,
            source_records=source_records,
            retrieval_status=retrieval_status,
            connector_outcomes=outcomes,
            dropped_duplicates=list(dedupe.dropped),
            domain_pack=domain_pack,
        )


def retrieve(
    question: str,
    *,
    cache_dir: str = ".vsa_cache",
    domain_pack: str | None = None,
) -> dict[str, Any]:
    """High-level retrieve returning subject + evidence + warnings."""
    cache = EvidenceCache(cache_dir)
    subject = parse_question(question)
    result = retrieve_evidence_with_meta(subject, cache=cache, domain_pack=domain_pack)
    return {
        "subject": subject,
        "evidence": result.evidence,
        "warnings": result.warnings,
        "retrieval_plan": result.retrieval_plan,
        "retrieval_status": result.retrieval_status,
        "connector_outcomes": result.outcomes_as_dicts(),
        "domain_pack": result.domain_pack,
    }
