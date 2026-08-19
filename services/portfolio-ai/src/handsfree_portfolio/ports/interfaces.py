from __future__ import annotations

from typing import Protocol, Sequence

from handsfree_portfolio.domain.conversation import ConversationState
from handsfree_portfolio.domain.knowledge import PublicClaimRecord
from handsfree_portfolio.domain.models import AnswerPlan, EvidenceRef, RenderedAnswer
from handsfree_portfolio.domain.retrieval import RetrievalResult


class ClaimCatalogPort(Protocol):
    def all_supported(self) -> tuple[PublicClaimRecord, ...]: ...
    def get(self, claim_id: str) -> PublicClaimRecord: ...


class ClaimRetrieverPort(Protocol):
    def retrieve(self, question: str) -> RetrievalResult: ...


class ConversationSessionPort(Protocol):
    def begin_turn(self, conversation_id: str) -> ConversationState: ...
    def get(self, conversation_id: str) -> ConversationState: ...
    def owns_generation(self, conversation_id: str, generation: int) -> bool: ...
    def update(
        self,
        conversation_id: str,
        generation: int,
        *,
        status: str | None = None,
        active_subject: str | None = None,
        referents: dict[str, str] | None = None,
    ) -> ConversationState: ...


class ClockPort(Protocol):
    def now_rfc3339(self) -> str: ...


class KnowledgePort(Protocol):
    def retrieve(self, question: str, *, mounted_packs: Sequence[str]) -> tuple[EvidenceRef, ...]: ...


class PlannerPort(Protocol):
    def plan(self, question: str, *, turn_id: str, generation: int, evidence: tuple[EvidenceRef, ...]) -> AnswerPlan: ...


class RendererPort(Protocol):
    def render(self, plan: AnswerPlan) -> RenderedAnswer: ...


class GroundingVerifierPort(Protocol):
    def verify(self, plan: AnswerPlan, rendered: RenderedAnswer) -> bool: ...


class CachePort(Protocol):
    def get(self, key: str) -> RenderedAnswer | None: ...
    def put(self, key: str, answer: RenderedAnswer) -> None: ...
