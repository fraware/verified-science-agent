"""Subject parser tests."""

from vsa.pipeline.subject_parser import parse_question


def test_material_formula():
    s = parse_question("LiFePO4 cathode material")
    assert s["entity_type"] == "material"
    assert s.get("material_id") == "LiFePO4"


def test_pmid():
    s = parse_question("PMID:12345678")
    assert s["entity_type"] == "paper"
    assert s["pmid"] == "12345678"


def test_gene_symbol():
    s = parse_question("EGFR")
    assert s["entity_type"] == "gene"
    assert s["gene_symbol"] == "EGFR"
