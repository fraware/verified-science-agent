# Architecture

## Pipeline

```text
input_question
  → subject parser (entity_type, identifiers)
  → retrieval_plan (connector routing)
  → connectors (NormalizedEvidence → SourceRecord + evidence view)
  → deduplication (DOI/PMID/title for papers)
  → quality scoring + ranking
  → claim extraction (rule or LLM; evidence IDs only; no source invention)
  → claim–evidence graph (support/contradict + spans)
  → contradiction detection
  → validation engine (dangling/scope/write barrier)
  → provenance hash chain
  → render / audit / sign / review / export
```

## Core rule

Retrieval produces immutable `SourceRecord`s. Evidence is a *view* over source digests. Generation produces claims that may only cite existing evidence/source IDs. Validation checks claims against evidence and rejects forged authoritative source fields.

## Components

| Layer | Module | Responsibility |
|-------|--------|------------------|
| CLI | `src/vsa/cli.py` | User-facing commands |
| Pipeline | `src/vsa/pipeline/` | Build, retrieve, parse subjects |
| Connectors | `src/vsa/connectors/` | Read-only database access |
| Claims | `src/vsa/claims/` | Rule and LLM extraction + graph normalize |
| Validate | `src/vsa/validate/` | Schema + semantic checks |
| Provenance | `src/vsa/provenance/` | Hashes, SourceRecord, signing |
| Audit | `src/vsa/llm/verifier.py` | Rule + hybrid LLM audit |
| Review | `src/vsa/review/workflow.py` | Human review events and chain verification |
| Scientific | `src/vsa/scientific/credibility.py` | Ambiguity caps, metadata/AlphaFold warnings |
| Artifacts | `src/vsa/artifacts/` | Export bundles, reconstruct, manifest verification |
| Acceptance | `src/vsa/acceptance/` | Offline baseline + skipped-live connector registry |
| Domain packs | `src/vsa/domain_packs/` | Clinical genetics / materials routing + review policy |
| API | `src/vsa/api/` | FastAPI REST server |
| Attestation | `src/vsa/provenance/attestation.py` | SLSA/in-toto statements |
| Telemetry | `src/vsa/telemetry.py` | Optional OpenTelemetry spans |
| Benchmark | `src/vsa/benchmark/` | 50-task offline evaluation suite |

## Hash layers

- `source_record_hashes` — per-evidence raw record SHA-256
- `evidence_bundle_hash` — full evidence array
- `evidence_content_hash` — summaries + domain metadata
- `claim_hashes` — per-claim content
- `report_hash` — subject, claims, evidence, source_records, contradictions, human_review
- `validation_run_hash` — validation_results snapshot
- `review_chain_hash` — human review event chain (when present)

## Export bundle

`vsa export` writes a directory with:

- `report.json`, `report.md`, `audit.json`, `provenance.json`, `review.json`
- `attestation.json` (unless skipped)
- `sources/` — SourceRecord + evidence view; raw body when `raw_response_retention=retained`
- `manifest.json` — SHA-256 hashes for all files

`vsa verify-bundle` checks manifest integrity and attestation digest.

`vsa reconstruct --verify` rebuilds report hashes from retained SourceRecords + config; fails if retention is `digest_only`/`unavailable`.

## Decision-time companions (additive)

ScientificReport **1.3.0** is the current report contract. Companion artifacts integrate VSA with AKTA and Scientific Memory:

| Artifact | Module | Role |
|----------|--------|------|
| Integration envelope | `src/vsa/identity/` | Stable IDs + digests beside a report |
| DecisionTimeEvidenceBundle | `src/vsa/decision_time/` | Cutoff-frozen evidence snapshot |
| AktaActionContext | `src/vsa/export/akta.py` | Stable export for AKTA (no authorization) |
| ScientificOutcomeLink | `src/vsa/outcome/` | Append-only outcome/calibration pointer |

Hard boundaries: VSA never authorizes actions, executes tools, issues grants, or certifies scientific correctness. Decision-time bundles are immutable; outcomes append as linked records only. See [ADR 0001](adr/0001-vsa-akta-scientific-memory-boundaries.md), [threat model](threat-model.md), and [decision-time quick start](decision-time-quickstart.md).

CLI: `snapshot-evidence`, `verify-decision-time-bundle`, `compare-cutoffs`, `export-akta-context`, `link-outcome`, `reconstruct`.

Public schema mirrors under `schemas/` must stay byte-identical to `src/vsa/schemas/`.

## Continuous integration

See `.github/workflows/ci.yml`. Offline acceptance writes `reports/acceptance_baseline.json` listing every skipped live connector.
