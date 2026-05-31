"""Migrate ScientificReport documents across schema versions."""

from __future__ import annotations

from typing import Any

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


def migrate_schema(report: dict[str, Any], *, target: str | None = None) -> dict[str, Any]:
    """Upgrade report fields to target schema version (default: current SCHEMA_VERSION)."""
    target = target or SCHEMA_VERSION
    out = dict(report)
    version = out.get("schema_version", "1.0.0")

    if version == target:
        return out

    subject = out.get("subject") or {}

    if version in ("1.0.0", "1.1.0") and target == "1.2.0":
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
        version = "1.2.0"

    if version == "1.0.0" and target in ("1.1.0", "1.2.0"):
        # 1.0.0 → 1.1.0: signature fields are optional; no structural change required
        if target == "1.1.0":
            out["schema_version"] = "1.1.0"
            version = "1.1.0"
        if target == "1.2.0" and version == "1.0.0":
            return migrate_schema(migrate_schema(out, target="1.1.0"), target="1.2.0")

    if version == "1.1.0" and target == "1.2.0":
        return migrate_schema(out, target="1.2.0")

    if out.get("schema_version") != target:
        raise ValueError(f"unsupported migration: {version} -> {target}")

    return out
