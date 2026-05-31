"""API authentication tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def test_api_key_required(monkeypatch, brca1_report):
    monkeypatch.setenv("VSA_API_KEY", "test-secret-key")
    from vsa.api.app import create_app

    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
    assert client.post("/v1/validate", json={"report": brca1_report}).status_code == 401
    resp = client.post(
        "/v1/validate",
        json={"report": brca1_report},
        headers={"X-API-Key": "test-secret-key"},
    )
    assert resp.status_code == 200
