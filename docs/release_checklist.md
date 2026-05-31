# Release checklist

Use this before tagging a release or updating README claims.

## Pre-release commands

```bash
pip install -e ".[dev,ui,pdf,signing]"
make demo
make test
vsa benchmark
```

All must pass on Ubuntu (CI canonical). Windows/macOS dev smoke recommended.

## Version bumps

- [ ] `src/vsa/version.py` — `__version__`, `SCHEMA_VERSION`, `VALIDATION_VERSION`
- [ ] `pyproject.toml` — `version`
- [ ] `CHANGELOG.md` — dated section
- [ ] `RELEASE_STATUS.md` — last verified date and feature matrix
- [ ] Rebuild pinned reports under `reports/` if schema or hash core changed

## README accuracy

- [ ] Badges reflect CI status
- [ ] Workflow examples match tested commands
- [ ] Known limitations section present
- [ ] No claims of clinical diagnostic use

## Schema

- [ ] `src/vsa/schemas/scientific_report.schema.json` synced to `schemas/`
- [ ] `docs/schema.md` updated for new fields
- [ ] Migration notes in CHANGELOG

## Connectors

- [ ] Mocked tests for changed connectors
- [ ] Ambiguous retrieval documented in `docs/connectors.md`
- [ ] Offline fixtures for benchmark tasks

## Benchmark

- [ ] 25 offline tasks pass
- [ ] Adversarial tasks (`expect_pass: false`) behave correctly
- [ ] CI runs `vsa benchmark`

## Artifacts

- [ ] `vsa audit report.json --out reports/audit.json` produces stable JSON
- [ ] `vsa export report.json --out-dir reports/bundle/` writes full bundle

## Safety

- [ ] Variant reports include clinical disclaimer in render output
- [ ] `.env` not committed

## Git tag

```bash
git tag v0.4.0
git push origin v0.4.0
```

Release workflow (`.github/workflows/release.yml`) runs on tag push.

## Version history

| Release | Focus |
|---------|-------|
| v0.1 | Schema, validate, render, hash, examples |
| v0.2 | Connectors, retrieve, build, benchmarks, UI |
| v0.3 | LLM extraction, audit, signing, human review |
| v0.4 | Connector hardening, schema 1.2.0, 25-task benchmark, docs, audit artifacts |
