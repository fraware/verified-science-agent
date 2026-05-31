"""ScientificReport validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vsa.provenance.hashchain import verify_provenance_hashes
from vsa.schema import assert_schema_version, validate_schema
from vsa.scoring.evidence_quality import score_evidence
from vsa.validate.contradictions import detect_contradictions
from vsa.version import VALIDATION_VERSION

REVIEW_BOUNDARIES = {
    "safe_summary",
    "requires_domain_review",
    "requires_clinical_review",
    "speculative",
    "unsupported",
}

CLINICAL_BOUNDARIES = {"requires_clinical_review"}


@dataclass
class ValidationCheck:
    check_id: str
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class ValidationResult:
    passed: bool
    status: str
    checks: list[ValidationCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_validation_results(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
            "validated_at": None,
        }


def _add(checks: list[ValidationCheck], check_id: str, name: str, ok: bool, message: str, *, warn: bool = False) -> None:
    if ok:
        status = "pass"
    elif warn:
        status = "warn"
    else:
        status = "fail"
    checks.append(ValidationCheck(check_id, name, status, message))


def validate_report(report: dict[str, Any], *, verify_hashes: bool = True) -> ValidationResult:
    checks: list[ValidationCheck] = []
    errors: list[str] = []

    # JSON Schema
    schema_errors = validate_schema(report)
    _add(checks, "schema", "JSON Schema conformance", not schema_errors, "; ".join(schema_errors) or "valid")
    errors.extend(schema_errors)

    version_errors = assert_schema_version(report)
    _add(checks, "schema_version", "Schema version", not version_errors, "; ".join(version_errors) or "matches")
    errors.extend(version_errors)

    evidence = report.get("evidence", [])
    claims = report.get("claims", [])
    evidence_ids = {e.get("evidence_id") for e in evidence if isinstance(e, dict)}

    # Every claim has evidence
    missing_evidence_claims = [
        c.get("claim_id", "?")
        for c in claims
        if not c.get("evidence_ids")
    ]
    _add(
        checks,
        "claim_evidence",
        "Every claim has evidence",
        not missing_evidence_claims,
        f"claims without evidence: {missing_evidence_claims}" if missing_evidence_claims else "all claims cite evidence",
    )
    if missing_evidence_claims:
        errors.append(f"claims missing evidence_ids: {missing_evidence_claims}")

    # Evidence references exist
    dangling_refs: list[str] = []
    for claim in claims:
        cid = claim.get("claim_id", "?")
        for eid in claim.get("evidence_ids", []):
            if eid not in evidence_ids:
                dangling_refs.append(f"{cid}->{eid}")
    _add(
        checks,
        "evidence_refs",
        "Claim evidence IDs resolve",
        not dangling_refs,
        f"unresolved evidence refs: {dangling_refs}" if dangling_refs else "all evidence IDs resolve",
    )
    if dangling_refs:
        errors.append(f"claims reference missing evidence: {dangling_refs}")

    # Evidence source type and retrieval path
    bad_evidence: list[str] = []
    for ev in evidence:
        eid = ev.get("evidence_id", "?")
        if not ev.get("source_type"):
            bad_evidence.append(f"{eid}: missing source_type")
        if not str(ev.get("retrieval_path", "")).strip():
            bad_evidence.append(f"{eid}: missing retrieval_path")
    _add(
        checks,
        "evidence_metadata",
        "Evidence source type and retrieval path",
        not bad_evidence,
        "; ".join(bad_evidence) or "all evidence items complete",
    )
    errors.extend(bad_evidence)

    # Confidence bounded
    bad_confidence: list[str] = []
    for claim in claims:
        conf = claim.get("confidence")
        if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            bad_confidence.append(str(claim.get("claim_id", "?")))
    _add(
        checks,
        "confidence",
        "Confidence bounded [0,1]",
        not bad_confidence,
        f"invalid confidence on: {bad_confidence}" if bad_confidence else "all confidence values valid",
    )
    if bad_confidence:
        errors.append(f"invalid confidence: {bad_confidence}")

    # Unsupported claims fail
    unsupported = [c.get("claim_id") for c in claims if c.get("review_boundary") == "unsupported"]
    _add(
        checks,
        "unsupported",
        "Unsupported claims flagged",
        not unsupported,
        f"unsupported claims: {unsupported}" if unsupported else "no unsupported claims",
    )
    if unsupported:
        errors.append(f"unsupported claims present: {unsupported}")

    # Speculative claims labeled
    speculative = [c.get("claim_id") for c in claims if c.get("review_boundary") == "speculative"]
    _add(
        checks,
        "speculative",
        "Speculative claims labeled",
        True,
        f"speculative claims (labeled): {speculative}" if speculative else "no speculative claims",
        warn=bool(speculative),
    )

    # Human review requirements
    clinical_claims = [c.get("claim_id") for c in claims if c.get("review_boundary") in CLINICAL_BOUNDARIES]
    human_review = report.get("human_review", {})
    review_required = human_review.get("required", True)
    if clinical_claims and human_review.get("status") == "approved":
        _add(
            checks,
            "clinical_review",
            "Clinical claims cannot be marked final without review",
            False,
            f"clinical claims {clinical_claims} but human_review.status is approved",
        )
        errors.append("clinical claims cannot be marked approved without domain review workflow")
    else:
        _add(
            checks,
            "human_review",
            "Human review requirements explicit",
            True,
            f"human_review.required={review_required}; clinical claims: {clinical_claims or 'none'}",
            warn=bool(clinical_claims),
        )

    # Review boundary validity
    bad_boundaries = [
        c.get("claim_id")
        for c in claims
        if c.get("review_boundary") not in REVIEW_BOUNDARIES
    ]
    _add(
        checks,
        "review_boundary",
        "Review boundary labels valid",
        not bad_boundaries,
        f"invalid review_boundary on: {bad_boundaries}" if bad_boundaries else "all boundaries valid",
    )
    if bad_boundaries:
        errors.append(f"invalid review_boundary: {bad_boundaries}")

    # Evidence quality warnings
    low_quality = []
    for ev in evidence:
        qs = ev.get("quality_score") or score_evidence(ev)
        if qs.get("score", 1) < 0.5:
            low_quality.append(ev.get("evidence_id"))
    _add(
        checks,
        "evidence_quality",
        "Evidence quality scoring",
        True,
        f"low-quality evidence warnings: {low_quality}" if low_quality else "evidence quality acceptable",
        warn=bool(low_quality),
    )

    # Contradictions
    contradictions = report.get("contradictions") or detect_contradictions(report)
    has_high_conflict = any(c.get("severity") == "high" for c in contradictions)
    _add(
        checks,
        "contradictions",
        "Contradiction detection",
        not has_high_conflict,
        f"{len(contradictions)} contradiction(s) detected" if contradictions else "no contradictions",
        warn=bool(contradictions) and not has_high_conflict,
    )
    if has_high_conflict:
        errors.append("high-severity contradictions present")

    # Provenance hashes
    if verify_hashes and report.get("provenance"):
        hash_errors = verify_provenance_hashes(report)
        _add(
            checks,
            "provenance",
            "Provenance hashes match",
            not hash_errors,
            "; ".join(hash_errors) or "hashes verified",
        )
        errors.extend(hash_errors)

    # Publication content depth (warn when only bibliographic metadata)
    from vsa.connectors.content_level import infer_content_level

    pub_evidence = [e for e in evidence if e.get("source_type") == "publication"]
    metadata_only = [
        e.get("evidence_id", "?")
        for e in pub_evidence
        if infer_content_level(e) == "metadata"
    ]
    if pub_evidence and len(metadata_only) == len(pub_evidence):
        _add(
            checks,
            "publication_content",
            "Publication content depth",
            True,
            f"CONTENT WARNING: all {len(metadata_only)} publication evidence item(s) are metadata-only",
            warn=True,
        )

    # Stale evidence retrieval dates
    from datetime import datetime, timedelta, timezone

    stale_ids: list[str] = []
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=365 * 5)
    for ev in evidence:
        retrieved = ev.get("retrieved_at")
        if not retrieved:
            continue
        try:
            dt = datetime.fromisoformat(str(retrieved).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < stale_cutoff:
                stale_ids.append(ev.get("evidence_id", "?"))
        except ValueError:
            continue
    if stale_ids:
        _add(
            checks,
            "stale_evidence",
            "Evidence retrieval freshness",
            True,
            f"stale retrieval (>5y): {stale_ids}",
            warn=True,
        )

    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    if fail_count:
        status = "fail"
        passed = False
    elif warn_count:
        status = "warn"
        passed = True
    else:
        status = "pass"
        passed = True

    return ValidationResult(passed=passed and not errors, status=status, checks=checks, errors=errors)


def run_validation(report: dict[str, Any], *, verify_hashes: bool = True) -> dict[str, Any]:
    """Validate report and attach validation_results section."""
    from vsa.provenance.hashchain import now_utc_iso

    report = dict(report)
    # Use placeholder validation_results so schema validation covers the rest of the report.
    payload = {k: v for k, v in report.items() if k != "validation_results"}
    payload["validation_results"] = {"status": "pass", "checks": []}
    result = validate_report(payload, verify_hashes=verify_hashes)
    vr = result.to_validation_results()
    vr["validated_at"] = now_utc_iso()
    report["validation_results"] = vr
    return report
