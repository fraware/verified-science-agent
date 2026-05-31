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
  → render / audit / sign / review
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
| Artifacts | `src/vsa/artifacts/` | Export audit/provenance bundles |
| API | `src/vsa/api/` | FastAPI REST server |
| Attestation | `src/vsa/provenance/attestation.py` | SLSA/in-toto statements |
| Telemetry | `src/vsa/telemetry.py` | Optional OpenTelemetry spans |

## Hash layers

- `source_record_hashes` — per-evidence raw record SHA-256
- `evidence_bundle_hash` — full evidence array
- `evidence_content_hash` — summaries + domain metadata
- `claim_hashes` — per-claim content
- `report_hash` — subject, claims, evidence, contradictions, human_review
- `validation_run_hash` — validation_results snapshot

## Release posture

See [RELEASE_STATUS.md](../RELEASE_STATUS.md) for production-ready vs experimental features.
