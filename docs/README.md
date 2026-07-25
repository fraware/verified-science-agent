# Documentation

User guide for **Verified Science Agent** (VSA) v0.7.2.

## Guides

| Document | Description |
|----------|-------------|
| [../README.md](../README.md) | Install, quick start, CLI overview |
| [decision-time-quickstart.md](decision-time-quickstart.md) | Cutoff freeze, verify, AKTA export |
| [operator-decision-time.md](operator-decision-time.md) | Decision-time operator commands and reconstruction |
| [architecture.md](architecture.md) | Pipeline, components, provenance, companions |
| [schema.md](schema.md) | ScientificReport and companion schema reference |
| [connectors.md](connectors.md) | Data sources and evidence policies |
| [benchmark.md](benchmark.md) | Evaluation suite and metrics |
| [api.md](api.md) | REST API reference |
| [adr/0001-vsa-akta-scientific-memory-boundaries.md](adr/0001-vsa-akta-scientific-memory-boundaries.md) | VSA / AKTA / Scientific Memory boundaries |
| [threat-model.md](threat-model.md) | Decision-time threat model |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../SECURITY.md](../SECURITY.md) | Security disclosure policy |

## Quick commands

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make demo          # build and verify a sample report
pytest             # offline tests (-m 'not live')
vsa benchmark      # run evaluation suite
```

Decision-time smoke:

```bash
vsa snapshot-evidence examples/decision_time/source_report.json \
  --cutoff 2024-01-01T00:00:00Z \
  --out reports/decision_time_bundle.json
vsa verify-decision-time-bundle reports/decision_time_bundle.json
vsa export-akta-context --bundle reports/decision_time_bundle.json --out reports/akta_context.json
```

## Versions

| Component | Version |
|-----------|---------|
| Package | 0.7.2 |
| ScientificReport schema | 1.2.0 |
| Companion schemas | 1.0.0 (`integration_envelope`, `decision_time_evidence_bundle`, `akta_action_context`, `scientific_outcome_link`) |

## Claim boundaries

VSA does not authorize actions, execute tools, issue grants, or certify scientific correctness. See [ADR 0001](adr/0001-vsa-akta-scientific-memory-boundaries.md).

## Safety

Research infrastructure only — not a medical device or clinical decision system. See the [README safety notice](../README.md#safety-notice).
