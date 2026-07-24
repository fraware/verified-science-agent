"""Integration envelope builder for stable cross-stack identity."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from vsa import __version__
from vsa.companion_schema import schema_digest, validate_companion
from vsa.provenance.hashchain import build_provenance, sha256_hex
from vsa.utils import canonical_json
from vsa.version import (
    ENVELOPE_SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
    VALIDATION_VERSION,
)

ENVELOPE_SCHEMA_NAME = "integration_envelope.schema.json"
NON_CLAIMS = {
    "authorizes_actions": False,
    "executes_tools": False,
    "issues_grants": False,
    "certifies_scientific_correctness": False,
}


def _stable_uuid(namespace: str, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "|".join((namespace, *parts))))


def build_envelope(
    report: dict[str, Any],
    *,
    cutoff: str | None = None,
    candidate_action_id: str | None = None,
    bundle_hash: str | None = None,
    akta_record_ref: str | None = None,
    source_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Build an IntegrationEnvelope beside a ScientificReport (1.0–1.2).

    Does not mutate the report. Fail closed if report_id or report_hash cannot be derived.
    """
    report_id = report.get("report_id")
    if not report_id:
        raise ValueError("report missing report_id")

    schema_version = report.get("schema_version")
    if schema_version not in ("1.0.0", "1.1.0", "1.2.0"):
        raise ValueError(
            f"unsupported ScientificReport schema_version for envelope: {schema_version!r}"
        )

    provenance = report.get("provenance") or build_provenance(report)
    report_hash = provenance.get("report_hash")
    if not report_hash:
        raise ValueError("report missing provenance.report_hash")

    subject = report.get("subject") or {}
    question_seed = (
        str(subject.get("display_name") or "")
        or str(subject.get("gene_symbol") or "")
        or str(report_id)
    )
    scientific_question_id = _stable_uuid("vsa:scientific_question", question_seed, str(report_id))
    snapshot_id = source_snapshot_id or _stable_uuid(
        "vsa:source_snapshot",
        str(report_id),
        str(report_hash),
        cutoff or "",
    )

    generated = (provenance.get("generated_by") or {}) if isinstance(provenance, dict) else {}
    claim_ids = [str(c["claim_id"]) for c in report.get("claims", []) if c.get("claim_id")]

    envelope: dict[str, Any] = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "scientific_question_id": scientific_question_id,
        "evidence_report_id": str(report_id),
        "claim_ids": claim_ids,
        "candidate_action_id": candidate_action_id,
        "source_snapshot_id": snapshot_id,
        "decision_time_cutoff": cutoff,
        "producer": {
            "package_version": __version__,
            "model_or_checkpoint_id": generated.get("model_or_agent_stack"),
            "validation_version": str(provenance.get("validation_version") or VALIDATION_VERSION),
            "prompt_template_version": generated.get("prompt_template_version")
            or PROMPT_TEMPLATE_VERSION,
        },
        "akta_record_ref": akta_record_ref,
        "digests": {
            "report_hash": str(report_hash),
            "bundle_hash": bundle_hash,
            "envelope_schema_digest": schema_digest(ENVELOPE_SCHEMA_NAME),
            "report_schema_digest": schema_digest("scientific_report.schema.json"),
        },
        "non_claims": dict(NON_CLAIMS),
    }

    errors = validate_companion(ENVELOPE_SCHEMA_NAME, envelope)
    if errors:
        raise ValueError("envelope schema validation failed: " + "; ".join(errors))
    return envelope


def validate_envelope(envelope: dict[str, Any]) -> list[str]:
    """Validate envelope schema version and JSON Schema; fail closed on unknown versions."""
    version = envelope.get("schema_version")
    if version != ENVELOPE_SCHEMA_VERSION:
        return [
            f"envelope schema_version unsupported: {version!r}; "
            f"supported: {ENVELOPE_SCHEMA_VERSION}"
        ]
    return validate_companion(ENVELOPE_SCHEMA_NAME, envelope)


def write_envelope_beside_report(
    report: dict[str, Any],
    report_path: Path,
    *,
    cutoff: str | None = None,
    candidate_action_id: str | None = None,
    bundle_hash: str | None = None,
) -> Path:
    """Write envelope.json next to a report path. Does not embed into the report."""
    import json

    envelope = build_envelope(
        report,
        cutoff=cutoff,
        candidate_action_id=candidate_action_id,
        bundle_hash=bundle_hash,
    )
    out = report_path.parent / "envelope.json"
    out.write_text(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def envelope_content_hash(envelope: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(envelope))
