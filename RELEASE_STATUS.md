# Release status

Last verified: CI on `main` (Ubuntu Python 3.10–3.12, macOS smoke). Local: `make demo`, `make test`, `vsa benchmark`.

## Package version

| Version | Tag | Status |
|---------|-----|--------|
| **0.6.0** | current dev | Paper content levels, export manifest, compare-audit, E2E tests |
| 0.5.0 | — | REST API, SLSA attestation, OTEL hooks, live connector CI |
| 0.4.0 | — | Schema 1.2.0, ClinVar hardening, 25-task benchmark, audit artifacts |
| 0.3.x | — | LLM audit, signing, human review |
| 0.2.x | — | Connectors, build pipeline, UI |
| 0.1.x | — | Schema, validate, render, hash |

## Production-ready

- JSON Schema validation, provenance hashes, rule-based claims
- Offline benchmark (25 tasks), renderers, human review, Ed25519 signing
- Hybrid audit with `--audit-mode rule`
- Audit/export artifact bundles with manifest and attestation
- `vsa compare-audit` for audit regression detection
- SLSA/in-toto attestation (`vsa attest`, `vsa verify-attestation`)
- Schema migration (`vsa migrate-schema`)
- REST API (`vsa serve`, `[api]` extra) — health, build, validate, audit, attest

## Experimental

- LLM claim extraction and LLM audit modes
- Live connector retrieval and weekly live test workflow
- OpenTelemetry (`VSA_OTEL_ENABLED=1`, `[otel]` extra)

## Stubbed / not yet implemented

- Full-text paper body parsing (abstract/metadata levels only)
- Curator-verified clinical gold standards
- Automated clinical variant classification

## Known limitations

See README **Known limitations**. ClinVar ambiguity flags, rule-based claims, heuristic benchmark gold labels.

## Verify locally

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make demo
make test
vsa benchmark
vsa attest reports/brca1_report.json --out reports/attestation.json
```

Optional: `pytest -m live` (network), `VSA_OTEL_ENABLED=1 vsa build ...`
