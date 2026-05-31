"""Streamlit UI v3 — build, inspect, review, and render ScientificReports."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from vsa.config import llm_available
from vsa.inspect import inspect_report
from vsa.pipeline.build import build_report
from vsa.pipeline.retrieval import retrieve_evidence_with_meta
from vsa.pipeline.subject_parser import parse_question
from vsa.render import render
from vsa.render.graph import evidence_graph_mermaid
from vsa.render.markdown import _credibility_warning_lines
from vsa.review.workflow import apply_review
from vsa.validate.engine import run_validation, validate_report

st.set_page_config(page_title="Verified Science Agent", layout="wide")
st.title("Verified Science Agent")
st.caption("Evidence-backed scientific report infrastructure — build, validate, review, reproduce")

if "report" not in st.session_state:
    st.session_state.report = None
if "build_warnings" not in st.session_state:
    st.session_state.build_warnings = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
if "sign_message" not in st.session_state:
    st.session_state.sign_message = None
if "export_paths" not in st.session_state:
    st.session_state.export_paths = None
if "attestation" not in st.session_state:
    st.session_state.attestation = None

# --- Sidebar: Build pipeline ---
with st.sidebar:
    st.header("Build pipeline")
    question = st.text_input("Scientific question", value="BRCA1 c.68_69del")
    claim_mode = st.selectbox("Claim mode", ["auto", "rule", "llm"], index=0)
    llm_provider = st.selectbox("LLM provider", ["anthropic", "openai"], index=0)
    llm_model = st.text_input("LLM model (optional)", value="")
    cache_dir = st.text_input("Cache directory", value=".vsa_cache")

    if llm_available():
        st.success("LLM API keys detected")
    else:
        st.info("No LLM keys — auto/rule modes use rule-based extraction")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Retrieve evidence", use_container_width=True):
            with st.spinner("Retrieving..."):
                subject = parse_question(question)
                cache = __import__("vsa.connectors.cache", fromlist=["EvidenceCache"]).EvidenceCache(cache_dir)
                result = retrieve_evidence_with_meta(subject, cache=cache)
                st.session_state.retrieve_preview = {
                    "subject": subject,
                    "evidence": result.evidence,
                    "warnings": result.warnings,
                }
    with col_b:
        if st.button("Build report", type="primary", use_container_width=True):
            with st.spinner("Building..."):
                try:
                    input_data = {"question": question, "claim_mode": claim_mode}
                    if llm_model:
                        input_data["llm_model"] = llm_model
                    input_data["llm_provider"] = llm_provider
                    subject = parse_question(question)
                    cache = __import__("vsa.connectors.cache", fromlist=["EvidenceCache"]).EvidenceCache(cache_dir)
                    retrieval = retrieve_evidence_with_meta(subject, cache=cache)
                    report = build_report(
                        {**input_data, "evidence": retrieval.evidence} if retrieval.evidence else input_data,
                        cache_dir=cache_dir,
                        claim_mode=claim_mode,
                        llm_provider=llm_provider,
                        llm_model=llm_model or None,
                        offline_evidence=retrieval.evidence if retrieval.evidence else None,
                    )
                    st.session_state.report = report
                    st.session_state.build_warnings = list(
                        dict.fromkeys(
                            retrieval.warnings + list(report.get("retrieval_warnings") or [])
                        )
                    )
                    st.success("Report built")
                except Exception as exc:
                    st.error(f"Build failed: {exc}")

    uploaded = st.file_uploader("Or load report JSON", type=["json"])
    if uploaded:
        st.session_state.report = json.loads(uploaded.read().decode("utf-8"))
        st.session_state.build_warnings = []

    if st.session_state.build_warnings:
        st.warning("Retrieval warnings")
        for w in st.session_state.build_warnings[:8]:
            st.caption(w)

    report_preview = st.session_state.report
    if report_preview:
        for w in _credibility_warning_lines(report_preview)[:4]:
            st.error(w[:200] + ("…" if len(w) > 200 else ""))

    st.divider()
    if st.session_state.report and st.download_button(
        "Download JSON",
        json.dumps(st.session_state.report, indent=2),
        file_name="scientific_report.json",
        mime="application/json",
        use_container_width=True,
    ):
        pass

# Load default if nothing in session
report = st.session_state.report
if report is None:
    default_path = Path("reports/brca1_report.json")
    if default_path.exists():
        report = json.loads(default_path.read_text(encoding="utf-8"))
        st.info(f"Loaded default: {default_path}")
    else:
        st.warning("Use the sidebar to build or upload a report.")
        if "retrieve_preview" in st.session_state:
            st.subheader("Retrieval preview")
            st.json(st.session_state.retrieve_preview)
        st.stop()

validation = validate_report(report)
summary = inspect_report(report)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Claims", summary["counts"]["claims"])
c2.metric("Evidence", summary["counts"]["evidence"])
c3.metric("Validation", validation.status.upper())
c4.metric("Contradictions", summary["counts"]["contradictions"])
c5.metric("Review", report.get("human_review", {}).get("status", "?"))

if not validation.passed:
    st.error("Validation failed")
    for check in validation.checks:
        if check.status == "fail":
            st.write(f"- **{check.name}:** {check.message}")
elif validation.status == "warn":
    st.warning("Validation passed with warnings")
else:
    st.success("Validation passed")

credibility_warnings = _credibility_warning_lines(report)
if credibility_warnings:
    st.subheader("Scientific credibility warnings")
    for warning in credibility_warnings:
        st.error(warning)

limitations = report.get("limitations") or []
retrieval_warnings = report.get("retrieval_warnings") or []
if limitations or retrieval_warnings:
    with st.expander("Limitations and retrieval warnings", expanded=bool(credibility_warnings)):
        for item in limitations:
            st.markdown(f"- {item}")
        for item in retrieval_warnings:
            st.markdown(f"- {item}")

(
    tab_overview,
    tab_claims,
    tab_evidence,
    tab_graph,
    tab_review,
    tab_provenance,
    tab_render,
) = st.tabs(
    ["Overview", "Claims", "Evidence", "Evidence graph", "Human review", "Provenance", "Render"]
)

with tab_overview:
    st.subheader("Subject")
    st.json(report.get("subject", {}))
    gen = report.get("provenance", {}).get("generated_by", {})
    st.caption(
        f"Extraction: {gen.get('model_or_agent_stack', '?')} | "
        f"prompt {gen.get('prompt_template_version', '?')}"
    )
    if report.get("contradictions"):
        st.subheader("Contradictions")
        for c in report["contradictions"]:
            st.warning(f"**{c.get('contradiction_id')}**: {c.get('description')}")

with tab_claims:
    evidence_by_id = {e["evidence_id"]: e for e in report.get("evidence", [])}
    unsupported = [c for c in report.get("claims", []) if c.get("review_boundary") == "unsupported"]
    if unsupported:
        st.error(f"{len(unsupported)} unsupported claim(s) — requires correction before use")
    rows = []
    for claim in report.get("claims", []):
        boundary = claim.get("review_boundary", "")
        rows.append(
            {
                "claim_id": claim["claim_id"],
                "type": claim.get("claim_type"),
                "boundary": boundary,
                "confidence": claim.get("confidence"),
                "evidence": ", ".join(claim.get("evidence_ids", [])),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    for claim in report.get("claims", []):
        boundary = claim.get("review_boundary", "")
        is_bad = boundary == "unsupported"
        with st.expander(f"{claim['claim_id']} — {boundary}", expanded=is_bad):
            if is_bad:
                st.error("Unsupported — evidence linkage invalid or missing")
            st.write(claim.get("claim_text"))
            st.write(
                f"Type: `{claim.get('claim_type')}` | "
                f"Confidence: {claim.get('confidence')} | "
                f"Uncertainty: {claim.get('uncertainty_level')}"
            )
            for eid in claim.get("evidence_ids", []):
                ev = evidence_by_id.get(eid, {})
                st.markdown(
                    f"- [{eid}](#) ({ev.get('source_name', '?')}): "
                    f"{ev.get('summary', '')[:180]}"
                )

with tab_evidence:
    for ev in report.get("evidence", []):
        meta = ev.get("domain_metadata") or {}
        reliability = ev.get("reliability", "—")
        ambiguous = meta.get("retrieval_ambiguity") or meta.get("gene_search_ambiguous")
        cols = st.columns([1, 3])
        cols[0].markdown(f"**{ev.get('evidence_id')}**")
        label = f"{ev.get('source_name')} ({ev.get('source_type')}) · reliability: {reliability}"
        if ambiguous:
            label += " · **AMBIGUOUS**"
        if meta.get("structure_type") == "predicted":
            label += " · **PREDICTED STRUCTURE**"
        cols[1].markdown(label)
        if ambiguous:
            st.warning(
                f"Ambiguous retrieval (match_score={meta.get('match_score', '?')}, "
                f"rank={meta.get('candidate_rank', '?')})"
            )
        st.write(ev.get("summary"))
        qs = ev.get("quality_score", {})
        if qs:
            st.progress(min(1.0, qs.get("score", 0)), text=f"Quality {qs.get('score')}")
            with st.expander("Score reasons"):
                for r in qs.get("reasons", []):
                    st.caption(r)
        st.link_button("Open source", ev.get("retrieval_path", ""), use_container_width=False)
        st.divider()

with tab_graph:
    mermaid = evidence_graph_mermaid(report)
    st.markdown("Claim → evidence linkage (Mermaid)")
    st.code(mermaid, language="mermaid")
    st.components.v1.html(
        f"""<pre class="mermaid">{mermaid}</pre>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({{startOnLoad:true}});</script>""",
        height=400,
        scrolling=True,
    )

with tab_review:
    hr = report.get("human_review", {})
    st.json(hr)
    st.subheader("Submit review")
    reviewer = st.text_input("Reviewer identity", value=hr.get("reviewer_identity", ""))
    claim_ids = [c["claim_id"] for c in report.get("claims", [])]
    approved = st.multiselect("Approve claims", claim_ids, default=hr.get("approved_claim_ids", []))
    notes = st.text_area("Review notes")
    corrections = st.text_input("Required corrections (comma-separated)")
    decision = st.selectbox("Decision", ["partial_approval", "approved", "needs_revision"])

    if st.button("Apply review", type="primary"):
        updated = apply_review(
            report,
            reviewer_identity=reviewer or "anonymous",
            review_decision=decision,
            approved_claim_ids=approved,
            required_corrections=[c.strip() for c in corrections.split(",") if c.strip()],
            review_notes=notes or None,
        )
        updated = run_validation(updated, verify_hashes=True)
        st.session_state.report = updated
        st.success(f"Review applied: {updated['human_review']['status']}")
        st.rerun()

with tab_provenance:
    st.json(report.get("provenance", {}))
    sig = report.get("provenance", {}).get("signature")
    if sig:
        st.success(f"Signed ({sig.get('algorithm', '?')}) by {sig.get('signed_by', '?')}")
    else:
        st.info("Report is not signed")

    col_audit, col_sign, col_verify = st.columns(3)
    audit_mode = st.selectbox("Audit mode", ["auto", "rule", "llm"], index=0, key="audit_mode")
    with col_audit:
        if st.button("Run audit", use_container_width=True):
            from vsa.llm.verifier import audit_report

            result = audit_report(
                report,
                mode=audit_mode,
                provider=llm_provider if audit_mode != "rule" else None,
                model=llm_model or None,
            )
            st.session_state.audit_result = result.to_dict()
            st.rerun()
    with col_sign:
        if st.button("Sign report", use_container_width=True):
            try:
                from vsa.provenance.signing import sign_report, verify_signature

                signed = sign_report(report)
                ok, msg = verify_signature(signed)
                st.session_state.report = signed
                st.session_state.sign_message = msg if ok else f"FAILED: {msg}"
                st.rerun()
            except ImportError:
                st.error("Install signing support: pip install verified-science-agent[signing]")
            except Exception as exc:
                st.error(str(exc))
    with col_verify:
        if sig and st.button("Verify signature", use_container_width=True):
            from vsa.provenance.signing import verify_signature

            ok, msg = verify_signature(report)
            st.session_state.sign_message = msg
            st.rerun()

    if st.session_state.get("sign_message"):
        st.caption(st.session_state.sign_message)
    if st.session_state.get("audit_result"):
        st.subheader("Audit result")
        audit = st.session_state.audit_result
        st.caption(f"Method: {audit.get('verifier_method')} | Status: {audit.get('overall_status')}")
        st.json(audit)
        if st.download_button(
            "Download audit JSON",
            json.dumps(audit, indent=2),
            file_name="audit.json",
            mime="application/json",
        ):
            pass

    st.subheader("Artifact bundle")
    col_export, col_attest = st.columns(2)
    with col_export:
        if st.button("Generate export bundle", use_container_width=True):
            import tempfile

            from vsa.artifacts.export import export_report_bundle

            tmp = Path(tempfile.mkdtemp(prefix="vsa_export_"))
            paths = export_report_bundle(report, tmp, audit_mode="rule")
            st.session_state.export_bundle_dir = tmp
            st.session_state.export_paths = paths
            st.rerun()
    with col_attest:
        if st.button("Generate attestation", use_container_width=True):
            from vsa.provenance.attestation import build_slsa_attestation, verify_attestation

            attestation = build_slsa_attestation(report, subject_name="report.json")
            ok, msg = verify_attestation(attestation, report, subject_name="report.json")
            st.session_state.attestation = attestation
            st.session_state.attestation_msg = f"{'PASS' if ok else 'FAIL'}: {msg}"
            st.rerun()

    if st.session_state.get("export_paths"):
        st.caption("Bundle files written to temp directory (download individually):")
        for name, path in st.session_state.export_paths.items():
            p = Path(path)
            if p.exists():
                st.download_button(
                    f"Download {p.name}",
                    p.read_text(encoding="utf-8"),
                    file_name=p.name,
                    mime="application/json",
                    key=f"dl_{name}",
                )
        manifest_path = st.session_state.export_paths.get("manifest")
        if manifest_path and Path(manifest_path).exists():
            st.json(json.loads(Path(manifest_path).read_text(encoding="utf-8")))

    if st.session_state.get("attestation"):
        st.caption(st.session_state.get("attestation_msg", ""))
        st.download_button(
            "Download attestation.json",
            json.dumps(st.session_state.attestation, indent=2),
            file_name="attestation.json",
            mime="application/json",
        )

    st.subheader("Validation checks")
    for check in report.get("validation_results", {}).get("checks", []):
        st.write(f"[{check.get('status', '?').upper()}] {check.get('name')}: {check.get('message')}")

with tab_render:
    fmt = st.selectbox("Format", ["markdown", "html", "json", "pdf"])
    try:
        output = render(report, fmt)
        if fmt == "pdf":
            st.download_button("Download PDF", output, file_name="report.pdf", mime="application/pdf")
        elif fmt == "html":
            st.components.v1.html(output, height=600, scrolling=True)
        else:
            st.code(output if isinstance(output, str) else output.decode(), language=fmt)
    except Exception as exc:
        st.error(str(exc))
        if fmt == "pdf":
            st.info("Install PDF support: pip install verified-science-agent[pdf]")
