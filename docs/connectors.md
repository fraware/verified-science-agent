# Connectors

Read-only connectors normalize external records into `NormalizedEvidence`.

## Shared output shape

Every connector returns: `source_name`, `source_type`, `identifier`, `retrieval_path`, `retrieved_at`, `summary`, `raw_record`, `reliability`, `domain_metadata`.

Raw records are cached under `.vsa_cache/` keyed by connector query.

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
- **Build warnings**: Metadata-only publication evidence triggers a CONTENT WARNING in report `limitations`
- **Limitation**: Claims are abstract/metadata-derived; full-text body parsing is not implemented

## Materials Project

- **Queries**: material formula / ID
- **API key**: `MATERIALS_PROJECT_API_KEY` for live retrieval
- **Offline**: Benchmark and tests use fixtures; missing key never breaks offline tests

## Testing

Mocked unit tests in `tests/connectors/`:

- `test_clinvar.py`, `test_uniprot.py`, `test_alphafold.py`
- `test_openalex.py`, `test_crossref.py`, `test_europe_pmc.py`, `test_semantic_scholar.py`

Live integration (optional): `pytest -m live`

See [RELEASE_STATUS.md](../RELEASE_STATUS.md) for experimental vs production-ready connector behavior.
