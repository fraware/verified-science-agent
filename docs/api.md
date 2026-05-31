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
| `VSA_API_DETERMINISTIC=1` | Force `claim_mode=rule` and `audit_mode=rule` on build/audit/export |
| `VSA_API_RATE_LIMIT=120` | Enable in-memory rate limiting (requests per 60s per client IP) |
| `VSA_OTEL_ENABLED=1` | OpenTelemetry spans (requires `[otel]` extra) |

## Error format

```json
{
  "error": {
    "code": "MISSING_INPUT",
    "message": "question or input required"
  }
}
```

Common codes: `MISSING_INPUT`, `VALIDATION_ERROR`, `RATE_LIMITED`, `HTTP_ERROR`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness + version |
| GET | `/v1/version` | Package version |
| POST | `/v1/retrieve` | Retrieve evidence for a question |
| POST | `/v1/build` | Build ScientificReport (typed `BuildRequest`) |
| POST | `/v1/validate` | Validate report JSON |
| POST | `/v1/audit` | Rule or hybrid audit |
| POST | `/v1/hash` | Provenance hash chain |
| POST | `/v1/render` | Render markdown/html/json/pdf |
| POST | `/v1/attest` | SLSA/in-toto statement (`subject_name: report.json`) |
| POST | `/v1/export` | Export artifact bundle (temp dir paths returned) |
| POST | `/v1/review/start` | Begin human review session |
| POST | `/v1/review/approve-claim` | Approve claim IDs |
| POST | `/v1/review/verify` | Verify review chain hashes |

## Example: build + export

```bash
curl -s http://127.0.0.1:8000/v1/build \
  -H "Content-Type: application/json" \
  -d '{"question":"BRCA1 c.68_69del","claim_mode":"rule","deterministic":true}'
```

## CLI parity

Review workflow CLI:

```bash
vsa review start reports/brca1_report.json --reviewer reviewer@example.com
vsa review approve-claim reports/brca1_report.json --reviewer reviewer@example.com --claim C001 --out reviewed.json
vsa review verify reviewed.json
vsa validate reviewed.json
vsa hash reviewed.json
```

Legacy flat flags remain supported:

```bash
vsa review reports/brca1_report.json --reviewer reviewer@example.com --approve C001 --out reviewed.json
```

## Attestation CLI

```bash
vsa attest reports/brca1_report.json --out reports/attestation.json --subject-name report.json
vsa verify-attestation reports/brca1_report.json reports/attestation.json --subject-name report.json
vsa verify-bundle reports/bundle
```
