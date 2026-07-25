# Connectors

Read-only connectors normalize external records into `NormalizedEvidence`, then emit an immutable `SourceRecord` (authority) plus an evidence *view*.

## Shared output shape

Every connector returns: `source_name`, `source_type`, `identifier`, `retrieval_path`, `retrieved_at`, `summary`, `raw_record`, `reliability`, `domain_metadata`.

Each item also produces a `SourceRecord` with `content_digest`, `raw_response_retention`, `query`, `transformation_history`, and `source_availability`. Evidence views link via `source_id` and must not invent digests/URLs/connectors.

Raw records are cached under `.vsa_cache/` keyed by connector query and by content digest (`_by_digest/`) when retained.

## ClinVar

- **Queries**: `clinvar_id`, `vcv_id`, `variation_id`, `rsid`, `gene_symbol` + `variant_hgvs_c`
- **Behavior**: ESearch up to 10 candidates, score by gene/HGVS/rsID match, return top 3
- **Ambiguity**: When top scores are within 0.12, sets `retrieval_ambiguity: true` and lowers `reliability`
- **Limitation**: Gene-only search is broad; prefer exact IDs for production workflows

## UniProt

- **Queries**: `protein_accession` or `gene_symbol` (human, top hit)
- **Behavior**: Distinguishes Swiss-Prot (reviewed) vs TrEMBL (unreviewed) in summary and metadata
- **Limitation**: Gene symbol may map to multiple isoforms; only primary hit returned

## AlphaFold DB

- **Queries**: `protein_accession`
- **Behavior**: Marks `structure_type: predicted` in metadata; summary states non-experimental
- **Limitation**: Not a substitute for PDB experimental structures

## Papers

Connectors: OpenAlex, Crossref, PubMed (NCBI E-utilities), Europe PMC, Semantic Scholar.

- **Queries**: `doi`, `pmid`, or text term
- **Content levels**: `domain_metadata.content_level` is `metadata`, `abstract`, or `fulltext` (Europe PMC sets `fulltext` when `hasFullText=Y`; Semantic Scholar sets level from abstract availability)
- **Dedup**: Merged by DOI, PMID, or normalized title+year in retrieval pipeline
- **Claims**: Rule extraction produces bibliographic identity (C001) and abstract/metadata observation (C002); full-text availability flagged as C003 when present
- **Build warnings**: Metadata-only publication evidence triggers SCIENTIFIC CREDIBILITY WARNING in report `limitations`
- **Ambiguity**: ClinVar ambiguous matches capped to `reliability: low` with CLINVAR AMBIGUITY ALERT in report warnings
- **Limitation**: Claims are abstract/metadata-derived; full-text body parsing is not implemented

## Materials Project

- **Queries**: material formula / ID
- **API key**: `MATERIALS_PROJECT_API_KEY` for live retrieval; skipped with explicit warning when unset
- **Offline**: Benchmark and tests use fixtures; missing key never breaks offline tests

## Testing

Mocked unit tests in `tests/connectors/`:

- `test_clinvar.py`, `test_uniprot.py`, `test_alphafold.py`
- `test_openalex.py`, `test_crossref.py`, `test_europe_pmc.py`, `test_semantic_scholar.py`
- Hardening matrix: `tests/connectors/hardening/` parametrized over all nine connectors (fixture success, schema drift, malformed JSON, timeout, 429, empty vs failure, duplicates, provenance retention, explicit degradation). JSON fixture packs live under `tests/connectors/fixtures/`.

Live integration tests (optional): `pytest -m live` with `VSA_ALLOW_NETWORK=1`.

Default acceptance never runs live connectors. The skip registry (`vsa.acceptance.skip_registry`) enumerates all nine connectors as `skipped_live` when `VSA_ALLOW_NETWORK` is unset; see `reports/acceptance_baseline.json` and [benchmark.md](benchmark.md).

## Retrieval failure visibility

`retrieve_evidence_with_meta` returns typed `connector_outcomes` and report-level `retrieval_status` (`complete` | `partial` | `failed`). Distinct warning codes include `connector_timeout`, `connector_rate_limited`, `connector_failure`, `malformed_response`, `empty_result`, and `schema_drift`. Failed retrieval must not be inferred as “no evidence exists.”

## Domain packs

Selectable packs under `src/vsa/domain_packs/` (`clinical_genetics`, `materials`) override connector routing via `vsa build --domain-pack <name>`. Review records: [domain_reviews](domain_reviews/TEMPLATE.md).
