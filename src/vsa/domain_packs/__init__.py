"""Domain packs: connector routing and review-boundary policy by scientific domain."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

PACKS_ROOT = Path(__file__).resolve().parent

# Fallback when a pack does not declare full routing (mirrors pipeline defaults).
_BASE_ROUTING: dict[str, list[str]] = {
    "variant": ["ClinVar", "UniProt", "PubMed", "Europe PMC"],
    "gene": ["UniProt", "ClinVar", "PubMed"],
    "protein": ["UniProt", "AlphaFold DB"],
    "paper": ["OpenAlex", "Crossref", "PubMed", "Europe PMC", "Semantic Scholar"],
    "target": ["UniProt", "OpenAlex", "PubMed"],
    "material": ["Materials Project", "OpenAlex", "PubMed"],
    "chemical": ["PubMed", "OpenAlex"],
    "experiment": ["OpenAlex", "PubMed", "Europe PMC"],
}


@dataclass(frozen=True)
class DomainPack:
    name: str
    description: str = ""
    entity_types: tuple[str, ...] = ()
    connectors: tuple[str, ...] = ()
    routing: dict[str, tuple[str, ...]] = field(default_factory=dict)
    warning_policy: dict[str, Any] = field(default_factory=dict)
    review_boundaries: tuple[str, ...] = ()

    def connectors_for(self, entity_type: str) -> list[str]:
        if entity_type in self.routing:
            return list(self.routing[entity_type])
        if entity_type in self.entity_types and self.connectors:
            return list(self.connectors)
        return list(_BASE_ROUTING.get(entity_type, _BASE_ROUTING["experiment"]))


def _strip_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "~", ""}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _load_simple_yaml(text: str) -> dict[str, Any]:
    """Load constrained pack YAML (mappings, nested maps, string lists).

    Packs are intentionally small; this avoids a PyYAML dependency while keeping
    human-editable ``pack.yaml`` files.
    """
    text = _strip_comments(text)
    # JSON is a valid YAML 1.2 subset — accept it for fixtures/tools.
    stripped = text.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError("pack root must be a mapping")
        return data

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]
    pending_key: str | None = None
    pending_indent = -1

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        while stack and indent <= stack[-1][0] and not (
            pending_key is not None and indent > pending_indent and line.startswith("- ")
        ):
            if len(stack) == 1:
                break
            if indent == stack[-1][0] and line.startswith("- "):
                break
            if indent <= stack[-1][0]:
                stack.pop()
            else:
                break

        parent = stack[-1][1]

        if line.startswith("- "):
            item_raw = line[2:].strip()
            if not isinstance(parent, list):
                if pending_key is None:
                    raise ValueError(f"list item without key at line {lineno}")
                # promote pending key to list
                if not isinstance(stack[-1][1], dict):
                    raise ValueError(f"invalid list parent at line {lineno}")
                new_list: list[Any] = []
                stack[-1][1][pending_key] = new_list  # type: ignore[index]
                stack.append((indent, new_list))
                parent = new_list
                pending_key = None
            assert isinstance(parent, list)
            if ":" in item_raw and not item_raw.startswith("http"):
                # list of mappings not required for packs
                parent.append(_parse_scalar(item_raw))
            else:
                parent.append(_parse_scalar(item_raw))
            continue

        if ":" not in line:
            raise ValueError(f"expected key: value at line {lineno}: {line!r}")

        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"mapping entry under list at line {lineno}")

        if rest == "":
            # Nested mapping or list follows
            # Peek: could be list or map — create dict placeholder; list promotion on "-"
            nested: dict[str, Any] = {}
            parent[key] = nested
            pending_key = key
            pending_indent = indent
            stack.append((indent, nested))
        else:
            parent[key] = _parse_scalar(rest)
            pending_key = None

    return root


def _pack_dir(name: str) -> Path:
    return PACKS_ROOT / name


def list_packs() -> list[str]:
    names = sorted(
        p.name
        for p in PACKS_ROOT.iterdir()
        if p.is_dir() and (p / "pack.yaml").exists() and not p.name.startswith("_")
    )
    return names


@lru_cache(maxsize=16)
def load_pack(name: str) -> DomainPack:
    path = _pack_dir(name) / "pack.yaml"
    if not path.is_file():
        known = ", ".join(list_packs()) or "(none)"
        raise KeyError(f"unknown domain pack {name!r}; available: {known}")
    data = _load_simple_yaml(path.read_text(encoding="utf-8"))
    routing_raw = data.get("routing") or {}
    routing = {
        str(k): tuple(str(x) for x in (v or []))
        for k, v in routing_raw.items()
        if isinstance(v, list)
    }
    return DomainPack(
        name=str(data.get("name") or name),
        description=str(data.get("description") or ""),
        entity_types=tuple(str(x) for x in (data.get("entity_types") or [])),
        connectors=tuple(str(x) for x in (data.get("connectors") or [])),
        routing=routing,
        warning_policy=dict(data.get("warning_policy") or {}),
        review_boundaries=tuple(str(x) for x in (data.get("review_boundaries") or [])),
    )


def routing_for_pack(name: str) -> dict[str, list[str]]:
    """Merge base routing with pack-specific connector lists."""
    pack = load_pack(name)
    merged = {k: list(v) for k, v in _BASE_ROUTING.items()}
    for entity, names in pack.routing.items():
        merged[entity] = list(names)
    # Ensure declared entity types have a route
    for entity in pack.entity_types:
        if entity not in merged and pack.connectors:
            merged[entity] = list(pack.connectors)
    return merged


def resolve_pack_name(value: str | None) -> str | None:
    if not value:
        return None
    name = value.strip()
    if not name:
        return None
    load_pack(name)  # validate
    return name
