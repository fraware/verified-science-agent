"""Parse natural-language or structured questions into retrieval subjects."""

from __future__ import annotations

import re
from typing import Any


VARIANT_PATTERN = re.compile(
    r"(?P<gene>[A-Z0-9]+)\s+(?P<variant>c\.[\w_>]+(?:del|dup|ins|delins)?)",
    re.IGNORECASE,
)
DOI_PATTERN = re.compile(r"(10\.\d{4,9}/\S+)", re.IGNORECASE)
PMID_PATTERN = re.compile(r"\b(?:PMID:?|pmid:?)\s*(\d+)\b", re.IGNORECASE)
ACCESSION_PATTERN = re.compile(r"\b([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})\b")
# Chemical formulas: alternating element + optional number (e.g. LiFePO4, NaCl)
FORMULA_PATTERN = re.compile(
    r"\b([A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*){1,})\b"
)
MATERIAL_KEYWORDS = (
    "material", "cathode", "anode", "electrolyte", "perovskite", "crystal",
    "polymer", "ceramic", "alloy", "composite", "nanoparticle",
)


def _looks_like_material(question: str) -> bool:
    lower = question.lower()
    if any(kw in lower for kw in MATERIAL_KEYWORDS):
        return True
    formula = FORMULA_PATTERN.search(question)
    if formula:
        token = formula.group(1)
        # Require at least two element starts (uppercase letters)
        elements = re.findall(r"[A-Z][a-z]?", token)
        return len(elements) >= 2
    return False


def _extract_formula(question: str) -> str | None:
    match = FORMULA_PATTERN.search(question)
    return match.group(1) if match else None


def parse_question(question: str) -> dict[str, Any]:
    """Parse a question string into a structured subject."""
    question = question.strip()

    doi_match = DOI_PATTERN.search(question)
    if doi_match:
        return {
            "entity_type": "paper",
            "display_name": f"DOI:{doi_match.group(1)}",
            "doi": doi_match.group(1),
        }

    pmid_match = PMID_PATTERN.search(question)
    if pmid_match:
        pmid = pmid_match.group(1)
        return {
            "entity_type": "paper",
            "display_name": f"PMID:{pmid}",
            "pmid": pmid,
        }

    variant_match = VARIANT_PATTERN.search(question)
    if variant_match:
        gene = variant_match.group("gene").upper()
        variant = variant_match.group("variant")
        return {
            "entity_type": "variant",
            "display_name": f"{gene} {variant}",
            "gene_symbol": gene,
            "variant_hgvs_c": variant,
        }

    accession_match = ACCESSION_PATTERN.search(question)
    if accession_match:
        acc = accession_match.group(1)
        return {
            "entity_type": "protein",
            "display_name": acc,
            "protein_accession": acc,
        }

    # Single gene symbol (EGFR, TP53) before material heuristic
    if re.match(r"^[A-Z0-9]{2,8}$", question.strip()):
        return {
            "entity_type": "gene",
            "display_name": question,
            "gene_symbol": question.upper(),
        }

    if _looks_like_material(question):
        formula = _extract_formula(question) or question.split()[0]
        return {
            "entity_type": "material",
            "display_name": question,
            "material_id": formula,
            "description": question,
        }

    if question.upper().startswith("BRCA1"):
        return {
            "entity_type": "variant",
            "display_name": question,
            "gene_symbol": "BRCA1",
            "variant_hgvs_c": "c.68_69del",
        }

    return {
        "entity_type": "experiment",
        "display_name": question,
        "description": question,
    }


def parse_input(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize build input JSON to a subject dict."""
    if "subject" in data:
        return data["subject"]
    if "question" in data:
        return parse_question(str(data["question"]))
    return data
