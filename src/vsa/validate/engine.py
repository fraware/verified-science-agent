"""ScientificReport validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vsa.provenance.hashchain import verify_provenance_hashes
from vsa.schema import assert_schema_version, validate_schema
from vsa.scoring.evidence_quality import score_evidence
from vsa.validate.contradictions import detect_contradictions
from vsa.version import VALIDATION_VERSION
from vsa.claims.normalize import (
    build_claim_evidence_graph,
    cited_evidence_ids,
    supporting_ids,
    contradicting_ids,
)

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
    evidence_by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict) and e.get("evidence_id")}
    source_records = {
        r.get("source_id"): r
        for r in (report.get("source_records") or [])
        if isinstance(r, dict) and r.get("source_id")
    }

    # Every claim has explicit support OR unsupported boundary with empty support
    missing_support: list[str] = []
    unsupported_with_support: list[str] = []
    for c in claims:
        cid = c.get("claim_id", "?")
        support = supporting_ids(c)
        boundary = c.get("review_boundary")
        if boundary == "unsupported":
            if support:
                unsupported_with_support.append(cid)
        elif not support and not c.get("evidence_ids"):
            missing_support.append(cid)
        elif not support:
            missing_support.append(cid)
    _add(
        checks,
        "claim_evidence",
        "Every claim has evidence support or unsupported boundary",
        not missing_support and not unsupported_with_support,
        (
            f"missing support: {missing_support}; unsupported-with-support: {unsupported_with_support}"
            if (missing_support or unsupported_with_support)
            else "all claims have explicit support or unsupported status"
        ),
    )
    if missing_support:
        errors.append(f"claims missing supporting evidence: {missing_support}")
    if unsupported_with_support:
        errors.append(
            f"unsupported claims must have empty supporting_evidence_ids: {unsupported_with_support}"
        )

    # Evidence references exist (supporting, contradicting, legacy, spans)
    dangling_refs: list[str] = []
    for claim in claims:
        cid = claim.get("claim_id", "?")
        for eid in cited_evidence_ids(claim):
            if eid not in evidence_ids:
                dangling_refs.append(f"{cid}->{eid}")
        for span in claim.get("source_spans") or []:
            if not isinstance(span, dict):
                continue
            eid = span.get("evidence_id")
            if eid and eid not in evidence_ids:
                dangling_refs.append(f"{cid}->span:{eid}")
            sid = span.get("source_id")
            if sid and source_records and sid not in source_records:
                dangling_refs.append(f"{cid}->span_source:{sid}")
    _add(
        checks,
        "evidence_refs",
        "Claim evidence IDs resolve",
        not dangling_refs,
        f"unresolved evidence refs: {dangling_refs}" if dangling_refs else "all evidence IDs resolve",
    )
    if dangling_refs:
        errors.append(f"claims reference missing evidence: {dangling_refs}")

    # Write barrier: evidence authoritative fields must match SourceRecords
    forged_authority: list[str] = []
    if source_records:
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            eid = ev.get("evidence_id", "?")
            sid = ev.get("source_id")
            if not sid or sid not in source_records:
                forged_authority.append(f"{eid}: missing or unknown source_id")
                continue
            sr = source_records[sid]
            if ev.get("raw_record_hash") and ev["raw_record_hash"] != sr.get("content_digest"):
                forged_authority.append(f"{eid}: content_digest/raw_record_hash mismatch")
            if ev.get("retrieval_path") and ev["retrieval_path"] != sr.get("canonical_url"):
                forged_authority.append(f"{eid}: canonical_url/retrieval_path mismatch")
            if ev.get("source_name") and ev["source_name"] != sr.get("connector"):
                forged_authority.append(f"{eid}: connector/source_name mismatch")
            if ev.get("identifier") and ev["identifier"] != sr.get("accession"):
                forged_authority.append(f"{eid}: accession/identifier mismatch")
    _add(
        checks,
        "source_authority",
        "Evidence authoritative fields match SourceRecords",
        not forged_authority,
        "; ".join(forged_authority) or "source authority intact",
    )
    if forged_authority:
        errors.append(f"forged or mismatched authoritative source fields: {forged_authority}")

    # Evidence reused outside declared subject scope
    subject = report.get("subject") or {}
    subject_key = (
        subject.get("display_name")
        or subject.get("gene_symbol")
        or (subject.get("identifiers") or {}).get("primary")
    )
    scope_violations: list[str] = []
    if subject_key:
        for claim in claims:
            cid = claim.get("claim_id", "?")
            for eid in supporting_ids(claim) + contradicting_ids(claim):
                ev = evidence_by_id.get(eid) or {}
                meta = ev.get("domain_metadata") or {}
                ev_subject = meta.get("subject_key")
                if ev_subject and str(ev_subject) != str(subject_key):
                    scope_violations.append(f"{cid}->{eid}: subject_key={ev_subject!r}")
    _add(
        checks,
        "evidence_scope",
        "Evidence subject scope matches claim subject",
        not scope_violations,
        f"out-of-scope evidence: {scope_violations}" if scope_violations else "evidence within subject scope",
    )
    if scope_violations:
        errors.append(f"evidence reused outside declared scope: {scope_violations}")

    # Claim–evidence graph present and free of dangling edges
    graph = report.get("claim_evidence_graph") or build_claim_evidence_graph(report)
    dangling_edges = [
        e for e in (graph.get("edges") or []) if isinstance(e, dict) and not e.get("resolves", True)
    ]
    _add(
        checks,
        "claim_evidence_graph",
        "Claim–evidence graph edges resolve",
        not dangling_edges,
        f"dangling graph edges: {dangling_edges}" if dangling_edges else "graph edges resolve",
    )
    if dangling_edges:
        errors.append(f"claim_evidence_graph has dangling edges: {dangling_edges}")

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
        lim_text = " ".join(str(x) for x in report.get("limitations", []))
        has_credibility_warning = "SCIENTIFIC CREDIBILITY WARNING" in lim_text.upper() or "METADATA-ONLY" in lim_text.upper()
        _add(
            checks,
            "publication_content",
            "Publication content depth",
            has_credibility_warning,
            f"SCIENTIFIC CREDIBILITY WARNING required: all {len(metadata_only)} publication evidence item(s) are metadata-only",
            warn=has_credibility_warning,
        )
        if not has_credibility_warning:
            errors.append("metadata-only publication reports must include SCIENTIFIC CREDIBILITY WARNING in limitations")

    # Ambiguous retrieval must not carry high reliability
    ambiguous_high = [
        ev.get("evidence_id", "?")
        for ev in evidence
        if (ev.get("domain_metadata") or {}).get("retrieval_ambiguity")
        and ev.get("reliability") == "high"
    ]
    _add(
        checks,
        "ambiguous_reliability",
        "Ambiguous evidence reliability cap",
        not ambiguous_high,
        f"high reliability on ambiguous evidence: {ambiguous_high}" if ambiguous_high else "ambiguous evidence capped",
    )
    if ambiguous_high:
        errors.append(f"ambiguous evidence cannot have high reliability: {ambiguous_high}")

    # AlphaFold must declare predicted structure
    alphafold_issues: list[str] = []
    for ev in evidence:
        if ev.get("source_name") != "AlphaFold DB":
            continue
        meta = ev.get("domain_metadata") or {}
        summary = str(ev.get("summary", "")).lower()
        if meta.get("structure_type") != "predicted":
            alphafold_issues.append(f"{ev.get('evidence_id')}: missing structure_type=predicted")
        if "predicted" not in summary:
            alphafold_issues.append(f"{ev.get('evidence_id')}: summary missing predicted-structure disclaimer")
    _add(
        checks,
        "alphafold_predicted",
        "AlphaFold predicted-structure labeling",
        not alphafold_issues,
        "; ".join(alphafold_issues) or "AlphaFold evidence correctly labeled as predicted",
    )
    errors.extend(alphafold_issues)

    # --- Credibility red-team checks (VSA-06) ---
    from vsa.scientific.credibility import (
        detect_duplicate_evidence,
        detect_fabricated_citations,
        detect_metadata_as_fulltext,
        detect_predicted_as_experimental,
        detect_prompt_injection,
        detect_retracted_papers,
        detect_title_mismatches,
        detect_unsupported_spans,
    )

    fabricated = detect_fabricated_citations(evidence)
    _add(
        checks,
        "fabricated_citations",
        "Citation identifier integrity",
        not fabricated,
        f"fabricated/malformed citations: {fabricated}" if fabricated else "citation identifiers intact",
    )
    if fabricated:
        errors.append(f"fabricated or malformed citation identifiers: {fabricated}")

    title_mismatch = detect_title_mismatches(evidence)
    _add(
        checks,
        "source_title_mismatch",
        "Source-title consistency",
        not title_mismatch,
        f"title mismatches: {title_mismatch}" if title_mismatch else "titles consistent",
    )
    if title_mismatch:
        errors.append(f"source-title mismatch: {title_mismatch}")

    retracted = detect_retracted_papers(evidence)
    _add(
        checks,
        "retracted_papers",
        "Retracted publication exclusion",
        not retracted,
        f"retracted evidence: {retracted}" if retracted else "no retracted publications",
    )
    if retracted:
        errors.append(f"retracted publications cited: {retracted}")

    dup = detect_duplicate_evidence(evidence)
    dup_fail = bool(dup["duplicate_ids"])
    dup_warn = bool(dup["duplicate_digests"]) and not dup_fail
    _add(
        checks,
        "duplicate_evidence",
        "Duplicate evidence detection",
        not dup_fail and not dup_warn,
        (
            f"duplicate_ids={dup['duplicate_ids']}; duplicate_digests={dup['duplicate_digests']}"
            if (dup_fail or dup_warn)
            else "no duplicate evidence"
        ),
        warn=dup_warn,
    )
    if dup_fail:
        errors.append(f"duplicate evidence_id: {dup['duplicate_ids']}")

    meta_as_ft = detect_metadata_as_fulltext(evidence)
    _add(
        checks,
        "metadata_as_fulltext",
        "Metadata-as-fulltext integrity",
        not meta_as_ft,
        f"metadata claimed as fulltext: {meta_as_ft}" if meta_as_ft else "content levels consistent",
        warn=bool(meta_as_ft),
    )
    # Soft fail via warn + require limitation/warning visibility when present without demotion path
    if meta_as_ft:
        lim_rw = " ".join(
            str(x) for x in list(report.get("limitations") or []) + list(report.get("retrieval_warnings") or [])
        )
        if "CONTENT WARNING" not in lim_rw.upper() and "METADATA" not in lim_rw.upper():
            errors.append(f"metadata presented as fulltext without CONTENT WARNING: {meta_as_ft}")

    predicted_exp = detect_predicted_as_experimental(evidence, claims)
    _add(
        checks,
        "predicted_as_experimental",
        "Predicted structures not presented as experimental",
        not predicted_exp,
        "; ".join(predicted_exp) or "no predicted→experimental misrepresentation",
    )
    if predicted_exp:
        errors.extend(predicted_exp)

    # Post-cutoff leakage when a decision-time cutoff is attached to the report
    cutoff = report.get("decision_time_cutoff")
    post_cutoff: list[str] = []
    cutoff_ts_errors: list[str] = []
    if cutoff:
        from vsa.decision_time.cutoff import apply_cutoff_filter

        included, excluded, cutoff_errs = apply_cutoff_filter(evidence, str(cutoff))
        cutoff_ts_errors = list(cutoff_errs)
        # Evidence still present in the report but past cutoff is leakage
        post_cutoff = [str(e.get("evidence_id") or "?") for e in excluded]
        # Fail closed if claims support themselves with post-cutoff IDs that remain included wrongly
        # (included set after filter should be the only admissible set)
        admissible = {str(e.get("evidence_id")) for e in included}
        for claim in claims:
            for eid in supporting_ids(claim):
                if eid not in admissible and eid in {str(e.get("evidence_id")) for e in evidence}:
                    leak = f"{claim.get('claim_id')}->{eid}"
                    if leak not in post_cutoff:
                        post_cutoff.append(leak)
    cutoff_ok = not post_cutoff and not cutoff_ts_errors
    _add(
        checks,
        "post_cutoff_leakage",
        "Post-cutoff evidence leakage",
        cutoff_ok if cutoff else True,
        (
            f"post-cutoff leakage: {post_cutoff}; timestamp errors: {cutoff_ts_errors}"
            if not cutoff_ok
            else "no post-cutoff leakage"
        ),
    )
    if post_cutoff:
        errors.append(f"post-cutoff evidence leakage: {post_cutoff}")
    errors.extend(cutoff_ts_errors)

    span_bad = detect_unsupported_spans(claims, evidence)
    _add(
        checks,
        "span_support",
        "Claim text supported by cited span",
        not span_bad,
        f"unsupported spans: {span_bad}" if span_bad else "cited spans support claims",
    )
    if span_bad:
        errors.append(f"claim text unsupported by cited span: {span_bad}")

    injections = detect_prompt_injection(evidence)
    _add(
        checks,
        "prompt_injection",
        "Prompt injection in source content",
        not injections,
        f"prompt injection in: {injections}" if injections else "no prompt injection detected",
        warn=bool(injections),
    )
    if injections:
        lim_rw = " ".join(
            str(x) for x in list(report.get("limitations") or []) + list(report.get("retrieval_warnings") or [])
        )
        demoted = any(
            (c.get("domain_metadata") or {}).get("confidence_demoted")
            or (
                isinstance(c.get("confidence"), (int, float))
                and float(c["confidence"]) <= 0.35
                and set(cited_evidence_ids(c)) & set(injections)
            )
            for c in claims
        )
        if "PROMPT INJECTION" not in lim_rw.upper() and not demoted:
            errors.append(f"prompt injection accepted silently: {injections}")

    # ClinVar ambiguity must surface in report warnings when present
    ambiguous_clinvar = [
        ev.get("evidence_id", "?")
        for ev in evidence
        if ev.get("source_name") == "ClinVar" and (ev.get("domain_metadata") or {}).get("retrieval_ambiguity")
    ]
    if ambiguous_clinvar:
        lim_text = " ".join(str(x) for x in report.get("limitations", []))
        rw_text = " ".join(str(x) for x in report.get("retrieval_warnings", []))
        surfaced = "CLINVAR AMBIGUITY" in lim_text.upper() or "AMBIGUITY ALERT" in rw_text.upper()
        _add(
            checks,
            "clinvar_ambiguity_surfaced",
            "ClinVar ambiguity visibility",
            surfaced,
            f"ambiguous ClinVar evidence {ambiguous_clinvar} must appear in limitations or retrieval_warnings",
        )
        if not surfaced:
            errors.append("ClinVar ambiguity not surfaced in report warnings")

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
        # ok=False + warn=True → status "warn" without failing the report
        _add(
            checks,
            "stale_evidence",
            "Evidence retrieval freshness",
            False,
            f"stale retrieval (>5y): {stale_ids}",
            warn=True,
        )

    # Additive non-breaking warnings (ScientificReport path stays pass-compatible)
    entity_ambiguity = [
        ev.get("evidence_id", "?")
        for ev in evidence
        if (ev.get("domain_metadata") or {}).get("retrieval_ambiguity")
    ]
    if entity_ambiguity:
        _add(
            checks,
            "entity_ambiguity_warn",
            "Unresolved entity ambiguity (advisory)",
            False,
            f"ambiguous evidence IDs: {entity_ambiguity}",
            warn=True,
        )

    for claim in claims:
        text = str(claim.get("claim_text") or "").lower()
        if (
            ("experimental structure" in text or "experimentally determined" in text)
            and "not" not in text
            and "do not" not in text
        ):
            for eid in cited_evidence_ids(claim):
                ev = next((e for e in evidence if e.get("evidence_id") == eid), None)
                if ev and (ev.get("domain_metadata") or {}).get("structure_type") == "predicted":
                    _add(
                        checks,
                        "comp_to_exp_warn",
                        "Computational->experimental language (advisory)",
                        False,
                        f"claim {claim.get('claim_id')} cites predicted structure {eid}",
                        warn=True,
                    )
                    break

    # Retrieval status must remain visible — failure ≠ silent empty evidence
    retrieval_status = report.get("retrieval_status") or "complete"
    rw_joined = " ".join(str(x) for x in report.get("retrieval_warnings", []))
    outcomes = report.get("connector_outcomes") or []
    hard_codes = {
        "connector_timeout",
        "connector_rate_limited",
        "connector_failure",
        "malformed_response",
    }
    hard_outcomes = [
        o
        for o in outcomes
        if isinstance(o, dict) and (o.get("code") in hard_codes or o.get("status") in hard_codes)
    ]
    if retrieval_status in {"partial", "failed"}:
        visible = (
            retrieval_status in rw_joined
            or "partial_retrieval" in rw_joined
            or any(code in rw_joined for code in hard_codes)
            or bool(hard_outcomes)
        )
        _add(
            checks,
            "retrieval_status_visible",
            "Retrieval failure visibility",
            visible,
            f"retrieval_status={retrieval_status} must appear in warnings/outcomes",
            warn=True,
        )
    elif hard_outcomes:
        _add(
            checks,
            "retrieval_status_visible",
            "Retrieval failure visibility",
            False,
            f"hard connector failures without retrieval_status partial/failed: {[o.get('connector') for o in hard_outcomes]}",
            warn=True,
        )
    else:
        _add(
            checks,
            "retrieval_status_visible",
            "Retrieval failure visibility",
            True,
            f"retrieval_status={retrieval_status}",
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
