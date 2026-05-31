# Benchmark suite

50 offline tasks measure whether the build pipeline produces valid, evidence-backed reports across representative scientific domains.

## Category minimums

| Category | Minimum | Purpose |
|----------|---------|---------|
| adversarial | 10 | Invalid claims, dangling evidence, missing paths, premature approval |
| ambiguity | 5 | ClinVar close scores, UniProt isoform ambiguity |
| contradiction | 5 | Pathogenic vs VUS, AlphaFold vs experimental language |
| metadata_only_paper | 5 | Bibliographic-only publication evidence |
| no_evidence | 5 | Empty retrieval must fail validation |

CI fails if any category falls below its minimum or pass rate drops below 100%.

## Run

```bash
vsa benchmark
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

Tasks are defined in `benchmarks/tasks.json`. Offline fixtures live in `benchmarks/fixtures/`.

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

Overall score is the mean of core and auxiliary metrics. Tasks pass when overall ≥ 0.7 and validation passes (unless `expect_pass: false`).

Task-specific gates also enforce:

- `expect_ambiguity_surfaced` — AMBIGUITY warnings in limitations or retrieval_warnings
- `expect_metadata_warning` — metadata-only publication warning surfaced
- `expect_predicted_structure_label` — AlphaFold summaries declare predicted structure

## CI regression gate

CI and `make acceptance` run `vsa benchmark --out reports/benchmark_summary.json`. The command exits non-zero if:

- any task fails, or
- pass rate drops below 100% (`regression: true` in summary JSON)

## Limitations

- Live benchmark mode is network-dependent and experimental
- Gold labels are heuristic, not curator-verified clinical truth
