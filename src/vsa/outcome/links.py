"""Append-only outcome / calibration link records."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from vsa.companion_schema import validate_companion
from vsa.decision_time.snapshot import compute_bundle_hash
from vsa.provenance.hashchain import now_utc_iso
from vsa.version import OUTCOME_LINK_SCHEMA_VERSION

OUTCOME_SCHEMA_NAME = "scientific_outcome_link.schema.json"


def build_outcome_link(
    bundle: dict[str, Any],
    *,
    outcome_ref: str,
    link_kind: str = "outcome",
    notes: str | None = None,
) -> dict[str, Any]:
    """Create a ScientificOutcomeLink without mutating the bundle."""
    if link_kind not in ("outcome", "calibration", "follow_up"):
        raise ValueError(f"unsupported link_kind: {link_kind!r}")
    bundle_id = bundle.get("bundle_id")
    if not bundle_id:
        raise ValueError("bundle missing bundle_id")
    integrity = bundle.get("integrity") or {}
    bundle_hash = integrity.get("bundle_hash")
    if not bundle_hash:
        raise ValueError("bundle missing integrity.bundle_hash")
    # Immutability guard: recompute and require equality
    recomputed = compute_bundle_hash(bundle)
    if recomputed != bundle_hash:
        raise ValueError("bundle_hash mismatch; refusing to link mutated bundle")

    link = {
        "schema_version": OUTCOME_LINK_SCHEMA_VERSION,
        "link_id": str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"vsa:outcome|{bundle_id}|{outcome_ref}|{link_kind}")
        ),
        "bundle_id": str(bundle_id),
        "bundle_hash": str(bundle_hash),
        "outcome_ref": outcome_ref,
        "linked_at": now_utc_iso(),
        "link_kind": link_kind,
        "notes": notes,
        "non_claims": {
            "mutates_bundle": False,
            "authorizes_actions": False,
        },
    }
    errors = validate_companion(OUTCOME_SCHEMA_NAME, link)
    if errors:
        raise ValueError("outcome link schema validation failed: " + "; ".join(errors))
    return link


def write_outcome_link(
    bundle: dict[str, Any],
    out_path: Path,
    *,
    outcome_ref: str,
    link_kind: str = "outcome",
    notes: str | None = None,
) -> dict[str, Any]:
    """Write link JSON to out_path; does not modify bundle file/bytes."""
    before_hash = (bundle.get("integrity") or {}).get("bundle_hash")
    link = build_outcome_link(bundle, outcome_ref=outcome_ref, link_kind=link_kind, notes=notes)
    after_hash = compute_bundle_hash(bundle)
    if before_hash != after_hash:
        raise RuntimeError("bundle mutated during link_outcome; aborting")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(link, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return link


def validate_outcome_link(link: dict[str, Any]) -> list[str]:
    version = link.get("schema_version")
    if version != OUTCOME_LINK_SCHEMA_VERSION:
        return [
            f"outcome link schema_version unsupported: {version!r}; "
            f"supported: {OUTCOME_LINK_SCHEMA_VERSION}"
        ]
    return validate_companion(OUTCOME_SCHEMA_NAME, link)
