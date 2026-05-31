"""Rule-based claim extraction from retrieved evidence (no LLM source invention)."""

from __future__ import annotations

from typing import Any

from vsa.connectors.content_level import abstract_snippet, has_abstract_content, infer_content_level

PROMPT_TEMPLATE_VERSION = "claim_extraction_v1"


def _boundary_for_claim(claim_type: str, evidence: list[dict[str, Any]]) -> str:
    clinical_terms = ("pathogenic", "clinical", "diagnosis", "prognosis", "therapy")
    text_blob = " ".join(
        str(e.get("summary", "")) + " " + str((e.get("domain_metadata") or {}))
        for e in evidence
    ).lower()
    if any(t in text_blob for t in clinical_terms):
        return "requires_clinical_review"
    if claim_type == "hypothesis":
        return "speculative"
    if claim_type in ("summary", "observation", "identity", "structure"):
        return "requires_domain_review"
    return "requires_domain_review"


def _evidence_by_source(evidence: list[dict[str, Any]], source: str) -> dict[str, Any] | None:
    return next((e for e in evidence if e.get("source_name") == source), None)


def _variant_claims(subject: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gene = subject.get("gene_symbol", "Unknown")
    variant = subject.get("variant_hgvs_c", "")
    claims: list[dict[str, Any]] = []
    cid = 1

    clinvar = _evidence_by_source(evidence, "ClinVar")
    if clinvar:
        meta = clinvar.get("domain_metadata") or {}
        sig = meta.get("clinical_significance", "")
        ambiguous = meta.get("retrieval_ambiguity", False)
        rank = meta.get("candidate_rank", 1)
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "identity",
                "claim_text": (
                    f"Variant {gene} {variant} matches ClinVar record {clinvar.get('identifier')} "
                    f"(retrieval strategy: {meta.get('retrieval_strategy', 'unknown')})."
                ),
                "evidence_ids": [clinvar["evidence_id"]],
                "confidence": 0.75 if ambiguous or rank > 1 else 0.88,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium" if ambiguous else "low",
                "support_level": "medium" if ambiguous else "high",
            }
        )
        cid += 1
        if sig:
            claims.append(
                {
                    "claim_id": f"C{cid:03d}",
                    "claim_type": "classification",
                    "claim_text": (
                        f"{gene} {variant} is recorded in ClinVar with clinical significance: {sig}."
                    ),
                    "evidence_ids": [clinvar["evidence_id"]],
                    "confidence": 0.7 if ambiguous else 0.85,
                    "review_boundary": _boundary_for_claim("classification", [clinvar]),
                    "uncertainty_level": "medium" if ambiguous else "low",
                    "support_level": "medium" if ambiguous else "high",
                }
            )
            cid += 1
        if ambiguous:
            claims.append(
                {
                    "claim_id": f"C{cid:03d}",
                    "claim_type": "observation",
                    "claim_text": (
                        f"ClinVar retrieval for {gene} {variant} is ambiguous; "
                        "multiple candidate records may match this query."
                    ),
                    "evidence_ids": [clinvar["evidence_id"]],
                    "confidence": 0.65,
                    "review_boundary": "requires_clinical_review",
                    "uncertainty_level": "high",
                    "support_level": "insufficient",
                }
            )
            cid += 1

    uniprot = _evidence_by_source(evidence, "UniProt")
    if uniprot:
        entry_type = (uniprot.get("domain_metadata") or {}).get("entry_type", "unknown")
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "identity",
                "claim_text": (
                    f"{gene} protein record is available in UniProt ({uniprot.get('identifier')}); "
                    f"entry type: {entry_type}."
                ),
                "evidence_ids": [uniprot["evidence_id"]],
                "confidence": 0.92 if entry_type == "reviewed" else 0.78,
                "review_boundary": "safe_summary",
                "uncertainty_level": "low",
                "support_level": "high" if entry_type == "reviewed" else "medium",
            }
        )
        cid += 1

    return claims


