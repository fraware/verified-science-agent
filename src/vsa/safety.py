"""Safety and non-clinical boundary messaging."""

from __future__ import annotations

CLINICAL_DISCLAIMER = (
    "Research infrastructure output. Not for diagnosis, treatment, or "
    "clinical decision-making without qualified expert review."
)

VARIANT_DISCLAIMER = (
    f"{CLINICAL_DISCLAIMER} Variant classifications require qualified "
    "genetics expert review before any clinical use."
)


def disclaimer_for_subject(subject: dict) -> str:
    entity = subject.get("entity_type", "")
    if entity in ("variant", "gene", "disease"):
        return VARIANT_DISCLAIMER
    return CLINICAL_DISCLAIMER
