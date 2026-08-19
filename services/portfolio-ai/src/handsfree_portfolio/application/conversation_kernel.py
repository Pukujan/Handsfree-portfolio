from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator
from uuid import uuid4

from handsfree_portfolio.application.conversation_planning import build_answer_plan, infer_subject, update_referents
from handsfree_portfolio.application.response_cache import ResponseCacheCoordinator
from handsfree_portfolio.domain.conversation import TurnEvent
from handsfree_portfolio.domain.models import AnswerPlan, RenderedAnswer
from handsfree_portfolio.ports.interfaces import (
    ClaimCatalogPort,
    ClaimRetrieverPort,
    ClockPort,
    ConversationSessionPort,
    GroundingVerifierPort,
    RendererPort,
)


def answer_plan_contract(plan: AnswerPlan) -> dict:
    return {
        "contractVersion": "1.0.0",
        "turnId": plan.turn_id,
        "generation": plan.generation,
        "dialogueAct": plan.dialogue_act,
        "claims": [
            {
                "claimId": claim.claim_id,
                "proposition": claim.proposition,
                "support": claim.support,
                "evidenceIds": list(claim.evidence_ids),
            }
            for claim in plan.claims
        ],
        "evidence": [
            {
                "evidenceId": item.evidence_id,
                "sourceRef": item.source_ref,
                "label": item.label,
            }
            for item in plan.evidence
        ],
    }


@dataclass
class ConversationKernel:
    catalog: ClaimCatalogPort
    retriever: ClaimRetrieverPort
    sessions: ConversationSessionPort
    renderer: RendererPort
    verifier: GroundingVerifierPort
    clock: ClockPort
    response_cache: ResponseCacheCoordinator | None = None

    def _event(self, turn_id: str, generation: int, event_type: str, payload: dict | None = None) -> TurnEvent:
        return TurnEvent(
            turn_id=turn_id,
            generation=generation,
            type=event_type,  # type: ignore[arg-type]
            occurred_at=self.clock.now_rfc3339(),
            payload=payload or {},
        )

    def _cancelled(self, turn_id: str, generation: int, reason: str) -> TurnEvent:
        return self._event(turn_id, generation, "turn.cancelled", {"reason": reason})

    def _owns(self, conversation_id: str, generation: int) -> bool:
        return self.sessions.owns_generation(conversation_id, generation)

    def _mark_error_if_owner(self, conversation_id: str, generation: int) -> None:
        if self._owns(conversation_id, generation):
            self.sessions.update(conversation_id, generation, status="error")

    def _publish_verified(
        self,
        *,
        conversation_id: str,
        turn_id: str,
        generation: int,
        subject: str | None,
        plan: AnswerPlan,
        rendered: RenderedAnswer,
        cancellation_prefix: str,
    ) -> Iterator[TurnEvent]:
        if plan.evidence:
            yield self._event(
                turn_id,
                generation,
                "evidence.found",
                {
                    "claimIds": [claim.claim_id for claim in plan.claims],
                    "evidenceIds": [item.evidence_id for item in plan.evidence],
                },
            )
            if not self._owns(conversation_id, generation):
                yield self._cancelled(turn_id, generation, f"superseded_{cancellation_prefix}_after_evidence")
                return

        self.sessions.update(conversation_id, generation, status="rendering")
        yield self._event(turn_id, generation, "answer.planned", answer_plan_contract(plan))
        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, f"superseded_{cancellation_prefix}_after_plan")
            return

        yield self._event(
            turn_id,
            generation,
            "answer.delta",
            {
                "text": rendered.text,
                "claimIds": list(rendered.claim_ids),
                "evidenceIds": [item.evidence_id for item in rendered.evidence],
            },
        )
        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, f"superseded_{cancellation_prefix}_after_delta")
            return

        yield self._event(
            turn_id,
            generation,
            "answer.grounded",
            {
                "claimIds": list(rendered.claim_ids),
                "evidenceIds": [item.evidence_id for item in rendered.evidence],
            },
        )
        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, f"superseded_{cancellation_prefix}_before_completion")
            return

        self.sessions.update(conversation_id, generation, status="complete")
        yield self._event(
            turn_id,
            generation,
            "turn.complete",
            {
                "claimIds": list(rendered.claim_ids),
                "evidenceIds": [item.evidence_id for item in rendered.evidence],
                "activeSubject": subject,
            },
        )

    def stream_turn(self, *, conversation_id: str, question: str) -> Iterator[TurnEvent]:
        question = question.strip()
        if not question:
            raise ValueError("question must not be empty")

        state = self.sessions.begin_turn(conversation_id)
        generation = state.active_generation
        turn_id = str(uuid4())
        subject = infer_subject(question, state.active_subject)
        referents = update_referents(subject, state.referents)
        self.sessions.update(
            conversation_id,
            generation,
            status="retrieving",
            active_subject=subject,
            referents=referents,
        )

        yield self._event(
            turn_id,
            generation,
            "turn.accepted",
            {
                "question": question,
                "activeSubject": subject,
                "referents": referents,
            },
        )
        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, "superseded_before_retrieval")
            return

        if self.response_cache is not None:
            cached = self.response_cache.lookup(
                question=question,
                subject=subject,
                referents=referents,
                turn_id=turn_id,
                generation=generation,
            )
            if not self._owns(conversation_id, generation):
                yield self._cancelled(turn_id, generation, "superseded_during_cache_validation")
                return
            if cached is not None:
                yield from self._publish_verified(
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    generation=generation,
                    subject=subject,
                    plan=cached.plan,
                    rendered=cached.rendered,
                    cancellation_prefix="cache",
                )
                return

        # This event is emitted only because retrieval is about to execute.
        yield self._event(turn_id, generation, "retrieval.started", {"activeSubject": subject})
        try:
            result = self.retriever.retrieve(question)
        except Exception as exc:
            self._mark_error_if_owner(conversation_id, generation)
            yield self._cancelled(turn_id, generation, f"retrieval_failed:{type(exc).__name__}")
            return

        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, "superseded_during_retrieval")
            return

        try:
            plan = build_answer_plan(
                catalog=self.catalog,
                result=result,
                turn_id=turn_id,
                generation=generation,
                question=question,
                subject=subject,
            )
        except Exception as exc:
            self._mark_error_if_owner(conversation_id, generation)
            yield self._cancelled(turn_id, generation, f"planning_failed:{type(exc).__name__}")
            return

        self.sessions.update(conversation_id, generation, status="rendering")
        try:
            rendered = self.renderer.render(plan)
            grounded = self.verifier.verify(plan, rendered)
        except Exception as exc:
            self._mark_error_if_owner(conversation_id, generation)
            yield self._cancelled(turn_id, generation, f"render_or_verify_failed:{type(exc).__name__}")
            return
        if not grounded:
            self._mark_error_if_owner(conversation_id, generation)
            yield self._cancelled(turn_id, generation, "grounding_verification_failed")
            return

        if not self._owns(conversation_id, generation):
            yield self._cancelled(turn_id, generation, "superseded_before_publication")
            return

        if self.response_cache is not None:
            self.response_cache.store(
                question=question,
                subject=subject,
                referents=referents,
                plan=plan,
                rendered=rendered,
            )
            if not self._owns(conversation_id, generation):
                yield self._cancelled(turn_id, generation, "superseded_during_cache_store")
                return

        # No unverified answer text is ever streamed. Delta publication starts only after verification.
        yield from self._publish_verified(
            conversation_id=conversation_id,
            turn_id=turn_id,
            generation=generation,
            subject=subject,
            plan=plan,
            rendered=rendered,
            cancellation_prefix="retrieval",
        )
