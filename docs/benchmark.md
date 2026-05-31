# Benchmark suite

The offline benchmark measures whether the build pipeline produces valid, evidence-backed reports across representative scientific tasks.

## Run

```bash
vsa benchmark
vsa benchmark --out reports/benchmark_summary.json
pytest  # unit tests (benchmark runner covered indirectly)
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

Each task reports:

- **evidence_recall** — expected sources found
- **evidence_precision** — retrieved sources that match expectations
- **citation_integrity** — claims cite valid evidence IDs
- **claim_atomicity** — claims have type, text, evidence, boundary
- **review_boundary_correctness** — expected review flags present
- **contradiction_detection** — adversarial contradiction tasks
- **hash_reproducibility** — stable hashes when `check_hash_stable` is set
- **audit_stability** — rule audit consistent across runs (optional)
- **gold_label_score** — optional `gold_labels` in task definition

Overall score is the mean of applicable metrics. Tasks pass when overall ≥ 0.7 and validation passes (unless `expect_pass: false`).

## CI regression gate

CI runs `vsa benchmark --out reports/benchmark_summary.json`. The command exits non-zero if:

- any task fails, or
- pass rate drops below 100% (`regression: true` in summary JSON)

## What can fail

- Missing offline fixture for a task
- Validation failure on reports that should pass
- Unexpected claim types or missing review boundaries
- Benchmark regression after connector or claim template changes

## Experimental

- Live benchmark mode (network variability)
- Gold labels are heuristic, not curator-verified clinical truth
