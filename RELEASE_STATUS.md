# Release status

Package **v0.7.2** — tagged and on `main`.

[![CI](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/fraware/verified-science-agent/actions/workflows/ci.yml)

## Verified release

| Field | Value |
|-------|--------|
| Version | **v0.7.2** |
| Commit | `903d834` |
| Tag | `v0.7.2` (pushed) |
| Focus | Scientific credibility hardening + 50-task benchmark with category minimums |

## Verification

| Item | Detail |
|------|--------|
| Acceptance bar | `make acceptance` (= `scripts/acceptance.sh`) |
| Ubuntu CI | Python 3.10, 3.11, 3.12 — build, validate, audit, export, verify-bundle, review smoke, API smoke, sign, pytest, benchmark |
| macOS smoke | Python 3.12 — `make test`, benchmark |
| Benchmark gate | 50 tasks, 100% pass rate, zero `category_gaps` |
| Artifacts | `report.json`, `report.md`, `audit.json`, `attestation.json`, `benchmark_summary.json`, `bundle/` |

Verify locally:

```bash
git clone https://github.com/fraware/verified-science-agent.git
cd verified-science-agent
make acceptance
```

## Production-ready (CI-evidence-backed)

- JSON Schema validation, provenance hashes, rule-based claims
- Scientific credibility policies: ClinVar ambiguity, metadata-only warnings, AlphaFold labeling, ambiguity reliability caps
- Offline benchmark (50 tasks) with category minimums and core metrics
- Export bundle + `vsa verify-bundle`
- Human review workflow + `vsa verify-review`
- SLSA/in-toto attestation
- REST API with optional `VSA_API_KEY` auth
- Credibility warnings in CLI render, markdown, HTML, and Streamlit UI

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
