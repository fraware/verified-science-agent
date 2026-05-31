# ScientificReport schema (v1.2.0)

Canonical artifact: `src/vsa/schemas/scientific_report.schema.json`

Supported versions: `1.0.0`, `1.1.0`, `1.2.0`

## Top-level fields

| Field | Required | Purpose | Example failure mode |
|-------|----------|---------|-------------------|
| `schema_version` | yes | Schema semver | Unsupported version rejected by validator |
| `report_id` | yes | Stable artifact ID | Missing breaks provenance tracking |
| `created_at` | yes | ISO-8601 timestamp | Invalid format fails JSON Schema |
| `input_question` | no (1.2+) | Original user question | Omitting loses reproducibility context |
| `domain` | no (1.2+) | Scientific domain label | Helps routing and review policy |
| `subject` | yes | Parsed entity | Wrong `entity_type` routes to wrong connectors |
| `claims` | yes (min 1) | Atomic assertions | Empty claims fail validation |
| `evidence` | yes (min 1) | Normalized sources | Dangling evidence refs fail validation |
| `retrieval_plan` | no (1.2+) | Connectors attempted | Documents what was queried |
| `retrieval_warnings` | no (1.2+) | Ambiguity / empty results | Silent ambiguity if ignored |
| `evidence_selection_method` | no (1.2+) | Ranking method | — |
| `claim_generation_method` | no (1.2+) | rule / llm stack | — |
| `review_policy` | no (1.2+) | When human review required | — |
| `limitations` | no (1.2+) | Safety and scope notes | — |
| `contradictions` | no | Detected conflicts | High severity fails validation |
| `provenance` | yes | Hash chain | Hash mismatch fails `vsa validate` |
| `validation_results` | yes | Check outcomes | `fail` status blocks release |
| `human_review` | yes | Review state | Clinical claims + approved = error |

## Claim fields

| Field | Purpose | Common failure |
|-------|---------|----------------|
| `claim_id` | Stable ID | Duplicate IDs break review |
| `claim_type` | Domain category | Wrong type skews audit |
| `claim_text` | Human-readable assertion | Too short fails audit |
| `evidence_ids` | Citations | Invented ID → `unsupported` |
| `confidence` | 0–1 score | Out of range fails validation |
| `review_boundary` | Safety label | Clinical text without `requires_clinical_review` |
| `uncertainty_level` | low/medium/high/unknown | Speculative + low uncertainty flagged |
| `support_level` | Evidence strength | — |

## Evidence fields

| Field | Purpose | Common failure |
|-------|---------|----------------|
| `evidence_id` | Citation target | Must resolve from claims |
| `source_name` | Connector label | — |
| `source_type` | database/publication/structure | Missing fails validation |
| `identifier` | Source-native ID | — |
| `retrieval_path` | Reproducible URL | Missing fails validation |
| `raw_record_hash` | Content fingerprint | Mismatch fails provenance check |
| `reliability` | high/medium/low | Ambiguous ClinVar → medium |
| `domain_metadata` | Connector-specific | `retrieval_ambiguity: true` needs review |

## Migration

- **1.0.0 → 1.1.0**: Add optional `signature`, review chain hashes; `human_review` in report hash core.
- **1.1.0 → 1.2.0**: Add lifecycle fields (`input_question`, `retrieval_warnings`, etc.) and `evidence_content_hash`, `validation_run_hash` in provenance. All new fields optional for backward compatibility.

Rebuild pinned reports after schema bumps: `vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule`
