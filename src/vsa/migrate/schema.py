"""Migrate ScientificReport documents across schema versions."""

from __future__ import annotations

from typing import Any

from vsa.claims.normalize import build_claim_evidence_graph, finalize_claims
from vsa.provenance.source_record import ensure_source_records
from vsa.safety import disclaimer_for_subject
from vsa.version import SCHEMA_VERSION


def _domain_from_subject(subject: dict[str, Any]) -> str:
    entity = subject.get("entity_type", "experiment")
    mapping = {
        "variant": "genomics",
        "gene": "genomics",
        "protein": "protein",
        "paper": "literature",
        "material": "materials",
        "molecule": "chemistry",
        "target": "drug_target",
        "chemical": "chemistry",
    }
    return mapping.get(entity, entity)


def _migrate_to_1_2(out: dict[str, Any]) -> dict[str, Any]:
    subject = out.get("subject") or {}
    out.setdefault("input_question", subject.get("display_name", ""))
    out.setdefault("domain", _domain_from_subject(subject))
    out.setdefault("retrieval_plan", [])
    out.setdefault("retrieval_warnings", [])
    out.setdefault("evidence_selection_method", "connector_ranking_by_quality_score")
    out.setdefault(
        "claim_generation_method",
        (out.get("provenance") or {}).get("generated_by", {}).get("model_or_agent_stack", "unknown"),
    )
    out.setdefault("review_policy", "human_review_required_for_clinical_and_speculative_claims")
    out.setdefault("limitations", [disclaimer_for_subject(subject)])
    out["schema_version"] = "1.2.0"
    return out


def _migrate_to_1_3(out: dict[str, Any]) -> dict[str, Any]:
    """SourceRecord authority + claim–evidence graph fields."""
    evidence = list(out.get("evidence") or [])
    source_records = list(out.get("source_records") or [])
    evidence, source_records = ensure_source_records(evidence, source_records)
    out["evidence"] = evidence
    out["source_records"] = source_records

    claims = finalize_claims(list(out.get("claims") or []), evidence, inference_method="rule")
    out["claims"] = claims
    out["claim_evidence_graph"] = build_claim_evidence_graph(out)
    out["schema_version"] = "1.3.0"
    return out


def migrate_schema(report: dict[str, Any], *, target: str | None = None) -> dict[str, Any]:
    """Upgrade report fields to target schema version (default: current SCHEMA_VERSION)."""
    target = target or SCHEMA_VERSION
    out = dict(report)
    version = out.get("schema_version", "1.0.0")

    if version == target:
        return out

    order = ["1.0.0", "1.1.0", "1.2.0", "1.3.0"]
    if version not in order or target not in order:
        raise ValueError(f"unsupported migration: {version} -> {target}")
    if order.index(version) > order.index(target):
        raise ValueError(f"downgrade not supported: {version} -> {target}")

    # Walk forward one step at a time
    while out.get("schema_version", version) != target:
        current = out.get("schema_version", version)
        if current == "1.0.0":
            out["schema_version"] = "1.1.0"
        elif current == "1.1.0":
            out = _migrate_to_1_2(out)
        elif current == "1.2.0":
            out = _migrate_to_1_3(out)
        else:
            raise ValueError(f"unsupported migration step from {current}")

    if out.get("schema_version") != target:
        raise ValueError(f"unsupported migration: {version} -> {target}")

    return out
