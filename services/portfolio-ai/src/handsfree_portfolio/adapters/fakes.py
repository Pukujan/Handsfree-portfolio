from __future__ import annotations

from handsfree_portfolio.domain.models import AnswerPlan, EvidenceRef, RenderedAnswer, SupportedClaim


class FakeKnowledge:
    def retrieve(self, question: str, *, mounted_packs: tuple[str, ...]):
        if mounted_packs != ("portfolio-public",):
            raise PermissionError("unexpected pack authority")
        return (
            EvidenceRef(
                evidence_id="fake-evidence-1",
                source_ref="fixture://portfolio-public/fossil",
                label="Fake public FOSSIL evidence",
            ),
        )


class FakePlanner:
    def plan(self, question: str, *, turn_id: str, generation: int, evidence: tuple[EvidenceRef, ...]):
        return AnswerPlan(
            turn_id=turn_id,
            generation=generation,
            dialogue_act="ANSWER_DIRECT",
            claims=(
                SupportedClaim(
                    claim_id="fake-claim-1",
                    proposition=f"Foundation fake answer for: {question}",
                    support="supported",
                    evidence_ids=tuple(item.evidence_id for item in evidence),
                ),
            ),
            evidence=evidence,
        )


class FakeRenderer:
    def render(self, plan: AnswerPlan):
        return RenderedAnswer(
            turn_id=plan.turn_id,
            generation=plan.generation,
            text=" ".join(claim.proposition for claim in plan.claims),
            evidence=plan.evidence,
        )


class FakeVerifier:
    def verify(self, plan: AnswerPlan, rendered: RenderedAnswer):
        supported_ids = {claim.claim_id for claim in plan.claims if claim.support == "supported"}
        evidence_ids = {item.evidence_id for item in plan.evidence}
        return bool(supported_ids) and {item.evidence_id for item in rendered.evidence} <= evidence_ids
