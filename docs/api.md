# REST API

Requires: `pip install verified-science-agent[api]`

## Start server

```bash
vsa serve --host 127.0.0.1 --port 8000
```

OpenAPI docs: http://127.0.0.1:8000/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + version |
| GET | `/v1/version` | Package version |
| POST | `/v1/retrieve` | `{"question": "...", "cache_dir": ".vsa_cache"}` |
| POST | `/v1/build` | `{"input": {...}}` or `{"question": "..."}` |
| POST | `/v1/validate` | `{"report": {...}}` |
| POST | `/v1/audit` | `{"report": {...}, "audit_mode": "rule"}` |
| POST | `/v1/hash` | `{"report": {...}}` |
| POST | `/v1/render?format=markdown` | `{"report": {...}}` |
| POST | `/v1/attest` | SLSA/in-toto statement for report |
| POST | `/v1/export?audit_mode=rule` | Export artifact bundle (temp dir) |

## OpenTelemetry

```bash
pip install verified-science-agent[otel]
VSA_OTEL_ENABLED=1 vsa serve
```

Spans are emitted for build, retrieve, and API handlers when enabled.

## Attestation CLI

```bash
vsa attest reports/brca1_report.json --out reports/attestation.json
vsa verify-attestation reports/brca1_report.json reports/attestation.json
```

Produces an [in-toto Statement](https://github.com/in-toto/attestation) with SLSA Provenance v1 predicate referencing `provenance.report_hash`.
