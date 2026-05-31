"""Environment configuration — loads .env without committing secrets."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path.cwd()
    for candidate in (root / ".env", root.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return
    load_dotenv(override=False)


@lru_cache(maxsize=1)
def ensure_env_loaded() -> None:
    _load_dotenv()


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1]
    return value or None


def get_env(name: str, default: str | None = None) -> str | None:
    ensure_env_loaded()
    return _clean_env_value(os.environ.get(name, default))


def openai_api_key() -> str | None:
    return get_env("OPENAI_API_KEY")


def anthropic_api_key() -> str | None:
    return get_env("ANTHROPIC_API_KEY")


def materials_project_api_key() -> str | None:
    return get_env("MATERIALS_PROJECT_API_KEY") or get_env("MP_API_KEY")


def default_llm_provider() -> str:
    if anthropic_api_key():
        return "anthropic"
    if openai_api_key():
        return "openai"
    return "none"


def llm_available() -> bool:
    return bool(openai_api_key() or anthropic_api_key())
