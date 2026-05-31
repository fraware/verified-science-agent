# Release checklist

Use this before tagging a release or updating README production-ready claims.

## Pre-release commands (acceptance bar)

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make demo && make test && vsa benchmark
```

All must pass on Ubuntu CI (canonical). macOS smoke runs in CI.

## Version bumps

- [ ] `src/vsa/version.py` — `__version__`, `SCHEMA_VERSION`, `VALIDATION_VERSION`
- [ ] `pyproject.toml` — `version`
- [ ] `CHANGELOG.md` — dated section
- [ ] `RELEASE_STATUS.md` — verified commit hash + date
- [ ] Rebuild pinned reports under `reports/` if schema or hash core changed

## README accuracy

- [ ] CI badge reflects passing workflow on verified commit
- [ ] Workflow examples match tested commands
- [ ] Known limitations section present
- [ ] No claims of clinical diagnostic use

## Schema

- [ ] `src/vsa/schemas/scientific_report.schema.json` synced to `schemas/`
- [ ] `docs/schema.md` updated for new fields
- [ ] Migration notes in CHANGELOG

## Connectors

- [ ] Mocked tests for changed connectors under `tests/connectors/`
- [ ] Ambiguous retrieval documented in `docs/connectors.md`
- [ ] Offline fixtures for benchmark tasks

## Benchmark

- [ ] 27 offline tasks pass (`vsa benchmark`)
- [ ] Adversarial tasks (`expect_pass: false`) behave correctly
- [ ] CI fails on benchmark regression

## Artifacts

- [ ] `vsa export report.json --out-dir reports/bundle/` writes full bundle
- [ ] `vsa verify-bundle reports/bundle` passes
- [ ] `vsa audit report.json --audit-mode rule --out reports/audit.json`

## Review workflow

- [ ] `vsa review start` / `approve-claim` / `verify` smoke tested
- [ ] Review chain hashes verify after `vsa validate`

## Safety

- [ ] Variant reports include clinical disclaimer in render output
- [ ] `.env` not committed

## Git tag (only after green CI)

```bash
git tag v0.7.0
git push origin v0.7.0
```

Update `RELEASE_STATUS.md` verified commit to match tag SHA.

## Version history

| Release | Focus |
|---------|-------|
| v0.7 | Review subcommands, API schemas, rate limits, verify-bundle |
| v0.6 | verify-bundle, export manifest, benchmark gate, connector hardening |
| v0.5 | REST API, SLSA attestation, OTEL, live connector CI |
| v0.4 | Schema 1.2.0, ClinVar hardening, 25+ task benchmark, docs |
| v0.3 | LLM audit, signing, human review |
| v0.2 | Connectors, build pipeline, UI |
| v0.1 | Schema, validate, render, hash |
