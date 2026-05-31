"""Rule-based claim extraction from retrieved evidence (no LLM source invention)."""

from __future__ import annotations

from typing import Any

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
        gene = subject.get("gene_symbol", "Unknown")
        variant = subject.get("variant_hgvs_c", "")
        clinvar = next((e for e in evidence if e.get("source_name") == "ClinVar"), evidence[0])
        eids = [clinvar["evidence_id"]]
        sig = (clinvar.get("domain_metadata") or {}).get("clinical_significance", "")
        claim_text = f"{gene} {variant} is recorded in ClinVar"
        if sig:
            claim_text += f" with significance: {sig}."
        else:
            claim_text += "."
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "classification",
                "claim_text": claim_text,
                "evidence_ids": eids,
                "confidence": 0.85 if sig else 0.7,
                "review_boundary": _boundary_for_claim("classification", [clinvar]),
                "uncertainty_level": "low" if sig else "medium",
                "support_level": "high" if sig else "medium",
            }
        )
        uniprot = next((e for e in evidence if e.get("source_name") == "UniProt"), None)
        if uniprot:
            claims.append(
                {
                    "claim_id": "C002",
                    "claim_type": "identity",
                    "claim_text": f"{gene} protein record is available in UniProt ({uniprot.get('identifier')}).",
                    "evidence_ids": [uniprot["evidence_id"]],
                    "confidence": 0.92,
                    "review_boundary": "safe_summary",
                    "uncertainty_level": "low",
                    "support_level": "high",
                }
            )

    elif entity_type == "protein":
        primary = evidence[0]
        eids = [primary["evidence_id"]]
        alphafold = next((e for e in evidence if e.get("source_name") == "AlphaFold DB"), None)
        if alphafold:
            eids.append(alphafold["evidence_id"])
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "structure" if alphafold else "summary",
                "claim_text": (
                    f"Protein {subject.get('protein_accession', primary.get('identifier'))} "
                    f"has curated metadata in {primary.get('source_name')}."
                    + (" Predicted structure available in AlphaFold DB." if alphafold else "")
                ),
                "evidence_ids": eids,
                "confidence": 0.9,
                "review_boundary": "requires_domain_review",
                "uncertainty_level": "low",
                "support_level": "high",
            }
        )

    elif entity_type == "paper":
        primary = evidence[0]
        claims.append(
            {
                "claim_id": "C001",
                "claim_type": "summary",
                "claim_text": f"Publication metadata retrieved for DOI {subject.get('doi')}: {primary.get('summary', '')[:200]}.",
                "evidence_ids": [primary["evidence_id"]],
                "confidence": 0.88,
                "review_boundary": "safe_summary",
                "uncertainty_level": "low",
                "support_level": "high",
            }
        )

    elif entity_type == "material":
        mp = next((e for e in evidence if e.get("source_name") == "Materials Project"), evidence[0])
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

    # Validate all evidence_ids exist
    for claim in claims:
        for eid in claim["evidence_ids"]:
            if eid not in evidence_by_id:
                claim["review_boundary"] = "unsupported"
                claim["confidence"] = 0.0

    return claims
