"""Verify DecisionTimeEvidenceBundle invariants and compare cutoffs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vsa.companion_schema import schema_digest, validate_companion
from vsa.decision_time.cutoff import apply_cutoff_filter, parse_timestamp
from vsa.decision_time.pcs import verify_portable_refs
from vsa.decision_time.snapshot import BUNDLE_SCHEMA_NAME, compute_bundle_hash
from vsa.provenance.hashchain import hash_source_records
from vsa.validate.decision_time_checks import run_decision_time_checks
from vsa.version import DECISION_TIME_BUNDLE_SCHEMA_VERSION


@dataclass
class BundleVerifyResult:
    passed: bool
    status: str
    checks: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "checks": self.checks,
            "errors": self.errors,
        }


def _check(
    checks: list[dict[str, str]],
    check_id: str,
    name: str,
    ok: bool,
    message: str,
    *,
    warn: bool = False,
) -> None:
    if ok:
        status = "pass"
    elif warn:
        status = "warn"
    else:
        status = "fail"
    checks.append({"check_id": check_id, "name": name, "status": status, "message": message})


def verify_decision_time_bundle(
    bundle: dict[str, Any],
    *,
    require_signature: bool = False,
) -> BundleVerifyResult:
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    version = bundle.get("schema_version")
    if version != DECISION_TIME_BUNDLE_SCHEMA_VERSION:
        msg = (
            f"bundle schema_version unsupported: {version!r}; "
            f"supported: {DECISION_TIME_BUNDLE_SCHEMA_VERSION}"
        )
        _check(checks, "schema_version", "Bundle schema version", False, msg)
        return BundleVerifyResult(False, "fail", checks, [msg])

    schema_errors = validate_companion(BUNDLE_SCHEMA_NAME, bundle)
    _check(
        checks,
        "schema",
        "JSON Schema conformance",
        not schema_errors,
        "; ".join(schema_errors) or "valid",
    )
    errors.extend(schema_errors)

    cutoff = bundle.get("decision_time_cutoff")
    try:
        parse_timestamp(str(cutoff) if cutoff else None)
        cutoff_ok = True
        cutoff_msg = f"cutoff={cutoff}"
    except (ValueError, TypeError) as exc:
        cutoff_ok = False
        cutoff_msg = str(exc)
    _check(checks, "cutoff_parse", "Decision-time cutoff parseable", cutoff_ok, cutoff_msg)
    if not cutoff_ok:
        errors.append(cutoff_msg)

    included = list(bundle.get("included_evidence") or [])
    excluded = list(bundle.get("excluded_post_cutoff") or [])

    # Re-run cutoff: no post-cutoff in included
    if cutoff_ok:
        re_included, re_excluded, cutoff_errs = apply_cutoff_filter(
            included, str(cutoff), require_timestamps=True
        )
        if cutoff_errs:
            _check(
                checks,
                "cutoff_timestamps",
                "Included evidence timestamps",
                False,
                "; ".join(cutoff_errs),
            )
            errors.extend(cutoff_errs)
        elif re_excluded:
            msg = f"post-cutoff evidence present in included set: {[e['evidence_id'] for e in re_excluded]}"
            _check(checks, "cutoff_inclusion", "No post-cutoff in included", False, msg)
            errors.append(msg)
        else:
            _check(
                checks,
                "cutoff_inclusion",
                "No post-cutoff in included",
                True,
                f"{len(re_included)} included; {len(excluded)} disclosed excluded",
            )

    # Digests present and stable
    missing_digest = [e.get("evidence_id", "?") for e in included if not e.get("raw_record_hash")]
    _check(
        checks,
        "source_digests",
        "Included evidence digests present",
        not missing_digest,
        f"missing digests: {missing_digest}" if missing_digest else "all digests present",
    )
    if missing_digest:
        errors.append(f"missing raw_record_hash: {missing_digest}")

    integrity = bundle.get("integrity") or {}
    expected_hashes = hash_source_records(included)
    stored_hashes = integrity.get("source_record_hashes") or {}
    hashes_ok = stored_hashes == expected_hashes
    _check(
        checks,
        "source_record_hashes",
        "Source record hashes match",
        hashes_ok,
        "match" if hashes_ok else "integrity.source_record_hashes mismatch",
    )
    if not hashes_ok:
        errors.append("integrity.source_record_hashes mismatch")

    expected_bundle_hash = compute_bundle_hash(bundle)
    stored_hash = integrity.get("bundle_hash")
    hash_ok = stored_hash == expected_bundle_hash
    _check(
        checks,
        "bundle_hash",
        "Bundle hash matches canonical material",
        hash_ok,
        "match" if hash_ok else f"expected {expected_bundle_hash}, got {stored_hash}",
    )
    if not hash_ok:
        errors.append("integrity.bundle_hash mismatch")

    expected_schema_digest = schema_digest(BUNDLE_SCHEMA_NAME)
    schema_digest_ok = integrity.get("schema_digest") == expected_schema_digest
    _check(
        checks,
        "schema_digest",
        "Pinned schema digest",
        schema_digest_ok,
        "match" if schema_digest_ok else "schema_digest mismatch",
    )
    if not schema_digest_ok:
        errors.append("integrity.schema_digest mismatch")

    # Portable refs
    pref_errors = verify_portable_refs(included, bundle.get("portable_refs"))
    _check(
        checks,
        "portable_refs",
        "PCS-shaped portable ref integrity",
        not pref_errors,
        "; ".join(pref_errors) or "portable refs consistent",
    )
    errors.extend(pref_errors)

    # Non-claims must remain explicitly false
    nc = bundle.get("non_claims") or {}
    expected_nc = {
        "authorizes_actions": False,
        "executes_tools": False,
        "issues_grants": False,
        "certifies_scientific_correctness": False,
    }
    nc_ok = all(nc.get(k) is expected_nc[k] for k in expected_nc)
    _check(
        checks,
        "non_claims",
        "Explicit non-claims",
        nc_ok,
        "non_claims intact" if nc_ok else f"non_claims corrupted: {nc}",
    )
    if not nc_ok:
        errors.append("non_claims must all be false")

    # Signature (optional unless required)
    sig = integrity.get("signature")
    if sig:
        from vsa.decision_time.signing import verify_bundle_signature

        ok, msg = verify_bundle_signature(bundle)
        _check(checks, "signature", "Ed25519 bundle signature", ok, msg)
        if not ok:
            errors.append(msg)
    elif require_signature:
        _check(
            checks, "signature", "Ed25519 bundle signature", False, "signature required but missing"
        )
        errors.append("signature required but missing")
    else:
        _check(
            checks,
            "signature",
            "Ed25519 bundle signature",
            True,
            "no signature (optional)",
            warn=True,
        )

    # Additive semantic checks
    for check in run_decision_time_checks(bundle):
        checks.append(check.to_dict())
        if check.status == "fail":
            errors.append(check.message)

    fail_count = sum(1 for c in checks if c.get("status") == "fail")
    warn_count = sum(1 for c in checks if c.get("status") == "warn")
    if fail_count or errors:
        status = "fail"
        passed = False
    elif warn_count:
        status = "warn"
        passed = True
    else:
        status = "pass"
        passed = True
    return BundleVerifyResult(passed=passed, status=status, checks=checks, errors=errors)


def compare_cutoffs(bundle_a: dict[str, Any], bundle_b: dict[str, Any]) -> dict[str, Any]:
    """Compare two decision-time bundles (typically different cutoffs).

    Both bundles are verified first; results are disclosed. Comparison remains
    informational and does not authorize actions.
    """
    verify_a = verify_decision_time_bundle(bundle_a)
    verify_b = verify_decision_time_bundle(bundle_b)
    a_ids = {e.get("evidence_id") for e in bundle_a.get("included_evidence") or []}
    b_ids = {e.get("evidence_id") for e in bundle_b.get("included_evidence") or []}
    a_excl = {e.get("evidence_id") for e in bundle_a.get("excluded_post_cutoff") or []}
    b_excl = {e.get("evidence_id") for e in bundle_b.get("excluded_post_cutoff") or []}
    return {
        "cutoff_a": bundle_a.get("decision_time_cutoff"),
        "cutoff_b": bundle_b.get("decision_time_cutoff"),
        "verify_a": {
            "passed": verify_a.passed,
            "status": verify_a.status,
            "errors": verify_a.errors,
        },
        "verify_b": {
            "passed": verify_b.passed,
            "status": verify_b.status,
            "errors": verify_b.errors,
        },
        "bundle_hash_a": (bundle_a.get("integrity") or {}).get("bundle_hash"),
        "bundle_hash_b": (bundle_b.get("integrity") or {}).get("bundle_hash"),
        "hash_match": (bundle_a.get("integrity") or {}).get("bundle_hash")
        == (bundle_b.get("integrity") or {}).get("bundle_hash"),
        "included_only_in_a": sorted(a_ids - b_ids),
        "included_only_in_b": sorted(b_ids - a_ids),
        "included_intersection": sorted(a_ids & b_ids),
        "excluded_only_in_a": sorted(a_excl - b_excl),
        "excluded_only_in_b": sorted(b_excl - a_excl),
        "claim_count_a": len(bundle_a.get("claims") or []),
        "claim_count_b": len(bundle_b.get("claims") or []),
        "contradiction_count_a": len(bundle_a.get("contradictions") or []),
        "contradiction_count_b": len(bundle_b.get("contradictions") or []),
        "non_claims": {
            "authorizes_actions": False,
            "note": "Comparison is informational; VSA does not authorize actions.",
        },
    }
