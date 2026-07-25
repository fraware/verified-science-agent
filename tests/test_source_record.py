"""SourceRecord authority, write barrier, and reconstruct tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vsa.artifacts.export import export_report_bundle
from vsa.artifacts.reconstruct import ReconstructError, reconstruct_report_from_bundle, verify_reconstructed_hash
from vsa.connectors.base import NormalizedEvidence, now_utc
from vsa.connectors.cache import EvidenceCache
from vsa.pipeline.build import build_report
from vsa.provenance.hashchain import stamp_report
from vsa.provenance.source_record import ensure_source_records, source_record_from_normalized
from vsa.schema import validate_schema
from vsa.validate.engine import validate_report


def _retained_evidence(tmp_path: Path) -> tuple[list[dict], list[dict], Path]:
    cache = EvidenceCache(tmp_path / "cache")
    raw = {"uid": "17662", "title": "BRCA1 c.68_69del", "clinical_significance": "pathogenic"}
    ne = NormalizedEvidence(
        source_name="ClinVar",
        source_type="database",
        identifier="VCV000017662",
        retrieval_path="https://www.ncbi.nlm.nih.gov/clinvar/variation/17662/",
        retrieved_at=now_utc(),
        summary="title: BRCA1 c.68_69del; clinical_significance: pathogenic",
        raw_record=raw,
        domain_metadata={"clinical_significance": "pathogenic"},
    )
    sr = ne.to_source_record({"gene_symbol": "BRCA1", "variant_hgvs_c": "c.68_69del"})
    cache.set_by_digest(sr.content_digest, raw)
    evidence = [ne.to_dict("E001", source_id=sr.source_id)]
    return evidence, [sr.to_dict()], Path(cache.cache_dir)


def test_source_record_schema_and_build(brca1_evidence):
    report = build_report(
        {"question": "BRCA1 c.68_69del", "report_id": "src-auth-1"},
        offline_evidence=copy.deepcopy(brca1_evidence),
        claim_mode="rule",
    )
    assert report["schema_version"] == "1.3.0"
    assert report.get("source_records")
    assert all(e.get("source_id") for e in report["evidence"])
    assert not validate_schema(report), validate_schema(report)


def test_write_barrier_rejects_forged_digest(brca1_report):
    report = copy.deepcopy(brca1_report)
    report["evidence"][0]["raw_record_hash"] = "a" * 64
    result = validate_report(report, verify_hashes=False)
    assert not result.passed
    assert any("authoritative" in e.lower() or "source" in e.lower() for e in result.errors)


def test_reconstruct_fails_on_digest_only(brca1_report, tmp_path: Path):
    paths = export_report_bundle(brca1_report, tmp_path / "bundle", audit_mode="rule")
    assert Path(paths["sources"]).exists()
    with pytest.raises(ReconstructError, match="retention"):
        reconstruct_report_from_bundle(tmp_path / "bundle", require_retained=True)


def test_reconstruct_matches_report_hash_when_retained(tmp_path: Path):
    evidence, source_records, cache_dir = _retained_evidence(tmp_path)
    # Force retained status (raw is in cache)
    for sr in source_records:
        sr["raw_response_retention"] = "retained"
    report = build_report(
        {
            "question": "BRCA1 c.68_69del",
            "report_id": "reconstruct-1",
            "source_records": source_records,
        },
        offline_evidence=evidence,
        claim_mode="rule",
        cache_dir=str(cache_dir),
    )
    bundle = tmp_path / "bundle"
    export_report_bundle(report, bundle, audit_mode="rule", cache_dir=cache_dir)
    # Ensure artifact has raw_response
    src_files = list((bundle / "sources").glob("*.json"))
    assert src_files
    artifact = json.loads(src_files[0].read_text(encoding="utf-8"))
    assert "raw_response" in artifact
    artifact["source_record"]["raw_response_retention"] = "retained"
    src_files[0].write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    ok, _hash, errors = verify_reconstructed_hash(bundle, require_retained=True)
    assert ok, errors


def test_source_record_from_normalized_digest():
    raw = {"a": 1}
    sr = source_record_from_normalized(
        connector="UniProt",
        identifier="P38398",
        retrieval_path="https://www.uniprot.org/uniprotkb/P38398/entry",
        retrieved_at="2026-05-30T12:00:00Z",
        raw_record=raw,
        query={"protein_accession": "P38398"},
    )
    assert sr.raw_response_retention == "retained"
    assert len(sr.content_digest) == 64
    ne = NormalizedEvidence(
        source_name="UniProt",
        source_type="database",
        identifier="P38398",
        retrieval_path=sr.canonical_url,
        retrieved_at=sr.retrieved_at,
        summary="x",
        raw_record=raw,
    )
    assert ne.raw_record_hash() == sr.content_digest


def test_ensure_source_records_synthesizes(brca1_evidence):
    ev, records = ensure_source_records(copy.deepcopy(brca1_evidence), [])
    assert len(records) == len(ev)
    assert all(e.get("source_id") for e in ev)
