# Verified Science Agent

[![CI](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/package-v0.7.2-orange)

Evidence-backed scientific AI report infrastructure. Treat every AI-generated scientific report like a software build artifact: inputs, source records, claims, validation checks, provenance, reproducibility metadata, and review status.

**Documentation:** [docs/README.md](docs/README.md) · **Release status:** [RELEASE_STATUS.md](RELEASE_STATUS.md)

## North star

A scientific AI report should be inspectable by engineers, readable by scientists, and shareable with reviewers — with signed or hashable outputs.

## Quick start

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
pip install -e ".[dev,ui,pdf,signing,api]"
make acceptance
```

`make acceptance` runs the full CI parity bar: build demo report, pytest, and the 50-task offline benchmark.

### Typical workflow

```bash
# Retrieve and build
vsa retrieve "BRCA1 c.68_69del"
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule

# Validate, audit, export
vsa validate reports/brca1_report.json
vsa audit reports/brca1_report.json --audit-mode rule --out reports/audit.json
vsa export reports/brca1_report.json --out-dir reports/bundle --audit-mode rule
vsa verify-bundle reports/bundle

# Attestation and review
vsa attest reports/brca1_report.json --out reports/attestation.json --subject-name report.json
vsa review start reports/brca1_report.json --reviewer you@example.com
vsa review approve-claim reports/brca1_report.json --reviewer you@example.com --claim C002
vsa verify-review reports/brca1_report.json

# Render, sign, serve
vsa render reports/brca1_report.json --format markdown --out reports/brca1_report.md
vsa sign reports/brca1_report.json
vsa serve --port 8000
```

Or run the Makefile demo only:

```bash
make demo
```

Launch the Streamlit UI:

```bash
streamlit run ui/app.py
```

## CLI commands

| Command | Description |
|---------|-------------|
| `vsa retrieve "question"` | Retrieve evidence from databases |
| `vsa build input.json --out report.json` | Build full ScientificReport |
| `vsa extract input.json` | Extract claims (rule or LLM) |
| `vsa validate report.json` | Schema + semantic validation |
| `vsa audit report.json` | Scientific audit (rule + optional LLM hybrid) |
| `vsa export report.json --out-dir dir/` | Export bundle: report, report.md, audit, provenance, review, attestation, sources/, manifest |
| `vsa verify-bundle dir/` | Verify bundle manifest hashes and attestation |
| `vsa attest report.json --out attestation.json` | SLSA/in-toto provenance attestation |
| `vsa verify-attestation report.json attestation.json` | Verify attestation digest |
| `vsa review start report.json --reviewer NAME` | Start human review session |
| `vsa review approve-claim report.json --reviewer NAME --claim C001` | Approve specific claims |
| `vsa review request-corrections report.json --reviewer NAME` | Request corrections |
| `vsa review reject report.json --reviewer NAME` | Reject report |
| `vsa review verify report.json` | Verify review chain hashes |
| `vsa verify-review report.json` | Same as `review verify` |
| `vsa render report.json --format markdown\|html\|json\|pdf` | Render report (PDF needs `[pdf]` extra) |
| `vsa hash report.json` | Provenance hash chain |
| `vsa inspect report.json` | Structural summary |
| `vsa compare report_a.json report_b.json` | Diff two reports |
| `vsa compare-audit audit_a.json audit_b.json` | Diff audit artifacts across runs |
| `vsa sign report.json` | Ed25519-sign report provenance hash |
| `vsa verify-signature report.json` | Verify Ed25519 signature |
| `vsa migrate ledger.json --out report.json` | Migrate legacy claim ledger |
| `vsa migrate-schema report.json --out migrated.json` | Upgrade schema version |
| `vsa benchmark` | Run 50-task benchmark suite (offline or `--live`) |
| `vsa serve --port 8000` | Start REST API (requires `[api]` extra) |

Legacy review flags remain supported: `vsa review report.json --reviewer NAME --approve C001`.

See [docs/api.md](docs/api.md) for REST endpoint parity.

## LLM modes (optional)

Copy `.env.example` to `.env` and add API keys. Never commit `.env`.

```bash
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode auto
vsa audit reports/brca1_report.json --audit-mode auto
```

Rule-based modes require no API keys and are used in CI:

```bash
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
vsa audit reports/brca1_report.json --audit-mode rule
```

The LLM auditor evaluates only claim text and cited evidence in the payload — it cannot introduce new sources.

## ScientificReport schema

Canonical artifact model (schema version **1.2.0**, also accepts **1.0.0** and **1.1.0**):

```
ScientificReport
  subject
  claims[]
  evidence[]
  methods[]
  provenance
  validation_results
  human_review
  generated_outputs
```

Schema file: `src/vsa/schemas/scientific_report.schema.json` (symlinked at `schemas/`).

Field reference: [docs/schema.md](docs/schema.md)

Domains supported: genomics variants, proteins, papers, chemicals, materials, experiments.

## Database connectors

Read-only connectors with normalized evidence output and file caching (`.vsa_cache/`):

- OpenAlex, Crossref, PubMed (NCBI E-utilities), Europe PMC, Semantic Scholar
- UniProt, ClinVar, AlphaFold DB
- Materials Project (requires `MATERIALS_PROJECT_API_KEY`)

Details: [docs/connectors.md](docs/connectors.md)

Each connector returns normalized evidence with `source_name`, `source_type`, `identifier`, `retrieval_path`, `retrieved_at`, `summary`, and `raw_record_hash`.

## Architecture

```
question → subject parser → connector queries → evidence candidates → ranking
         → claim extraction (evidence IDs only) → validation → provenance → render
```

Core rule: **retrieval produces evidence, generation produces claims, validation checks claims against evidence.** Models cannot invent source fields.

Details: [docs/architecture.md](docs/architecture.md)

## Repository structure

```text
src/vsa/           Python package (CLI, validation, connectors, pipeline, render, API)
schemas/           JSON Schema (symlink to package schema)
examples/          Input files and good/bad report examples
benchmarks/        50 evaluation tasks and offline fixtures
reports/           Generated report snapshots
tests/             pytest suite (99 tests)
ui/                Streamlit inspector
scripts/           acceptance.sh (CI parity bar)
.github/workflows/ CI and release pipelines
docs/              Architecture, schema, connectors, benchmark, API, release checklist
```

## Validation engine

- JSON Schema conformance
- Every claim has evidence; every evidence ID resolves
- Source type and retrieval path present
- Confidence bounded [0, 1]
- Unsupported claims fail; speculative claims labeled
- Human review requirements explicit
- Explainable evidence quality scoring
- Contradiction detection
- Provenance hash verification

## Benchmarks

50 offline tasks covering genomics, protein, paper, materials, and adversarial cases:

```bash
vsa benchmark
```

Scoring includes source coverage, claim validity, citation integrity, contradiction detection, and hash reproducibility. CI fails on any regression below 100% pass rate.

Details: [docs/benchmark.md](docs/benchmark.md)

## Known limitations

- **Connectors**: Live retrieval can be ambiguous; inspect `retrieval_warnings` and evidence `domain_metadata.retrieval_ambiguity`.
- **Claims**: Rule extraction uses domain templates — not deep variant interpretation.
- **Benchmark**: Heuristic gold labels, not curator-verified clinical truth.
- **Audit**: Hybrid LLM audit is experimental; use `--audit-mode rule` for deterministic CI.
- **API**: In-memory rate limiting; optional shared-secret auth via `VSA_API_KEY`.

See [RELEASE_STATUS.md](RELEASE_STATUS.md) for production-ready vs experimental features.

## Development

```bash
pip install -e ".[dev,signing,api]"
pytest
make demo
```

## Safety notice

Research infrastructure only. Not a medical device, clinical decision system, or diagnostic platform.

Every variant report includes:

> Research infrastructure output. Not for diagnosis, treatment, or clinical decision-making without qualified expert review.

Human expert review is required before any clinical use.

## License

MIT License.
