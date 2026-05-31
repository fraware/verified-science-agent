# Release status

Package **v0.7.1** on `main`. CI is the source of truth for verification.

[![CI](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml)

## Verification

| Item | Detail |
|------|--------|
| Acceptance bar | `make acceptance` (= `scripts/acceptance.sh`) |
| Ubuntu CI | Python 3.10, 3.11, 3.12 — build, validate, audit, export, verify-bundle, review smoke, API smoke, sign, pytest, benchmark |
| macOS smoke | Python 3.12 — `make test`, benchmark |
| Acceptance job | Full acceptance script after matrix jobs pass |
| Artifacts | `report.json`, `report.md`, `audit.json`, `attestation.json`, `benchmark_summary.json`, `bundle/` |

Verify locally:

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
make acceptance
```

## Tagging a release

After green CI on the commit you intend to ship:

```bash
git tag v0.7.1
git push origin v0.7.1
```

The [release workflow](.github/workflows/release.yml) runs the acceptance bar, builds a bundle zip, and attaches artifacts to the GitHub Release.

## Production-ready (CI-evidence-backed)

- JSON Schema validation, provenance hashes, rule-based claims
- Offline benchmark (27 tasks) with 100% regression gate
- Export bundle + `vsa verify-bundle`
- Human review workflow + `vsa verify-review`
- SLSA/in-toto attestation
- REST API with optional `VSA_API_KEY` auth

## Experimental

- LLM claim extraction and LLM audit modes
- Live connector retrieval (`pytest -m live`)
- OpenTelemetry (`VSA_OTEL_ENABLED=1`, `[otel]` extra)
- In-memory API rate limiting (`VSA_API_RATE_LIMIT`)

## Not yet implemented

- Full-text paper body parsing
- Curator-verified clinical gold standards
- External SLSA registry integration
- Distributed rate limiting

## Known limitations

Rule-based claims are infrastructure-grade; benchmark gold labels are heuristic. See [README.md](README.md).
