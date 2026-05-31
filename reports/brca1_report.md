# Scientific Report: BRCA1 c.68_69del

> Research infrastructure output. Not for diagnosis, treatment, or clinical decision-making without qualified expert review. Variant classifications require qualified genetics expert review before any clinical use.

## Executive summary

- **Validation status:** pass
- **Human review:** pending (required: True)
- **Claims:** 4
- **Evidence items:** 2
- **Contradictions:** 0

## Subject

- **entity_type:** variant
- **display_name:** BRCA1 c.68_69del
- **gene_symbol:** BRCA1
- **variant_hgvs_c:** c.68_69del

## Evidence table

| ID | Source | Type | Identifier | Quality | Summary |
|---|---|---|---|---|---|
| E001 | ClinVar | database | VCV000017662 | 1.0 | title: BRCA1 c.68_69del; clinical_significance: pathogenic |
| E002 | UniProt | database | P38398 | 1.0 | accession: P38398; protein_name: Breast cancer type 1 susceptibility protein; ge |

## Claim table

| ID | Type | Boundary | Confidence | Claim | Evidence |
|---|---|---|---|---|---|
| C001 | identity | requires_domain_review | 0.88 | Variant BRCA1 c.68_69del matches ClinVar record VCV000017662 (strategy: unknown, rank 1). | E001 |
| C002 | identity | safe_summary | 0.9 | ClinVar database record identity: UID ?, identifier VCV000017662. | E001 |
| C003 | classification | requires_clinical_review | 0.85 | BRCA1 c.68_69del is recorded in ClinVar with clinical significance: pathogenic. | E001 |
| C004 | identity | safe_summary | 0.78 | BRCA1 protein record is available in UniProt (P38398); entry type: unknown. | E002 |

## Contradictions

_No contradictions detected._

## Review status

- Required: True
- Status: pending

## Provenance

- Report hash: `658a0a78fa8739d613fd69c67864605d63b4025606368384fb00bfe96af45d6f`
- Evidence bundle hash: `21675ed9bf8c2683afe1202ec2761d5199d34cd85715e8699700a79cdf3de6dc`
- Validation version: 1.2.0
- Renderer version: 1.2.0

## Reproducibility instructions

- Input hash: `17038c201a8976e0c46f79dfec6c01eee4c03e3f5edac741340dbce83366b003`
- Cache directory: `.vsa_cache`
- Re-run `vsa build <input.json> --out <report.json>` with the same input and connector cache to reproduce evidence retrieval and hashes.

## Validation checks

- [PASS] JSON Schema conformance: valid
- [PASS] Schema version: matches
- [PASS] Every claim has evidence: all claims cite evidence
- [PASS] Claim evidence IDs resolve: all evidence IDs resolve
- [PASS] Evidence source type and retrieval path: all evidence items complete
- [PASS] Confidence bounded [0,1]: all confidence values valid
- [PASS] Unsupported claims flagged: no unsupported claims
- [PASS] Speculative claims labeled: no speculative claims
- [PASS] Human review requirements explicit: human_review.required=True; clinical claims: ['C003']
- [PASS] Review boundary labels valid: all boundaries valid
- [PASS] Evidence quality scoring: evidence quality acceptable
- [PASS] Contradiction detection: no contradictions
- [PASS] Provenance hashes match: hashes verified
