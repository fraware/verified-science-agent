"""LLM provider abstraction for structured claim extraction."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from vsa.http_client import make_client

from vsa.config import anthropic_api_key, openai_api_key


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        """Return parsed JSON object from model response."""


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", client: httpx.Client | None = None) -> None:
        self.model = model
        key = openai_api_key()
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = client or make_client(
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        resp = self.client.post("https://api.openai.com/v1/chat/completions", json=payload)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-20250514", client: httpx.Client | None = None) -> None:
        self.model = model
        key = anthropic_api_key()
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self.client = client or make_client(
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system + "\n\nRespond with valid JSON only. No markdown fences.",
            "messages": [{"role": "user", "content": user}],
            "temperature": 0.1,
        }
        resp = self.client.post("https://api.anthropic.com/v1/messages", json=payload)
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return json.loads(text)


def get_provider(name: str | None = None, model: str | None = None) -> LLMProvider:
    from vsa.config import default_llm_provider

    chosen = (name or default_llm_provider()).lower()
    if chosen == "openai":
        return OpenAIProvider(model=model or "gpt-4o-mini")
    if chosen == "anthropic":
        return AnthropicProvider(model=model or "claude-sonnet-4-20250514")
    raise RuntimeError(f"No LLM provider available (requested: {chosen}). Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
