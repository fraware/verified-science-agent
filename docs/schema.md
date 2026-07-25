# ScientificReport schema (v1.3.0)

Canonical package artifact: `src/vsa/schemas/scientific_report.schema.json`

Public mirror (must stay byte-identical): `schemas/scientific_report.schema.json`

Supported versions: `1.0.0`, `1.1.0`, `1.2.0`, `1.3.0`

Migrate with: `vsa migrate-schema report.json --out migrated.json`

Standalone SourceRecord contract: `schemas/source_record.schema.json` (mirrored under `src/vsa/schemas/`).

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
| `evidence` | yes (min 1) | Views over SourceRecords | Dangling evidence refs fail validation |
| `source_records` | no (1.3+) | Immutable source authority | Forged digests/URLs fail write barrier |
| `claim_evidence_graph` | no (1.3+) | Support/contradict edges | Dangling graph edges fail validation |
| `retrieval_plan` | no (1.2+) | Connectors attempted | Documents what was queried |
| `retrieval_warnings` | no (1.2+) | Ambiguity / empty results / typed failure codes | Silent ambiguity if ignored |
| `retrieval_status` | no (1.3+) | `complete` \| `partial` \| `failed` | Failure must not be read as empty evidence |
| `connector_outcomes` | no (1.3+) | Per-connector typed outcomes | Collapse of failure into silent empty |
| `domain_pack` | no (1.3+) | Selected domain pack name | Wrong connector routing if ignored |
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
| `claim_text_normalized` | Stable normalized text (1.3+) | — |
| `supporting_evidence_ids` | Supporting citations (1.3+) | Empty unless `unsupported` |
| `contradicting_evidence_ids` | Contradicting citations (1.3+) | Dangling ID fails validation |
| `evidence_ids` | Compatibility union of support/contradict | Invented ID → dangling fail |
| `source_spans` | Quote spans into sources (1.3+) | Missing source_id / evidence_id |
| `inference_method` | `direct_extract` \| `rule` \| `llm` \| … | — |
| `confidence` | 0–1 score | Out of range fails validation |
| `confidence_semantics` | Scale interpretation (1.3+) | Bare float alone is insufficient |
| `validation_result` | Per-claim check status (1.3+) | — |
| `reviewer_status` | unreviewed/approved/rejected/needs_revision | — |
| `review_boundary` | Safety label | Clinical text without `requires_clinical_review` |
| `uncertainty_level` | low/medium/high/unknown | Speculative + low uncertainty flagged |
| `support_level` | Evidence strength | — |

## Evidence fields

| Field | Purpose | Common failure |
|-------|---------|----------------|
| `evidence_id` | Citation target | Must resolve from claims |
| `source_id` | Link to SourceRecord (1.3+) | Missing when source_records present |
| `source_name` | Connector label | Must match SourceRecord.connector |
| `source_type` | database/publication/structure | Missing fails validation |
| `identifier` | Source-native ID | Must match SourceRecord.accession |
| `retrieval_path` | Reproducible URL | Must match SourceRecord.canonical_url |
| `raw_record_hash` | Content fingerprint | Must match SourceRecord.content_digest |
| `reliability` | high/medium/low | Ambiguous ClinVar → low |
| `domain_metadata` | Connector-specific | `subject_key` mismatch → scope fail |

## SourceRecord fields (1.3+)

| Field | Purpose |
|-------|---------|
| `source_id` | Stable connector+accession id |
| `content_digest` | SHA-256 of canonical raw bytes/JSON |
| `raw_response_retention` | `retained` \| `digest_only` \| `unavailable` |
| `query` | Exact retrieval query |
| `transformation_history` | Ordered `{op, at, digest_in, digest_out}` |
| `source_availability` | `available` \| `cached` \| `unavailable` \| `substituted` |

Generated models may only attach to existing `source_id`s. Inventing digests/URLs/connectors fails the `source_authority` write barrier.

Rebuild from a retained export bundle:

```bash
vsa reconstruct reports/bundle --verify
```

Fails closed when any SourceRecord is `digest_only` or `unavailable`.

## Version history

| Version | Changes |
|---------|---------|
| **1.3.0** | Immutable `SourceRecord`; claim–evidence graph fields; write barrier; reconstruct path |
| **1.2.0** | Lifecycle fields (`input_question`, `retrieval_warnings`, `limitations`, etc.); `evidence_content_hash`, `validation_run_hash` in provenance |
| **1.1.0** | Optional `signature`; review chain hashes; `human_review` in report hash core |
| **1.0.0** | Initial canonical artifact model |

Rebuild pinned reports after schema bumps:

```bash
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
```

## Companion schemas (additive)

ScientificReport **1.3.0** is the current report contract. Integration contracts live beside it (each companion `schema_version` **1.0.0**). Files exist under both `src/vsa/schemas/` and `schemas/` and must remain byte-identical:

| Schema | Module | Purpose |
|--------|--------|---------|
| `source_record.schema.json` | `vsa.provenance.source_record` | Immutable retrieved-source authority |
| `integration_envelope.schema.json` | `vsa.identity` | Stable IDs + digests |
| `decision_time_evidence_bundle.schema.json` | `vsa.decision_time` | Cutoff-frozen evidence |
| `akta_action_context.schema.json` | `vsa.export.akta` | AKTA context (`authorization: none`) |
| `scientific_outcome_link.schema.json` | `vsa.outcome` | Append-only outcome links |

See [decision-time-quickstart.md](decision-time-quickstart.md), [operator-decision-time.md](operator-decision-time.md), and [ADR 0001](adr/0001-vsa-akta-scientific-memory-boundaries.md).

**Non-claims:** companion artifacts do not authorize actions, execute tools, issue grants, or certify scientific correctness.
