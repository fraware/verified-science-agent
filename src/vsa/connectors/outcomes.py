"""Typed connector retrieval outcome codes and classification."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

# Distinct warning codes — failure must never collapse into silent empty success.
CONNECTOR_TIMEOUT = "connector_timeout"
CONNECTOR_RATE_LIMITED = "connector_rate_limited"
CONNECTOR_FAILURE = "connector_failure"
MALFORMED_RESPONSE = "malformed_response"
SCHEMA_DRIFT = "schema_drift"
EMPTY_RESULT = "empty_result"
DUPLICATE_DROPPED = "duplicate_dropped"
PARTIAL_RETRIEVAL = "partial_retrieval"
CONNECTOR_SKIPPED = "connector_skipped"

RetrievalStatus = str  # complete | partial | failed

OUTCOME_SUCCESS = "success"
OUTCOME_EMPTY = "empty_result"
OUTCOME_FAILURE = "connector_failure"
OUTCOME_TIMEOUT = "connector_timeout"
OUTCOME_RATE_LIMITED = "connector_rate_limited"
OUTCOME_MALFORMED = "malformed_response"
OUTCOME_SCHEMA_DRIFT = "schema_drift"
OUTCOME_DEGRADED = "degraded"
OUTCOME_SKIPPED = "skipped"


@dataclass
class ConnectorOutcome:
    """Per-connector typed retrieval outcome."""

    connector: str
    status: str
    code: str | None = None
    evidence_count: int = 0
    warning: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_warning(self) -> str | None:
        if not self.warning and not self.code:
            return None
        code = self.code or self.status
        msg = self.warning or self.status
        return f"{code}: {self.connector}: {msg}"


def classify_exception(exc: BaseException) -> tuple[str, str, str]:
    """Map an exception to (outcome_status, warning_code, message)."""
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return OUTCOME_TIMEOUT, CONNECTOR_TIMEOUT, f"timeout: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status == 429:
            return OUTCOME_RATE_LIMITED, CONNECTOR_RATE_LIMITED, f"HTTP 429 rate limited: {exc}"
        return OUTCOME_FAILURE, CONNECTOR_FAILURE, f"HTTP {status}: {exc}"
    if isinstance(exc, json.JSONDecodeError):
        return OUTCOME_MALFORMED, MALFORMED_RESPONSE, f"malformed JSON: {exc}"
    if isinstance(exc, (httpx.DecodingError, UnicodeDecodeError)):
        return OUTCOME_MALFORMED, MALFORMED_RESPONSE, f"malformed response body: {exc}"
    # httpx may wrap JSON errors; inspect cause / message
    text = str(exc).lower()
    if "expecting value" in text or "json" in text and "decode" in text:
        return OUTCOME_MALFORMED, MALFORMED_RESPONSE, f"malformed response: {exc}"
    return OUTCOME_FAILURE, CONNECTOR_FAILURE, str(exc)


def looks_schema_drifted(item: Any) -> bool:
    """Heuristic: successful HTTP mapped to structurally incomplete evidence."""
    identifier = str(getattr(item, "identifier", "") or "").strip()
    summary = str(getattr(item, "summary", "") or "").strip()
    raw = getattr(item, "raw_record", None) or {}
    meta = getattr(item, "domain_metadata", None) or {}
    source = str(getattr(item, "source_name", "") or "")
    if meta.get("schema_drift"):
        return True
    if not identifier or identifier.lower() in {"unknown", "none", "null"}:
        return True
    if not raw:
        return True
    if summary.lower().startswith("unknown") and len(raw) <= 2:
        return True
    # Source-specific expected keys (fixture-driven drift detection)
    if source == "AlphaFold DB" and not raw.get("uniprotAccession") and not raw.get("pdbUrl"):
        return True
    if source == "Materials Project" and not (
        raw.get("material_id") or raw.get("formula_pretty") or raw.get("formula")
    ):
        return True
    if source == "OpenAlex" and not (raw.get("title") or (raw.get("id") or "").strip()):
        return True
    if source == "Semantic Scholar" and not (raw.get("title") or (raw.get("paperId") or "").strip()):
        return True
    if source == "Europe PMC" and not (raw.get("title") or raw.get("pmid") or raw.get("id")):
        return True
    if source == "Crossref" and not raw.get("title") and not raw.get("DOI") and not raw.get("doi"):
        return True
    if source == "ClinVar" and not raw.get("title") and not raw.get("clinical_significance"):
        return True
    if source == "UniProt" and not raw.get("primaryAccession") and not raw.get("genes"):
        return True
    if source == "PubMed" and not raw.get("title"):
        return True
    return False


def aggregate_retrieval_status(outcomes: list[ConnectorOutcome]) -> str:
    """Derive report-level retrieval_status from per-connector outcomes."""
    if not outcomes:
        return "complete"
    hard_fail = {
        OUTCOME_FAILURE,
        OUTCOME_TIMEOUT,
        OUTCOME_RATE_LIMITED,
        OUTCOME_MALFORMED,
    }
    soft = {OUTCOME_EMPTY, OUTCOME_SCHEMA_DRIFT, OUTCOME_DEGRADED, OUTCOME_SKIPPED}
    statuses = {o.status for o in outcomes}
    any_success = any(o.status == OUTCOME_SUCCESS and o.evidence_count > 0 for o in outcomes)
    any_hard = bool(statuses & hard_fail)
    any_soft = bool(statuses & soft) or any(
        o.status == OUTCOME_SCHEMA_DRIFT for o in outcomes
    )
    if any_hard and not any_success:
        return "failed"
    if any_hard or any_soft or any(o.status == OUTCOME_SCHEMA_DRIFT for o in outcomes):
        if any_success or any(o.evidence_count > 0 for o in outcomes):
            return "partial"
        if any_hard:
            return "failed"
        # All empty/skipped with no evidence
        return "partial" if OUTCOME_EMPTY in statuses or OUTCOME_SKIPPED in statuses else "failed"
    return "complete"
