# Signing and Attestations

VSA signing and attestation prove **artifact integrity**, not scientific truth.
Operators must keep four layers separate.

## Four layers

| Layer | What it means | What it does **not** mean |
|-------|---------------|---------------------------|
| **1. Artifact integrity** | Ed25519 over `report_hash` / `bundle_hash` (or SLSA subject digest match) confirms bytes/content identity | Claims are true; evidence is complete; science is correct |
| **2. Signer identity** | Key attribution / trusted-key pin (`--trusted-key`, `--trusted-key-file`) establishes *who* signed | Organizational policy approval; reviewer endorsement |
| **3. Reviewer approval** | Hash-linked `review_events` (`vsa review verify`) record human decisions | Cryptographic artifact signature; scientific correctness |
| **4. Scientific correctness** | Domain review, validation checks, credibility warnings, and external expertise | Never claimed by signatures, attestations, or digest match |

## Commands

- `vsa sign` — Ed25519-sign the report provenance hash (integrity only).
- `vsa verify-signature` — Verify the embedded Ed25519 signature (integrity only; pin trusted keys out-of-band for identity trust).
- `vsa attest` / `vsa verify-attestation` — Build or check an in-toto/SLSA statement whose subject digest matches `report_hash`. Digest match is **not** a crypto endorsement of scientific correctness.
- `vsa review verify` — Verify the hash-linked review event chain (layer 3).

## Related documents

- [threat-model.md](threat-model.md) — decision-time integrity and signature trust notes
- [../SECURITY.md](../SECURITY.md) — key handling and disclosure
- [adr/0001-vsa-akta-scientific-memory-boundaries.md](adr/0001-vsa-akta-scientific-memory-boundaries.md) — AKTA exports never authorize actions
