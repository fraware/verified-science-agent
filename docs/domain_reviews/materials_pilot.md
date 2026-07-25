# Domain review: materials (pilot)

## Metadata

| Field | Value |
|-------|-------|
| Reviewer | Pilot Reviewer (materials) |
| Pack | `materials` |
| Date | 2026-07-25 |
| VSA version | 0.7.2 |
| Workflow | Offline fixture / materials demo with `--domain-pack materials` |

## Claims reviewed

| Claim ID | Claim text (short) | Reviewer status | Notes |
|----------|--------------------|-----------------|-------|
| C001 | LiFePO4 Materials Project identity / crystal system | approved | Acceptable when `material_id` retained in SourceRecord |
| C002 | Property claim from metadata-only paper | needs_revision | Property magnitude claims need non-metadata evidence or domain review |
| C003 | Speculative application claim | rejected | Correct `speculative` / unsupported boundary |

## Disagreements

1. Literature connectors may attach OpenAlex/PubMed hits that share formula tokens but not the same phase; reviewer rejects property transfer without explicit material_id linkage.
2. When `MATERIALS_PROJECT_API_KEY` is unset, skip must remain an explicit `connector_skipped` warning — never silent empty success.

## Unsupported warnings

1. Empty Materials Project `data: []` → `empty_result` with `retrieval_status=partial`.
2. Rate-limit 429 → `connector_rate_limited` with failed/partial status visible in validation check `retrieval_status_visible`.

## False-confidence cases

1. Using Crossref/OpenAlex metadata title match alone to assert quantitative `energy_above_hull` values.
2. Treating skipped Materials Project (no API key) as “material not in database”.

## Calibration notes

1. Pack routes `material` → Materials Project, OpenAlex, PubMed, Crossref.
2. `property_claim_review: requires_domain_review` should gate quantitative property claims.
3. Provenance retention: retained raw Materials Project payloads must keep `material_id` + formula for reconstruction.

## Workflow reproduction steps

1. `pip install -e ".[dev]"`
2. Prepare material subject JSON (`entity_type: material`, `formula` or `material_id`).
3. `vsa build input.json --domain-pack materials --out reports/materials_pilot.json --claim-mode rule`
4. Confirm `domain_pack=materials` and Materials Project outcome (success, skip, empty, or failure code).
5. `vsa review start reports/materials_pilot.json --reviewer "pilot-mat" --out reports/materials_pilot.json`
6. `vsa review verify reports/materials_pilot.json`

## Sign-off

| Role | Name | Date |
|------|------|------|
| Pilot reviewer | Pilot Reviewer (materials) | 2026-07-25 |
