"""Privacy-safe pilot metrics (counts and histograms only)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

ALLOWED_METRIC_KEYS = frozenset(
    {
        "included_source_count",
        "excluded_source_count",
        "contradiction_severity_histogram",
        "uncertainty_distribution",
    }
)

# Reject hex digests and common secret-shaped tokens if they leak into metrics.
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_SECRETISH = re.compile(
    r"(private[_-]?key|api[_-]?key|authorization|bearer\s|-----BEGIN)",
    re.I,
)


def assert_privacy_safe_metrics(metrics: dict[str, Any] | None) -> list[str]:
    """Return errors if metrics contain payloads beyond counts/histograms."""
    if metrics is None:
        return []
    if not isinstance(metrics, dict):
        return ["privacy_safe_metrics must be an object"]
    errors: list[str] = []
    extra = set(metrics) - ALLOWED_METRIC_KEYS
    if extra:
        errors.append(f"privacy_safe_metrics has disallowed keys: {sorted(extra)}")
    for key in ("included_source_count", "excluded_source_count"):
        if key in metrics and not isinstance(metrics[key], int):
            errors.append(f"{key} must be int")
        elif key in metrics and int(metrics[key]) < 0:
            errors.append(f"{key} must be >= 0")
    for hist_key in ("contradiction_severity_histogram", "uncertainty_distribution"):
        hist = metrics.get(hist_key)
        if hist is None:
            continue
        if not isinstance(hist, dict):
            errors.append(f"{hist_key} must be an object")
            continue
        for k, v in hist.items():
            if not isinstance(k, str) or not isinstance(v, int) or v < 0:
                errors.append(f"{hist_key} entries must be string->non-negative int")
                break
            if _HEX64.match(k) or _SECRETISH.search(k):
                errors.append(f"{hist_key} key looks like digest/secret: {k!r}")
    blob = str(metrics)
    if _SECRETISH.search(blob):
        errors.append("privacy_safe_metrics blob matches secret-like pattern")
    return errors


def privacy_safe_metrics(
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate metrics without raw partner payloads, keys, or private rationales."""
    severity = Counter(str(c.get("severity") or "unknown") for c in contradictions)
    uncertainty = Counter(str(c.get("uncertainty_level") or "unspecified") for c in claims)
    metrics: dict[str, Any] = {
        "included_source_count": len(included),
        "excluded_source_count": len(excluded),
        "contradiction_severity_histogram": dict(severity),
        "uncertainty_distribution": dict(uncertainty),
    }
    leaks = assert_privacy_safe_metrics(metrics)
    if leaks:
        raise ValueError("privacy_safe_metrics failed privacy check: " + "; ".join(leaks))
    return metrics
