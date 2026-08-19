from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping

from handsfree_portfolio.domain.knowledge import PublicClaimRecord
from handsfree_portfolio.domain.retrieval import RetrievalCandidate, RetrievalResult
from handsfree_portfolio.ports.interfaces import ClaimCatalogPort

_STOPWORDS = {
    "a", "an", "and", "are", "be", "can", "does", "every", "how", "if", "is", "it", "just",
    "of", "or", "the", "this", "to", "what", "why", "will"
}
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_query(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.lower()))


def content_tokens(value: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(value.lower()) if token not in _STOPWORDS and len(token) > 1}


@dataclass(frozen=True)
class RetrievalPolicy:
    exact_aliases: Mapping[str, tuple[str, ...]]
    concepts: Mapping[str, tuple[str, ...]]
    top_k: int = 2
    minimum_sparse_score: float = 1.5


@dataclass
class PublicClaimRetriever:
    catalog: ClaimCatalogPort
    policy: RetrievalPolicy

    def retrieve(self, question: str) -> RetrievalResult:
        normalized = normalize_query(question)
        exact = self.policy.exact_aliases.get(normalized)
        if exact:
            available = {record.claim_id for record in self.catalog.all_supported()}
            claim_ids = tuple(claim_id for claim_id in exact if claim_id in available)
            return RetrievalResult(
                lane="exact",
                candidates=tuple(RetrievalCandidate(claim_id=claim_id, score=1.0) for claim_id in claim_ids),
            )
        return self._sparse_semantic(question)

    def _sparse_semantic(self, question: str) -> RetrievalResult:
        records = self.catalog.all_supported()
        if not records:
            return RetrievalResult(lane="abstain", candidates=())

        query_normalized = normalize_query(question)
        query_tokens = content_tokens(question)
        documents: dict[str, set[str]] = {}
        for record in records:
            concept_text = " ".join(self.policy.concepts.get(record.claim_id, ()))
            documents[record.claim_id] = content_tokens(f"{record.proposition} {record.cited_text} {concept_text}")

        doc_count = len(documents)
        document_frequency: dict[str, int] = {}
        for tokens in documents.values():
            for token in tokens:
                document_frequency[token] = document_frequency.get(token, 0) + 1

        scored: list[RetrievalCandidate] = []
        by_id = {record.claim_id: record for record in records}
        for claim_id, doc_tokens in documents.items():
            token_score = 0.0
            for token in query_tokens & doc_tokens:
                df = document_frequency[token]
                token_score += math.log((doc_count + 1) / (df + 0.5)) + 0.5

            phrase_score = 0.0
            for phrase in self.policy.concepts.get(claim_id, ()):
                normalized_phrase = normalize_query(phrase)
                if normalized_phrase and normalized_phrase in query_normalized:
                    phrase_score += 2.5 + 0.25 * len(content_tokens(phrase))

            # A direct lexical phrase from the authoritative proposition is useful but weaker than a curated concept alias.
            proposition = normalize_query(by_id[claim_id].proposition)
            proposition_tokens = content_tokens(proposition)
            proposition_overlap = len(query_tokens & proposition_tokens) / max(1, len(query_tokens))
            score = token_score + phrase_score + proposition_overlap
            if score >= self.policy.minimum_sparse_score:
                scored.append(RetrievalCandidate(claim_id=claim_id, score=round(score, 6)))

        scored.sort(key=lambda candidate: (-candidate.score, candidate.claim_id))
        candidates = tuple(scored[: self.policy.top_k])
        return RetrievalResult(lane="sparse-semantic" if candidates else "abstain", candidates=candidates)
