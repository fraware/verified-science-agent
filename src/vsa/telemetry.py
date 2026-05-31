"""Optional OpenTelemetry instrumentation for pipeline and HTTP clients."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

_TRACER: Any = None
_INITIALIZED = False


def otel_enabled() -> bool:
    return os.getenv("VSA_OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def setup_telemetry(service_name: str = "verified-science-agent") -> Any | None:
    """Initialize OTEL tracer and httpx instrumentation when enabled."""
    global _TRACER, _INITIALIZED
    if _INITIALIZED:
        return _TRACER
    _INITIALIZED = True
    if not otel_enabled():
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        return None

    resource = Resource.create({"service.name": service_name, "service.version": __import__("vsa").__version__})
    provider = TracerProvider(resource=resource)
    exporter = os.getenv("VSA_OTEL_EXPORTER", "console")
    if exporter == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("vsa")

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass

    return _TRACER


def get_tracer() -> Any | None:
    if not _INITIALIZED:
        setup_telemetry()
    return _TRACER


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Create a span when OTEL is enabled; no-op otherwise."""
    tracer = get_tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield
