# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Schema versioning

- **ScientificReport schema 1.2.0** — lifecycle fields, `evidence_content_hash`, `validation_run_hash`
- **ScientificReport schema 1.1.0** — Ed25519 signature, review chain hash, audit metadata
- **ScientificReport schema 1.0.0** — initial canonical artifact model

## [0.7.2] - 2026-05-31

### Added

- Scientific credibility module (`src/vsa/scientific/credibility.py`) with ambiguity caps and report warnings
- Validation checks: ambiguous reliability cap, AlphaFold predicted labeling, ClinVar ambiguity visibility
- Benchmark expanded to 50 tasks with category minimums (10 adversarial, 5 each for ambiguity/contradiction/metadata-only/no-evidence)
- Core benchmark metrics: source recall/precision, citation integrity, evidence-ID validity, review-boundary accuracy, contradiction detection, bundle reproducibility
- Tests for credibility policies and Materials Project missing-key degradation

### Changed

- ClinVar ambiguous queries always return `reliability: low`
- UniProt gene search sets `retrieval_ambiguity` and caps reliability to low
- Materials Project skipped cleanly with explicit warning when API key missing
- Scientific credibility warnings in markdown and HTML render output
- Retrieval pipeline applies credibility hardening before evidence is returned
- Acceptance bar and CI assert benchmark category minimums (50 tasks)
- Streamlit UI surfaces scientific credibility warnings and evidence reliability/ambiguity flags
- `vsa benchmark` prints category coverage summary on success

## [0.7.1] - 2026-05-31

### Added

- Optional API key auth (`VSA_API_KEY`, `X-API-Key` header)
- `vsa verify-review` top-level command
- `scripts/acceptance.sh` and `make acceptance` (CI parity)
- Mocked connector tests: Semantic Scholar, Europe PMC
- Release workflow attaches full artifact bundle zip

### Changed

- Semantic Scholar connector sets `content_level` metadata
- Build pipeline adds metadata-only CONTENT WARNING to limitations
- Acceptance CI job uses shared acceptance script
- Documentation consolidated and updated across README, docs/, and RELEASE_STATUS

## [0.7.0] - 2026-05-30

### Added

- Review subcommands: `start`, `approve-claim`, `request-corrections`, `reject`, `verify`
- API review endpoints: `/v1/review/start`, `/v1/review/approve-claim`, `/v1/review/verify`
- Typed Pydantic request/response models for core API routes
- Structured API error codes (`MISSING_INPUT`, `VALIDATION_ERROR`, `RATE_LIMITED`)
- Optional rate limiting (`VSA_API_RATE_LIMIT`) and deterministic mode (`VSA_API_DETERMINISTIC`)
- Review chain verification via `vsa review verify` and `verify_review_chain()`

### Changed

- `docs/api.md` expanded with env vars, error format, review parity
- CI runs review workflow smoke after bundle verification

## [0.6.1] - 2026-05-30

### Added

- `vsa verify-bundle` — manifest hash verification and attestation check
- Export bundle v1.1: `report.md`, `sources/`, manifest `created_at`, schema/validation versions
- Benchmark regression gate (100% pass rate), expanded metrics, 27 tasks (fake evidence ID, stale source)
- CI acceptance job: clean-clone `make demo && make test && vsa benchmark`
- `docs/benchmark.md`; RELEASE_STATUS verified-commit table

### Changed

- Deeper variant/paper/protein/material claim templates
- ClinVar HGVS-only lookup; UniProt gene disambiguation warnings
- macOS CI smoke installs `[signing]`; Makefile `install` includes `[api]`
- Metadata-only paper claims use explicit CONTENT WARNING

## [0.6.0] - 2026-05-30

### Added

- Publication **content levels** (`metadata`, `abstract`, `fulltext`) on OpenAlex, Crossref, and Europe PMC connectors
- Paper claim templates: bibliographic identity, abstract-derived observation, full-text availability flag
- Export bundle **manifest.json** with SHA-256 hashes for all artifacts; attestation included by default
- `vsa compare-audit` for diffing audit artifacts across runs
- Validation check: warn when all publication evidence is metadata-only
- Streamlit: export bundle download and attestation generation in Provenance tab
- E2E pipeline test (build → validate → audit → attest → export)
- Expanded benchmark gold labels (paper_doi, tp53, egfr)

## [0.5.0] - 2026-05-30

### Added

- REST API (`vsa serve`, `[api]` extra): `/v1/build`, `/validate`, `/audit`, `/attest`, `/retrieve`, `/health`
- SLSA Provenance v1 / in-toto Statement attestation (`vsa attest`, `vsa verify-attestation`)
- OpenTelemetry hooks (`VSA_OTEL_ENABLED=1`, `[otel]` extra) with httpx instrumentation
- Schema migration CLI (`vsa migrate-schema`) for 1.0.0/1.1.0 → 1.2.0
- Benchmark gold label scoring (`gold_labels` in tasks.json)
- Live connector tests (`pytest -m live`) and weekly GitHub Actions workflow
- macOS CI smoke job

