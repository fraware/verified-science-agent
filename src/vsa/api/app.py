"""REST API for Verified Science Agent."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

from vsa import __version__


def _api_error(code: str, message: str, status: int):
    from fastapi import HTTPException

    raise HTTPException(status_code=status, detail={"error": {"code": code, "message": message}})


def create_app():
    """Create FastAPI application (requires [api] extra)."""
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI not installed. Install with: pip install verified-science-agent[api]"
        ) from exc

    from vsa.api.middleware import RateLimitMiddleware, deterministic_mode, rate_limit_enabled
    from vsa.api.schemas import (
        HealthResponse,
        RenderResponse,
        RetrieveRequest,
        ValidateResponse,
        ValidationCheck,
        VersionResponse,
    )
    from vsa.artifacts.export import export_report_bundle
    from vsa.pipeline.build import build_report
    from vsa.pipeline.retrieval import retrieve
    from vsa.provenance.attestation import build_slsa_attestation
    from vsa.provenance.hashchain import build_provenance
    from vsa.render import render
    from vsa.review.workflow import approve_claims, start_review, verify_review_chain
    from vsa.telemetry import setup_telemetry, span
    from vsa.validate.engine import validate_report

    setup_telemetry("vsa-api")

    app = FastAPI(
        title="Verified Science Agent API",
        version=__version__,
        description="Evidence-backed scientific report infrastructure",
    )

    if rate_limit_enabled():
        limit = int(os.environ.get("VSA_API_RATE_LIMIT", "120"))
        app.add_middleware(RateLimitMiddleware, max_requests=limit)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc.errors()),
                }
            },
        )

    def _force_deterministic(_body: Any) -> None:
        pass  # deterministic mode applied inline per endpoint

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/v1/version", response_model=VersionResponse)
    def version() -> VersionResponse:
        return VersionResponse(version=__version__)

    @app.post("/v1/retrieve")
    def api_retrieve(body: RetrieveRequest) -> dict[str, Any]:
        with span("api.retrieve", question=body.question):
            return retrieve(body.question, cache_dir=body.cache_dir)

    @app.post("/v1/build")
    def api_build(body: dict[str, Any]) -> dict[str, Any]:
        claim_mode = body.get("claim_mode", "rule")
        cache_dir = body.get("cache_dir", ".vsa_cache")
        if deterministic_mode() or body.get("deterministic"):
            claim_mode = "rule"
        with span("api.build", claim_mode=claim_mode):
            if body.get("input"):
                data = dict(body["input"])
            elif body.get("question"):
                data = {"question": body["question"]}
            elif body.get("subject") or body.get("evidence") is not None:
                data = {k: body[k] for k in ("subject", "evidence", "question") if k in body}
            else:
                _api_error("MISSING_INPUT", "question or input required", 400)
            data.setdefault("claim_mode", claim_mode)
            return build_report(data, cache_dir=cache_dir, claim_mode=claim_mode)

    @app.post("/v1/validate", response_model=ValidateResponse)
    def api_validate(body: dict[str, Any]) -> ValidateResponse:
        report = body.get("report", body)
        with span("api.validate"):
            result = validate_report(report)
            return ValidateResponse(
                passed=result.passed,
                status=result.status,
                checks=[
                    ValidationCheck(name=c.name, status=c.status, message=c.message)
                    for c in result.checks
                ],
            )

    @app.post("/v1/audit")
    def api_audit(body: dict[str, Any]) -> dict[str, Any]:
        from vsa.llm.verifier import audit_report

        report = body.get("report", body)
        audit_mode = body.get("audit_mode", "rule")
        if deterministic_mode() or body.get("deterministic"):
            audit_mode = "rule"
        with span("api.audit", mode=audit_mode):
            return audit_report(report, mode=audit_mode).to_dict()

    @app.post("/v1/hash")
    def api_hash(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.hash"):
            return build_provenance(report)

    @app.post("/v1/render", response_model=RenderResponse)
    def api_render(body: dict[str, Any]) -> RenderResponse:
        report = body.get("report", body)
        fmt = body.get("format", "markdown")
        with span("api.render", format=fmt):
            output = render(report, fmt)
            if isinstance(output, bytes):
                return RenderResponse(
                    format=fmt,
                    content_b64=base64.b64encode(output).decode("ascii"),
                )
            return RenderResponse(format=fmt, content=output)

    @app.post("/v1/attest")
    def api_attest(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        with span("api.attest"):
            return build_slsa_attestation(report, subject_name="report.json")

    @app.post("/v1/export")
    def api_export(body: dict[str, Any]) -> dict[str, str]:
        report = body.get("report", body)
        audit_mode = body.get("audit_mode", "rule")
        if deterministic_mode() or body.get("deterministic"):
            audit_mode = "rule"
        with span("api.export"):
            out_dir = Path(tempfile.mkdtemp(prefix="vsa-export-"))
            return export_report_bundle(report, out_dir, audit_mode=audit_mode)

    @app.post("/v1/review/start")
    def api_review_start(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report")
        reviewer = body.get("reviewer")
        if not report or not reviewer:
            _api_error("MISSING_INPUT", "report and reviewer required", 400)
        with span("api.review.start"):
            updated = start_review(report, reviewer_identity=reviewer, review_notes=body.get("notes"))
            return updated

    @app.post("/v1/review/approve-claim")
    def api_review_approve(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report")
        reviewer = body.get("reviewer")
        claim_ids = body.get("claim_ids") or ([body["claim_id"]] if body.get("claim_id") else [])
        if not report or not reviewer or not claim_ids:
            _api_error("MISSING_INPUT", "report, reviewer, and claim_ids required", 400)
        with span("api.review.approve"):
            return approve_claims(
                report,
                reviewer_identity=reviewer,
                claim_ids=claim_ids,
                review_notes=body.get("notes"),
            )

    @app.post("/v1/review/verify")
    def api_review_verify(body: dict[str, Any]) -> dict[str, Any]:
        report = body.get("report", body)
        ok, errors = verify_review_chain(report)
        return {"passed": ok, "errors": errors}

    return app
