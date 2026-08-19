from __future__ import annotations

from handsfree_portfolio.domain.models import AnswerPlan, RenderedAnswer

ABSTENTION_TEXT = "I don't have supported public evidence in the current portfolio knowledge pack to answer that."


def canonical_render_text(plan: AnswerPlan) -> str:
    if plan.dialogue_act == "ABSTAIN" or not plan.claims:
        return ABSTENTION_TEXT
    propositions = " ".join(claim.proposition.strip() for claim in plan.claims)
    if plan.dialogue_act == "CORRECT_PREMISE":
        return f"Not quite. {propositions}"
    return propositions


class ClaimBoundTemplateRenderer:
    """G3 renderer: can only realize already-supported propositions plus fixed non-factual connectives."""

    def render(self, plan: AnswerPlan) -> RenderedAnswer:
        return RenderedAnswer(
            turn_id=plan.turn_id,
            generation=plan.generation,
            text=canonical_render_text(plan),
            evidence=plan.evidence,
            claim_ids=tuple(claim.claim_id for claim in plan.claims),
        )


class DeterministicGroundingVerifier:
    """Recomputes the exact admissible G3 rendering and rejects any expansion or evidence drift."""

    def verify(self, plan: AnswerPlan, rendered: RenderedAnswer) -> bool:
        if rendered.turn_id != plan.turn_id or rendered.generation != plan.generation:
            return False
        if any(claim.support != "supported" for claim in plan.claims):
            return False
        expected_claim_ids = tuple(claim.claim_id for claim in plan.claims)
        if rendered.claim_ids != expected_claim_ids:
            return False
        if rendered.text != canonical_render_text(plan):
            return False
        plan_evidence = tuple((item.evidence_id, item.source_ref, item.label) for item in plan.evidence)
        rendered_evidence = tuple((item.evidence_id, item.source_ref, item.label) for item in rendered.evidence)
        return rendered_evidence == plan_evidence
