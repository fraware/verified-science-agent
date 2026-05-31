"""Attestation tests."""

from __future__ import annotations

from vsa.provenance.attestation import build_slsa_attestation, verify_attestation


def test_build_and_verify_attestation(brca1_report):
    attestation = build_slsa_attestation(brca1_report)
    assert attestation["_type"] == "https://in-toto.io/Statement/v1"
    assert attestation["predicateType"] == "https://slsa.dev/provenance/v1"
    ok, msg = verify_attestation(attestation, brca1_report)
    assert ok, msg


def test_verify_attestation_fails_on_tamper(brca1_report):
    from vsa.provenance.hashchain import stamp_report

    attestation = build_slsa_attestation(brca1_report)
    brca1_report["claims"][0]["claim_text"] = "Tampered claim text for attestation test."
    rehashed = stamp_report(brca1_report)
    ok, _ = verify_attestation(attestation, rehashed)
    assert not ok
