"""Build a ScientificReport from input JSON."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from vsa.claims.llm_extraction import extract_claims
from vsa.claims.extraction import PROMPT_TEMPLATE_VERSION
from vsa.connectors.cache import EvidenceCache
from vsa.pipeline.retrieval import retrieve_evidence_with_meta
from vsa.pipeline.subject_parser import parse_input
from vsa.provenance.hashchain import now_utc_iso, stamp_report
from vsa.safety import disclaimer_for_subject
from vsa.scoring.evidence_quality import apply_quality_scores
from vsa.validate.contradictions import detect_contradictions
from vsa.validate.engine import run_validation
from vsa.version import RENDERER_VERSION, SCHEMA_VERSION, VALIDATION_VERSION


def _input_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


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


def build_report(
    input_data: dict[str, Any],
    *,
    cache_dir: str = ".vsa_cache",
    offline_evidence: list[dict[str, Any]] | None = None,
    claim_mode: str = "auto",
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    """Build a complete ScientificReport from input JSON."""
    from vsa.telemetry import span

    with span("build_report", claim_mode=claim_mode):
        return _build_report_impl(
            input_data,
            cache_dir=cache_dir,
            offline_evidence=offline_evidence,
            claim_mode=claim_mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )


def _build_report_impl(
    input_data: dict[str, Any],
    *,
    cache_dir: str = ".vsa_cache",
    offline_evidence: list[dict[str, Any]] | None = None,
    claim_mode: str = "auto",
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    subject = parse_input(input_data)
    cache = EvidenceCache(cache_dir)
    input_question = input_data.get("question") or subject.get("display_name", "")
    retrieval_warnings: list[str] = list(input_data.get("retrieval_warnings") or [])
    retrieval_plan: list[str] = list(input_data.get("retrieval_plan") or [])

    if offline_evidence is not None:
        evidence = offline_evidence
    elif input_data.get("evidence"):
        evidence = input_data["evidence"]
    else:
        result = retrieve_evidence_with_meta(subject, cache=cache)
        evidence = result.evidence
        retrieval_warnings.extend(result.warnings)
        retrieval_plan = result.retrieval_plan or retrieval_plan

    evidence = apply_quality_scores({"evidence": evidence})["evidence"]

    if input_data.get("claims"):
        claims = input_data["claims"]
        claim_stack = "provided"
    else:
        mode = input_data.get("claim_mode", claim_mode)
        provider = input_data.get("llm_provider", llm_provider)
        model = input_data.get("llm_model", llm_model)
        claims, claim_stack = extract_claims(
            subject, evidence, mode=mode, provider=provider, model=model
        )
    contradictions = detect_contradictions({"evidence": evidence, "claims": claims})

    speculative = any(c.get("review_boundary") == "speculative" for c in claims)
    domain_review = any(c.get("review_boundary") == "requires_domain_review" for c in claims)
    clinical_present = any(c.get("review_boundary") == "requires_clinical_review" for c in claims)
    review_required = clinical_present or speculative or domain_review or bool(contradictions)

    limitations = [
        disclaimer_for_subject(subject),
        "Claims are generated from retrieved metadata only unless full text is explicitly provided.",
        "Connector retrieval may be ambiguous; inspect retrieval_warnings and evidence reliability.",
    ]

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": input_data.get("report_id") or f"vsa-{uuid.uuid4().hex[:12]}",
        "created_at": now_utc_iso(),
        "input_question": input_question,
        "domain": input_data.get("domain") or _domain_from_subject(subject),
        "subject": subject,
        "claims": claims,
        "evidence": evidence,
        "retrieval_plan": retrieval_plan,
        "retrieval_warnings": retrieval_warnings,
        "evidence_selection_method": "connector_ranking_by_quality_score",
        "claim_generation_method": claim_stack,
        "review_policy": "human_review_required_for_clinical_and_speculative_claims",
        "limitations": limitations,
        "methods": [
            {
                "method_id": "M001",
                "name": "evidence_retrieval_pipeline",
                "version": "1.1.0",
                "description": "Subject parser → connector queries → deduplication → quality ranking",
            },
            {
                "method_id": "M002",
                "name": "claim_extraction",
                "version": PROMPT_TEMPLATE_VERSION,
                "description": f"Claim extraction ({claim_stack}) from retrieved evidence IDs",
            },
        ],
        "provenance": {
            "source_record_hashes": {},
            "evidence_bundle_hash": "0" * 64,
            "claim_hashes": {},
            "report_hash": "0" * 64,
            "validation_version": VALIDATION_VERSION,
            "renderer_version": RENDERER_VERSION,
            "generated_by": {
                "system_name": "verified-science-agent",
                "model_or_agent_stack": claim_stack,
                "prompt_template_version": PROMPT_TEMPLATE_VERSION,
            },
        },
        "validation_results": {"status": "pending", "checks": []},
        "human_review": {
            "required": review_required,
            "status": "pending" if review_required else "not_required",
            "required_corrections": [],
            "approved_claim_ids": [],
        },
        "generated_outputs": {"formats_available": ["json", "markdown", "html", "pdf"]},
        "contradictions": contradictions,
    }

    inp_hash = _input_hash(input_data)
    report = stamp_report(report, input_hash=inp_hash, cache_dir=cache_dir)
    report = run_validation(report, verify_hashes=True)
    return report


def build_from_file(
    path: Path,
    *,
    cache_dir: str = ".vsa_cache",
    claim_mode: str = "auto",
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return build_report(
        data,
        cache_dir=cache_dir,
        claim_mode=claim_mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
