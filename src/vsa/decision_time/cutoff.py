"""Cutoff timestamp parsing and evidence inclusion filter.

Precedence for effective timestamp (first present wins):
1. source_timestamp (explicit source/event time)
2. published_at / publication_date (domain_metadata or top-level)
3. retrieved_at (retrieval clock)

Evidence with effective_ts > decision_time_cutoff is excluded and disclosed.
Missing timestamps always fail closed (all modes): indeterminate time cannot be
classified as pre- or post-cutoff.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def evidence_effective_timestamp(evidence: dict[str, Any]) -> tuple[datetime | None, str | None]:
    """Return (effective_datetime, field_name) using documented precedence."""
    meta = evidence.get("domain_metadata") or {}
    candidates = [
        ("source_timestamp", evidence.get("source_timestamp")),
        (
            "published_at",
            evidence.get("published_at")
            or meta.get("published_at")
            or meta.get("publication_date"),
        ),
        ("retrieved_at", evidence.get("retrieved_at")),
    ]
    for name, raw in candidates:
        if raw:
            return parse_timestamp(str(raw)), name
    return None, None


def apply_cutoff_filter(
    evidence: list[dict[str, Any]],
    cutoff: str,
    *,
    require_timestamps: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Split evidence into included and excluded_post_cutoff lists.

    Returns (included, excluded_records, errors).

    Missing timestamps always produce errors (fail closed). The
    ``require_timestamps`` keyword is retained for call-site compatibility; it
    does not relax fail-closed behavior (passing False is ignored).
    """
    del require_timestamps  # always fail closed; kept for API compatibility
    cutoff_dt = parse_timestamp(cutoff)
    if cutoff_dt is None:
        raise ValueError(f"decision_time_cutoff required and must be ISO-8601: {cutoff!r}")

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    errors: list[str] = []

    for item in evidence:
        if not isinstance(item, dict):
            errors.append("evidence item is not an object")
            continue
        eid = str(item.get("evidence_id") or "?")
        effective, field_name = evidence_effective_timestamp(item)
        if effective is None:
            errors.append(
                f"{eid}: missing source/publication/retrieval timestamp "
                "(indeterminate; fail closed)"
            )
            continue
        if effective > cutoff_dt:
            excluded.append(
                {
                    "evidence_id": eid,
                    "reason": (
                        f"effective timestamp {field_name}={effective.isoformat().replace('+00:00', 'Z')} "
                        f"after decision_time_cutoff {cutoff}"
                    ),
                    "effective_timestamp": effective.isoformat().replace("+00:00", "Z"),
                    "raw_record_hash": item.get("raw_record_hash"),
                    "summary": item.get("summary"),
                }
            )
        else:
            included.append(item)

    return included, excluded, errors
