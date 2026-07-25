# Benchmark suite

66 offline tasks on the **holdout** evaluation suite measure whether the build pipeline
produces valid, evidence-backed reports across representative scientific domains.

## Dev / holdout split

| Suite | Path | Use |
|-------|------|-----|
| **holdout** (default) | `benchmarks/fixtures/holdout/` | CI `acceptance`, `vsa benchmark`, advertised evaluation |
| **dev** | `benchmarks/fixtures/dev/` | Local iteration and unit / extractor tests |

`vsa benchmark` and `run_benchmark()` default to `--suite holdout`. Use `--suite dev` only
for local iteration against the development fixtures.

**Holdout discipline:** extractor unit tests must not import holdout fixtures. `tests/conftest.py`
points shared fixtures at `dev/` and installs a path guard that fails closed if an extractor
test reads under `benchmarks/fixtures/holdout/`.

Tasks are defined in `benchmarks/tasks.json` and must validate against the task-governance
schema (`schemas/benchmark_task.schema.json` / `src/vsa/schemas/benchmark_task.schema.json`).

## Category minimums

| Category | Minimum | Purpose |
|----------|---------|---------|
| adversarial | 10 | Unsupported claims, dangling evidence, missing paths, premature approval |
| ambiguity | 5 | ClinVar close scores, UniProt isoform ambiguity |
| contradiction | 5 | Pathogenic vs VUS, AlphaFold vs experimental language |
| metadata_only_paper | 5 | Bibliographic-only publication evidence |
| no_evidence | 5 | Empty retrieval must fail validation |
| source_substitution | 5 | Substituted / mirror sources must be visible |
| unavailable_source | 5 | Unavailable primary sources must be visible |
| temporal_cutoff | 5 | Post-cutoff / temporal leakage signals must be visible |

CI fails if any category falls below its minimum, governance schema validation fails,
the holdout suite has fewer than 50 tasks, or pass rate drops below 100%.

## Domain-balance ledger

Primary domain counts on the evaluation task list (one domain per task):

| Domain | Tasks | Role |
|--------|------:|------|
| genomics | 28 | ClinVar / variant classification and clinical review boundaries |
| literature | 15 | DOI/PMID metadata and abstract-supported publication tasks |
| protein | 12 | UniProt / AlphaFold structure and predicted-label tasks |
| materials | 5 | Materials Project property lookups |
| drug_target | 3 | Gene / target identity probes (e.g. EGFR) |
| adversarial | 3 | Synthetic negative-control fixture reports |

The ledger is descriptive, not a hard quota: category minima and the ≥50 holdout task floor
are the regression gates. When adding tasks, prefer under-represented domains so the suite
does not collapse into a single connector family.

## Run

```bash
vsa benchmark
vsa benchmark --suite holdout
vsa benchmark --suite dev
vsa benchmark --out reports/benchmark_summary.json
pytest
```

Live mode hits real connectors (network required):

```bash
vsa benchmark --live
pytest -m live
```

## Task classes

| Class | Example task_id | Intent |
|-------|-----------------|--------|
| Exact lookup | `clinvar_exact`, `paper_doi` | Known ID resolves to expected sources |
| Ambiguous lookup | `variant_ambiguous` | Ambiguity flagged, not silent high reliability |
| No-result lookup | `no_evidence` | Empty evidence fails validation |
| Conflicting evidence | `conflicting_clinical` | Contradictions detected |
| Metadata-only paper | `metadata_paper` | Content warnings when no abstract |
| Abstract-supported paper | `paper_doi` | Abstract-level claims when available |
| Predicted structure only | `alphafold_only` | AlphaFold never implies experimental structure |
| Low-quality source | `low_quality` | Low reliability evidence scored |
| Fake evidence ID | `fake_evidence_id` | Dangling evidence refs fail validation |
| Stale source | `stale_source` | Old `retrieved_at` triggers validation warning |
| Source substitution | `source_substitution_1` | Substituted source metadata surfaced |
| Unavailable source | `unavailable_source_1` | Unavailable source metadata surfaced |
| Temporal cutoff | `temporal_cutoff_1` | Post-cutoff leakage signal surfaced |

Each task carries required governance metadata: `provenance`, `license`, `expected_outputs`,
`scoring_rationale`, `domain`, and boolean `flags` for ambiguity / contradiction /
metadata-only / source-substitution / unavailable-source / temporal-cutoff.

## Metrics

Each task reports core scientific credibility metrics:

- **source_recall** — expected sources found
- **source_precision** — retrieved sources that match expectations
- **citation_integrity** — claims cite valid evidence IDs
- **evidence_id_validity** — evidence IDs present and claim references resolve
- **review_boundary_accuracy** — expected review flags present
- **contradiction_detection** — adversarial contradiction tasks
- **bundle_reproducibility** — stable export bundle artifact hashes across repeated exports

Additional metrics: type coverage, validation pass, claim atomicity, gold labels, hash reproducibility.

Overall score is the mean of core and auxiliary metrics. Tasks pass when overall ≥ 0.7 and validation passes (unless the task expects failure).

## Quality checks

`make acceptance` and CI run the holdout benchmark after unit tests. All evaluation tasks must pass.

Acceptance is offline-first: `pytest` defaults to `-m 'not live'`, and live connectors are never exercised unless `VSA_ALLOW_NETWORK` is set. Each acceptance run writes `reports/acceptance_baseline.json` with timestamp, git SHA, Python version, extras, command exit codes, and `skipped_live_connectors` (see `src/vsa/acceptance/skip_registry.py`).

## Limitations

- Live benchmark mode is network-dependent and experimental
- Gold labels are heuristic, not curator-verified clinical truth
- Holdout fixtures must not be copied into extractor unit tests; use `dev/` instead
