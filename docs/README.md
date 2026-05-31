# Documentation

Verified Science Agent **v0.7.1** — evidence-backed scientific AI report infrastructure.

## Start here

| Document | Contents |
|----------|----------|
| [../README.md](../README.md) | Quick start, CLI reference, install extras |
| [../RELEASE_STATUS.md](../RELEASE_STATUS.md) | Production vs experimental features, CI verification |
| [architecture.md](architecture.md) | Pipeline, components, hash layers |
| [schema.md](schema.md) | ScientificReport v1.2.0 field reference |
| [connectors.md](connectors.md) | Database connectors, ambiguity, content levels |
| [benchmark.md](benchmark.md) | 27-task offline suite, metrics, regression gate |
| [api.md](api.md) | REST API, auth, endpoints, CLI parity |
| [release_checklist.md](release_checklist.md) | Pre-tag acceptance bar and release steps |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |

## Acceptance bar

The canonical quality gate (CI parity):

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make acceptance
```

Equivalent to `bash scripts/acceptance.sh` (demo → pytest → benchmark).

## Package versions

| Constant | Value |
|----------|-------|
| Package | `0.7.1` |
| Schema | `1.2.0` (also accepts `1.0.0`, `1.1.0`) |
| Validation | `1.2.0` |

## Safety

Research infrastructure only. Not a medical device or clinical decision system. See README safety notice.
