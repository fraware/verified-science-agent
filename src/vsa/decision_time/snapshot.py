"""Build immutable DecisionTimeEvidenceBundle snapshots."""

from __future__ import annotations

import uuid
from typing import Any

from vsa import __version__
from vsa.companion_schema import schema_digest, validate_companion
from vsa.decision_time.cutoff import apply_cutoff_filter
from vsa.decision_time.metrics import privacy_safe_metrics
from vsa.decision_time.pcs import build_portable_refs
from vsa.provenance.hashchain import hash_source_records, sha256_hex
from vsa.utils import canonical_json
from vsa.validate.contradictions import detect_contradictions
from vsa.version import (
    DECISION_TIME_BUNDLE_SCHEMA_VERSION,
    PROMPT_TEMPLATE_VERSION,
    VALIDATION_VERSION,
)

BUNDLE_SCHEMA_NAME = "decision_time_evidence_bundle.schema.json"
NON_CLAIMS = {
    "authorizes_actions": False,
    "executes_tools": False,
    "issues_grants": False,
    "certifies_scientific_correctness": False,
}


def _bundle_core_for_hash(bundle: dict[str, Any]) -> dict[str, Any]:
    """Canonical material covered by bundle_hash (excludes integrity.signature)."""
    return {
        "schema_version": bundle.get("schema_version"),
        "bundle_id": bundle.get("bundle_id"),
        "source_snapshot_id": bundle.get("source_snapshot_id"),
        "evidence_report_id": bundle.get("evidence_report_id"),
        "scientific_question_id": bundle.get("scientific_question_id"),
        "decision_time_cutoff": bundle.get("decision_time_cutoff"),
        "mode": bundle.get("mode"),
        "query": bundle.get("query"),
        "included_evidence": bundle.get("included_evidence"),
        "excluded_post_cutoff": bundle.get("excluded_post_cutoff"),
        "claims": bundle.get("claims"),
        "contradictions": bundle.get("contradictions"),
        "uncertainty": bundle.get("uncertainty"),
        "source_quality_warnings": bundle.get("source_quality_warnings"),
        "unresolved_questions": bundle.get("unresolved_questions"),
        "candidate_action_evidence_requirements": bundle.get(
            "candidate_action_evidence_requirements"
        ),
        "portable_refs": bundle.get("portable_refs"),
        "producer": bundle.get("producer"),
        "privacy_safe_metrics": bundle.get("privacy_safe_metrics"),
        "non_claims": bundle.get("non_claims"),
    }


def compute_bundle_hash(bundle: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(_bundle_core_for_hash(bundle)))


def _claims_for_included(
    claims: list[dict[str, Any]],
    included_ids: set[str],
) -> list[dict[str, Any]]:
    """Keep claims whose evidence_ids intersect included set; drop dangling post-cutoff-only claims."""
    kept: list[dict[str, Any]] = []
    for claim in claims:
        eids = [e for e in claim.get("evidence_ids", []) if e in included_ids]
        if not eids and claim.get("evidence_ids"):
            # Claim only supported by excluded evidence — omit from frozen package
            continue
        c = dict(claim)
        if claim.get("evidence_ids"):
            c["evidence_ids"] = eids
        kept.append(c)
    return kept


