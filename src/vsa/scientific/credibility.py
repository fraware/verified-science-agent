"""Scientific credibility policies for evidence and report warnings."""

from __future__ import annotations

import re
from typing import Any

from vsa.claims.normalize import cited_evidence_ids, quote_hash, supporting_ids

PREDICTED_STRUCTURE_PHRASE = "predicted structure"
METADATA_ONLY_WARNING = (
    "SCIENTIFIC CREDIBILITY WARNING: All publication evidence is metadata-only. "
    "Claims must not exceed bibliographic facts; abstract or full-text evidence is required "
    "for substantive scientific conclusions."
)
CLINVAR_AMBIGUITY_WARNING = (
    "CLINVAR AMBIGUITY ALERT: One or more ClinVar records were retrieved from an ambiguous "
    "query (multiple closely scored candidates). Do not treat clinical significance as definitive "
    "without expert review and exact variant ID confirmation."
)
GENERIC_AMBIGUITY_WARNING = (
    "RETRIEVAL AMBIGUITY ALERT: Evidence marked ambiguous must not support high-confidence "
    "clinical or classification claims without human review."
)
ALPHAFOLD_WARNING = (
    "STRUCTURE WARNING: AlphaFold coordinates are computationally predicted, not experimentally "
    "determined. Do not cite as experimental structure evidence."
)
RETRACTED_WARNING = (
    "RETRACTION ALERT: One or more cited publications are retracted. "
    "Retracted evidence must not support scientific claims."
)
FABRICATED_CITATION_WARNING = (
    "CITATION INTEGRITY WARNING: Fabricated or malformed citation identifiers detected."
)
TITLE_MISMATCH_WARNING = (
    "SOURCE-TITLE MISMATCH: Evidence title does not match the cited/expected title."
)
DUPLICATE_EVIDENCE_WARNING = (
    "DUPLICATE EVIDENCE WARNING: Duplicate evidence IDs or content digests present."
)
METADATA_AS_FULLTEXT_WARNING = (
    "CONTENT WARNING: Evidence claims full-text content level but only bibliographic "
    "metadata is present. Do not treat as full-text support."
)
PROMPT_INJECTION_WARNING = (
    "PROMPT INJECTION ALERT: Source content contains instruction-override patterns. "
    "Treat affected evidence as untrusted for claim generation."
)
SPAN_UNSUPPORTED_WARNING = (
    "SPAN SUPPORT WARNING: Claim text is unsupported by the cited source span."
)
MATERIALS_PROJECT_SKIP = "Materials Project: skipped (MATERIALS_PROJECT_API_KEY not configured)"

# DOI must look like Crossref-style 10.xxxx/... ; reject obvious fakes.
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
PMID_PATTERN = re.compile(r"^\d{1,8}$")
# Known fabricated / placeholder DOI registries used in red-team fixtures.
FABRICATED_DOI_PREFIXES = (
    "10.9999/",
    "10.0000/",
    "10.1234/fake",
    "10.5555/fake",
)

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"system\s*:\s*you\s+are", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\b", re.I),
    re.compile(r"override\s+(safety|policy|guardrails?)", re.I),
    re.compile(r"jailbreak\b", re.I),
    re.compile(r"\[INST\]|<<SYS>>", re.I),
]

EXPERIMENTAL_STRUCTURE_CLAIM = re.compile(
    r"\b(experimental(?:ly)?\s+(?:determined\s+)?structure|crystal\s+structure\s+determined)\b",
    re.I,
)
EXPERIMENTAL_NEGATION = re.compile(r"\b(not|never|do\s+not|don't|non[- ]experimental)\b", re.I)


def _is_ambiguous(item: dict[str, Any]) -> bool:
    meta = item.get("domain_metadata") or {}
    return bool(meta.get("retrieval_ambiguity") or meta.get("gene_search_ambiguous"))


