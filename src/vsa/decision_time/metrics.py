"""Privacy-safe pilot metrics (counts and histograms only)."""

from __future__ import annotations

from collections import Counter
from typing import Any


def privacy_safe_metrics(
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate metrics without raw partner payloads, keys, or private rationales."""
    severity = Counter(str(c.get("severity") or "unknown") for c in contradictions)
    uncertainty = Counter(str(c.get("uncertainty_level") or "unspecified") for c in claims)
    return {
        "included_source_count": len(included),
        "excluded_source_count": len(excluded),
        "contradiction_severity_histogram": dict(severity),
        "uncertainty_distribution": dict(uncertainty),
    }
