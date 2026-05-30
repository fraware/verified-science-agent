"""Example adapter for external evidence systems."""

from typing import Dict, Any


def build_query(subject: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'gene_symbol': subject.get('gene_symbol'),
        'variant': subject.get('variant_hgvs_c')
    }


def normalize_result(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'source_name': raw_result.get('source_name', 'unknown'),
        'retrieval_path': raw_result.get('retrieval_path', ''),
        'summary': raw_result.get('summary', '')
    }
