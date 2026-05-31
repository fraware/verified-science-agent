# Verified Science Agent

[![CI](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/package-v0.6.0-orange)

Evidence-backed scientific AI report infrastructure. Treat every AI-generated scientific report like a software build artifact: inputs, source records, claims, validation checks, provenance, reproducibility metadata, and review status.

**Release status:** see [RELEASE_STATUS.md](RELEASE_STATUS.md) · **Docs:** [architecture](docs/architecture.md) · [schema](docs/schema.md) · [connectors](docs/connectors.md)

## North star

A scientific AI report should be inspectable by engineers, readable by scientists, and shareable with reviewers — with signed or hashable outputs.

## Quick start

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
pip install -e ".[dev,ui,pdf,signing]"
```

### v0.6.0 workflow (CI-verified)

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make demo && make test && vsa benchmark
vsa serve --port 8000          # REST API at http://127.0.0.1:8000
vsa attest reports/brca1_report.json --out reports/attestation.json
pytest -m live                 # optional live connector tests
```

### v0.4.0 workflow (CI-verified)

```bash
vsa retrieve "BRCA1 c.68_69del"
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
vsa validate reports/brca1_report.json
vsa audit reports/brca1_report.json --audit-mode rule --out reports/audit.json
vsa export reports/brca1_report.json --out-dir reports/bundle/
vsa compare-audit reports/audit.json reports/audit.json
vsa sign reports/brca1_report.json
vsa benchmark
make demo && make test
```

### v0.3.0 workflow

```bash
vsa retrieve "BRCA1 c.68_69del"
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
vsa validate reports/brca1_report.json
vsa audit reports/brca1_report.json
vsa sign reports/brca1_report.json
vsa verify-signature reports/brca1_report.json
vsa render reports/brca1_report.json --format markdown
vsa hash reports/brca1_report.json
vsa benchmark
streamlit run ui/app.py
```

### v0.1.0 workflow

```bash
vsa retrieve "BRCA1 c.68_69del"
vsa build examples/brca1_input.json --out reports/brca1_report.json
vsa validate reports/brca1_report.json
vsa render reports/brca1_report.json --format markdown
vsa hash reports/brca1_report.json
vsa inspect reports/brca1_report.json
vsa compare reports/brca1_report.json reports/brca1_report.json
```

Or run the full demo:

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
| `vsa validate report.json` | Schema + semantic validation |
| `vsa render report.json --format markdown\|html\|json` | Render readable report |
| `vsa hash report.json` | Provenance hash chain |
| `vsa inspect report.json` | Structural summary |
| `vsa compare report_a.json report_b.json` | Diff two reports |
| `vsa retrieve "question"` | Retrieve evidence from databases |
| `vsa build input.json --out report.json` | Build full ScientificReport |
| `vsa extract input.json` | Extract claims (rule or LLM) |
| `vsa render report.json --format markdown\|html\|json\|pdf` | Render report (PDF needs `[pdf]` extra) |
| `vsa review report.json --reviewer NAME --approve C001 --notes "..."` | Human review workflow |
| `vsa audit report.json` | Scientific audit (rule + optional LLM hybrid) |
| `vsa sign report.json` | Ed25519-sign report provenance hash |
| `vsa verify-signature report.json` | Verify Ed25519 signature |
| `vsa migrate ledger.json --out report.json` | Migrate legacy claim ledger |
| `vsa export report.json --out-dir dir/` | Export bundle: report, audit, provenance, review, attestation, manifest |
| `vsa compare-audit audit_a.json audit_b.json` | Diff audit artifacts across runs |
| `vsa attest report.json --out attestation.json` | SLSA/in-toto provenance attestation |
| `vsa verify-attestation report.json attestation.json` | Verify attestation digest |
| `vsa migrate-schema report.json --out migrated.json` | Upgrade schema version |
| `vsa serve --port 8000` | Start REST API (requires `[api]` extra) |
| `vsa benchmark` | Run benchmark task suite (offline or `--live`) |
| `vsa compare report_a.json report_b.json --strict` | Diff reports (exit 1 if hashes differ) |

Launch the full UI (build, review, evidence graph, PDF export):

```bash
pip install -e ".[ui,pdf]"
streamlit run ui/app.py
```

## LLM claim extraction

Set API keys in `.env` (see `.env.example`):

```bash
cp .env.example .env
# Edit .env with your keys — never commit .env
```

Build with LLM claims (auto-detects provider):

```bash
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode llm
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode auto
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode llm --llm-provider anthropic
```

Rule-based fallback (no API keys required):

```bash
vsa build examples/brca1_input.json --out reports/brca1_report.json --claim-mode rule
```

## LLM scientific audit

Hybrid verifier: deterministic rule checks plus optional LLM semantic review (conservative merge — rules cannot be overridden).

```bash
vsa audit reports/brca1_report.json                      # auto: LLM if keys present
vsa audit reports/brca1_report.json --audit-mode rule    # deterministic only
vsa audit reports/brca1_report.json --audit-mode llm     # LLM + mandatory rule overlay
vsa audit reports/brca1_report.json --audit-mode llm --llm-provider anthropic
```

Rule-based fallback (no API keys required):

```bash
vsa audit reports/brca1_report.json --audit-mode rule
```

The LLM auditor evaluates only the claim text and cited evidence provided in the payload — it cannot introduce new sources.

## ScientificReport schema

Canonical artifact model (schema version **1.1.0**, also accepts **1.0.0**):

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

Schema file: `src/vsa/schemas/scientific_report.schema.json`

Domains supported: genomics variants, proteins, papers, chemicals, materials, experiments.

## Database connectors

Read-only connectors with normalized evidence output and file caching (`.vsa_cache/`):

- OpenAlex
- **PubMed** (NCBI E-utilities)
- Europe PMC
- UniProt
- ClinVar
- AlphaFold DB
- Crossref
- Materials Project (requires API key)

Each connector returns:

```json
{
  "source_name": "...",
  "source_type": "...",
  "identifier": "...",
  "retrieval_path": "...",
  "retrieved_at": "...",
  "summary": "...",
  "raw_record_hash": "..."
}
```

## Architecture

```
question → subject parser → connector queries → evidence candidates → ranking
         → claim extraction (evidence IDs only) → validation → provenance → render
```

Core rule: **retrieval produces evidence, generation produces claims, validation checks claims against evidence.** Models cannot invent source fields.

## Repository structure

```text
src/vsa/           Python package (CLI, validation, connectors, pipeline, render)
schemas/           JSON Schema (symlink to package schema)
examples/          Input files and good/bad report examples
benchmarks/        Evaluation tasks and offline fixtures
reports/           Generated report snapshots
tests/             pytest suite
ui/                Streamlit inspector
.github/workflows/ CI pipeline
```

## Validation engine

Checks include:

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

25 offline tasks (genomics, protein, paper, materials, adversarial cases):

```bash
vsa benchmark
```

Scoring includes source coverage, claim validity, citation integrity, contradiction detection, and hash reproducibility. See `benchmarks/tasks.json`.

## Known limitations

- **Connectors**: Live retrieval can be ambiguous; inspect `retrieval_warnings` and evidence `domain_metadata.retrieval_ambiguity`.
- **Claims**: Rule extraction uses domain templates — not deep variant interpretation.
- **Benchmark**: Heuristic gold labels, not curator-verified clinical truth.
- **Audit**: Hybrid LLM audit is experimental; use `--audit-mode rule` for deterministic CI.
- **Platform**: CI canonical environment is Ubuntu; see [RELEASE_STATUS.md](RELEASE_STATUS.md).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Safety notice

Research infrastructure only. Not a medical device, clinical decision system, or diagnostic platform.

Every variant report includes:

> Research infrastructure output. Not for diagnosis, treatment, or clinical decision-making without qualified expert review.

Human expert review is required before any clinical use.

## License

MIT License.
