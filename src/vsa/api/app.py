"""REST API for Verified Science Agent."""

from __future__ import annotations

from typing import Any

from vsa import __version__


def create_app():
    """Create FastAPI application (requires [api] extra)."""
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI not installed. Install with: pip install verified-science-agent[api]"
        ) from exc

    from vsa.artifacts.export import export_report_bundle
    from vsa.pipeline.build import build_report
    from vsa.pipeline.retrieval import retrieve
    from vsa.provenance.attestation import build_slsa_attestation
    from vsa.provenance.hashchain import build_provenance
    from vsa.render import render
    from vsa.telemetry import setup_telemetry, span
    from vsa.validate.engine import validate_report

    setup_telemetry("vsa-api")

    app = FastAPI(
        title="Verified Science Agent API",
        version=__version__,
        description="Evidence-backed scientific report infrastructure",
    )

    class RetrieveRequest(BaseModel):
        question: str
        cache_dir: str = ".vsa_cache"

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/v1/version")
    def version() -> dict[str, str]:
        return {"version": __version__}

    @app.post("/v1/retrieve")
    def api_retrieve(body: RetrieveRequest) -> dict[str, Any]:
        with span("api.retrieve", question=body.question):
            return retrieve(body.question, cache_dir=body.cache_dir)

    @app.post("/v1/build")
    def api_build(body: dict[str, Any]) -> dict[str, Any]:
        claim_mode = body.get("claim_mode", "rule")
        cache_dir = body.get("cache_dir", ".vsa_cache")
        with span("api.build", claim_mode=claim_mode):
            if body.get("input"):
                data = dict(body["input"])
            elif body.get("question"):
                data = {"question": body["question"]}
            elif body.get("subject") or body.get("evidence"):
                data = dict(body)
            else:
                raise HTTPException(status_code=400, detail="question or input required")
            data.setdefault("claim_mode", claim_mode)
            return build_report(data, cache_dir=cache_dir, claim_mode=claim_mode)

    @app.post("/v1/validate")
    def api_validate(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.validate"):
            result = validate_report(report)
            return {
                "passed": result.passed,
                "status": result.status,
                "checks": [
                    {"name": c.name, "status": c.status, "message": c.message} for c in result.checks
                ],
            }

    @app.post("/v1/audit")
    def api_audit(body: dict[str, Any]) -> dict[str, Any]:
        from vsa.llm.verifier import audit_report

        report = body.get("report", body)
        audit_mode = body.get("audit_mode", "rule")
        with span("api.audit", mode=audit_mode):
            return audit_report(report, mode=audit_mode).to_dict()

    @app.post("/v1/hash")
    def api_hash(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.hash"):
            return build_provenance(report)

    @app.post("/v1/render")
    def api_render(body: dict[str, Any], format: str = "markdown") -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.render", format=format):
            output = render(report, format)
            if isinstance(output, bytes):
                import base64

                return {"format": format, "content_b64": base64.b64encode(output).decode("ascii")}
            return {"format": format, "content": output}

    @app.post("/v1/attest")
    def api_attest(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.attest"):
            return build_slsa_attestation(report)

    @app.post("/v1/export")
    def api_export(body: dict[str, Any], audit_mode: str = "rule") -> dict[str, str]:
        import tempfile
        from pathlib import Path

        report = body.get("report", body)
        with span("api.export"):
            out_dir = Path(tempfile.mkdtemp(prefix="vsa-export-"))
            return export_report_bundle(report, out_dir, audit_mode=audit_mode)

    return app
