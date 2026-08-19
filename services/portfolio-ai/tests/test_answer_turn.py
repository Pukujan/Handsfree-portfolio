from __future__ import annotations

from hypothesis import given, strategies as st
import pytest

from handsfree_portfolio.adapters.fakes import FakePlanner, FakeRenderer, FakeVerifier
from handsfree_portfolio.application.answer_turn import AnswerTurn, GroundingFailure
from handsfree_portfolio.domain.models import EvidenceRef


class CapturingKnowledge:
    def __init__(self) -> None:
        self.seen_mounts: list[tuple[str, ...]] = []

    def retrieve(self, question: str, *, mounted_packs):
        mounts = tuple(mounted_packs)
        self.seen_mounts.append(mounts)
        return (EvidenceRef("ev-1", "fixture://public", "Public fixture"),)


@given(st.text(min_size=1, max_size=200).filter(lambda value: value.strip() != ""), st.integers(min_value=0, max_value=10000))
def test_generated_questions_never_widen_public_pack(question: str, generation: int) -> None:
    knowledge = CapturingKnowledge()
    use_case = AnswerTurn(knowledge, FakePlanner(), FakeRenderer(), FakeVerifier())

    answer = use_case.execute(question=question, generation=generation)

    assert knowledge.seen_mounts == [("portfolio-public",)]
    assert answer.generation == generation


def test_grounding_failure_fails_closed() -> None:
    knowledge = CapturingKnowledge()

    class RejectAll:
        def verify(self, plan, rendered) -> bool:
            return False

    use_case = AnswerTurn(knowledge, FakePlanner(), FakeRenderer(), RejectAll())

    with pytest.raises(GroundingFailure):
        use_case.execute(question="What is FOSSIL?", generation=1)
