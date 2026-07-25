# PCS-shaped fixtures

VSA emits portable evidence references that reuse the PCS shape
(`content_digest`, `media_type`, `producer`, `retrieved_at`, `schema_id`).

This does **not** redefine PCS core. Digests come from the existing
VSA hashchain (`raw_record_hash`).

Pinned files:

- `CHECKSUMS.json` — fixture content digests
- `schema_digests.json` — companion JSON Schema SHA-256 digests under `src/vsa/schemas/`
- `portable_refs_sample.json` — sample portable refs

**Upstream blocker:** official PCS schema ID/digest registry pins remain
out-of-band. These fixtures are local shape and content pins only.
