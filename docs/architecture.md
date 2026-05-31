# Architecture

## Pipeline

```text
input_question
  → subject parser (entity_type, identifiers)
  → retrieval_plan (connector routing)
  → connectors (NormalizedEvidence, raw_record cached)
  → deduplication (DOI/PMID/title for papers)
  → quality scoring + ranking
  → claim extraction (rule or LLM; evidence IDs only)
  → contradiction detection
  → validation engine
  → provenance hash chain
  → render / audit / sign / review / export
```

## Core rule

Retrieval produces evidence. Generation produces claims. Validation checks claims against evidence. Models cannot invent source fields.

## Components

| Layer | Module | Responsibility |
|-------|--------|------------------|
| CLI | `src/vsa/cli.py` | User-facing commands |
| Pipeline | `src/vsa/pipeline/` | Build, retrieve, parse subjects |
| Connectors | `src/vsa/connectors/` | Read-only database access |
| Claims | `src/vsa/claims/` | Rule and LLM extraction |
| Validate | `src/vsa/validate/` | Schema + semantic checks |
| Provenance | `src/vsa/provenance/` | Hashes, signing |
| Audit | `src/vsa/llm/verifier.py` | Rule + hybrid LLM audit |
| Review | `src/vsa/review/workflow.py` | Human review events and chain verification |
| Artifacts | `src/vsa/artifacts/` | Export bundles, manifest verification |
| API | `src/vsa/api/` | FastAPI REST server |
| Attestation | `src/vsa/provenance/attestation.py` | SLSA/in-toto statements |
| Telemetry | `src/vsa/telemetry.py` | Optional OpenTelemetry spans |
| Benchmark | `src/vsa/benchmark/` | 27-task offline evaluation suite |

## Hash layers

- `source_record_hashes` — per-evidence raw record SHA-256
- `evidence_bundle_hash` — full evidence array
- `evidence_content_hash` — summaries + domain metadata
- `claim_hashes` — per-claim content
- `report_hash` — subject, claims, evidence, contradictions, human_review
- `validation_run_hash` — validation_results snapshot
- `review_chain_hash` — human review event chain (when present)

## Export bundle

`vsa export` writes a directory with:

- `report.json`, `report.md`, `audit.json`, `provenance.json`, `review.json`
- `attestation.json` (unless skipped)
- `sources/` — cached raw connector records
- `manifest.json` — SHA-256 hashes for all files

`vsa verify-bundle` checks manifest integrity and attestation digest.

## CI and acceptance

`.github/workflows/ci.yml` runs the full pipeline on Ubuntu (Python 3.10–3.12) plus macOS smoke. The acceptance job runs `scripts/acceptance.sh` after matrix jobs pass.

See [RELEASE_STATUS.md](../RELEASE_STATUS.md) for production-ready vs experimental features.
