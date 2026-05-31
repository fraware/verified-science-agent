"""Shared HTTP client factory with reliable TLS on all platforms."""

from __future__ import annotations

import os
import ssl

import httpx


def default_verify() -> ssl.SSLContext | bool:
    if os.environ.get("VSA_SSL_VERIFY", "true").lower() in ("0", "false", "no"):
        return False
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return True


def make_client(**kwargs: object) -> httpx.Client:
    kwargs.setdefault("verify", default_verify())
    kwargs.setdefault("timeout", 60.0)
    return httpx.Client(**kwargs)