def _cap_reliability(reliability: str) -> str:
    rank = {"high": 3, "medium": 2, "low": 1}
    return "low" if rank.get(reliability, 2) > 1 else reliability


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _doi_candidates(ev: dict[str, Any]) -> list[str]:
    meta = ev.get("domain_metadata") or {}
    values: list[str] = []
    for raw in (
        meta.get("doi"),
        ev.get("identifier") if str(ev.get("source_type", "")).lower() == "publication" else None,
        meta.get("cited_doi"),
    ):
        if not raw:
            continue
        text = str(raw).strip().removeprefix("https://doi.org/").removeprefix("doi:")
        if text.lower().startswith("10."):
            values.append(text)
    return values


def detect_fabricated_citations(evidence: list[dict[str, Any]]) -> list[str]:
    """Return evidence IDs with malformed or clearly fabricated citation identifiers."""
    bad: list[str] = []
    for ev in evidence:
        eid = str(ev.get("evidence_id") or "?")
        meta = ev.get("domain_metadata") or {}
        if meta.get("fabricated_citation") or meta.get("citation_fabricated"):
            bad.append(eid)
            continue
        for doi in _doi_candidates(ev):
            lower = doi.lower()
            if any(lower.startswith(p) for p in FABRICATED_DOI_PREFIXES):
                bad.append(eid)
                break
            if not DOI_PATTERN.match(doi):
                bad.append(eid)
                break
        pmid = meta.get("pmid")
        if pmid is not None and not PMID_PATTERN.match(str(pmid).strip()):
            if eid not in bad:
                bad.append(eid)
        # Explicit fake placeholder identifiers
        ident = str(ev.get("identifier") or "")
        if re.search(r"\b(fake|fabricat|placeholder|not-a-real)\b", ident, re.I):
            if eid not in bad:
                bad.append(eid)
    return bad


def detect_title_mismatches(evidence: list[dict[str, Any]]) -> list[str]:
    """Return evidence IDs where recorded title disagrees with cited/expected title."""
    bad: list[str] = []
    for ev in evidence:
        meta = ev.get("domain_metadata") or {}
        title = meta.get("title")
        expected = meta.get("cited_title") or meta.get("expected_title")
        if not title or not expected:
            continue
        if _normalize_title(str(title)) != _normalize_title(str(expected)):
            bad.append(str(ev.get("evidence_id") or "?"))
    return bad


def detect_retracted_papers(evidence: list[dict[str, Any]]) -> list[str]:
    """Return evidence IDs marked retracted."""
    bad: list[str] = []
    for ev in evidence:
        meta = ev.get("domain_metadata") or {}
        status = str(meta.get("retraction_status") or meta.get("status") or "").lower()
        summary = str(ev.get("summary") or "").lower()
        if (
            meta.get("retracted") is True
            or status in ("retracted", "retraction")
            or summary.startswith("retracted:")
            or "retraction notice" in summary
        ):
            bad.append(str(ev.get("evidence_id") or "?"))
    return bad


