"""Materials Project read-only connector."""

from __future__ import annotations

from typing import Any

from vsa.config import materials_project_api_key
from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client
from vsa.scientific.credibility import MATERIALS_PROJECT_SKIP


def materials_project_skipped_reason() -> str | None:
    """Return a user-visible skip reason when live retrieval cannot run."""
    if materials_project_api_key():
        return None
    return MATERIALS_PROJECT_SKIP


class MaterialsProjectConnector(Connector):
    name = "Materials Project"
    BASE = "https://api.materialsproject.org/materials/summary/"

    def __init__(self, cache: EvidenceCache | None = None, client: httpx.Client | None = None) -> None:
        self.cache = cache or EvidenceCache()
        key = materials_project_api_key()
        headers = {"X-API-KEY": key} if key else {}
        self.client = client or make_client(timeout=30.0, headers=headers)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        formula = query.get("material_id") or query.get("formula")
        if not formula and query.get("display_name"):
            formula = query["display_name"].split()[0]
        if not formula:
            return []

        cache_query = {"formula": formula}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            records = cached
        else:
            if not materials_project_api_key():
                return []
            resp = self.client.get(self.BASE, params={"formula": formula, "_limit": 1})
            if resp.status_code in (401, 403):
                return []
            resp.raise_for_status()
            records = resp.json().get("data", [])
            self.cache.set(self.name, cache_query, records)

        if not records:
            return []

        record = records[0] if isinstance(records, list) else records
        mp_id = record.get("material_id") or record.get("task_id", formula)
        formula_out = record.get("formula_pretty") or record.get("formula", formula)
        symmetry = record.get("symmetry", {})
        crystal_system = symmetry.get("crystal_system") if isinstance(symmetry, dict) else None

        return [
            NormalizedEvidence(
                source_name="Materials Project",
                source_type="database",
                identifier=str(mp_id),
                retrieval_path=f"https://materialsproject.org/materials/{mp_id}",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {
                        "material_id": mp_id,
                        "formula": formula_out,
                        "crystal_system": crystal_system,
                        "energy_above_hull": record.get("energy_above_hull"),
                    },
                    ["material_id", "formula", "crystal_system", "energy_above_hull"],
                ),
                raw_record=record,
                domain_metadata={
                    "material_id": mp_id,
                    "formula": formula_out,
                    "crystal_system": crystal_system,
                },
            )
        ]