def _paper_claims(subject: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    doi = subject.get("doi") or subject.get("display_name", "")
    primary = evidence[0]
    claims: list[dict[str, Any]] = [
        {
            "claim_id": "C001",
            "claim_type": "identity",
            "claim_text": (
                f"Publication bibliographic record retrieved for DOI {doi} "
                f"from {primary.get('source_name')} ({primary.get('identifier')})."
            ),
            "evidence_ids": [primary["evidence_id"]],
            "confidence": 0.9,
            "review_boundary": "safe_summary",
            "uncertainty_level": "low",
            "support_level": "high",
        }
    ]

    abstract_sources = [e for e in evidence if has_abstract_content(e)]
    if abstract_sources:
        best = abstract_sources[0]
        snippet = abstract_snippet(best)
        level = infer_content_level(best)
        claims.append(
            {
                "claim_id": "C002",
                "claim_type": "observation",
                "claim_text": (
                    f"Abstract-level content ({level}) available from {best.get('source_name')}: "
                    f"{snippet}"
                ),
                "evidence_ids": [best["evidence_id"]],
                "confidence": 0.82 if level == "abstract" else 0.75,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium",
                "support_level": "medium",
            }
        )
    else:
        claims.append(
            {
                "claim_id": "C002",
                "claim_type": "observation",
                "claim_text": (
                    "Only bibliographic metadata retrieved; no abstract or full-text body "
                    "available in evidence bundle."
                ),
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.85,
                "review_boundary": "safe_summary",
                "uncertainty_level": "low",
                "support_level": "insufficient",
            }
        )

    fulltext = [e for e in evidence if infer_content_level(e) == "fulltext"]
    if fulltext:
        claims.append(
            {
                "claim_id": "C003",
                "claim_type": "summary",
                "claim_text": (
                    f"Full-text record flagged available via {fulltext[0].get('source_name')}; "
                    "claims remain abstract/metadata-derived until full text is ingested."
                ),
                "evidence_ids": [fulltext[0]["evidence_id"]],
                "confidence": 0.7,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium",
                "support_level": "medium",
            }
        )

    return claims


def extract_claims(subject: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Produce atomic claims referencing only retrieved evidence IDs.
    Does not invent source fields — claims map strictly to evidence_ids.
    """
    if not evidence:
        return []

    evidence_by_id = {e["evidence_id"]: e for e in evidence}
    claims: list[dict[str, Any]] = []
    entity_type = subject.get("entity_type", "experiment")

    if entity_type == "variant":
        claims = _variant_claims(subject, evidence)

    elif entity_type == "protein":
        primary = evidence[0]
        eids = [primary["evidence_id"]]
        alphafold = _evidence_by_source(evidence, "AlphaFold DB")
        if alphafold:
            eids.append(alphafold["evidence_id"])
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "structure" if alphafold else "summary",
                "claim_text": (
                    f"Protein {subject.get('protein_accession', primary.get('identifier'))} "
                    f"has curated metadata in {primary.get('source_name')}."
                    + (
                        " Predicted structure available in AlphaFold DB (not experimental)."
                        if alphafold
                        else ""
                    )
                ),
                "evidence_ids": eids,
                "confidence": 0.9,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "low",
                "support_level": "high",
            }
        )

    elif entity_type == "paper":
        claims = _paper_claims(subject, evidence)

    elif entity_type == "material":
        mp = _evidence_by_source(evidence, "Materials Project") or evidence[0]
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "property",
                "claim_text": f"Material {subject.get('material_id', subject.get('display_name'))} has curated metadata in {mp.get('source_name')}.",
                "evidence_ids": [mp["evidence_id"]],
                "confidence": 0.88,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "low",
                "support_level": "high",
            }
        )

    else:
        primary = evidence[0]
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "observation",
                "claim_text": f"Evidence retrieved for subject '{subject.get('display_name')}': {primary.get('summary', '')[:180]}.",
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.75,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium",
                "support_level": "medium",
            }
        )

    if not claims:
        primary = evidence[0]
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "observation",
                "claim_text": f"Evidence retrieved: {primary.get('summary', '')[:180]}.",
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.7,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium",
                "support_level": "medium",
            }
        )

    for claim in claims:
        for eid in claim["evidence_ids"]:
            if eid not in evidence_by_id:
                claim["review_boundary"] = "unsupported"
                claim["confidence"] = 0.0

    return claims
