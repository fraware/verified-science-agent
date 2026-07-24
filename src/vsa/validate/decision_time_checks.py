"""Additive decision-time semantic checks (versioned check IDs).

These apply to DecisionTimeEvidenceBundle verification. ScientificReport
validate_report behavior remains stable; report-path gains only non-breaking warnings
where noted in engine.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vsa.decision_time.cutoff import parse_timestamp
from vsa.validate.contradictions import detect_contradictions


@dataclass
class DTCheck:
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


def _quality_score(ev: dict[str, Any]) -> float:
    qs = ev.get("quality_score")
    if isinstance(qs, dict) and isinstance(qs.get("score"), int | float):
        return float(qs["score"])
    return 0.5


def run_decision_time_checks(bundle: dict[str, Any]) -> list[DTCheck]:
    checks: list[DTCheck] = []
    evidence = list(bundle.get("included_evidence") or [])
    claims = list(bundle.get("claims") or [])
    evidence_ids = {e.get("evidence_id") for e in evidence if isinstance(e, dict)}
    cutoff = bundle.get("decision_time_cutoff")

    # Claim without source support
    unsupported = [
        c.get("claim_id", "?")
        for c in claims
        if not c.get("evidence_ids") or not set(c.get("evidence_ids") or []) & evidence_ids
    ]
    checks.append(
        DTCheck(
            "dt_claim_source_binding",
            "Claim-source binding under cutoff",
            "fail" if unsupported else "pass",
            f"claims without included support: {unsupported}"
            if unsupported
            else "all claims bound",
        )
    )

    # Source added after cutoff (hard fail — should already be caught, restate)
    post = []
    if cutoff:
        cutoff_dt = parse_timestamp(str(cutoff))
        for ev in evidence:
            from vsa.decision_time.cutoff import evidence_effective_timestamp

            eff, _ = evidence_effective_timestamp(ev)
            if eff and cutoff_dt and eff > cutoff_dt:
                post.append(ev.get("evidence_id"))
    checks.append(
        DTCheck(
            "dt_post_cutoff_included",
            "Source after cutoff hard fail",
            "fail" if post else "pass",
            f"post-cutoff included: {post}" if post else "no post-cutoff included",
        )
    )

    # Contradictory high-quality evidence
    mini = {"evidence": evidence, "claims": claims}
    contradictions = bundle.get("contradictions") or detect_contradictions(mini)
    hq_conflicts = []
    for c in contradictions:
        eids = c.get("evidence_ids") or []
        scores = [
            _quality_score(next((e for e in evidence if e.get("evidence_id") == eid), {}))
            for eid in eids
        ]
        if len(scores) >= 2 and min(scores) >= 0.7 and c.get("severity") in ("high", "medium"):
            hq_conflicts.append(c.get("contradiction_id") or c.get("description", "?")[:60])
    checks.append(
        DTCheck(
            "dt_hq_contradiction",
            "Contradictory high-quality evidence",
            "fail" if hq_conflicts else "pass",
            f"high-quality contradictions: {hq_conflicts}" if hq_conflicts else "none",
        )
    )

    # Metadata-only dependence
    from vsa.connectors.content_level import infer_content_level

    pubs = [e for e in evidence if e.get("source_type") == "publication"]
    meta_only = [e.get("evidence_id") for e in pubs if infer_content_level(e) == "metadata"]
    if pubs and len(meta_only) == len(pubs):
        checks.append(
            DTCheck(
                "dt_metadata_only",
                "Metadata-only dependence",
                "warn",
                f"all publication evidence metadata-only: {meta_only}",
            )
        )
    else:
        checks.append(
            DTCheck(
                "dt_metadata_only",
                "Metadata-only dependence",
                "pass",
                "not solely metadata-dependent" if pubs else "no publication evidence",
            )
        )

    # Missing methods / population context
    missing_context = []
    for c in claims:
        text = str(c.get("claim_text") or "").lower()
        if any(k in text for k in ("population", "cohort", "patients", "subjects")):
            has_pop = any(
                (e.get("domain_metadata") or {}).get("population")
                or (e.get("domain_metadata") or {}).get("sample_size")
                for e in evidence
                if e.get("evidence_id") in (c.get("evidence_ids") or [])
            )
            if not has_pop:
                missing_context.append(c.get("claim_id"))
    checks.append(
        DTCheck(
            "dt_population_context",
            "Population/methods context",
            "warn" if missing_context else "pass",
            f"claims lacking population context: {missing_context}" if missing_context else "ok",
        )
    )

    # Stale source snapshots vs decision cutoff (not only 5-year wall clock)
    stale = []
    if cutoff:
        cutoff_dt = parse_timestamp(str(cutoff))
        for ev in evidence:
            retrieved = ev.get("retrieved_at")
            if not retrieved or not cutoff_dt:
                continue
            try:
                rdt = parse_timestamp(str(retrieved))
            except ValueError:
                continue
            if rdt and (cutoff_dt - rdt).days > 365 * 5:
                stale.append(ev.get("evidence_id"))
    checks.append(
        DTCheck(
            "dt_stale_vs_cutoff",
            "Stale source vs decision cutoff",
            "warn" if stale else "pass",
            f"retrieved >5y before cutoff: {stale}" if stale else "fresh relative to cutoff",
        )
    )

    # Unresolved entity ambiguity
    ambiguous = [
        e.get("evidence_id")
        for e in evidence
        if (e.get("domain_metadata") or {}).get("retrieval_ambiguity")
    ]
    high_conf_on_ambiguous = []
    for c in claims:
        if float(c.get("confidence") or 0) >= 0.8 and set(c.get("evidence_ids") or []) & set(
            ambiguous
        ):
            high_conf_on_ambiguous.append(c.get("claim_id"))
    checks.append(
        DTCheck(
            "dt_entity_ambiguity",
            "Unresolved entity ambiguity",
            "fail" if high_conf_on_ambiguous else ("warn" if ambiguous else "pass"),
            (
                f"high-confidence claims on ambiguous evidence: {high_conf_on_ambiguous}"
                if high_conf_on_ambiguous
                else (f"ambiguous evidence present: {ambiguous}" if ambiguous else "no ambiguity")
            ),
        )
    )

    # Unsupported computational → experimental extrapolation
    extrapolations = []
    for c in contradictions:
        desc = str(c.get("description") or "").lower()
        if "predicted" in desc and "experimental" in desc:
            extrapolations.append(c.get("contradiction_id"))
    for c in claims:
        text = str(c.get("claim_text") or "").lower()
        if "experimental" in text or "experimentally determined" in text:
            if any(
                neg in text
                for neg in (
                    "not an experimental",
                    "not experimental",
                    "do not treat as experimental",
                    "predicted",
                )
            ):
                continue
            for eid in c.get("evidence_ids") or []:
                ev = next((e for e in evidence if e.get("evidence_id") == eid), None)
                if not ev:
                    continue
                meta = ev.get("domain_metadata") or {}
                if (
                    meta.get("structure_type") == "predicted"
                    or "alphafold" in str(ev.get("source_name") or "").lower()
                ):
                    extrapolations.append(c.get("claim_id"))
    checks.append(
        DTCheck(
            "dt_comp_to_exp",
            "Computational to experimental extrapolation",
            "fail" if extrapolations else "pass",
            f"unsupported extrapolation: {extrapolations}" if extrapolations else "none detected",
        )
    )

    # Uncertainty preservation
    unc = bundle.get("uncertainty") or {}
    has_unc = isinstance(unc.get("claim_uncertainty"), list)
    checks.append(
        DTCheck(
            "dt_uncertainty_preserved",
            "Uncertainty preservation",
            "pass" if has_unc else "fail",
            "claim_uncertainty present" if has_unc else "uncertainty block missing",
        )
    )

    return checks
