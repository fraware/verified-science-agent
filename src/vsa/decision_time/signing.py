"""Ed25519 signing for DecisionTimeEvidenceBundle integrity.bundle_hash."""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from vsa.decision_time.snapshot import compute_bundle_hash
from vsa.provenance.hashchain import now_utc_iso


def _load_private_key(key_path: str | None = None) -> Ed25519PrivateKey:
    raw = os.environ.get("VSA_SIGNING_PRIVATE_KEY")
    if raw:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw.strip()))
    env_key = os.environ.get("VSA_SIGNING_KEY_FILE")
    seed_path = key_path if key_path is not None else (env_key or ".vsa_signing_key")
    if os.path.isfile(seed_path):
        with open(seed_path, encoding="utf-8") as handle:
            key_bytes = base64.b64decode(handle.read().strip())
        return Ed25519PrivateKey.from_private_bytes(key_bytes)
    raise RuntimeError(
        "No signing key found. Set VSA_SIGNING_PRIVATE_KEY or run `vsa sign --generate-key`."
    )


def sign_bundle(bundle: dict[str, Any], *, key_path: str | None = None) -> dict[str, Any]:
    """Attach Ed25519 signature over integrity.bundle_hash."""
    bundle = dict(bundle)
    integrity = dict(bundle.get("integrity") or {})
    bundle_hash = integrity.get("bundle_hash") or compute_bundle_hash(bundle)
    integrity["bundle_hash"] = bundle_hash

    private_key = _load_private_key(key_path)
    signature_bytes = private_key.sign(bundle_hash.encode("utf-8"))
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    integrity["signature"] = {
        "algorithm": "ed25519",
        "public_key_b64": base64.b64encode(public_bytes).decode(),
        "signature_b64": base64.b64encode(signature_bytes).decode(),
        "signed_at": now_utc_iso(),
        "payload": "integrity.bundle_hash",
    }
    bundle["integrity"] = integrity
    return bundle


def verify_bundle_signature(bundle: dict[str, Any]) -> tuple[bool, str]:
    """Verify Ed25519 signature over the recomputed bundle_hash (fail closed).

    The embedded public key is self-attesting; operators must pin trusted keys
    out-of-band. Signature alone does not establish a trust root.
    """
    integrity = bundle.get("integrity") or {}
    sig = integrity.get("signature")
    if not sig:
        return False, "no signature present"
    if not isinstance(sig, dict):
        return False, "signature block malformed"
    if sig.get("algorithm") not in (None, "ed25519"):
        return False, f"unsupported signature algorithm: {sig.get('algorithm')!r}"
    if sig.get("payload") not in (None, "integrity.bundle_hash"):
        return False, f"unexpected signature payload: {sig.get('payload')!r}"

    stored_hash = integrity.get("bundle_hash")
    recomputed = compute_bundle_hash(bundle)
    if not stored_hash:
        return False, "missing bundle_hash"
    if stored_hash != recomputed:
        return False, "bundle_hash mismatch; refusing signature verify on mutated material"

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(sig["public_key_b64"]))
        public_key.verify(base64.b64decode(sig["signature_b64"]), recomputed.encode("utf-8"))
        return True, "signature valid over recomputed bundle_hash"
    except InvalidSignature:
        return False, "signature invalid"
    except Exception as exc:
        return False, str(exc)
