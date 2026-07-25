# Domain review record template

Use one record per pack review session. Commit filled records under `docs/domain_reviews/`.

## Metadata

| Field | Value |
|-------|-------|
| Reviewer | |
| Pack | `clinical_genetics` \| `materials` |
| Date | YYYY-MM-DD |
| VSA version | |
| Workflow | |

## Claims reviewed

| Claim ID | Claim text (short) | Reviewer status | Notes |
|----------|--------------------|-----------------|-------|
| | | approved / rejected / needs_revision / unreviewed | |

## Disagreements

List where the reviewer disagrees with automated claim text, confidence, or review_boundary.

1.

## Unsupported warnings

Cases where the system correctly or incorrectly flagged unsupported claims / empty support.

1.

## False-confidence cases

Claims with confidence that overstated evidence (metadata-only, ambiguous retrieval, predicted structures, etc.).

1.

## Calibration notes

Ambiguity, connector degradation (`retrieval_status`), or domain-pack warning policy issues.

1.

## Workflow reproduction steps

Independent reviewers should be able to reproduce from these steps:

1. Install: `pip install -e ".[dev]"`
2. Build with pack: `vsa build <input.json> --domain-pack <pack> --out report.json --claim-mode rule`
3. Inspect `retrieval_status`, `retrieval_warnings`, `connector_outcomes`, and `domain_pack` on the report
4. Apply review events: `vsa review start|approve-claim|request-corrections|reject`
5. Verify chain: `vsa review verify report.json`

## Sign-off

| Role | Name | Date |
|------|------|------|
| Pilot reviewer | | |
