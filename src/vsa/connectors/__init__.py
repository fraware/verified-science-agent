from vsa.connectors.alphafold import AlphaFoldConnector
from vsa.connectors.base import Connector, NormalizedEvidence
from vsa.connectors.cache import EvidenceCache
from vsa.connectors.clinvar import ClinVarConnector
from vsa.connectors.crossref import CrossrefConnector
from vsa.connectors.materials_project import MaterialsProjectConnector
from vsa.connectors.ncbi_pubmed import PubMedConnector
from vsa.connectors.openalex import OpenAlexConnector
from vsa.connectors.pubmed import EuropePMCConnector
from vsa.connectors.semantic_scholar import SemanticScholarConnector
from vsa.connectors.uniprot import UniProtConnector

__all__ = [
    "AlphaFoldConnector",
    "ClinVarConnector",
    "Connector",
    "CrossrefConnector",
    "EuropePMCConnector",
    "EvidenceCache",
    "MaterialsProjectConnector",
    "NormalizedEvidence",
    "OpenAlexConnector",
    "PubMedConnector",
    "SemanticScholarConnector",
    "UniProtConnector",
    "default_connectors",
]


def default_connectors(cache: EvidenceCache | None = None) -> list[Connector]:
    cache = cache or EvidenceCache()
    return [
        ClinVarConnector(cache),
        UniProtConnector(cache),
        AlphaFoldConnector(cache),
        OpenAlexConnector(cache),
        PubMedConnector(cache),
        EuropePMCConnector(cache),
        CrossrefConnector(cache),
        SemanticScholarConnector(cache),
        MaterialsProjectConnector(cache),
    ]
