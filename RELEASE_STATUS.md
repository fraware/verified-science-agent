# Release status

Last verified: pending CI on `main` (v0.7.0 review + API hardening).

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
| **0.7.0** | pending tag after green CI | Review subcommands, API schemas, rate-limit hooks |
| 0.6.1 | — | verify-bundle, export manifest v1.1, benchmark gate |
| 0.6.0 | — | Paper content levels, compare-audit, E2E tests |

## Production-ready (CI-evidence-backed)

Claims below require green CI on the verified commit above.

- JSON Schema validation, provenance hashes, rule-based claims
- Offline benchmark (27 tasks) with regression gate
- Export bundle + `vsa verify-bundle`
- Human review workflow (`review start`, `approve-claim`, `verify`)
- Hybrid audit with `--audit-mode rule`
- SLSA/in-toto attestation
- REST API with typed schemas and `/v1/review/*`

## Experimental

- LLM claim extraction and LLM audit modes
- Live connector retrieval and weekly live test workflow
- OpenTelemetry (`VSA_OTEL_ENABLED=1`, `[otel]` extra)
- In-memory API rate limiting (not distributed)

## Stubbed / not yet implemented

- Full-text paper body parsing
- Curator-verified clinical gold standards
- External SLSA registry integration
- Distributed rate limiting / auth for API

## Verify locally (acceptance bar)

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
pip install -e ".[dev,ui,pdf,signing,api]"
make demo && make test && vsa benchmark
vsa review start reports/brca1_report.json --reviewer you@example.com
vsa review approve-claim reports/brca1_report.json --reviewer you@example.com --claim C002
vsa review verify reports/brca1_report.json
```

## Known limitations

See README **Known limitations**. Rule-based claims are infrastructure-grade; benchmark gold labels are heuristic.
