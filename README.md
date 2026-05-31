# Verified Science Agent

Evidence-backed scientific AI report infrastructure. Treat every AI-generated scientific report like a software build artifact: inputs, source records, claims, validation checks, provenance, reproducibility metadata, and review status.

## North star

A scientific AI report should be inspectable by engineers, readable by scientists, and shareable with reviewers — with signed or hashable outputs.

## Quick start

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
pip install -e ".[dev,ui,pdf,signing]"
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

Six domain tasks with offline fixtures (genomics, protein, paper, materials):

```bash
vsa benchmark
# or
python benchmarks/run_benchmark.py
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Safety notice

Research infrastructure only. Not a medical device, clinical decision system, or diagnostic platform. Human expert review is required before any clinical use.

## License

MIT License.
