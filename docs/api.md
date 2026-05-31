# REST API

Requires: `pip install verified-science-agent[api]`

## Start server

```bash
vsa serve --host 127.0.0.1 --port 8000
```

OpenAPI docs: http://127.0.0.1:8000/docs

## Environment

| Variable | Purpose |
|----------|---------|
| `VSA_API_KEY` | Require `X-API-Key` or `Authorization: Bearer` on non-public routes |
| `VSA_API_DETERMINISTIC=1` | Force `claim_mode=rule` and `audit_mode=rule` on build/audit/export |
| `VSA_API_RATE_LIMIT=120` | Enable in-memory rate limiting (requests per 60s per client IP) |
| `VSA_OTEL_ENABLED=1` | OpenTelemetry spans (requires `[otel]` extra) |

Public routes (no API key): `/health`, `/v1/version`, `/docs`, `/openapi.json`, `/redoc`.

## Authentication

When `VSA_API_KEY` is set:

```bash
curl -H "X-API-Key: your-secret" http://127.0.0.1:8000/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"report": {...}}'
```

Missing or invalid keys return HTTP 401 with code `UNAUTHORIZED`.

## Error format

```json
{
  "error": {
    "code": "MISSING_INPUT",
    "message": "question or input required"
  }
}
```

Codes: `MISSING_INPUT`, `VALIDATION_ERROR`, `RATE_LIMITED`, `UNAUTHORIZED`, `HTTP_ERROR`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + version |
| GET | `/v1/version` | Package version |
| POST | `/v1/retrieve` | Retrieve evidence for a question |
| POST | `/v1/build` | Build ScientificReport (JSON body) |
| POST | `/v1/validate` | Validate report JSON |
| POST | `/v1/audit` | Rule or hybrid audit |
| POST | `/v1/hash` | Provenance hash chain |
| POST | `/v1/render` | Render markdown/html/json/pdf |
| POST | `/v1/attest` | SLSA/in-toto statement (`subject_name: report.json`) |
| POST | `/v1/export` | Export artifact bundle (temp dir paths returned) |
| POST | `/v1/review/start` | Begin human review session |
| POST | `/v1/review/approve-claim` | Approve claim IDs |
| POST | `/v1/review/verify` | Verify review chain hashes |

Report endpoints accept flexible JSON bodies (`{"report": {...}}` or the report object directly) so nested evidence structures are not rejected by strict schema validation at the HTTP layer.

## Example: build

```bash
curl -s http://127.0.0.1:8000/v1/build \
  -H "Content-Type: application/json" \
  -d '{"question":"BRCA1 c.68_69del","claim_mode":"rule","deterministic":true}'
```

## CLI parity

Review workflow:

```bash
vsa review start reports/brca1_report.json --reviewer reviewer@example.com
vsa review approve-claim reports/brca1_report.json --reviewer reviewer@example.com --claim C001 --out reviewed.json
vsa verify-review reviewed.json
vsa validate reviewed.json
```

Attestation and bundle verification:

```bash
vsa attest reports/brca1_report.json --out reports/attestation.json --subject-name report.json
vsa verify-attestation reports/brca1_report.json reports/attestation.json --subject-name report.json
vsa verify-bundle reports/bundle
```

Legacy review flags:

```bash
vsa review reports/brca1_report.json --reviewer reviewer@example.com --approve C001 --out reviewed.json
```
