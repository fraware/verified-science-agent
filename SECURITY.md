# Security Policy

## Supported versions

Security fixes are accepted for the current release line of `verified-science-agent` (0.7.x) while ScientificReport schema 1.2.0 remains the public artifact baseline.

## Reporting a vulnerability

Report security issues privately to the repository maintainers (GitHub Security Advisories preferred when available). Do not open public issues that include exploit details, private partner evidence, signing keys, or API credentials.

Include:

- affected package version and commit SHA when known;
- impact description (integrity, confidentiality, availability);
- minimal reproduction without live partner payloads or secrets.

## Scope notes

- VSA validates and packages scientific evidence; it does not authorize actions, execute tools, issue grants, or certify scientific correctness.
- Signing keys (`VSA_SIGNING_PRIVATE_KEY`, `.vsa_signing_key`) and API keys must never appear in fixtures, logs, or CI artifacts.
- Connector caches and export bundles may contain retrieved scientific records; treat them according to your data-handling policy.
- Optional Ed25519 signatures are self-attesting (public key embedded). Pin trusted keys out-of-band (`vsa verify-decision-time-bundle --trusted-key` / `--trusted-key-file`) before treating a signature as organizationally trusted.
- Decision-time privacy-safe metrics must remain counts/histograms only — never raw partner payloads or private rationales (re-checked on verify).
- Never commit `.env`; see `.env.example` for optional configuration keys only.

## Decision-time integrity

- Post-cutoff evidence must be excluded and disclosed; inclusion is a hard verification failure.
- Outcome/calibration links are append-only and must not mutate `DecisionTimeEvidenceBundle` bytes or `bundle_hash`.
- Companion schema versions unknown to this package fail closed.
