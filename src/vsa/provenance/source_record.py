"""Immutable SourceRecord contract — authority for retrieved source material."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from vsa.utils import canonical_json

AUTHORITATIVE_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "canonical_url",
        "accession",
        "retrieved_at",
        "content_digest",
        "media_type",
        "database_version",
        "query",
        "raw_response_retention",
        "license",
        "connector",
        "transformation_history",
        "source_availability",
    }
)

RETENTION_VALUES = frozenset({"retained", "digest_only", "unavailable"})
AVAILABILITY_VALUES = frozenset({"available", "cached", "unavailable", "substituted"})

_SAFE_ID = re.compile(r"[^a-zA-Z0-9._-]+")


@dataclass
class TransformationStep:
    op: str
    at: str
    digest_in: str
    digest_out: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class SourceRecord:
    """Immutable retrieved-source authority. Evidence is a view over these digests."""

    source_id: str
    canonical_url: str
    accession: str
    retrieved_at: str
    content_digest: str
    media_type: str
    database_version: str | None
    query: dict[str, Any]
    raw_response_retention: str
    license: str
    connector: str
    transformation_history: list[TransformationStep] = field(default_factory=list)
    source_availability: str = "available"

    def __post_init__(self) -> None:
        if self.raw_response_retention not in RETENTION_VALUES:
            raise ValueError(f"invalid raw_response_retention: {self.raw_response_retention!r}")
        if self.source_availability not in AVAILABILITY_VALUES:
            raise ValueError(f"invalid source_availability: {self.source_availability!r}")
        if not re.fullmatch(r"[a-f0-9]{64}", self.content_digest):
            raise ValueError("content_digest must be 64 lowercase hex chars")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "canonical_url": self.canonical_url,
            "accession": self.accession,
            "retrieved_at": self.retrieved_at,
            "content_digest": self.content_digest,
            "media_type": self.media_type,
            "database_version": self.database_version,
            "query": dict(self.query),
            "raw_response_retention": self.raw_response_retention,
            "license": self.license,
            "connector": self.connector,
            "transformation_history": [t.to_dict() for t in self.transformation_history],
            "source_availability": self.source_availability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRecord:
        history = [
            TransformationStep(**step) if isinstance(step, dict) else step
            for step in (data.get("transformation_history") or [])
        ]
        return cls(
            source_id=str(data["source_id"]),
            canonical_url=str(data.get("canonical_url") or ""),
            accession=str(data.get("accession") or ""),
            retrieved_at=str(data["retrieved_at"]),
            content_digest=str(data["content_digest"]),
            media_type=str(data.get("media_type") or "application/json"),
            database_version=data.get("database_version"),
            query=dict(data.get("query") or {}),
            raw_response_retention=str(data.get("raw_response_retention") or "digest_only"),
            license=str(data.get("license") or "unknown"),
            connector=str(data["connector"]),
            transformation_history=list(history),
            source_availability=str(data.get("source_availability") or "available"),
        )


def content_digest_for(raw: Any) -> str:
    """SHA-256 of canonical JSON (dicts/lists) or UTF-8 bytes/text."""
    if isinstance(raw, (bytes, bytearray)):
        return hashlib.sha256(bytes(raw)).hexdigest()
    if isinstance(raw, str):
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical_json(raw).encode("utf-8")).hexdigest()


def make_source_id(connector: str, accession: str) -> str:
    """Stable source_id from connector + accession."""
    conn = _SAFE_ID.sub("_", connector.strip()) or "unknown"
    acc = _SAFE_ID.sub("_", (accession or "unknown").strip()) or "unknown"
    return f"{conn}:{acc}"


def source_record_from_normalized(
    *,
    connector: str,
    identifier: str,
    retrieval_path: str,
    retrieved_at: str,
    raw_record: dict[str, Any],
    query: dict[str, Any],
    media_type: str = "application/json",
    database_version: str | None = None,
    license: str = "unknown",
    retention: str | None = None,
    availability: str = "available",
    source_id: str | None = None,
) -> SourceRecord:
    """Build a SourceRecord from connector-normalized fields."""
    digest = content_digest_for(raw_record) if raw_record else content_digest_for({})
    if retention is None:
        retention = "retained" if raw_record else "digest_only"
    sid = source_id or make_source_id(connector, identifier)
    history = [
        TransformationStep(
            op="normalize",
            at=retrieved_at,
            digest_in=digest,
            digest_out=digest,
        )
    ]
    return SourceRecord(
        source_id=sid,
        canonical_url=retrieval_path,
        accession=identifier,
        retrieved_at=retrieved_at,
        content_digest=digest,
        media_type=media_type,
        database_version=database_version,
        query=dict(query),
        raw_response_retention=retention,
        license=license,
        connector=connector,
        transformation_history=history,
        source_availability=availability,
    )


def source_record_from_evidence_view(
    evidence: dict[str, Any],
    *,
    query: dict[str, Any] | None = None,
    retention: str = "digest_only",
) -> SourceRecord:
    """Synthesize a SourceRecord from an evidence view (offline fixtures)."""
    connector = str(evidence.get("source_name") or "unknown")
    identifier = str(evidence.get("identifier") or evidence.get("evidence_id") or "unknown")
    digest = str(evidence.get("raw_record_hash") or content_digest_for({}))
    sid = evidence.get("source_id") or make_source_id(connector, identifier)
    return SourceRecord(
        source_id=str(sid),
        canonical_url=str(evidence.get("retrieval_path") or ""),
        accession=identifier,
        retrieved_at=str(evidence.get("retrieved_at") or ""),
        content_digest=digest,
        media_type="application/json",
        database_version=None,
        query=dict(query or {}),
        raw_response_retention=retention,
        license="unknown",
        connector=connector,
        transformation_history=[
            TransformationStep(
                op="synthesize_from_evidence_view",
                at=str(evidence.get("retrieved_at") or ""),
                digest_in=digest,
                digest_out=digest,
            )
        ],
        source_availability="cached" if retention == "digest_only" else "available",
    )


def ensure_source_records(
    evidence: list[dict[str, Any]],
    source_records: list[dict[str, Any]] | None = None,
    *,
    query: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach source_id on evidence; synthesize missing SourceRecords (digest_only)."""
    records = [dict(r) for r in (source_records or [])]
    by_id = {r["source_id"]: r for r in records if r.get("source_id")}
    by_digest = {r["content_digest"]: r for r in records if r.get("content_digest")}
    out_evidence: list[dict[str, Any]] = []

    for ev in evidence:
        item = dict(ev)
        sid = item.get("source_id")
        digest = item.get("raw_record_hash")
        record = None
        if sid and sid in by_id:
            record = by_id[sid]
        elif digest and digest in by_digest:
            record = by_digest[digest]
            sid = record["source_id"]
        if record is None:
            synthesized = source_record_from_evidence_view(item, query=query, retention="digest_only")
            record = synthesized.to_dict()
            sid = record["source_id"]
            records.append(record)
            by_id[sid] = record
            by_digest[record["content_digest"]] = record
        item["source_id"] = sid
        out_evidence.append(item)

    return out_evidence, records
