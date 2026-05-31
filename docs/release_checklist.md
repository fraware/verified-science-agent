# Release checklist

Use before tagging a release or claiming a feature is production-ready.

## Acceptance bar

```bash
pip install -e ".[dev,ui,pdf,signing,api]"
make acceptance
```

This runs `scripts/acceptance.sh`: demo build, pytest, and benchmark. Must pass on Ubuntu CI (canonical). macOS smoke runs separately in CI.

## Version bumps

- [ ] `src/vsa/version.py` — `__version__`, `SCHEMA_VERSION`, `VALIDATION_VERSION`
- [ ] `pyproject.toml` — `version`
- [ ] `CHANGELOG.md` — dated section
- [ ] `README.md` — version badge and workflow examples
- [ ] `docs/README.md` — package version table
- [ ] Rebuild pinned reports under `reports/` if schema or hash core changed

## Schema

- [ ] `src/vsa/schemas/scientific_report.schema.json` synced to `schemas/`
- [ ] `docs/schema.md` updated for new fields
- [ ] Migration notes in `CHANGELOG.md`

## Connectors

- [ ] Mocked tests for changed connectors under `tests/connectors/`
- [ ] Ambiguity and content levels documented in `docs/connectors.md`
- [ ] Offline fixtures for new benchmark tasks

## Benchmark

- [ ] 50 offline tasks pass (`vsa benchmark`)
- [ ] Adversarial tasks (`expect_pass: false`) behave correctly
- [ ] CI fails on benchmark regression (pass rate below 100%)

## Artifacts

- [ ] `vsa export report.json --out-dir reports/bundle/` writes full bundle
- [ ] `vsa verify-bundle reports/bundle` passes
- [ ] `vsa audit report.json --audit-mode rule --out reports/audit.json`

## Review workflow

- [ ] `vsa review start` / `approve-claim` / `verify` smoke tested
- [ ] `vsa verify-review report.json` passes after review events
- [ ] Review chain hashes verify after `vsa validate`

## API

- [ ] `pytest tests/test_api.py tests/test_api_auth.py` pass
- [ ] `docs/api.md` matches endpoints and env vars

## Safety

- [ ] Variant reports include clinical disclaimer in render output
- [ ] `.env` not committed

## Git tag (only after green CI)

```bash
git tag v0.7.1
git push origin v0.7.1
```

Release workflow attaches: report, audit, attestation, benchmark summary, bundle zip, schema.
