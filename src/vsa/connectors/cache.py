"""File-based cache for raw connector responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class EvidenceCache:
    def __init__(self, cache_dir: Path | str = ".vsa_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, connector: str, query: dict[str, Any]) -> Path:
        digest = hashlib.sha256(
            json.dumps({"connector": connector, "query": query}, sort_keys=True).encode()
        ).hexdigest()
        return self.cache_dir / connector / f"{digest}.json"

    def get(self, connector: str, query: dict[str, Any]) -> dict[str, Any] | None:
        path = self._key_path(connector, query)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def set(self, connector: str, query: dict[str, Any], record: dict[str, Any]) -> Path:
        path = self._key_path(connector, query)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def snapshot_path(self, connector: str, query: dict[str, Any]) -> str:
        return str(self._key_path(connector, query))
