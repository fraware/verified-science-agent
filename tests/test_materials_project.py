"""Materials Project connector tests."""

from __future__ import annotations

import httpx
import respx

from vsa.connectors.cache import EvidenceCache
from vsa.connectors.materials_project import MaterialsProjectConnector


@respx.mock
def test_materials_project_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("MATERIALS_PROJECT_API_KEY", "test-mp-key")
    respx.get("https://api.materialsproject.org/materials/summary/").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "material_id": "mp-19017",
                        "formula_pretty": "LiFePO4",
                        "symmetry": {"crystal_system": "Orthorhombic"},
                        "energy_above_hull": 0.0,
                    }
                ]
            },
        )
    )
    cache = EvidenceCache(tmp_path)
    results = MaterialsProjectConnector(cache).fetch({"material_id": "LiFePO4"})
    assert results[0].source_name == "Materials Project"
    assert "LiFePO4" in results[0].summary
