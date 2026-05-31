# Release status

Last verified: pending CI on `main` (v0.7.1 production hardening).

## Verified commit

| Field | Value |
|-------|--------|
| Commit | `pending` — update after green CI run on `main` |
| CI workflow | [ci.yml](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml) |
| CI badge | [![CI](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml) |
| Ubuntu matrix | Python 3.10, 3.11, 3.12 — full pipeline + artifact upload |
| macOS smoke | Python 3.12 — `make test`, `vsa benchmark` |
| Acceptance | `bash scripts/acceptance.sh` (same as `make acceptance`) |

CI uploads: `report.json`, `report.md`, `audit.json`, `attestation.json`, `benchmark_summary.json`, full `bundle/`.

After green CI, update the commit field above and tag:

```bash
git tag v0.7.1
git push origin v0.7.1
```

## Package version

| Version | Tag | Status |
|---------|-----|--------|
| **0.7.1** | pending | API auth, full connector test matrix, release bundle zip |
| 0.7.0 | — | Review subcommands, API schemas, rate-limit hooks |
| 0.6.1 | — | verify-bundle, export manifest v1.1, benchmark gate |

## Production-ready (CI-evidence-backed)

- JSON Schema validation, provenance hashes, rule-based claims
- Offline benchmark (27 tasks) with regression gate
- Export bundle + `vsa verify-bundle`
- Human review workflow + `vsa verify-review`
- SLSA/in-toto attestation
- REST API with optional `VSA_API_KEY` auth

## Experimental

- LLM claim extraction and LLM audit modes
- Live connector retrieval (`pytest -m live`)
- OpenTelemetry (`VSA_OTEL_ENABLED=1`)
- In-memory API rate limiting

## Stubbed / not yet implemented

- Full-text paper body parsing
- Curator-verified clinical gold standards
- External SLSA registry integration

## Verify locally

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
make acceptance
```

## Known limitations

Rule-based claims are infrastructure-grade; benchmark gold labels are heuristic. See README.
