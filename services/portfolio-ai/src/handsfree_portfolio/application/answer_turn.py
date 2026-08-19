from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from handsfree_portfolio.domain.models import RenderedAnswer
from handsfree_portfolio.ports.interfaces import GroundingVerifierPort, KnowledgePort, PlannerPort, RendererPort

PUBLIC_PACKS = ("portfolio-public",)


class GroundingFailure(RuntimeError):
    pass


@dataclass
class AnswerTurn:
    knowledge: KnowledgePort
    planner: PlannerPort
    renderer: RendererPort
    verifier: GroundingVerifierPort

    def execute(self, *, question: str, generation: int) -> RenderedAnswer:
        turn_id = str(uuid4())
        evidence = self.knowledge.retrieve(question, mounted_packs=PUBLIC_PACKS)
        plan = self.planner.plan(
            question,
            turn_id=turn_id,
            generation=generation,
            evidence=evidence,
        )
        rendered = self.renderer.render(plan)
        if rendered.turn_id != turn_id or rendered.generation != generation:
            raise GroundingFailure("rendered answer identity does not match active turn")
        if not self.verifier.verify(plan, rendered):
            raise GroundingFailure("rendered answer failed grounding verification")
        return rendered