def build_decision_time_bundle(
    source: dict[str, Any],
    *,
    cutoff: str,
    mode: str = "retrospective",
    candidate_action_id: str | None = None,
    question: str | None = None,
    retrieval_params: dict[str, Any] | None = None,
    sign: bool = False,
    key_path: str | None = None,
) -> dict[str, Any]:
    """Build a DecisionTimeEvidenceBundle from a ScientificReport or evidence-bearing input.

    Retrospective mode requires timestamps and digests on all source evidence (fail closed).
    Mode shadow marks prospective generation without tool execution.
    """
    if mode not in ("retrospective", "shadow", "read_only"):
        raise ValueError(f"unsupported mode: {mode!r}")
    # All modes fail closed on missing digests/timestamps. Mode only tags intent:
    # retrospective (historical), shadow (prospective freeze; no tool execution),
    # read_only (decision-support tag; prefer export-akta-context for AKTA-only).

    evidence = list(source.get("evidence") or [])
    claims = list(source.get("claims") or [])

    # Fail closed: missing digests
    missing_digest = [
        str(e.get("evidence_id") or "?")
        for e in evidence
        if isinstance(e, dict) and not e.get("raw_record_hash")
    ]
    if missing_digest:
        raise ValueError(f"fail closed: evidence missing raw_record_hash: {missing_digest}")

    # Fail closed: duplicate evidence_id in source
    seen_ids: set[str] = set()
    dup_ids: list[str] = []
    for e in evidence:
        if not isinstance(e, dict) or not e.get("evidence_id"):
            continue
        eid = str(e["evidence_id"])
        if eid in seen_ids:
            dup_ids.append(eid)
        seen_ids.add(eid)
    if dup_ids:
        raise ValueError(f"fail closed: duplicate evidence_id in source: {sorted(set(dup_ids))}")

    included, excluded, cutoff_errors = apply_cutoff_filter(evidence, cutoff)
    if cutoff_errors:
        raise ValueError("fail closed: " + "; ".join(cutoff_errors))

    included_ids = {str(e["evidence_id"]) for e in included if e.get("evidence_id")}
    frozen_claims = _claims_for_included(claims, included_ids)

    # Detect contradictions against included evidence only
    mini_report = {
        "evidence": included,
        "claims": frozen_claims,
        "contradictions": source.get("contradictions") or [],
    }
    contradictions = detect_contradictions(mini_report)

    uncertainty_items = [
        {
            "claim_id": str(c.get("claim_id")),
            "uncertainty_level": str(c.get("uncertainty_level") or "unspecified"),
            "notes": None,
        }
        for c in frozen_claims
        if c.get("claim_id")
    ]
    missing_evidence: list[str] = []
    if not included:
        missing_evidence.append("no pre-cutoff evidence included")
    for c in frozen_claims:
        if not c.get("evidence_ids"):
            missing_evidence.append(f"claim {c.get('claim_id')} has no included evidence")

    quality_warnings: list[str] = []
    for ev in included:
        qs = ev.get("quality_score") or {}
        for w in qs.get("warnings") or []:
            quality_warnings.append(f"{ev.get('evidence_id')}: {w}")
        if (ev.get("domain_metadata") or {}).get("retrieval_ambiguity"):
            quality_warnings.append(f"{ev.get('evidence_id')}: retrieval_ambiguity")

    unresolved = list(source.get("limitations") or [])[:20]
    subject = source.get("subject") or {}
    qtext = question or str(subject.get("display_name") or source.get("input_question") or "")

    retrieval_timestamps = {
        str(e["evidence_id"]): str(e.get("retrieved_at"))
        for e in included
        if e.get("evidence_id") and e.get("retrieved_at")
    }

    report_id = source.get("report_id")
    snapshot_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"vsa:snapshot|{report_id or qtext}|{cutoff}|{mode}",
        )
    )
    bundle_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vsa:dteb|{snapshot_id}|{cutoff}"))

    requirements: list[str] = []
    if candidate_action_id:
        requirements.append(
            f"Candidate action {candidate_action_id} requires pre-cutoff evidence with digests; "
            "VSA does not authorize the action."
        )
    if missing_evidence:
        requirements.extend(f"Resolve: {m}" for m in missing_evidence)

    generated = (source.get("provenance") or {}).get("generated_by") or {}

    bundle: dict[str, Any] = {
        "schema_version": DECISION_TIME_BUNDLE_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "source_snapshot_id": snapshot_id,
        "evidence_report_id": report_id,
        "scientific_question_id": None,
        "decision_time_cutoff": cutoff,
        "mode": mode,
        "query": {
            "question": qtext,
            "retrieval_params": retrieval_params or {},
            "retrieval_timestamps": retrieval_timestamps,
        },
        "included_evidence": included,
        "excluded_post_cutoff": excluded,
        "claims": frozen_claims,
        "contradictions": contradictions,
        "uncertainty": {
            "claim_uncertainty": uncertainty_items,
            "missing_evidence": missing_evidence,
        },
        "source_quality_warnings": quality_warnings,
        "unresolved_questions": unresolved,
        "candidate_action_evidence_requirements": requirements,
        "portable_refs": build_portable_refs(included),
        "producer": {
            "package_version": __version__,
            "model_or_checkpoint_id": generated.get("model_or_agent_stack"),
            "validation_version": VALIDATION_VERSION,
            "prompt_template_version": generated.get("prompt_template_version")
            or PROMPT_TEMPLATE_VERSION,
        },
        "integrity": {
            "bundle_hash": "",  # filled below
            "source_record_hashes": hash_source_records(included),
            "schema_digest": schema_digest(BUNDLE_SCHEMA_NAME),
            "signature": None,
        },
        "privacy_safe_metrics": privacy_safe_metrics(
            included, excluded, contradictions, frozen_claims
        ),
        "non_claims": dict(NON_CLAIMS),
    }

    bundle["integrity"]["bundle_hash"] = compute_bundle_hash(bundle)

    if sign:
        from vsa.decision_time.signing import sign_bundle

        bundle = sign_bundle(bundle, key_path=key_path)

    errors = validate_companion(BUNDLE_SCHEMA_NAME, bundle)
    if errors:
        raise ValueError("bundle schema validation failed: " + "; ".join(errors))
    return bundle
