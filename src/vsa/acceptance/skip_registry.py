"""Registry of live-only connectors skipped by the default offline acceptance gate."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Connector display names matching Connector.name on each implementation.
# All remote connectors are live-capable; default acceptance never exercises them
# (pytest -m 'not live', VSA_ALLOW_NETWORK unset).
LIVE_CONNECTOR_NAMES: tuple[str, ...] = (
    "ClinVar",
    "UniProt",
    "AlphaFold DB",
    "OpenAlex",
    "PubMed",
    "Europe PMC",
    "Crossref",
    "Semantic Scholar",
    "Materials Project",
)

DEFAULT_BASELINE_PATH = Path("reports/acceptance_baseline.json")


def network_allowed() -> bool:
    """True when live network connectors may run."""
    flag = (os.environ.get("VSA_ALLOW_NETWORK") or "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def skipped_live_connectors(*, allow_network: bool | None = None) -> list[dict[str, str]]:
    """Enumerate connectors and mark live-only ones skipped under the offline gate.

    When ``VSA_ALLOW_NETWORK`` is unset/false (default acceptance), every registered
    live connector is recorded as skipped. Offline fixtures and mocked unit tests
    still exercise connector code paths without network.
    """
    allow = network_allowed() if allow_network is None else allow_network
    rows: list[dict[str, str]] = []
    for name in LIVE_CONNECTOR_NAMES:
        if allow:
            rows.append(
                {
                    "connector": name,
                    "status": "eligible_live",
                    "reason": "VSA_ALLOW_NETWORK set; live markers may run",
                }
            )
        else:
            rows.append(
                {
                    "connector": name,
                    "status": "skipped_live",
                    "reason": "offline acceptance gate (VSA_ALLOW_NETWORK unset; pytest -m 'not live')",
                }
            )
    return rows


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "unknown"


def _extras_installed() -> list[str]:
    """Best-effort list of optional extras present in the current environment."""
    extras: list[str] = []
    probes = {
        "dev": "pytest",
        "ui": "streamlit",
        "pdf": "fpdf",
        "signing": "cryptography",
        "api": "fastapi",
    }
    for extra, module in probes.items():
        try:
            __import__(module)
            extras.append(extra)
        except ImportError:
            continue
    return extras


def build_acceptance_baseline(
    *,
    command_exit_codes: dict[str, int] | None = None,
    extras: list[str] | None = None,
    allow_network: bool | None = None,
) -> dict[str, Any]:
    """Build the durable acceptance baseline artifact payload."""
    return {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_sha": _git_sha(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "extras_installed": extras if extras is not None else _extras_installed(),
        "network_allowed": network_allowed() if allow_network is None else allow_network,
        "command_exit_codes": command_exit_codes or {},
        "skipped_live_connectors": skipped_live_connectors(allow_network=allow_network),
        "notes": (
            "Default acceptance is offline-first. Live connector tests require "
            "VSA_ALLOW_NETWORK=1 and pytest -m live."
        ),
    }


def write_acceptance_baseline(
    path: Path | str = DEFAULT_BASELINE_PATH,
    *,
    command_exit_codes: dict[str, int] | None = None,
    extras: list[str] | None = None,
    allow_network: bool | None = None,
) -> Path:
    """Write ``reports/acceptance_baseline.json`` (or custom path)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_acceptance_baseline(
        command_exit_codes=command_exit_codes,
        extras=extras,
        allow_network=allow_network,
    )
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI entry for acceptance.sh: write baseline with optional exit-code JSON."""
    argv = list(argv if argv is not None else sys.argv[1:])
    out = DEFAULT_BASELINE_PATH
    codes: dict[str, int] = {}
    if argv and argv[0] == "--out":
        out = Path(argv[1])
        argv = argv[2:]
    if argv and argv[0] == "--exit-codes":
        codes = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    write_acceptance_baseline(out, command_exit_codes=codes)
    print(f"Wrote acceptance baseline: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
