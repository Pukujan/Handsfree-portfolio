from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from handsfree_portfolio.application.conversation_planning import build_answer_plan
from handsfree_portfolio.application.retrieval import normalize_query
from handsfree_portfolio.domain.cache import CachedAnswerArtifact
from handsfree_portfolio.domain.models import AnswerPlan, RenderedAnswer
from handsfree_portfolio.domain.retrieval import RetrievalCandidate, RetrievalResult
from handsfree_portfolio.ports.interfaces import (
    CacheAuthorityPort,
    CachePort,
    ClaimCatalogPort,
    GroundingVerifierPort,
)


@dataclass(frozen=True)
class ValidatedCacheHit:
    key: str
    plan: AnswerPlan
    rendered: RenderedAnswer


@dataclass
class ResponseCacheCoordinator:
    catalog: ClaimCatalogPort
    cache: CachePort
    authority: CacheAuthorityPort
    verifier: GroundingVerifierPort
    retrieval_policy_revision: str
    answer_contract_version: str = "1.0.0"
    renderer_policy_version: str = "claim-bound-template-v1"

    def key_for(
        self,
        *,
        question: str,
        subject: str | None,
        referents: dict[str, str],
    ) -> str:
        payload = {
            "questionFingerprintInput": normalize_query(question),
            "conversationContext": {
                "activeSubject": subject,
                "referents": sorted(referents.items()),
            },
            "authorityRevision": self.authority.fingerprint(),
            "retrievalPolicyRevision": self.retrieval_policy_revision,
            "answerContractVersion": self.answer_contract_version,
            "rendererPolicyVersion": self.renderer_policy_version,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _mark_outage(self) -> None:
        try:
            self.cache.mark_outage()
        except Exception:
            pass

    def _reject(self, key: str) -> None:
        try:
            self.cache.mark_stale_rejection()
        except Exception:
            pass
        try:
            self.cache.delete(key)
        except Exception:
            self._mark_outage()

    def lookup(
        self,
        *,
        question: str,
        subject: str | None,
        referents: dict[str, str],
        turn_id: str,
        generation: int,
    ) -> ValidatedCacheHit | None:
        try:
            key = self.key_for(question=question, subject=subject, referents=referents)
            artifact = self.cache.get(key)
        except Exception:
            self._mark_outage()
            return None
        if artifact is None:
            return None

        try:
            result = RetrievalResult(
                lane="exact",
                candidates=tuple(
                    RetrievalCandidate(claim_id=claim_id, score=1.0)
                    for claim_id in artifact.claim_ids
                ),
            )
            plan = build_answer_plan(
                catalog=self.catalog,
                result=result,
                turn_id=turn_id,
                generation=generation,
                question=question,
                subject=subject,
            )
            current_evidence_ids = tuple(item.evidence_id for item in plan.evidence)
            if current_evidence_ids != artifact.evidence_ids:
                self._reject(key)
                return None
            rendered = RenderedAnswer(
                turn_id=turn_id,
                generation=generation,
                text=artifact.text,
                evidence=plan.evidence,
                claim_ids=artifact.claim_ids,
            )
            if not self.verifier.verify(plan, rendered):
                self._reject(key)
                return None
        except Exception:
            self._reject(key)
            return None

        try:
            self.cache.mark_validated_hit()
        except Exception:
            self._mark_outage()
        return ValidatedCacheHit(key=key, plan=plan, rendered=rendered)

    def store(
        self,
        *,
        question: str,
        subject: str | None,
        referents: dict[str, str],
        plan: AnswerPlan,
        rendered: RenderedAnswer,
    ) -> None:
        # Abstentions remain cheap to recompute and are not shared as cached conclusions.
        if not plan.claims:
            return
        artifact = CachedAnswerArtifact(
            text=rendered.text,
            claim_ids=tuple(rendered.claim_ids),
            evidence_ids=tuple(item.evidence_id for item in rendered.evidence),
        )
        try:
            key = self.key_for(question=question, subject=subject, referents=referents)
            self.cache.put(key, artifact)
        except Exception:
            self._mark_outage()
