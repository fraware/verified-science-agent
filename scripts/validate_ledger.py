#!/usr/bin/env python3
"""Validate a Verified Science Agent claim ledger with no third-party dependencies."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

REQ_TOP = {"ledger_id", "ledger_version", "created_at_utc", "generated_by", "subject", "claims", "report_level_assessment"}
REQ_CLAIM = {"claim_id", "claim_type", "claim_text", "support_level", "confidence", "evidence", "verification"}
REQ_EVIDENCE = {"evidence_id", "source_name", "source_type", "retrieval_path", "accessed_at_utc", "quoted_or_structured_evidence", "evidence_role", "reliability"}
REQ_VERIFICATION = {"status", "checks_performed", "issues", "verifier_notes"}
BLOCKING = {"unsupported", "contradicted"}

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"FAIL: could not load JSON: {exc}") from exc

def validate(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing_top = REQ_TOP - ledger.keys()
    if missing_top:
        errors.append(f"missing top-level fields: {sorted(missing_top)}")
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        return errors + ["claims must be a non-empty list"]
    seen_claims: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            errors.append(f"claim #{index} is not an object")
            continue
        claim_id = str(claim.get("claim_id", f"claim #{index}"))
        if claim_id in seen_claims:
            errors.append(f"duplicate claim_id: {claim_id}")
        seen_claims.add(claim_id)
        missing_claim = REQ_CLAIM - claim.keys()
        if missing_claim:
            errors.append(f"{claim_id}: missing claim fields: {sorted(missing_claim)}")
        if not isinstance(claim.get("claim_text"), str) or len(claim.get("claim_text", "")) < 20:
            errors.append(f"{claim_id}: claim_text must be specific and non-empty")
        confidence = claim.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{claim_id}: confidence must be a number between 0 and 1")
        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{claim_id}: evidence must be a non-empty list")
        else:
            seen_evidence: set[str] = set()
            for ev in evidence:
                if not isinstance(ev, dict):
                    errors.append(f"{claim_id}: evidence item is not an object")
                    continue
                evidence_id = str(ev.get("evidence_id", "missing-evidence-id"))
                if evidence_id in seen_evidence:
                    errors.append(f"{claim_id}: duplicate evidence_id: {evidence_id}")
                seen_evidence.add(evidence_id)
                missing_ev = REQ_EVIDENCE - ev.keys()
                if missing_ev:
                    errors.append(f"{claim_id}/{evidence_id}: missing evidence fields: {sorted(missing_ev)}")
                if not str(ev.get("retrieval_path", "")).strip():
                    errors.append(f"{claim_id}/{evidence_id}: retrieval_path is empty")
        verification = claim.get("verification")
        if not isinstance(verification, dict):
            errors.append(f"{claim_id}: verification must be an object")
        else:
            missing_verification = REQ_VERIFICATION - verification.keys()
            if missing_verification:
                errors.append(f"{claim_id}: missing verification fields: {sorted(missing_verification)}")
            if verification.get("status") in BLOCKING:
                errors.append(f"{claim_id}: blocking verification status: {verification.get('status')}")
    blocking = ledger.get("report_level_assessment", {}).get("blocking_issues", [])
    if blocking:
        errors.append(f"report has blocking issues: {blocking}")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a claim ledger JSON file.")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    ledger = load_json(args.ledger)
    errors = validate(ledger)
    claims = ledger.get("claims", []) if isinstance(ledger.get("claims"), list) else []
    with_evidence = sum(1 for c in claims if isinstance(c, dict) and c.get("evidence"))
    with_verification = sum(1 for c in claims if isinstance(c, dict) and isinstance(c.get("verification"), dict))
    if errors:
        print("FAIL: ledger validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: ledger is structurally valid")
    print(f"PASS: {with_evidence}/{len(claims)} claims have at least one evidence item")
    print(f"PASS: {with_verification}/{len(claims)} claims have verification status")
    print("PASS: 0 blocking issues")
    return 0

if __name__ == "__main__":
    sys.exit(main())
