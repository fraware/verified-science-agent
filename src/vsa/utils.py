"""Canonical JSON serialization for hashing."""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
