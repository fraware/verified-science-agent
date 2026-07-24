# Operator guide: decision-time evidence

VSA produces immutable scientific evidence packages. It does **not** authorize actions, execute tools, issue grants, or certify scientific correctness.

## Cutoff timestamp precedence

Effective evidence time (first present wins):

1. `source_timestamp` (explicit source/event time)
2. `published_at` / `domain_metadata.publication_date`
3. `retrieved_at` (retrieval clock)

Evidence with effective time **after** `decision_time_cutoff` is disclosed in `excluded_post_cutoff` and must not appear in `included_evidence`. Missing timestamps fail closed in retrospective and read_only modes.

## Modes

| Mode | How | Purpose |
|------|-----|---------|
| Retrospective | `vsa snapshot-evidence ... --mode retrospective` (default) | Reconstruct evidence available at or before a historical cutoff |
| Shadow | `vsa snapshot-evidence ... --mode shadow` | Prospective freeze alongside a live report; **no** tool execution |
| Read-only decision support | Prefer `vsa export-akta-context` (optional: `--mode read_only` on snapshot to tag a freeze) | Export AKTA context only; `authorization` is always `none` |

## Snapshot evidence at a cutoff

```bash
vsa snapshot-evidence examples/decision_time/source_report.json \
  --cutoff 2024-01-01T00:00:00Z \
  --out decision_time_bundle.json
```

Shadow (prospective, no execution):

```bash
vsa snapshot-evidence report.json --cutoff 2026-07-24T00:00:00Z --mode shadow --out shadow_bundle.json
```

Optional Ed25519 signature over `integrity.bundle_hash`:

```bash
vsa sign --generate-key
vsa snapshot-evidence report.json --cutoff 2024-01-01T00:00:00Z --sign --out signed_bundle.json
```

## Verify and compare

```bash
vsa verify-decision-time-bundle decision_time_bundle.json
vsa verify-decision-time-bundle signed_bundle.json --require-signature
vsa compare-cutoffs bundle_a.json bundle_b.json
```

Verification covers: companion schema version, cutoff inclusion, source digests, `bundle_hash`, schema digest pin, PCS-shaped portable refs, explicit non-claims, optional signature (over **recomputed** hash), and decision-time semantic checks. `compare-cutoffs` always embeds `verify_a` / `verify_b` results; comparison itself is informational and does not authorize actions.

## Export AKTA context (authorization=none)

```bash
vsa export-akta-context --bundle decision_time_bundle.json --out akta_context.json
vsa export-akta-context --report report.json --bundle decision_time_bundle.json --out akta_context.json
```

AKTA consumes this document without field-guessing. `authorization` is always `none`. Exports that imply authorization, execution, or correctness certification are rejected.

## Outcome / calibration append links

Later outcomes attach as separate records. Bundle bytes and `bundle_hash` must not change:

```bash
vsa link-outcome decision_time_bundle.json \
  --outcome-ref outcome://partner/case/123 \
  --kind calibration \
  --out outcome_link.json
```

## Privacy-safe metrics

Bundles may include `privacy_safe_metrics` with counts and histograms only (included/excluded sources, contradiction severity, uncertainty distribution). Do not log raw partner payloads, keys, or private rationales. Metrics are covered by `bundle_hash`.

## Independent reconstruction (exact commands)

Retain the original ScientificReport (or evidence-bearing JSON) and any connector cache used at build time. Then:

```bash
# 1) Rebuild from the same input + cutoff
vsa snapshot-evidence path/to/original_input.json \
  --cutoff 2024-01-01T00:00:00Z \
  --mode retrospective \
  --out reconstructed_bundle.json

# 2) Confirm hash equality against the archived bundle
python -c "import json; a=json.load(open('archived_bundle.json')); b=json.load(open('reconstructed_bundle.json')); assert a['integrity']['bundle_hash']==b['integrity']['bundle_hash']; print('bundle_hash match', a['integrity']['bundle_hash'])"

# 3) Verify invariants (and signature if present)
vsa verify-decision-time-bundle reconstructed_bundle.json
# If signed at archive time:
vsa verify-decision-time-bundle archived_bundle.json --require-signature
```

Pin package version, companion schema digests (`tests/fixtures/pcs/schema_digests.json`), and validation version into your archive metadata.

## Non-claims

- No action authorization
- No tool execution or grants
- No scientific correctness certification
- Decision-time bundles are immutable; outcomes are append-only links
- Ed25519 signatures are self-attesting via the embedded public key; pin trusted keys out-of-band
