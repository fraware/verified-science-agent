"""Ed25519 report signing and verification."""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from vsa.provenance.hashchain import now_utc_iso


def _load_private_key() -> Ed25519PrivateKey:
    raw = os.environ.get("VSA_SIGNING_PRIVATE_KEY")
    if raw:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw.strip()))
    seed_path = os.environ.get("VSA_SIGNING_KEY_FILE", ".vsa_signing_key")
    if os.path.isfile(seed_path):
        key_bytes = base64.b64decode(open(seed_path, encoding="utf-8").read().strip())
        return Ed25519PrivateKey.from_private_bytes(key_bytes)
    raise RuntimeError(
        "No signing key found. Set VSA_SIGNING_PRIVATE_KEY or run `vsa sign --generate-key`."
    )


def generate_keypair(path: str = ".vsa_signing_key") -> dict[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    priv_b64 = base64.b64encode(private_bytes).decode()
    pub_b64 = base64.b64encode(public_bytes).decode()
    with open(path, "w", encoding="utf-8") as f:
        f.write(priv_b64)
    return {"private_key_path": path, "public_key_b64": pub_b64}


def sign_report(report: dict[str, Any], *, key_path: str | None = None) -> dict[str, Any]:
    """Attach Ed25519 signature over report_hash to provenance."""
    if key_path:
        os.environ["VSA_SIGNING_KEY_FILE"] = key_path
    private_key = _load_private_key()
    report_hash = report.get("provenance", {}).get("report_hash")
    if not report_hash:
        raise ValueError("report has no provenance.report_hash — run vsa build first")

    signature_bytes = private_key.sign(report_hash.encode("utf-8"))
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    report = dict(report)
    prov = dict(report.get("provenance", {}))
    prov["signature"] = {
        "algorithm": "ed25519",
        "public_key_b64": base64.b64encode(public_bytes).decode(),
        "signature_b64": base64.b64encode(signature_bytes).decode(),
        "signed_at": now_utc_iso(),
        "payload": "provenance.report_hash",
    }
    report["provenance"] = prov
    return report


def verify_signature(report: dict[str, Any]) -> tuple[bool, str]:
    """Verify Ed25519 signature on report if present."""
    prov = report.get("provenance", {})
    sig = prov.get("signature")
    if not sig:
        return False, "no signature present"
    report_hash = prov.get("report_hash")
    if not report_hash:
        return False, "missing report_hash"

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(sig["public_key_b64"]))
        public_key.verify(base64.b64decode(sig["signature_b64"]), report_hash.encode("utf-8"))
        return True, "signature valid"
    except InvalidSignature:
        return False, "signature invalid"
    except Exception as exc:
        return False, str(exc)
