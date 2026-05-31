"""Base types and utilities for read-only database connectors."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from vsa.utils import canonical_json


@dataclass
class NormalizedEvidence:
    source_name: str
    source_type: str
    identifier: str
    retrieval_path: str
    retrieved_at: str
    summary: str
    raw_record: dict[str, Any] = field(default_factory=dict)
    evidence_role: str = "supports"
    reliability: str = "high"
    domain_metadata: dict[str, Any] = field(default_factory=dict)

    def raw_record_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.raw_record).encode("utf-8")).hexdigest()

    def to_dict(self, evidence_id: str) -> dict[str, Any]:
        return {
            "evidence_id": evidence_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "identifier": self.identifier,
            "retrieval_path": self.retrieval_path,
            "retrieved_at": self.retrieved_at,
            "summary": self.summary,
            "raw_record_hash": self.raw_record_hash(),
            "evidence_role": self.evidence_role,
            "reliability": self.reliability,
            "domain_metadata": self.domain_metadata,
        }


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Connector(ABC):
    name: str

    @abstractmethod
    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        """Fetch normalized evidence for a structured query."""


def summarize_record(record: dict[str, Any], keys: list[str]) -> str:
    parts = []
    for key in keys:
        val = record.get(key)
        if val:
            parts.append(f"{key}: {val}")
    return "; ".join(parts) if parts else json.dumps(record)[:500]
