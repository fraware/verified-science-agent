#!/usr/bin/env python3
"""Create a simple provenance hash chain over claim records."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def build_chain(ledger: dict[str, Any]) -> dict[str, Any]:
    previous = "GENESIS"
    entries = []
    for claim in ledger.get("claims", []):
        payload = {"previous_hash": previous, "claim": claim}
        digest = hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
        entries.append({"claim_id": claim.get("claim_id"), "previous_hash": previous, "claim_hash": digest})
        previous = digest
    return {"ledger_id": ledger.get("ledger_id"), "algorithm": "sha256", "chain": entries, "root_hash": previous}

def main() -> int:
    parser = argparse.ArgumentParser(description="Build a provenance hash chain for a ledger.")
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    chain = build_chain(ledger)
    text = json.dumps(chain, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
