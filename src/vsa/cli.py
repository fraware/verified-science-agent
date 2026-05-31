"""Verified Science Agent CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vsa import __version__
from vsa.compare import compare_reports, format_compare
from vsa.inspect import format_inspect, inspect_report
from vsa.pipeline.build import build_from_file
from vsa.pipeline.retrieval import retrieve
from vsa.provenance.hashchain import build_provenance, stamp_report
from vsa.render import render
from vsa.validate.engine import validate_report, run_validation
from vsa.review.workflow import apply_review
from vsa.claims.llm_extraction import extract_claims as extract_claims_auto
from vsa.pipeline.subject_parser import parse_input
from vsa.connectors.cache import EvidenceCache
from vsa.pipeline.retrieval import retrieve_evidence
from vsa.scoring.evidence_quality import apply_quality_scores


def _load_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: could not load {path}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _write_output(text: str | bytes, out: Path | None) -> None:
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            out.write_bytes(text)
        else:
            out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    elif isinstance(text, bytes):
        sys.stdout.buffer.write(text)
    else:
        print(text)


def cmd_validate(args: argparse.Namespace) -> int:
    paths = args.reports if hasattr(args, "reports") else [args.report]
    exit_code = 0
    for path in paths:
        report = _load_report(path)
        result = validate_report(report, verify_hashes=not args.skip_hash_check)
        status = "PASS" if result.passed else "FAIL"
        print(f"{status}: {path} [{result.status}]")
        for check in result.checks:
            prefix = check.status.upper()
            print(f"  [{prefix}] {check.name}: {check.message}")
        if not result.passed:
            exit_code = 1
    return exit_code


def cmd_render(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    output = render(report, args.format)
    _write_output(output, args.out)
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    provenance = build_provenance(report)
    if args.json:
        text = json.dumps(provenance, indent=2, ensure_ascii=False) + "\n"
    else:
        text = "\n".join(
            [
                f"report_hash: {provenance.get('report_hash')}",
                f"evidence_bundle_hash: {provenance.get('evidence_bundle_hash')}",
                f"claim_hashes: {len(provenance.get('claim_hashes', {}))} claims",
                f"validation_version: {provenance.get('validation_version')}",
            ]
        ) + "\n"
    _write_output(text, args.out)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    summary = inspect_report(report)
    if args.json:
        text = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    else:
        text = format_inspect(summary)
    _write_output(text, args.out)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    a = _load_report(args.report_a)
    b = _load_report(args.report_b)
    diff = compare_reports(a, b)
    _write_output(format_compare(diff), args.out)
    if args.strict and not diff.get("hash_match"):
        return 1
    return 0


def cmd_retrieve(args: argparse.Namespace) -> int:
    result = retrieve(args.question, cache_dir=args.cache_dir)
    if result.get("warnings") and not args.quiet:
        for w in result["warnings"]:
            print(f"WARN: {w}", file=sys.stderr)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    _write_output(text, args.out)
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    data = json.loads(args.input.read_text(encoding="utf-8"))
    subject = parse_input(data)
    cache = EvidenceCache(args.cache_dir)
    evidence = data.get("evidence") or retrieve_evidence(subject, cache=cache)
    evidence = apply_quality_scores({"evidence": evidence})["evidence"]
    claims, stack = extract_claims_auto(
        subject,
        evidence,
        mode=args.claim_mode,
        provider=args.llm_provider,
        model=args.llm_model,
    )
    out = {"subject": subject, "evidence": evidence, "claims": claims, "extraction_method": stack}
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    _write_output(text, args.out)
    return 0


def _write_reviewed_report(report: dict[str, Any], report_path: Path, out: Path | None) -> None:
    out_path = out or report_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {out_path}")
    print(f"review status: {report['human_review']['status']}")


def cmd_review_legacy(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    approved = [c.strip() for c in args.approve.split(",") if c.strip()] if args.approve else []
    report = apply_review(
        report,
        reviewer_identity=args.reviewer,
        review_decision=args.decision,
        approved_claim_ids=approved,
        required_corrections=args.corrections or [],
        reject=args.reject,
        review_notes=args.notes,
    )
    report = run_validation(report, verify_hashes=True)
    _write_reviewed_report(report, args.report, args.out)
    return 0


def cmd_review_start(args: argparse.Namespace) -> int:
    from vsa.review.workflow import start_review

    report = _load_report(args.report)
    report = start_review(report, reviewer_identity=args.reviewer, review_notes=args.notes)
    report = run_validation(report, verify_hashes=True)
    _write_reviewed_report(report, args.report, args.out)
    return 0


def cmd_review_approve_claim(args: argparse.Namespace) -> int:
    from vsa.review.workflow import approve_claims

    report = _load_report(args.report)
    claim_ids = args.claim if isinstance(args.claim, list) else [args.claim]
    report = approve_claims(
        report,
        reviewer_identity=args.reviewer,
        claim_ids=claim_ids,
        review_notes=args.notes,
    )
    report = run_validation(report, verify_hashes=True)
    _write_reviewed_report(report, args.report, args.out)
    return 0


def cmd_review_request_corrections(args: argparse.Namespace) -> int:
    from vsa.review.workflow import request_corrections

    report = _load_report(args.report)
    report = request_corrections(
        report,
        reviewer_identity=args.reviewer,
        corrections=args.corrections,
        review_notes=args.notes,
    )
    report = run_validation(report, verify_hashes=True)
    _write_reviewed_report(report, args.report, args.out)
    return 0


def cmd_review_reject(args: argparse.Namespace) -> int:
    from vsa.review.workflow import reject_review

    report = _load_report(args.report)
    report = reject_review(report, reviewer_identity=args.reviewer, review_notes=args.notes)
    report = run_validation(report, verify_hashes=True)
    _write_reviewed_report(report, args.report, args.out)
    return 0


def cmd_review_verify(args: argparse.Namespace) -> int:
    from vsa.review.workflow import verify_review_chain

    report = _load_report(args.report)
    ok, errors = verify_review_chain(report)
    if ok:
        print("PASS: review chain verified")
        return 0
    print("FAIL: review chain verification errors:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


def cmd_review(args: argparse.Namespace) -> int:
    """Dispatch review subcommands or legacy flat flags."""
    action = getattr(args, "review_action", None)
    if action == "apply":
        return cmd_review_legacy(args)
    if action == "start":
        return cmd_review_start(args)
    if action == "approve-claim":
        return cmd_review_approve_claim(args)
    if action == "request-corrections":
        return cmd_review_request_corrections(args)
    if action == "reject":
        return cmd_review_reject(args)
    if action == "verify":
        return cmd_review_verify(args)
    print("ERROR: review requires a subcommand (start, approve-claim, request-corrections, reject, verify, apply)", file=sys.stderr)
    return 1


def cmd_build(args: argparse.Namespace) -> int:
    report = build_from_file(
        args.input,
        cache_dir=args.cache_dir,
        claim_mode=args.claim_mode,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
    )
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    vr = report.get("validation_results", {})
    print(f"validation: {vr.get('status')}")
    print(f"report_hash: {report.get('provenance', {}).get('report_hash')}")
    print(f"claim extraction: {report.get('provenance', {}).get('generated_by', {}).get('model_or_agent_stack', '?')}")
    return 0 if vr.get("status") != "fail" else 1


def cmd_sign(args: argparse.Namespace) -> int:
    from vsa.provenance.signing import generate_keypair, sign_report, verify_signature

    if args.generate_key:
        info = generate_keypair(args.key_file)
        print(f"Generated signing key: {info['private_key_path']}")
        print(f"Public key (b64): {info['public_key_b64']}")
        return 0

    if not args.report:
        print("ERROR: report path required (unless --generate-key)", file=sys.stderr)
        return 1

    report = _load_report(args.report)
    signed = sign_report(report, key_path=args.key_file)
    out = args.out or args.report
    out.write_text(json.dumps(signed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok, msg = verify_signature(signed)
    print(f"wrote {out}")
    print(f"signature: {msg}" if ok else f"signature FAILED: {msg}", file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


def cmd_verify_signature(args: argparse.Namespace) -> int:
    from vsa.provenance.signing import verify_signature

    report = _load_report(args.report)
    ok, msg = verify_signature(report)
    print("PASS" if ok else "FAIL", msg)
    return 0 if ok else 1


def cmd_audit(args: argparse.Namespace) -> int:
    from vsa.artifacts.export import write_audit_artifact
    from vsa.llm.verifier import audit_report

    report = _load_report(args.report)
    result = audit_report(
        report,
        mode=args.audit_mode,
        provider=args.llm_provider,
        model=args.llm_model,
    )
    if args.export_dir:
        from vsa.artifacts.export import export_report_bundle

        paths = export_report_bundle(report, args.export_dir, audit_mode=args.audit_mode)
        print(json.dumps(paths, indent=2))
        return 0 if result.overall_status in ("passed", "partial") else 1

    if args.out:
        write_audit_artifact(
            report,
            args.out,
            mode=args.audit_mode,
            provider=args.llm_provider,
            model=args.llm_model,
            result=result,
        )
        print(f"wrote {args.out}")
        return 0 if result.overall_status in ("passed", "partial") else 1

    text = json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"
    _write_output(text, None)
    return 0 if result.overall_status in ("passed", "partial") else 1


def cmd_export(args: argparse.Namespace) -> int:
    from vsa.artifacts.export import export_report_bundle

    report = _load_report(args.report)
    paths = export_report_bundle(
        report,
        args.out_dir,
        audit_mode=args.audit_mode,
        include_attestation=not args.no_attestation,
    )
    print(json.dumps(paths, indent=2))
    return 0


def cmd_verify_review(args: argparse.Namespace) -> int:
    return cmd_review_verify(args)


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    from vsa.artifacts.verify import verify_bundle

    ok, errors = verify_bundle(args.bundle_dir, verify_attestation_digest=not args.skip_attestation)
    if ok:
        print("PASS: bundle verified")
        return 0
    print("FAIL: bundle verification errors:", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


def cmd_compare_audit(args: argparse.Namespace) -> int:
    from vsa.compare_audit import compare_audits, format_compare_audits

    audit_a = json.loads(args.audit_a.read_text(encoding="utf-8"))
    audit_b = json.loads(args.audit_b.read_text(encoding="utf-8"))
    diff = compare_audits(audit_a, audit_b)
    text = format_compare_audits(diff) + "\n"
    if args.json:
        text = json.dumps(diff, indent=2, ensure_ascii=False) + "\n"
    _write_output(text, args.out)
    if args.strict and diff.get("overall_changed"):
        return 1
    return 0


def cmd_attest(args: argparse.Namespace) -> int:
    from vsa.provenance.attestation import build_slsa_attestation

    report = _load_report(args.report)
    attestation = build_slsa_attestation(report, subject_name=args.subject_name)
    text = json.dumps(attestation, indent=2, ensure_ascii=False) + "\n"
    _write_output(text, args.out)
    return 0


def cmd_verify_attestation(args: argparse.Namespace) -> int:
    from vsa.provenance.attestation import verify_attestation

    report = _load_report(args.report)
    attestation = json.loads(args.attestation.read_text(encoding="utf-8"))
    ok, msg = verify_attestation(attestation, report, subject_name=args.subject_name)
    print("PASS" if ok else "FAIL", msg)
    return 0 if ok else 1


def cmd_migrate_schema(args: argparse.Namespace) -> int:
    from vsa.migrate.schema import migrate_schema
    from vsa.provenance.hashchain import stamp_report
    from vsa.validate.engine import run_validation

    report = json.loads(args.input.read_text(encoding="utf-8"))
    migrated = migrate_schema(report, target=args.target)
    migrated = stamp_report(migrated)
    migrated = run_validation(migrated, verify_hashes=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"schema_version: {migrated.get('schema_version')}")
    print(f"validation: {migrated['validation_results']['status']}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn not installed. pip install verified-science-agent[api]", file=sys.stderr)
        return 1
    from vsa.api.app import create_app
    from vsa.telemetry import setup_telemetry

    setup_telemetry("vsa-api")
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    from vsa.migrate.ledger import is_ledger, migrate_ledger
    from vsa.provenance.hashchain import stamp_report

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if not is_ledger(data):
        print("ERROR: input is not a legacy claim ledger", file=sys.stderr)
        return 1
    report = migrate_ledger(data)
    if not report.get("evidence"):
        print("ERROR: migrated report has no evidence", file=sys.stderr)
        return 1
    report = stamp_report(report)
    report = run_validation(report, verify_hashes=True)
    out = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"validation: {report['validation_results']['status']}")
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from vsa.benchmark.runner import run_benchmark

    summary = run_benchmark(offline=not args.live, cache_dir=args.cache_dir)
    text = json.dumps(summary, indent=2) + "\n"
    _write_output(text, args.out)
    if summary.get("regression"):
        gaps = summary.get("category_gaps") or {}
        gap_msg = ", ".join(f"{k} missing {v}" for k, v in gaps.items() if v)
        if gap_msg:
            print(f"FAIL: benchmark category gaps: {gap_msg}", file=sys.stderr)
        print("FAIL: benchmark regression detected", file=sys.stderr)
        return 1
    return 0 if summary["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vsa",
        description="Verified Science Agent — evidence-backed scientific report infrastructure.",
    )
    parser.add_argument("--version", action="version", version=f"vsa {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate report JSON against schema and rules")
    p_validate.add_argument("reports", nargs="+", type=Path, help="Report JSON file(s)")
    p_validate.add_argument("--skip-hash-check", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_render = sub.add_parser("render", help="Render report to markdown, html, or json")
    p_render.add_argument("report", type=Path)
    p_render.add_argument("--format", "-f", default="markdown", choices=["markdown", "md", "html", "json", "pdf"])
    p_render.add_argument("--out", "-o", type=Path, default=None)
    p_render.set_defaults(func=cmd_render)

    p_hash = sub.add_parser("hash", help="Compute provenance hashes for a report")
    p_hash.add_argument("report", type=Path)
    p_hash.add_argument("--out", "-o", type=Path, default=None)
    p_hash.add_argument("--json", action="store_true")
    p_hash.set_defaults(func=cmd_hash)

    p_inspect = sub.add_parser("inspect", help="Summarize report structure and validation status")
    p_inspect.add_argument("report", type=Path)
    p_inspect.add_argument("--out", "-o", type=Path, default=None)
    p_inspect.add_argument("--json", action="store_true")
    p_inspect.set_defaults(func=cmd_inspect)

    p_compare = sub.add_parser("compare", help="Compare two report artifacts")
    p_compare.add_argument("report_a", type=Path)
    p_compare.add_argument("report_b", type=Path)
    p_compare.add_argument("--out", "-o", type=Path, default=None)
    p_compare.add_argument("--strict", action="store_true", help="Exit 1 if report hashes differ")
    p_compare.set_defaults(func=cmd_compare)

    p_retrieve = sub.add_parser("retrieve", help="Retrieve evidence for a scientific question")
    p_retrieve.add_argument("question", type=str)
    p_retrieve.add_argument("--cache-dir", default=".vsa_cache")
    p_retrieve.add_argument("--out", "-o", type=Path, default=None)
    p_retrieve.add_argument("--quiet", "-q", action="store_true")
    p_retrieve.set_defaults(func=cmd_retrieve)

    p_build = sub.add_parser("build", help="Build a report from input JSON")
    p_build.add_argument("input", type=Path)
    p_build.add_argument("--out", "-o", type=Path, required=True)
    p_build.add_argument("--cache-dir", default=".vsa_cache")
    p_build.add_argument("--claim-mode", default="auto", choices=["auto", "rule", "llm"])
    p_build.add_argument("--llm-provider", choices=["openai", "anthropic"], default=None)
    p_build.add_argument("--llm-model", default=None)
    p_build.set_defaults(func=cmd_build)

    p_extract = sub.add_parser("extract", help="Extract claims from input JSON (rule or LLM)")
    p_extract.add_argument("input", type=Path)
    p_extract.add_argument("--out", "-o", type=Path, default=None)
    p_extract.add_argument("--cache-dir", default=".vsa_cache")
    p_extract.add_argument("--claim-mode", default="auto", choices=["auto", "rule", "llm"])
    p_extract.add_argument("--llm-provider", choices=["openai", "anthropic"], default=None)
    p_extract.add_argument("--llm-model", default=None)
    p_extract.set_defaults(func=cmd_extract)

    p_review = sub.add_parser("review", help="Human review workflow")
    p_review.add_argument("--reviewer", default=None, help="Reviewer identity (legacy apply mode)")
    p_review.add_argument("--decision", default="approved", help="Review decision (legacy apply mode)")
    p_review.add_argument("--approve", default="", help="Comma-separated claim IDs (legacy apply mode)")
    p_review.add_argument("--corrections", nargs="*", default=[], help="Required corrections")
    p_review.add_argument("--notes", default=None, help="Reviewer notes")
    p_review.add_argument("--out", "-o", type=Path, default=None)
    p_review.add_argument("--reject", action="store_true", help="Reject report (legacy apply mode)")
    review_sub = p_review.add_subparsers(dest="review_action")

    p_apply = review_sub.add_parser("apply", help="Apply review with legacy flags")
    p_apply.add_argument("report", type=Path)
    p_apply.add_argument("--reviewer", required=True)
    p_apply.add_argument("--decision", default="approved")
    p_apply.add_argument("--approve", default="")
    p_apply.add_argument("--corrections", nargs="*", default=[])
    p_apply.add_argument("--notes", default=None)
    p_apply.add_argument("--out", "-o", type=Path, default=None)
    p_apply.add_argument("--reject", action="store_true")
    p_apply.set_defaults(func=cmd_review)

    p_rs = review_sub.add_parser("start", help="Start human review session")
    p_rs.add_argument("report", type=Path)
    p_rs.add_argument("--reviewer", required=True)
    p_rs.add_argument("--notes", default=None)
    p_rs.add_argument("--out", "-o", type=Path, default=None)
    p_rs.set_defaults(func=cmd_review)

    p_ra = review_sub.add_parser("approve-claim", help="Approve one or more claims")
    p_ra.add_argument("report", type=Path)
    p_ra.add_argument("--reviewer", required=True)
    p_ra.add_argument("--claim", action="append", required=True, help="Claim ID (repeatable)")
    p_ra.add_argument("--notes", default=None)
    p_ra.add_argument("--out", "-o", type=Path, default=None)
    p_ra.set_defaults(func=cmd_review)

    p_rr = review_sub.add_parser("request-corrections", help="Request corrections without approving")
    p_rr.add_argument("report", type=Path)
    p_rr.add_argument("--reviewer", required=True)
    p_rr.add_argument("--corrections", nargs="+", required=True)
    p_rr.add_argument("--notes", default=None)
    p_rr.add_argument("--out", "-o", type=Path, default=None)
    p_rr.set_defaults(func=cmd_review)

    p_rj = review_sub.add_parser("reject", help="Reject report")
    p_rj.add_argument("report", type=Path)
    p_rj.add_argument("--reviewer", required=True)
    p_rj.add_argument("--notes", default=None)
    p_rj.add_argument("--out", "-o", type=Path, default=None)
    p_rj.set_defaults(func=cmd_review)

    p_rv = review_sub.add_parser("verify", help="Verify review event chain hashes")
    p_rv.add_argument("report", type=Path)
    p_rv.set_defaults(func=cmd_review)

    p_review.set_defaults(func=cmd_review)

    p_sign = sub.add_parser("sign", help="Ed25519-sign report provenance hash")
    p_sign.add_argument("report", type=Path, nargs="?", default=None)
    p_sign.add_argument("--out", "-o", type=Path, default=None)
    p_sign.add_argument("--key-file", default=".vsa_signing_key")
    p_sign.add_argument("--generate-key", action="store_true")
    p_sign.set_defaults(func=cmd_sign)

    p_vsig = sub.add_parser("verify-signature", help="Verify Ed25519 signature on report")
    p_vsig.add_argument("report", type=Path)
    p_vsig.set_defaults(func=cmd_verify_signature)

    p_audit = sub.add_parser("audit", help="Scientific audit (rule + optional LLM verifier)")
    p_audit.add_argument("report", type=Path)
    p_audit.add_argument("--out", "-o", type=Path, default=None)
    p_audit.add_argument("--export-dir", type=Path, default=None, help="Export report bundle with audit.json")
    p_audit.add_argument("--audit-mode", default="auto", choices=["auto", "rule", "llm"])
    p_audit.add_argument("--llm-provider", choices=["openai", "anthropic"], default=None)
    p_audit.add_argument("--llm-model", default=None)
    p_audit.set_defaults(func=cmd_audit)

    p_export = sub.add_parser("export", help="Export report artifact bundle (report, audit, provenance, review)")
    p_export.add_argument("report", type=Path)
    p_export.add_argument("--out-dir", "-o", type=Path, required=True)
    p_export.add_argument("--audit-mode", default="rule", choices=["auto", "rule", "llm"])
    p_export.add_argument("--no-attestation", action="store_true", help="Skip attestation.json in bundle")
    p_export.set_defaults(func=cmd_export)

    p_verify_bundle = sub.add_parser("verify-bundle", help="Verify export bundle manifest hashes and attestation")
    p_verify_bundle.add_argument("bundle_dir", type=Path)
    p_verify_bundle.add_argument("--skip-attestation", action="store_true")
    p_verify_bundle.set_defaults(func=cmd_verify_bundle)

    p_verify_review = sub.add_parser("verify-review", help="Verify review event chain hashes on a report")
    p_verify_review.add_argument("report", type=Path)
    p_verify_review.set_defaults(func=cmd_verify_review)

    p_compare_audit = sub.add_parser("compare-audit", help="Compare two audit JSON artifacts")
    p_compare_audit.add_argument("audit_a", type=Path)
    p_compare_audit.add_argument("audit_b", type=Path)
    p_compare_audit.add_argument("--out", "-o", type=Path, default=None)
    p_compare_audit.add_argument("--json", action="store_true")
    p_compare_audit.add_argument("--strict", action="store_true", help="Exit 1 if overall audit status changed")
    p_compare_audit.set_defaults(func=cmd_compare_audit)

    p_migrate = sub.add_parser("migrate", help="Migrate legacy claim-ledger JSON to ScientificReport")
    p_migrate.add_argument("input", type=Path)
    p_migrate.add_argument("--out", "-o", type=Path, required=True)
    p_migrate.set_defaults(func=cmd_migrate)

    p_bench = sub.add_parser("benchmark", help="Run benchmark task suite")
    p_bench.add_argument("--live", action="store_true")
    p_bench.add_argument("--cache-dir", default=".vsa_cache")
    p_bench.add_argument("--out", "-o", type=Path, default=None)
    p_bench.set_defaults(func=cmd_benchmark)

    p_attest = sub.add_parser("attest", help="Generate SLSA/in-toto provenance attestation")
    p_attest.add_argument("report", type=Path)
    p_attest.add_argument("--out", "-o", type=Path, default=None)
    p_attest.add_argument("--subject-name", default="scientific_report.json")
    p_attest.set_defaults(func=cmd_attest)

    p_vattest = sub.add_parser("verify-attestation", help="Verify attestation matches report hash")
    p_vattest.add_argument("report", type=Path)
    p_vattest.add_argument("attestation", type=Path)
    p_vattest.add_argument("--subject-name", default="scientific_report.json")
    p_vattest.set_defaults(func=cmd_verify_attestation)

    p_mschema = sub.add_parser("migrate-schema", help="Migrate report to newer schema version")
    p_mschema.add_argument("input", type=Path)
    p_mschema.add_argument("--out", "-o", type=Path, required=True)
    p_mschema.add_argument("--target", default=None, help="Target schema version (default: current)")
    p_mschema.set_defaults(func=cmd_migrate_schema)

    p_serve = sub.add_parser("serve", help="Start REST API server (requires [api] extra)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parsed_argv = list(argv) if argv is not None else None
    if parsed_argv is not None and len(parsed_argv) >= 2 and parsed_argv[0] == "review":
        subs = {"start", "approve-claim", "request-corrections", "reject", "verify", "apply"}
        if parsed_argv[1] not in subs and not parsed_argv[1].startswith("-"):
            parsed_argv.insert(1, "apply")
    parser = build_parser()
    args = parser.parse_args(parsed_argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