## [0.4.0] - 2026-05-30

### Added

- Schema **1.2.0** lifecycle fields: `input_question`, `retrieval_plan`, `retrieval_warnings`, `limitations`, `domain`, etc.
- Provenance: `evidence_content_hash`, `validation_run_hash`
- ClinVar candidate ranking (up to 10 search hits, ambiguity flags, reliability scoring)
- Paper deduplication across OpenAlex/Crossref/PubMed/Europe PMC/Semantic Scholar
- UniProt Swiss-Prot vs TrEMBL labeling; AlphaFold predicted-structure warnings
- 25-task offline benchmark with adversarial cases and expanded scoring
- Audit artifacts: `vsa audit --out`, `vsa export --out-dir`
- Docs: `docs/architecture.md`, `docs/schema.md`, `docs/connectors.md`, `docs/release_checklist.md`
- `RELEASE_STATUS.md`, README badges, known limitations
- Connector tests under `tests/connectors/`
- Expanded variant claim templates (identity, classification, ambiguity)

### Changed

- CI uploads report/audit/benchmark artifacts
- `make demo` uses `--audit-mode rule` for deterministic output

## [0.3.1] - 2026-05-30

### Added

- LLM-backed scientific verifier (`vsa audit --audit-mode auto|rule|llm`)
- Hybrid audit merge: rule structural checks plus LLM semantic review (conservative)
- Audit output fields: `missing_evidence`, `confidence_concerns`, `verifier_method`
- Packaged verifier prompt at `src/vsa/prompts/verifier_prompt_v1.md`
- Streamlit audit mode selector (auto / rule / llm)

## [0.3.0] - 2026-05-30

### Added

- Ed25519 report signing (`vsa sign`, `vsa verify-signature`) via `[signing]` extra
- Rule-based scientific audit layer (`vsa audit`) implementing verifier prompt logic
- Schema **1.1.0**: `signature`, `review_chain_hash`, `review_event_hash`, PDF output format
- Legacy claim-ledger migration (`vsa migrate`)
- Benchmark CLI (`vsa benchmark`) with offline and `--live` modes
- Materials domain example input and pipeline test
- Streamlit: audit, sign, and verify-signature actions in Provenance tab

### Changed

- `human_review` included in provenance `report_hash` core
- `human_review.required` is conditional (clinical/speculative/contradictions), not always true
- Provenance preserves `signature`, `generated_by`, and `review_chain_hash` across re-stamping

## [0.2.1] - 2026-05-30

### Added

- NCBI PubMed connector (`src/vsa/connectors/ncbi_pubmed.py`)
- PDF report renderer (`pip install verified-science-agent[pdf]`)
- Evidence graph (Mermaid) in UI and `src/vsa/render/graph.py`
- Streamlit v3: build pipeline, LLM controls, human review tab, PDF download
- Material/chemical subject parsing (LiFePO4, cathode keywords)
- Retrieval warnings surfaced in CLI and UI
- Release workflow on git tags (`.github/workflows/release.yml`)

### Fixed

- Connector cache now propagates through `--cache-dir`
- Materials Project routing for material entity types
- CLI: `inspect --json`, `compare --strict`, `review --out --notes`
- Legacy scripts delegate to `vsa` CLI

## [0.2.0] - 2026-05-30

### Added

- LLM claim extraction via OpenAI and Anthropic (`--claim-mode auto|rule|llm`)
- `vsa extract` command for inspectable claim JSON
- `vsa review` command for claim-by-claim human review workflow
- Materials Project connector (requires `MATERIALS_PROJECT_API_KEY`)
- Environment config via `.env` (`python-dotenv`)
- `.env.example` template

### Changed

- `vsa build` auto-selects LLM when API keys are present; falls back to rule-based
- Provenance records review events and extraction method stack

## [0.1.0] - 2026-05-30

### Added

- Canonical `ScientificReport` JSON Schema (v1.0.0) with support for genomics, proteins, papers, chemicals, materials, and experiments
- Installable Python package with `vsa` CLI: `validate`, `render`, `hash`, `inspect`, `compare`, `retrieve`, `build`
- Validation engine with schema conformance, evidence linkage, confidence bounds, review boundaries, contradiction detection, and provenance hash verification
- Read-only database connectors: OpenAlex, Europe PMC, UniProt, ClinVar, AlphaFold DB, Crossref, Semantic Scholar
- Evidence retrieval pipeline with file-based caching
- Rule-based claim extraction (no LLM source field invention)
- Explainable evidence quality scoring
- Markdown and HTML report renderers
- Streamlit UI v2 with claim explorer, evidence view, provenance, and validation failures
- Benchmark suite with 6 domain tasks and offline fixtures
- CI workflow: schema validation, pytest, CLI smoke tests, render/hash tests
- Example reports and bad examples for regression testing

[0.1.0]: https://github.com/fraware/verified-science-agent/releases/tag/v0.1.0
