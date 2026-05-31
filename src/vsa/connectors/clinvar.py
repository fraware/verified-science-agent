"""ClinVar read-only connector via NCBI E-utilities with candidate ranking."""

from __future__ import annotations

import re
from typing import Any

from vsa.connectors.base import Connector, NormalizedEvidence, now_utc, summarize_record
from vsa.connectors.cache import EvidenceCache
from vsa.http_client import make_client

MAX_CANDIDATES = 10
MAX_RETURN = 3
AMBIGUITY_SCORE_GAP = 0.12
MIN_CONFIDENT_SCORE = 0.55


class ClinVarConnector(Connector):
    name = "ClinVar"
    ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, cache: EvidenceCache | None = None, client: Any | None = None) -> None:
        self.cache = cache or EvidenceCache()
        self.client = client or make_client(timeout=30.0)

    def fetch(self, query: dict[str, Any]) -> list[NormalizedEvidence]:
        direct = (
            query.get("clinvar_id")
            or query.get("vcv_id")
            or query.get("variation_id")
            or (query.get("identifiers") or {}).get("clinvar_id")
            or (query.get("identifiers") or {}).get("vcv_id")
        )
        rsid = query.get("rsid") or (query.get("identifiers") or {}).get("rsid")
        if direct:
            uid = self._normalize_uid(str(direct))
            return self._records_from_uid(uid, query, strategy="direct_id", term=str(direct), rank=1, score=1.0)

        if rsid and not query.get("gene_symbol") and not query.get("variant_hgvs_c"):
            return self._search_candidates(query, [(f"{rsid}[Variant Name]", "rsid")])

        gene = query.get("gene_symbol")
        variant = query.get("variant_hgvs_c") or query.get("variant")
        if not gene and not variant and not rsid:
            return []

        terms: list[tuple[str, str]] = []
        if rsid:
            terms.append((f"{rsid}[Variant Name]", "rsid"))
        if gene and variant:
            terms.append((f"{gene}[gene] AND {variant}[Variant Name]", "gene_hgvs_variant_name"))
            terms.append((f"{gene}[gene] AND {variant}", "gene_hgvs_raw"))
        elif variant:
            terms.append((f"{variant}[Variant Name]", "hgvs_only"))
            terms.append((variant, "hgvs_raw"))
        elif gene:
            terms.append((f"{gene}[gene]", "gene_only"))

        return self._search_candidates(query, terms)

    def _normalize_uid(self, value: str) -> str:
        value = value.strip()
        for prefix in ("VCV", "vcv", "RCV", "rcv"):
            if value.startswith(prefix):
                return re.sub(r"^" + prefix, "", value).lstrip("0") or value
        return value

    def _search_candidates(
        self,
        query: dict[str, Any],
        terms: list[tuple[str, str]],
    ) -> list[NormalizedEvidence]:
        candidates: dict[str, tuple[float, dict[str, Any], str, str]] = {}

        for term, strategy in terms:
            cache_query = {"term": term, "retmax": MAX_CANDIDATES}
            cached = self.cache.get(self.name, cache_query)
            if cached:
                uids = cached.get("uids", [])
            else:
                resp = self.client.get(
                    self.ESEARCH,
                    params={"db": "clinvar", "term": term, "retmode": "json", "retmax": MAX_CANDIDATES},
                )
                resp.raise_for_status()
                uids = resp.json().get("esearchresult", {}).get("idlist", [])
                self.cache.set(self.name, cache_query, {"uids": uids})

            for uid in uids:
                record = self._load_summary(uid)
                score = self._score_candidate(record, query)
                prev = candidates.get(uid)
                if prev is None or score > prev[0]:
                    candidates[uid] = (score, record, strategy, term)

        if not candidates:
            return []

        ranked = sorted(candidates.items(), key=lambda item: (-item[1][0], item[0]))
        top_score = ranked[0][1][0]
        second_score = ranked[1][1][0] if len(ranked) > 1 else 0.0
        ambiguous = len(ranked) > 1 and (top_score - second_score) < AMBIGUITY_SCORE_GAP

        results: list[NormalizedEvidence] = []
        for rank, (uid, (score, record, strategy, term)) in enumerate(ranked[:MAX_RETURN], start=1):
            if rank > 1 and score < 0.25:
                continue
            reliability = self._reliability_for_candidate(rank, score, ambiguous)
            results.extend(
                self._records_from_uid(
                    uid,
                    query,
                    strategy=strategy,
                    term=term,
                    rank=rank,
                    score=score,
                    ambiguous=ambiguous,
                    record=record,
                    reliability=reliability,
                )
            )
        return results

    def _reliability_for_candidate(self, rank: int, score: float, ambiguous: bool) -> str:
        if rank == 1 and score >= MIN_CONFIDENT_SCORE and not ambiguous:
            return "high"
        if rank == 1 and score >= 0.35:
            return "medium"
        return "low"

    def _load_summary(self, uid: str) -> dict[str, Any]:
        cache_query = {"uid": uid}
        cached = self.cache.get(self.name, cache_query)
        if cached:
            return cached
        resp = self.client.get(
            self.ESUMMARY,
            params={"db": "clinvar", "id": uid, "retmode": "json"},
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        record = result.get(uid, result)
        self.cache.set(self.name, cache_query, record)
        return record

    def _score_candidate(self, record: dict[str, Any], query: dict[str, Any]) -> float:
        title = str(record.get("title", "")).lower()
        gene = str(query.get("gene_symbol") or "").lower()
        variant = str(query.get("variant_hgvs_c") or query.get("variant") or "").lower()
        rsid = str(query.get("rsid") or (query.get("identifiers") or {}).get("rsid") or "").lower()

        score = 0.0
        if gene and gene in title:
            score += 0.35
        if variant:
            norm_variant = variant.replace(" ", "")
            if norm_variant in title.replace(" ", ""):
                score += 0.45
            elif any(part in title for part in variant.split(".") if len(part) > 3):
                score += 0.2
        if rsid and rsid in title:
            score += 0.4
        if record.get("clinical_significance"):
            score += 0.05
        return min(score, 1.0)

    def _records_from_uid(
        self,
        uid: str,
        query: dict[str, Any],
        *,
        strategy: str,
        term: str,
        rank: int,
        score: float,
        ambiguous: bool = False,
        record: dict[str, Any] | None = None,
        reliability: str = "high",
    ) -> list[NormalizedEvidence]:
        record = record or self._load_summary(uid)
        title = record.get("title", "ClinVar variant")
        significance = record.get("clinical_significance") or record.get("description", "")
        if isinstance(significance, dict):
            significance = significance.get("description", str(significance))
        if isinstance(significance, list):
            significance = "; ".join(str(s) for s in significance)

        identifier = f"VCV{uid}" if not str(uid).startswith("VCV") else str(uid)
        return [
            NormalizedEvidence(
                source_name="ClinVar",
                source_type="database",
                identifier=identifier,
                retrieval_path=f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/",
                retrieved_at=now_utc(),
                summary=summarize_record(
                    {"title": title, "clinical_significance": significance},
                    ["title", "clinical_significance"],
                ),
                raw_record=record,
                reliability=reliability,
                domain_metadata={
                    "clinical_significance": str(significance).lower(),
                    "candidate_rank": rank,
                    "match_score": round(score, 3),
                    "retrieval_ambiguity": ambiguous,
                    "retrieval_strategy": strategy,
                    "retrieval_query": term,
                    "entrez_uid": uid,
                },
            )
        ]
