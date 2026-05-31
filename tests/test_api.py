"""REST API tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from vsa.api.app import create_app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_validate_endpoint(client, brca1_report):
    resp = client.post("/v1/validate", json={"report": brca1_report})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("pass", "warn")
    assert body["passed"] is True


def test_build_offline(client, brca1_evidence):
    resp = client.post(
        "/v1/build",
        json={
            "input": {"question": "BRCA1 c.68_69del", "evidence": brca1_evidence},
            "claim_mode": "rule",
        },
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["schema_version"]
    assert len(report["claims"]) >= 1


def test_attest_endpoint(client, brca1_report):
    resp = client.post("/v1/attest", json={"report": brca1_report})
    assert resp.status_code == 200
    assert resp.json()["predicateType"] == "https://slsa.dev/provenance/v1"


def test_audit_endpoint(client, brca1_report):
    resp = client.post("/v1/audit", json={"report": brca1_report, "audit_mode": "rule"})
    assert resp.status_code == 200
    assert resp.json()["overall_status"] in ("passed", "partial")


def test_export_endpoint(client, brca1_report):
    resp = client.post("/v1/export", json={"report": brca1_report, "audit_mode": "rule"})
    assert resp.status_code == 200
    assert "manifest" in resp.json()


def test_build_missing_input(client):
    resp = client.post("/v1/build", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_INPUT"


def test_review_api_flow(client, brca1_report):
    resp = client.post(
        "/v1/review/start",
        json={"report": brca1_report, "reviewer": "reviewer@example.com"},
    )
    assert resp.status_code == 200
    started = resp.json()
    resp2 = client.post(
        "/v1/review/approve-claim",
        json={
            "report": started,
            "reviewer": "reviewer@example.com",
            "claim_ids": ["C002"],
        },
    )
    assert resp2.status_code == 200
    resp3 = client.post("/v1/review/verify", json={"report": resp2.json()})
    assert resp3.status_code == 200
    assert resp3.json()["passed"] is True


def test_deterministic_build(client, brca1_evidence, monkeypatch):
    monkeypatch.setenv("VSA_API_DETERMINISTIC", "1")
    from vsa.api.app import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    resp = client.post(
        "/v1/build",
        json={"input": {"question": "BRCA1 c.68_69del", "evidence": brca1_evidence}},
    )
    assert resp.status_code == 200


def test_version_endpoint(client):
    resp = client.get("/v1/version")
    assert resp.status_code == 200
    assert resp.json()["version"]
