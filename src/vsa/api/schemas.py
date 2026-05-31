"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    version: str


class VersionResponse(BaseModel):
    version: str


class RetrieveRequest(BaseModel):
    question: str = Field(examples=["BRCA1 c.68_69del"])
    cache_dir: str = ".vsa_cache"


class BuildRequest(BaseModel):
    input: dict[str, Any] | None = None
    question: str | None = None
    subject: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] | None = None
    claim_mode: str = "rule"
    cache_dir: str = ".vsa_cache"
    deterministic: bool = False


class ReportRequest(BaseModel):
    report: dict[str, Any]


class AuditRequest(BaseModel):
    report: dict[str, Any]
    audit_mode: str = "rule"
    deterministic: bool = False


class RenderRequest(BaseModel):
    report: dict[str, Any]
    format: str = "markdown"


class ExportRequest(BaseModel):
    report: dict[str, Any]
    audit_mode: str = "rule"
    deterministic: bool = False


class ValidationCheck(BaseModel):
    name: str
    status: str
    message: str


class ValidateResponse(BaseModel):
    passed: bool
    status: str
    checks: list[ValidationCheck]


class RenderResponse(BaseModel):
    format: str
    content: str | None = None
    content_b64: str | None = None
