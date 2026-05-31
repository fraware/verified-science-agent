"""JSON report renderer (pretty-printed artifact)."""

from __future__ import annotations

import json
from typing import Any


def render_json(report: dict[str, Any], *, indent: int = 2) -> str:
    return json.dumps(report, indent=indent, ensure_ascii=False) + "\n"