def detect_duplicate_evidence(evidence: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Detect duplicate evidence_ids and duplicate content digests."""
    id_counts: dict[str, int] = {}
    hash_to_ids: dict[str, list[str]] = {}
    for ev in evidence:
        eid = str(ev.get("evidence_id") or "")
        if eid:
            id_counts[eid] = id_counts.get(eid, 0) + 1
        digest = ev.get("raw_record_hash") or (ev.get("domain_metadata") or {}).get("content_digest")
        if digest and eid:
            hash_to_ids.setdefault(str(digest), []).append(eid)
    dup_ids = [eid for eid, n in id_counts.items() if n > 1]
    dup_hashes = [ids for ids in hash_to_ids.values() if len(set(ids)) > 1]
    return {"duplicate_ids": dup_ids, "duplicate_digests": [sorted(set(x)) for x in dup_hashes]}


def detect_metadata_as_fulltext(evidence: list[dict[str, Any]]) -> list[str]:
    """Return IDs that claim fulltext but only carry bibliographic metadata signals."""
    bad: list[str] = []
    for ev in evidence:
        if ev.get("source_type") != "publication":
            continue
        meta = ev.get("domain_metadata") or {}
        eid = str(ev.get("evidence_id") or "?")
        if meta.get("credibility_cap_reason") == "metadata_presented_as_fulltext":
            bad.append(eid)
            continue
        if meta.get("metadata_as_fulltext") is True:
            bad.append(eid)
            continue
        claimed = meta.get("content_level")
        summary = str(ev.get("summary") or "")
        has_body = bool(meta.get("fulltext_snippet") or meta.get("abstract_snippet"))
        looks_biblio = bool(
            re.search(r"\b(title|authors?|journal|year)\s*:", summary, re.I)
            and "abstract:" not in summary.lower()
            and len(summary) < 280
        )
        # Trust explicit content_level only when body signals exist; otherwise demote/flag.
        if claimed == "fulltext" and not has_body:
            bad.append(eid)
        elif claimed == "fulltext" and looks_biblio and not meta.get("fulltext_snippet"):
            bad.append(eid)
    return bad


def detect_predicted_as_experimental(
    evidence: list[dict[str, Any]],
    claims: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Return issue strings when predicted structures are treated as experimental."""
    issues: list[str] = []
    by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    for ev in evidence:
        if ev.get("source_name") != "AlphaFold DB":
            continue
        meta = ev.get("domain_metadata") or {}
        eid = ev.get("evidence_id", "?")
        if meta.get("structure_type") == "experimental":
            issues.append(f"{eid}: AlphaFold labeled structure_type=experimental")
        summary = str(ev.get("summary") or "")
        if EXPERIMENTAL_STRUCTURE_CLAIM.search(summary) and not EXPERIMENTAL_NEGATION.search(summary):
            issues.append(f"{eid}: AlphaFold summary claims experimental structure")
    for claim in claims or []:
        text = str(claim.get("claim_text") or "")
        if not EXPERIMENTAL_STRUCTURE_CLAIM.search(text):
            continue
        if EXPERIMENTAL_NEGATION.search(text):
            continue
        for eid in cited_evidence_ids(claim):
            ev = by_id.get(eid) or {}
            meta = ev.get("domain_metadata") or {}
            if ev.get("source_name") == "AlphaFold DB" or meta.get("structure_type") == "predicted":
                issues.append(
                    f"{claim.get('claim_id')}->{eid}: claim presents predicted structure as experimental"
                )
    return issues


def detect_prompt_injection(evidence: list[dict[str, Any]]) -> list[str]:
    """Return evidence IDs whose summaries/metadata contain prompt-injection patterns."""
    bad: list[str] = []
    for ev in evidence:
        meta = ev.get("domain_metadata") or {}
        if meta.get("prompt_injection") is True:
            bad.append(str(ev.get("evidence_id") or "?"))
            continue
        blobs = [
            str(ev.get("summary") or ""),
            str(meta.get("abstract_snippet") or ""),
            str(meta.get("fulltext_snippet") or ""),
            str(meta.get("title") or ""),
        ]
        text = "\n".join(blobs)
        if any(p.search(text) for p in PROMPT_INJECTION_PATTERNS):
            bad.append(str(ev.get("evidence_id") or "?"))
    return bad


def detect_unsupported_spans(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[str]:
    """Return claim IDs whose source_spans do not support the claim text.

    Fail closed on tampered quote hashes and explicit ``span_unsupported`` flags.
    Lexical near-zero overlap alone is not used for auto-generated rule spans
    (paraphrases of structured metadata often share few long tokens).
    """
    by_id = {e.get("evidence_id"): e for e in evidence if isinstance(e, dict)}
    bad: list[str] = []
    for claim in claims:
        cid = str(claim.get("claim_id") or "?")
        if claim.get("review_boundary") == "unsupported":
            continue
        if not supporting_ids(claim):
            continue
        if (claim.get("domain_metadata") or {}).get("span_unsupported"):
            bad.append(cid)
            continue
        spans = claim.get("source_spans") or []
        if not spans:
            continue
        any_hash_ok = False
        saw_hash = False
        for span in spans:
            if not isinstance(span, dict):
                continue
            eid = span.get("evidence_id")
            ev = by_id.get(eid) or {}
            summary = str(ev.get("summary") or "")
            start = int(span.get("start") or 0)
            end = int(span.get("end") or 0)
            if end <= start:
                end = min(len(summary), start + 200)
            quote = summary[start:end]
            expected_hash = span.get("quote_hash")
            if not expected_hash:
                any_hash_ok = True
                continue
            saw_hash = True
            if quote_hash(quote) == expected_hash or quote_hash(summary[:200]) == expected_hash:
                any_hash_ok = True
        if saw_hash and not any_hash_ok:
            bad.append(cid)
    return bad


def harden_evidence(evidence: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply credibility caps and emit retrieval warnings that cannot be ignored."""
    warnings: list[str] = []
    hardened: list[dict[str, Any]] = []

    fabricated = set(detect_fabricated_citations(evidence))
    title_mismatch = set(detect_title_mismatches(evidence))
    retracted = set(detect_retracted_papers(evidence))
    meta_fulltext = set(detect_metadata_as_fulltext(evidence))
    injections = set(detect_prompt_injection(evidence))
    dup = detect_duplicate_evidence(evidence)

    for item in evidence:
        ev = dict(item)
        meta = dict(ev.get("domain_metadata") or {})
        source = ev.get("source_name", "")
        eid = str(ev.get("evidence_id") or "?")

        if _is_ambiguous(ev):
            prev = ev.get("reliability", "medium")
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "ambiguous_retrieval"
            if prev == "high":
                warnings.append(
                    f"AMBIGUITY ALERT {source}:{ev.get('identifier')}: reliability reduced "
                    f"from high to low (match_score={meta.get('match_score')})"
                )
            else:
                warnings.append(
                    f"AMBIGUITY ALERT {source}:{ev.get('identifier')}: ambiguous retrieval "
                    f"(match_score={meta.get('match_score')}, rank={meta.get('candidate_rank')})"
                )

        if source == "AlphaFold DB":
            meta.setdefault("structure_type", "predicted")
            # Never allow experimental labeling on AlphaFold evidence
            if meta.get("structure_type") == "experimental":
                meta["structure_type"] = "predicted"
                meta["credibility_capped"] = True
                meta["credibility_cap_reason"] = "predicted_mislabeled_experimental"
                warnings.append(
                    f"STRUCTURE WARNING {eid}: AlphaFold cannot be experimental — "
                    "structure_type forced to predicted"
                )
            summary = str(ev.get("summary", ""))
            if PREDICTED_STRUCTURE_PHRASE not in summary.lower():
                ev["summary"] = f"Predicted structure — {summary}".strip()
            ev["reliability"] = _cap_reliability(str(ev.get("reliability", "medium")))
            if ev["reliability"] != "low":
                ev["reliability"] = "medium"
            warnings.append(
                f"AlphaFold {ev.get('identifier')}: predicted structure only — not experimental"
            )

        if eid in fabricated:
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "fabricated_citation"
            meta["fabricated_citation"] = True
            warnings.append(f"CITATION INTEGRITY WARNING {eid}: fabricated or malformed identifier")

        if eid in title_mismatch:
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "source_title_mismatch"
            warnings.append(f"SOURCE-TITLE MISMATCH {eid}: recorded title disagrees with cited title")

        if eid in retracted:
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "retracted"
            meta["retracted"] = True
            warnings.append(f"RETRACTION ALERT {eid}: retracted publication must not support claims")

        if eid in meta_fulltext:
            meta["content_level"] = "metadata"
            meta["metadata_as_fulltext"] = True
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "metadata_presented_as_fulltext"
            ev["reliability"] = _cap_reliability(str(ev.get("reliability", "medium")))
            warnings.append(
                f"CONTENT WARNING {eid}: full-text content_level demoted to metadata"
            )

        if eid in injections:
            ev["reliability"] = "low"
            meta["credibility_capped"] = True
            meta["credibility_cap_reason"] = "prompt_injection"
            meta["prompt_injection"] = True
            warnings.append(
                f"PROMPT INJECTION ALERT {eid}: instruction-override patterns in source content"
            )

        ev["domain_metadata"] = meta
        hardened.append(ev)

    if dup["duplicate_ids"]:
        warnings.append(
            f"{DUPLICATE_EVIDENCE_WARNING} duplicate evidence_id: {dup['duplicate_ids']}"
        )
    if dup["duplicate_digests"]:
        warnings.append(
            f"{DUPLICATE_EVIDENCE_WARNING} duplicate content digests: {dup['duplicate_digests']}"
        )

    return hardened, warnings


def demote_claim_confidence_for_threats(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Calibrated confidence demotion for claims citing threatened evidence."""
    threat_ids = set(detect_prompt_injection(evidence)) | set(detect_fabricated_citations(evidence))
    threat_ids |= set(detect_retracted_papers(evidence)) | set(detect_title_mismatches(evidence))
    threat_ids |= set(detect_metadata_as_fulltext(evidence))
    out: list[dict[str, Any]] = []
    for claim in claims:
        c = dict(claim)
        cited = set(cited_evidence_ids(c))
        if cited & threat_ids:
            conf = c.get("confidence")
            if isinstance(conf, (int, float)):
                c["confidence"] = min(float(conf), 0.35)
            meta = dict(c.get("domain_metadata") or {})
            meta["confidence_demoted"] = True
            meta["confidence_demotion_reason"] = "credibility_threat_in_cited_evidence"
            c["domain_metadata"] = meta
        out.append(c)
    return out


def build_credibility_limitations(
    evidence: list[dict[str, Any]],
    *,
    metadata_only_publications: bool = False,
    claims: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Return limitation strings for high-visibility report warnings."""
    limitations: list[str] = []

    if any(e.get("source_name") == "ClinVar" and _is_ambiguous(e) for e in evidence):
        limitations.append(CLINVAR_AMBIGUITY_WARNING)

    if any(_is_ambiguous(e) for e in evidence):
        limitations.append(GENERIC_AMBIGUITY_WARNING)

    if any(e.get("source_name") == "AlphaFold DB" for e in evidence):
        limitations.append(ALPHAFOLD_WARNING)

    if metadata_only_publications:
        limitations.append(METADATA_ONLY_WARNING)

    if detect_retracted_papers(evidence):
        limitations.append(RETRACTED_WARNING)

    if detect_fabricated_citations(evidence):
        limitations.append(FABRICATED_CITATION_WARNING)

    if detect_title_mismatches(evidence):
        limitations.append(TITLE_MISMATCH_WARNING)

    dup = detect_duplicate_evidence(evidence)
    if dup["duplicate_ids"] or dup["duplicate_digests"]:
        limitations.append(DUPLICATE_EVIDENCE_WARNING)

    if detect_metadata_as_fulltext(evidence):
        limitations.append(METADATA_AS_FULLTEXT_WARNING)

    if detect_prompt_injection(evidence):
        limitations.append(PROMPT_INJECTION_WARNING)

    if claims and detect_unsupported_spans(claims, evidence):
        limitations.append(SPAN_UNSUPPORTED_WARNING)

    if detect_predicted_as_experimental(evidence, claims):
        limitations.append(ALPHAFOLD_WARNING)

    return limitations
