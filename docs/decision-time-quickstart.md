# Decision-time and AKTA export — quick start

Freeze evidence at a cutoff, verify the bundle, and export AKTA context. Companion schemas are additive; ScientificReport **1.3.0** is unchanged.

**Non-claims:** VSA does not authorize actions, execute tools, issue grants, or certify scientific correctness.

Full operator detail: [operator-decision-time.md](operator-decision-time.md). Boundaries: [ADR 0001](adr/0001-vsa-akta-scientific-memory-boundaries.md).

## Prerequisites

```bash
pip install -e ".[dev,signing]"
```

Signing is optional; omit `--sign` if you do not need Ed25519 signatures.

## 1. Snapshot evidence at a cutoff

```bash
vsa snapshot-evidence examples/decision_time/source_report.json \
  --cutoff 2024-01-01T00:00:00Z \
  --mode retrospective \
  --out reports/decision_time_bundle.json
```

Modes: `retrospective` (default), `shadow`, `read_only`. See the operator guide for semantics.

Optional signature over `integrity.bundle_hash`:

```bash
vsa sign --generate-key
vsa snapshot-evidence examples/decision_time/source_report.json \
  --cutoff 2024-01-01T00:00:00Z \
  --sign \
  --out reports/decision_time_bundle.json
```

## 2. Verify

```bash
vsa verify-decision-time-bundle reports/decision_time_bundle.json
```

If signed and you pin a trust root out-of-band:

```bash
vsa verify-decision-time-bundle reports/decision_time_bundle.json \
  --trusted-key "$TRUSTED_PK_B64"
```

## 3. Export AKTA context (`authorization=none`)

```bash
vsa export-akta-context \
  --bundle reports/decision_time_bundle.json \
  --out reports/akta_context.json
```

Optionally attach the source report as well:

```bash
vsa export-akta-context \
  --report examples/decision_time/source_report.json \
  --bundle reports/decision_time_bundle.json \
  --out reports/akta_context.json
```

`authorization` is always `none`. Exports that imply grants, execution, or correctness certification are rejected.

## 4. Append an outcome link (does not mutate the bundle)

```bash
vsa link-outcome reports/decision_time_bundle.json \
  --outcome-ref outcome://example/case/1 \
  --kind calibration \
  --out reports/outcome_link.json
```

## Schemas

Public mirrors (byte-identical to the packaged copies):

| Artifact | Schema |
|----------|--------|
| DecisionTimeEvidenceBundle | `schemas/decision_time_evidence_bundle.schema.json` |
| AktaActionContext | `schemas/akta_action_context.schema.json` |
| IntegrationEnvelope | `schemas/integration_envelope.schema.json` |
| ScientificOutcomeLink | `schemas/scientific_outcome_link.schema.json` |

Package path: `src/vsa/schemas/`. Both trees must stay in sync.

## Upstream pins (out-of-band)

Not distributed as a global registry in this repository:

1. Official PCS schema ID / digest registry pins (local PCS-shaped refs and fixture digests only).
2. AKTA upstream acknowledgment of the `AktaActionContext` contract.
3. Organizational Ed25519 trust roots (use `--trusted-key` / `--trusted-key-file`).
