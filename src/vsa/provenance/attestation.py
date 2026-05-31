"""SLSA / in-toto provenance attestation for ScientificReport artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from vsa import __version__

BUILD_TYPE = "https://verified-science-agent.dev/build/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"


def _sha256_file_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_slsa_attestation(
    report: dict[str, Any],
    *,
    subject_name: str = "scientific_report.json",
    builder_id: str | None = None,
) -> dict[str, Any]:
    """
    Build an in-toto Statement with SLSA Provenance v1 predicate for a report.

    The subject digest uses provenance.report_hash when present (content-addressable artifact).
    """
    provenance = report.get("provenance") or {}
    report_hash = provenance.get("report_hash") or _sha256_file_bytes(
        json.dumps(report, sort_keys=True).encode("utf-8")
    )
    builder_id = builder_id or f"https://verified-science-agent.dev/vsa@{__version__}"

    reproducibility = provenance.get("reproducibility") or {}
    generated_by = provenance.get("generated_by") or {}

    external_parameters: dict[str, Any] = {
        "input_question": report.get("input_question") or report.get("subject", {}).get("display_name"),
        "domain": report.get("domain"),
        "claim_generation_method": report.get("claim_generation_method") or generated_by.get("model_or_agent_stack"),
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
    }
    external_parameters = {k: v for k, v in external_parameters.items() if v is not None}

    resolved_dependencies = [
        {
            "uri": f"evidence:{eid}",
            "digest": {"sha256": digest},
        }
        for eid, digest in (provenance.get("source_record_hashes") or {}).items()
    ]

    byproducts = []
    if provenance.get("evidence_bundle_hash"):
        byproducts.append(
            {
                "name": "evidence_bundle_hash",
                "digest": {"sha256": provenance["evidence_bundle_hash"]},
            }
        )
    if provenance.get("evidence_content_hash"):
        byproducts.append(
            {
                "name": "evidence_content_hash",
                "digest": {"sha256": provenance["evidence_content_hash"]},
            }
        )
    if provenance.get("validation_run_hash"):
        byproducts.append(
            {
                "name": "validation_run_hash",
                "digest": {"sha256": provenance["validation_run_hash"]},
            }
        )

    finished = report.get("created_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": subject_name,
                "digest": {"sha256": report_hash},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": external_parameters,
                "internalParameters": {
                    "validation_version": provenance.get("validation_version"),
                    "renderer_version": provenance.get("renderer_version"),
                    "cache_dir": reproducibility.get("cache_dir"),
                },
                "resolvedDependencies": resolved_dependencies,
            },
            "runDetails": {
                "builder": {"id": builder_id, "version": {"vsa": __version__}},
                "metadata": {
                    "invocationId": report.get("report_id"),
                    "startedOn": finished,
                    "finishedOn": finished,
                    "input_hash": reproducibility.get("input_hash"),
                },
                "byproducts": byproducts,
            },
        },
    }


def verify_attestation(
    attestation: dict[str, Any],
    report: dict[str, Any],
    *,
    subject_name: str = "scientific_report.json",
) -> tuple[bool, str]:
    """Verify attestation subject digest matches report provenance hash."""
    if attestation.get("_type") != STATEMENT_TYPE:
        return False, "invalid statement _type"
    if attestation.get("predicateType") != PREDICATE_TYPE:
        return False, "invalid predicateType"

    subjects = attestation.get("subject") or []
    if not subjects:
        return False, "missing subject"

    expected_hash = (report.get("provenance") or {}).get("report_hash")
    if not expected_hash:
        return False, "report missing provenance.report_hash"

    matched = any(
        s.get("name") == subject_name and (s.get("digest") or {}).get("sha256") == expected_hash
        for s in subjects
    )
    if not matched:
        return False, f"subject digest does not match report_hash {expected_hash[:16]}..."

    return True, "attestation subject matches report provenance hash"
