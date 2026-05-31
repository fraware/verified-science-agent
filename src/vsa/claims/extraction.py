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


def _evidence_all_by_source(evidence: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [e for e in evidence if e.get("source_name") == source]


def _clinvar_review_status(record: dict[str, Any]) -> str:
    for key in ("review_status", "review_status_explanation", "last_evaluated"):
        val = record.get(key)
        if val:
            return str(val)
    return "not_reported"


def _clinvar_disease_context(record: dict[str, Any]) -> str:
    title = str(record.get("title", "")).strip()
    return title if len(title) > 12 else ""


def _variant_claims(subject: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gene = subject.get("gene_symbol", "Unknown")
    variant = subject.get("variant_hgvs_c", "")
    claims: list[dict[str, Any]] = []
    cid = 1

    clinvar_records = _evidence_all_by_source(evidence, "ClinVar")
    primary_clinvar = clinvar_records[0] if clinvar_records else None

    if primary_clinvar:
        meta = primary_clinvar.get("domain_metadata") or {}
        raw = primary_clinvar.get("raw_record") or {}
        sig = meta.get("clinical_significance", "")
        ambiguous = meta.get("retrieval_ambiguity", False)
        rank = meta.get("candidate_rank", 1)
        review_status = _clinvar_review_status(raw)
        disease = _clinvar_disease_context(raw)

        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "identity",
                "claim_text": (
                    f"Variant {gene} {variant} matches ClinVar record {primary_clinvar.get('identifier')} "
                    f"(strategy: {meta.get('retrieval_strategy', 'unknown')}, rank {rank})."
                ),
                "evidence_ids": [primary_clinvar["evidence_id"]],
                "confidence": 0.75 if ambiguous or rank > 1 else 0.88,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "medium" if ambiguous else "low",
                "support_level": "medium" if ambiguous else "high",
            }
        )
        cid += 1

        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "identity",
                "claim_text": (
                    f"ClinVar database record identity: UID {meta.get('entrez_uid', '?')}, "
                    f"identifier {primary_clinvar.get('identifier')}."
                ),
                "evidence_ids": [primary_clinvar["evidence_id"]],
                "confidence": 0.9 if not ambiguous else 0.7,
                "review_boundary": "safe_summary",
                "uncertainty_level": "low" if not ambiguous else "medium",
                "support_level": "high" if not ambiguous else "medium",
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
                    "evidence_ids": [primary_clinvar["evidence_id"]],
                    "confidence": 0.7 if ambiguous else 0.85,
                    "review_boundary": _boundary_for_claim("classification", [primary_clinvar]),
                    "uncertainty_level": "medium" if ambiguous else "low",
                    "support_level": "medium" if ambiguous else "high",
                }
            )
            cid += 1

        if review_status != "not_reported":
            claims.append(
                {
                    "claim_id": f"C{cid:03d}",
                    "claim_type": "observation",
                    "claim_text": f"ClinVar review status for this record: {review_status}.",
                    "evidence_ids": [primary_clinvar["evidence_id"]],
                    "confidence": 0.8,
                    "review_boundary": "requires_domain_review",
                    "uncertainty_level": "low",
                    "support_level": "medium",
                }
            )
            cid += 1

        if disease:
            claims.append(
                {
                    "claim_id": f"C{cid:03d}",
                    "claim_type": "observation",
                    "claim_text": f"ClinVar disease/phenotype context from record title: {disease[:200]}.",
                    "evidence_ids": [primary_clinvar["evidence_id"]],
                    "confidence": 0.72,
                    "review_boundary": "requires_clinical_review",
                    "uncertainty_level": "medium",
                    "support_level": "medium",
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
                    "evidence_ids": [primary_clinvar["evidence_id"]],
                    "confidence": 0.65,
                    "review_boundary": "requires_clinical_review",
                    "uncertainty_level": "high",
                    "support_level": "insufficient",
                }
            )
            cid += 1

        if len(clinvar_records) > 1:
            secondary = clinvar_records[1]
            sec_meta = secondary.get("domain_metadata") or {}
            sec_sig = sec_meta.get("clinical_significance", "")
            pri_sig = sig
            if sec_sig and pri_sig and sec_sig != pri_sig:
                claims.append(
                    {
                        "claim_id": f"C{cid:03d}",
                        "claim_type": "observation",
                        "claim_text": (
                            f"Conflicting ClinVar candidates: primary significance '{pri_sig}' vs "
                            f"candidate rank {sec_meta.get('candidate_rank', 2)} significance '{sec_sig}'."
                        ),
                        "evidence_ids": [primary_clinvar["evidence_id"], secondary["evidence_id"]],
                        "confidence": 0.6,
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
    claims: list[dict[str, Any]] = []
    cid = 1

    claims.append(
        {
            "claim_id": f"C{cid:03d}",
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
    )
    cid += 1

    abstract_sources = [e for e in evidence if has_abstract_content(e)]
    if abstract_sources:
        best = abstract_sources[0]
        snippet = abstract_snippet(best)
        level = infer_content_level(best)
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
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
        cid += 1
    else:
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "observation",
                "claim_text": (
                    "SCIENTIFIC CREDIBILITY WARNING: Only bibliographic metadata retrieved; no abstract "
                    "or full-text body available in evidence bundle."
                ),
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.55,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "high",
                "support_level": "insufficient",
            }
        )
        cid += 1
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
                "claim_type": "summary",
                "claim_text": (
                    "Source limitation: scientific claims in this report cannot exceed bibliographic "
                    "metadata until abstract or full-text evidence is retrieved."
                ),
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.6,
                "review_boundary": "safe_summary",
                "uncertainty_level": "low",
                "support_level": "insufficient",
            }
        )
        cid += 1

    fulltext = [e for e in evidence if infer_content_level(e) == "fulltext"]
    if fulltext:
        claims.append(
            {
                "claim_id": f"C{cid:03d}",
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
        primary = _evidence_by_source(evidence, "UniProt") or evidence[0]
        alphafold = _evidence_by_source(evidence, "AlphaFold DB")
        entry_type = (primary.get("domain_metadata") or {}).get("entry_type", "unknown")
        accession = subject.get("protein_accession", primary.get("identifier"))

        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "identity",
                "claim_text": (
                    f"Protein {accession} has curated metadata in {primary.get('source_name')} "
                    f"(entry type: {entry_type})."
                ),
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.92 if entry_type == "reviewed" else 0.78,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "low",
                "support_level": "high" if entry_type == "reviewed" else "medium",
            }
        )
        if alphafold:
            claims.append(
                {
                    "claim_id": "C002",
                    "claim_type": "structure",
                    "claim_text": (
                        f"Predicted structure for {accession} is available in AlphaFold DB; "
                        "this is a computational model, not an experimental structure."
                    ),
                    "evidence_ids": [alphafold["evidence_id"]],
                    "confidence": 0.85,
                    "review_boundary": "requires_domain_review",
                    "uncertainty_level": "medium",
                    "support_level": "medium",
                }
            )
            claims.append(
                {
                    "claim_id": "C003",
                    "claim_type": "observation",
                    "claim_text": (
                        "STRUCTURE WARNING: AlphaFold coordinates are predicted; do not treat as "
                        "experimental evidence from crystallography or cryo-EM."
                    ),
                    "evidence_ids": [alphafold["evidence_id"]],
                    "confidence": 0.95,
                    "review_boundary": "safe_summary",
                    "uncertainty_level": "low",
                    "support_level": "high",
                }
            )

    elif entity_type == "paper":
        claims = _paper_claims(subject, evidence)

    elif entity_type == "material":
        mp = _evidence_by_source(evidence, "Materials Project") or evidence[0]
        material_id = subject.get("material_id", subject.get("display_name"))
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "identity",
                "claim_text": f"Material {material_id} has a curated record in {mp.get('source_name')}.",
                "evidence_ids": [mp["evidence_id"]],
                "confidence": 0.88,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "low",
                "support_level": "high",
            }
        )
        meta = mp.get("domain_metadata") or {}
        if meta.get("formula") or meta.get("band_gap") is not None:
            props = []
            if meta.get("formula"):
                props.append(f"formula {meta['formula']}")
            if meta.get("band_gap") is not None:
                props.append(f"band gap {meta['band_gap']} eV")
            claims.append(
                {
                    "claim_id": "C002",
                    "claim_type": "property",
                    "claim_text": f"Reported material properties from {mp.get('source_name')}: {', '.join(props)}.",
                    "evidence_ids": [mp["evidence_id"]],
                    "confidence": 0.82,
                    "review_boundary": "requires_domain_review",
                    "uncertainty_level": "medium",
                    "support_level": "medium",
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
