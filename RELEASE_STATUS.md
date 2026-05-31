# Release status

Last verified: pending CI on `main` after verification-hardening push.

## Verified commit

| Field | Value |
|-------|--------|
| Commit | `pending` — update after green CI run |
| CI workflow | [ci.yml](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml) |
| Ubuntu matrix | Python 3.10, 3.11, 3.12 — full pipeline + artifact upload |
| macOS smoke | Python 3.12 — `make test`, `vsa benchmark` |
| Acceptance job | Clean-clone `make demo && make test && vsa benchmark` |

CI uploads: `report.json`, `report.md`, `audit.json`, `attestation.json`, `benchmark_summary.json`, full `bundle/` (includes `manifest.json`, `sources/`).

## Package version

| Version | Tag | Status |
|---------|-----|--------|
| **0.6.1** | pending tag after green CI | verify-bundle, export manifest v1.1, benchmark gate |
| 0.5.0 | — | REST API, SLSA attestation, OTEL hooks, live connector CI |
| 0.4.0 | — | Schema 1.2.0, ClinVar hardening, 25-task benchmark, audit artifacts |

## Production-ready (CI-evidence-backed)

Claims below require green CI on the verified commit above.

- JSON Schema validation, provenance hashes, rule-based claims
- Offline benchmark (27 tasks) with regression gate
- Export bundle + `vsa verify-bundle`
- Hybrid audit with `--audit-mode rule`
- SLSA/in-toto attestation (`vsa attest`, `vsa verify-attestation`)
- Schema migration (`vsa migrate-schema`)
- REST API (`vsa serve`, `[api]` extra)

## Experimental

- LLM claim extraction and LLM audit modes
- Live connector retrieval and weekly live test workflow
- OpenTelemetry (`VSA_OTEL_ENABLED=1`, `[otel]` extra)

## Stubbed / not yet implemented

- Full-text paper body parsing (abstract/metadata levels only)
- Curator-verified clinical gold standards
- Automated clinical variant classification
- Review CLI subcommands (`review start`, `approve-claim`) — flat `vsa review` flags work today

## Verify locally (acceptance bar)

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
pip install -e ".[dev,ui,pdf,signing,api]"
make demo && make test && vsa benchmark
```

## Known limitations

See README **Known limitations**. ClinVar ambiguity flags, rule-based claims, heuristic benchmark gold labels.
