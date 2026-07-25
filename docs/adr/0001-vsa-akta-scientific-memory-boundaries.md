# ADR 0001: VSA / AKTA / Scientific Memory Boundaries

- **Status:** Accepted
- **Date:** 2026-07-24
- **Package:** verified-science-agent 0.7.2
- **Baseline commit:** `669be9173a6a3f0f46cbf9bcd5959390929a9ba4`
- **Toolchain:** Python 3.10–3.12 supported; baseline capture ran on Python 3.13.11
- **Baseline tests:** `pytest` (offline, `-m 'not live'`) passed; `scripts/acceptance.sh` present

## Context

VSA produces immutable, evidence-backed ScientificReport artifacts (schema 1.3.0). Downstream systems need:

1. **AKTA** — action admissibility / authorization decisions that consume scientific context without field-guessing.
2. **Scientific Memory** — append-only storage of evidence packages and later outcome/calibration links.
3. **PCS-shaped portable refs** — content-addressed evidence references for cross-repo exchange.

These concerns must not blur VSA’s role into authorizing actions, executing tools, or certifying scientific correctness.

## Decision

### Ownership boundaries

| System | Owns | Does not own |
|--------|------|--------------|
| **VSA** | Evidence retrieval, claim↔evidence binding, contradiction/uncertainty surfacing, decision-time cutoff freeze, companion integration contracts | Action authorization, tool execution, grants, scientific correctness certification |
| **AKTA** | Admissibility / authorization using exported `AktaActionContext` | Producing or mutating VSA evidence packages |
| **Scientific Memory** | Append-only persistence of envelopes, bundles, outcome links | Rewriting historical decision-time bundles |

### Decision-time semantics

- A **DecisionTimeEvidenceBundle** freezes evidence available at or before `decision_time_cutoff`.
- Effective timestamp precedence: `source_timestamp` → `published_at` / `publication_date` → `retrieved_at`.
- Evidence with effective timestamps after the cutoff is moved to `excluded_post_cutoff` with disclosure.
- Bundles are **immutable**. Later outcomes and calibration attach only as append-only **ScientificOutcomeLink** records that reference the original `bundle_hash`.
- Fail closed: unknown schema versions, missing digests/timestamps (all modes), post-cutoff evidence left in the included set, included/excluded ID overlap, or corrupted non-claims → explicit fail/indeterminate, never silent pass.

### Companion schemas (additive)

ScientificReport **1.3.0** remains the compatibility baseline. New companion schemas do not mutate required ScientificReport fields:

- `integration_envelope.schema.json`
- `decision_time_evidence_bundle.schema.json`
- `akta_action_context.schema.json`
- `scientific_outcome_link.schema.json`

### Non-claims (mandatory)

VSA:

- does **not** authorize actions;
- does **not** execute tools or issue grants;
- does **not** certify scientific correctness;
- does **not** redefine PCS core — it emits PCS-shaped portable refs from existing digests only.

## Consequences

- New CLI verbs (`snapshot-evidence`, `verify-decision-time-bundle`, `compare-cutoffs`, `export-akta-context`, `link-outcome`) operate on companion artifacts.
- Offline deterministic tests cover cutoff, export, signing, and immutability.
- Rollback of companion features leaves ScientificReport validate/build unchanged.
- Public consumers start from [decision-time-quickstart.md](../decision-time-quickstart.md); operators use [operator-decision-time.md](../operator-decision-time.md).

## Upstream blockers (explicit, out-of-band)

These are integration pins outside this repository, not unfinished local work:

1. Official PCS schema ID / digest registry pins beyond local PCS-shaped refs and fixture digests.
2. AKTA upstream acknowledgment that `AktaActionContext` is the consumed contract (`authorization=none`).
3. Organizational out-of-band Ed25519 trust roots (`--trusted-key` / `--trusted-key-file`).

## Freeze note

ScientificReport schema **1.3.0** and the current 50-task offline benchmark remain the compatibility baseline for this hardening track.
