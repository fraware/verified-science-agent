# Demo narrative

## Slide 1 — Why scientific AI systems need evidence infrastructure

AI systems can summarize papers, search databases, inspect molecular structures, and generate research hypotheses quickly.

The difficult problem is no longer generation alone. Research teams need outputs that are:

- reviewable,
- reproducible,
- traceable,
- auditable.

This repository provides infrastructure for evidence-backed AI reports — treating scientific outputs like software build artifacts.

---

## Slide 2 — What this repository demonstrates

The pipeline converts scientific questions into structured `ScientificReport` JSON artifacts:

- normalized evidence from read-only database connectors,
- claims bound to evidence IDs (no invented sources),
- validation, provenance hashes, and optional Ed25519 signing,
- rule-based or LLM audit with conservative merge,
- human review workflow with verifiable event chains,
- export bundles with manifest verification (`vsa verify-bundle`),
- 27-task offline benchmark with CI regression gate,
- REST API with optional auth.

Supporting tools: CLI, Streamlit UI, SLSA/in-toto attestation, benchmark suite.

---

## Slide 3 — Scope and direction

**Production-ready today (CI-verified):** schema validation, rule-based claims, export bundles, review workflow, attestation, offline benchmark.

**Experimental:** LLM claim extraction, LLM audit, live connector retrieval, OpenTelemetry.

**Not yet implemented:** full-text paper parsing, curator-verified clinical gold standards, external SLSA registry.

This is research infrastructure — not a medical device. Human expert review is required before any clinical use.
