# Threat Model (Decision-Time Evidence)

## Assets

- ScientificReport and DecisionTimeEvidenceBundle integrity (hashes, optional Ed25519 signatures)
- Claim↔evidence binding and contradiction/uncertainty disclosures
- Signing private keys and connector/API credentials
- Partner or private evidence (must not appear in public fixtures or privacy-safe metrics)

## Trust boundaries

| Boundary | Trust assumption |
|----------|------------------|
| Connectors / parsers | Untrusted input; trusted kernel sees only normalized typed records |
| Decision-time cutoff | Evidence after cutoff must not silently enter the included set |
| AKTA export | Context only; any language implying authorization/execution/correctness certification is rejected |
| Scientific Memory | Append-only; outcome links must not mutate prior bundle bytes |

## Adversaries / failure modes

1. **Post-cutoff injection** — future evidence smuggled into a retrospective reconstruction.
2. **Digest substitution** — altered source records without hash mismatch detection.
3. **Authorization implication** — exports that look like grants or tool permissions.
4. **Silent schema drift** — unknown companion schema versions accepted as pass.
5. **Secret leakage** — keys or private rationales in metrics, logs, or fixtures.

## Mitigations (VSA)

- Fail closed on missing digests, missing timestamps (all modes), unknown schema versions, post-cutoff inclusion, included/excluded ID overlap, duplicate evidence IDs, missing portable refs when digests exist, corrupted non-claims, and privacy-metric shape violations.
- Reuse SHA-256 hashchain + optional Ed25519 over **recomputed** `bundle_hash` (not a stale stored hash alone).
- Optional `--trusted-key` / `--trusted-key-file` pins for signature verify (embedded key must be in the operator-supplied set).
- Semantic validation on `AktaActionContext` for non-authorization language, forbidden execution-class tokens, and digest disagreement with the source report.
- Privacy-safe pilot metrics: counts and histograms only; metrics are included in `bundle_hash` and re-checked on verify.
- Explicit non-claims in docs, schemas, and CLI help.

## Signature trust note

Optional Ed25519 signatures embed the signing public key. Cryptographic validity proves possession of the corresponding private key at signing time; it does **not** by itself establish a trust root. Operators must pin trusted public keys out-of-band (CLI `--trusted-key` / `--trusted-key-file`).

Artifact integrity, signer identity, reviewer approval, and scientific correctness are separate layers — see [signing.md](signing.md).

## Upstream blockers (explicit)

Not solved in this repository alone (integration pins, not unfinished local features):

- Official PCS schema ID/digest registry pins beyond local shape + fixture digests
- AKTA upstream acknowledgment of the `AktaActionContext` contract
- Organizational out-of-band signing trust roots (beyond operator-supplied pin files)

## Out of scope

- AKTA admissibility logic and tool runners
- Network attackers against live connector endpoints (opt-in `-m live` only)
- Certifying scientific truth of claims
- Defining PCS core (VSA only emits PCS-shaped portable refs from existing digests)
- Authorizing actions, executing tools, or issuing grants
