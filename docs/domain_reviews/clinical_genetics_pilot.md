# Domain review: clinical_genetics (pilot)

## Metadata

| Field | Value |
|-------|-------|
| Reviewer | Pilot Reviewer (clinical genetics) |
| Pack | `clinical_genetics` |
| Date | 2026-07-25 |
| VSA version | 0.7.2 |
| Workflow | Offline fixture / demo build with `--domain-pack clinical_genetics` |

## Claims reviewed

| Claim ID | Claim text (short) | Reviewer status | Notes |
|----------|--------------------|-----------------|-------|
| C001 | BRCA1 variant clinical significance from ClinVar | needs_revision | Ambiguous gene+HGVS retrieval can surface multiple VCVs; do not treat as definitive without VCV ID |
| C002 | UniProt gene product identity | approved | Acceptable bibliographic/database identity when accession is exact |
| C003 | Unsupported speculative penetrance claim | rejected | Correctly unsupported / clinical boundary |

## Disagreements

1. Automated confidence on ClinVar ambiguous matches remained too high before reliability cap; pack policy requires `ambiguity_reliability_cap: low` and clinical review boundary.
2. Rule extractor sometimes phrased ClinVar significance as definitive classification; reviewer requires hedging plus `requires_clinical_review`.

## Unsupported warnings

1. Empty ClinVar search correctly emitted `empty_result` (not `connector_failure`) with `retrieval_status=partial`.
2. Timeout injection produced `connector_timeout` and `retrieval_status=failed` — visible in `retrieval_warnings` (failure ≠ silent no-evidence).

## False-confidence cases

1. Gene-only ClinVar search: multiple candidates with close scores → ambiguity; any confidence ≥0.8 would be false confidence.
2. UniProt gene-symbol search returning multiple human isoforms: isoform choice must not imply reviewed clinical annotation.

## Calibration notes

1. Pack routes `variant` → ClinVar, UniProt, PubMed, Europe PMC as declared in `pack.yaml`.
2. Reviewer expects `retrieval_status` and per-connector outcomes on every degraded build.
3. Domain pack warning policy `clinical_review_required: true` aligns with claim `requires_clinical_review`.

## Workflow reproduction steps

1. `pip install -e ".[dev]"`
2. Prepare variant subject JSON (`entity_type: variant`, gene + HGVS or ClinVar ID).
3. `vsa build input.json --domain-pack clinical_genetics --out reports/clinical_genetics_pilot.json --claim-mode rule`
4. Confirm report fields: `domain_pack=clinical_genetics`, inspect `retrieval_warnings` / `connector_outcomes`.
5. `vsa review start reports/clinical_genetics_pilot.json --reviewer "pilot-cg" --out reports/clinical_genetics_pilot.json`
6. `vsa review verify reports/clinical_genetics_pilot.json`

## Sign-off

| Role | Name | Date |
|------|------|------|
| Pilot reviewer | Pilot Reviewer (clinical genetics) | 2026-07-25 |
