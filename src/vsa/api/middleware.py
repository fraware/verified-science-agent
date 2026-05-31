"""Optional API middleware (rate limiting)."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, app, *, max_requests: int = 120, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in ("/health", "/v1/version", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds
        hits = [t for t in self._hits[client] if t >= window_start]
        if len(hits) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": f"Rate limit exceeded ({self.max_requests}/{self.window_seconds}s)",
                    }
                },
            )
        hits.append(now)
        self._hits[client] = hits
        return await call_next(request)


def rate_limit_enabled() -> bool:
    return os.environ.get("VSA_API_RATE_LIMIT", "").strip() not in ("", "0", "false", "False")


def deterministic_mode() -> bool:
    return os.environ.get("VSA_API_DETERMINISTIC", "").strip() in ("1", "true", "True")


def api_key_required() -> bool:
    return bool(os.environ.get("VSA_API_KEY", "").strip())


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional shared-secret gate for non-public API routes."""

    def __init__(self, app, *, api_key: str) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        public_paths = {"/health", "/v1/version", "/docs", "/openapi.json", "/redoc"}
        if request.url.path in public_paths:
            return await call_next(request)
        provided = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if provided != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Invalid or missing API key"}},
            )
        return await call_next(request)
