"""Ed25519 signing for DecisionTimeEvidenceBundle integrity.bundle_hash."""

from __future__ import annotations

import base64
import os
from collections.abc import Collection, Iterable
from pathlib import Path
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


def load_trusted_public_keys(
    keys_b64: Iterable[str] | None = None,
    *,
    key_files: Iterable[str | Path] | None = None,
) -> list[str]:
    """Load out-of-band trusted Ed25519 public keys (raw 32-byte, base64)."""
    trusted: list[str] = []
    for key in keys_b64 or []:
        text = str(key).strip()
        if text:
            trusted.append(text)
    for path in key_files or []:
        p = Path(path)
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            trusted.append(line)
    # Validate decodability early (fail closed)
    for item in trusted:
        try:
            raw = base64.b64decode(item, validate=True)
        except TypeError:
            # validate= added in 3.11; fall back for 3.10
            raw = base64.b64decode(item)
        except Exception as exc:
            raise ValueError(f"trusted public key is not valid base64: {exc}") from exc
        if len(raw) != 32:
            raise ValueError(
                f"trusted public key must be 32 raw Ed25519 bytes (base64); got {len(raw)} bytes"
            )
    return trusted


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


def verify_bundle_signature(
    bundle: dict[str, Any],
    *,
    trusted_public_keys_b64: Collection[str] | None = None,
) -> tuple[bool, str]:
    """Verify Ed25519 signature over the recomputed bundle_hash (fail closed).

    The embedded public key is self-attesting; operators must pin trusted keys
    out-of-band. When ``trusted_public_keys_b64`` is provided, the embedded key
    must be in that set or verification fails.
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

    embedded_pk = sig.get("public_key_b64")
    if not embedded_pk or not isinstance(embedded_pk, str):
        return False, "signature missing public_key_b64"
    if trusted_public_keys_b64 is not None:
        if embedded_pk not in set(trusted_public_keys_b64):
            return False, (
                "signing public key not in trusted set "
                "(pin keys out-of-band; embedded key is self-attesting only)"
            )

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(embedded_pk))
        public_key.verify(base64.b64decode(sig["signature_b64"]), recomputed.encode("utf-8"))
        if trusted_public_keys_b64 is not None:
            return True, "signature valid over recomputed bundle_hash (trusted key pin matched)"
        return True, "signature valid over recomputed bundle_hash (no out-of-band trust pin)"
    except InvalidSignature:
        return False, "signature invalid"
    except Exception as exc:
        return False, str(exc)
