# Documentation

User guide for **Verified Science Agent** (VSA) v0.7.2.

## Guides

| Document | Description |
|----------|-------------|
| [../README.md](../README.md) | Install, quick start, CLI overview |
| [architecture.md](architecture.md) | Pipeline, components, provenance |
| [schema.md](schema.md) | ScientificReport field reference |
| [connectors.md](connectors.md) | Data sources and evidence policies |
| [benchmark.md](benchmark.md) | Evaluation suite and metrics |
| [api.md](api.md) | REST API reference |
| [adr/0001-vsa-akta-scientific-memory-boundaries.md](adr/0001-vsa-akta-scientific-memory-boundaries.md) | VSA / AKTA / Scientific Memory boundaries |
| [threat-model.md](threat-model.md) | Decision-time threat model |
| [operator-decision-time.md](operator-decision-time.md) | Decision-time operator commands |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../SECURITY.md](../SECURITY.md) | Security disclosure policy |

## Quick commands

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make demo          # build and verify a sample report
pytest             # run tests
vsa benchmark      # run evaluation suite
```

## Versions

| Component | Version |
|-----------|---------|
| Package | 0.7.2 |
| Schema | 1.2.0 |

## Safety

Research infrastructure only — not a medical device or clinical decision system. See the [README safety notice](../README.md#safety-notice).
