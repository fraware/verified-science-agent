"""Publication content-level classification for evidence records."""

from __future__ import annotations

from typing import Any

CONTENT_LEVELS = ("metadata", "abstract", "fulltext")


def infer_content_level(evidence: dict[str, Any]) -> str:
    meta = evidence.get("domain_metadata") or {}
    level = meta.get("content_level")
    if level in CONTENT_LEVELS:
        return level
    summary = str(evidence.get("summary", "")).lower()
    if "abstract:" in summary and len(summary.split("abstract:", 1)[-1].strip()) > 40:
        return "abstract"
    return "metadata"


def has_abstract_content(evidence: dict[str, Any]) -> bool:
    return infer_content_level(evidence) in ("abstract", "fulltext")


def abstract_snippet(evidence: dict[str, Any], limit: int = 220) -> str:
    meta = evidence.get("domain_metadata") or {}
    if meta.get("abstract_snippet"):
        return str(meta["abstract_snippet"])[:limit]
    summary = str(evidence.get("summary", ""))
    if "abstract:" in summary.lower():
        part = summary.split("abstract:", 1)[-1].strip()
        if part:
            return part[:limit]
    return summary[:limit]
