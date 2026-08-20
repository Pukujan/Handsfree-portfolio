from __future__ import annotations

import json
import threading
from pathlib import Path

from hypothesis import given, strategies as st
from jsonschema import Draft202012Validator, FormatChecker

from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.conversation_planning import (
    SPOKEN_PROPOSITION_WORD_BUDGET,
    extractive_spoken_proposition,
)
from handsfree_portfolio.application.grounded_rendering import (
    ABSTENTION_TEXT,
    ClaimBoundTemplateRenderer,
    DeterministicGroundingVerifier,
)
from handsfree_portfolio.application.retrieval import PublicClaimRetriever
from handsfree_portfolio.domain.knowledge import PublicClaimRecord
from handsfree_portfolio.domain.models import RenderedAnswer

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"
POLICY = KNOWLEDGE / "retrieval-v1.json"
SCHEMAS = ROOT / "contracts" / "schemas"


class FixtureCatalog:
    def __init__(self) -> None:
        payload = json.loads((KNOWLEDGE / "slice1-reviewed-claims.json").read_text(encoding="utf-8"))
        self.records = tuple(
            PublicClaimRecord(
                claim_id=claim["claimId"],
                proposition=claim["claimText"],
                evidence_ids=(f"fixture:{claim['claimId']}:evidence",),
                snapshot_ids=(f"fixture:{claim['claimId']}:snapshot",),
                citation_id=f"fixture:{claim['claimId']}:citation",
                source_ref=f"{claim['source']['repository']}@{claim['source']['revision']}:{claim['source']['path']}",
                cited_text=claim["source"]["anchorText"],
            )
            for claim in payload["claims"]
        )

    def all_supported(self):
        return self.records

    def get(self, claim_id: str):
        return next(record for record in self.records if record.claim_id == claim_id)


class BrokenCatalog(FixtureCatalog):
    def get(self, claim_id: str):
        raise RuntimeError("evidence catalog unavailable")


class MaliciousRenderer:
    def __init__(self) -> None:
        self.good = ClaimBoundTemplateRenderer()

    def render(self, plan):
        rendered = self.good.render(plan)
        return RenderedAnswer(
            turn_id=rendered.turn_id,
            generation=rendered.generation,
            text=rendered.text + " Pujan secretly built an unsupported system.",
            evidence=rendered.evidence,
            claim_ids=rendered.claim_ids,
        )


class BlockingFirstRetriever:
    def __init__(self, delegate) -> None:
        self.delegate = delegate
        self.calls = 0
        self.lock = threading.Lock()
        self.started = threading.Event()
        self.release = threading.Event()

    def retrieve(self, question: str):
        with self.lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self.started.set()
            assert self.release.wait(timeout=5), "test did not release first retrieval"
        return self.delegate.retrieve(question)


def make_kernel(*, catalog=None, retriever=None, renderer=None, sessions=None):
    catalog = catalog or FixtureCatalog()
    retriever = retriever or PublicClaimRetriever(catalog, load_retrieval_policy(POLICY))
    return ConversationKernel(
        catalog=catalog,
        retriever=retriever,
        sessions=sessions or InMemoryConversationSessions(),
        renderer=renderer or ClaimBoundTemplateRenderer(),
        verifier=DeterministicGroundingVerifier(),
        clock=SystemClock(),
    )


def event_of(events, event_type: str):
    return next(event for event in events if event.type == event_type)


def assert_contracts(events, state) -> None:
    turn_schema = json.loads((SCHEMAS / "turn-event-v1.schema.json").read_text(encoding="utf-8"))
    answer_schema = json.loads((SCHEMAS / "portfolio-answer-v1.schema.json").read_text(encoding="utf-8"))
    state_schema = json.loads((SCHEMAS / "conversation-state-v1.schema.json").read_text(encoding="utf-8"))
    turn_validator = Draft202012Validator(turn_schema, format_checker=FormatChecker())
    answer_validator = Draft202012Validator(answer_schema, format_checker=FormatChecker())
    state_validator = Draft202012Validator(state_schema, format_checker=FormatChecker())
    for event in events:
        turn_validator.validate(event.to_contract())
        if event.type == "answer.planned":
            answer_validator.validate(event.payload)
    state_validator.validate(state.to_contract())


def test_reviewed_slice1_claims_have_extractable_spoken_prefixes() -> None:
    for record in FixtureCatalog().all_supported():
        spoken = extractive_spoken_proposition(record.proposition)
        assert record.proposition.rstrip(".!?").startswith(spoken.rstrip(".!?"))
        assert len(spoken.rstrip(".").split()) <= SPOKEN_PROPOSITION_WORD_BUDGET


def test_slice1_two_turn_context_and_grounded_evidence() -> None:
    sessions = InMemoryConversationSessions()
    kernel = make_kernel(sessions=sessions)

    first = list(kernel.stream_turn(conversation_id="c1", question="What is FOSSIL?"))
    second = list(kernel.stream_turn(conversation_id="c1", question="Why not just use Neo4j?"))

    assert [event.type for event in first] == [
        "turn.accepted", "retrieval.started", "evidence.found", "answer.planned",
        "answer.delta", "answer.grounded", "turn.complete",
    ]
    assert event_of(first, "turn.accepted").payload["activeSubject"] == "FOSSIL"
    first_delta = event_of(first, "answer.delta")
    assert first_delta.payload["claimIds"] == ["clm_portfolio_fossil_durable_truth_0001"]
    assert first_delta.payload["text"] == "FOSSIL's durable knowledge authority is its evidence."

    accepted = event_of(second, "turn.accepted")
    plan = event_of(second, "answer.planned")
    delta = event_of(second, "answer.delta")
    assert accepted.payload["activeSubject"] == "FOSSIL"
    assert accepted.payload["referents"]["it"] == "FOSSIL"
    assert plan.payload["dialogueAct"] == "EXPLAIN"
    assert not delta.payload["text"].startswith("Not quite. ")
    assert delta.payload["text"] == "Graphiti and Neo4j are replaceable projections of already-durable FOSSIL knowledge."
    assert delta.payload["claimIds"] == ["clm_portfolio_fossil_projection_0001"]
    assert len(delta.payload["evidenceIds"]) == 1
    assert event_of(second, "answer.grounded").payload["evidenceIds"] == delta.payload["evidenceIds"]
    assert sessions.get("c1").active_generation == 2
    assert sessions.get("c1").active_subject == "FOSSIL"
    assert sessions.get("c1").status == "complete"
    assert_contracts(first + second, sessions.get("c1"))


def test_explicit_neo4j_premise_challenge_uses_concise_correction() -> None:
    sessions = InMemoryConversationSessions()
    kernel = make_kernel(sessions=sessions)
    list(kernel.stream_turn(conversation_id="premise", question="What is FOSSIL?"))
    events = list(
        kernel.stream_turn(
            conversation_id="premise",
            question="I thought Neo4j was the durable authority.",
        )
    )
    plan = event_of(events, "answer.planned")
    delta = event_of(events, "answer.delta")
    assert plan.payload["dialogueAct"] == "CORRECT_PREMISE"
    assert delta.payload["text"].startswith("Not quite. ")
    assert len(delta.payload["claimIds"]) == 1
    assert len(delta.payload["evidenceIds"]) == 1
    assert events[-1].type == "turn.complete"


def test_unsupported_question_abstains_without_evidence() -> None:
    sessions = InMemoryConversationSessions()
    events = list(make_kernel(sessions=sessions).stream_turn(conversation_id="c2", question="What is Pujan's favorite food?"))
    assert "evidence.found" not in [event.type for event in events]
    plan = event_of(events, "answer.planned")
    delta = event_of(events, "answer.delta")
    assert plan.payload["dialogueAct"] == "ABSTAIN"
    assert plan.payload["claims"] == []
    assert delta.payload["text"] == ABSTENTION_TEXT
    assert delta.payload["claimIds"] == []
    assert delta.payload["evidenceIds"] == []
    assert events[-1].type == "turn.complete"


def test_renderer_fact_expansion_fails_before_answer_delta() -> None:
    events = list(make_kernel(renderer=MaliciousRenderer()).stream_turn(conversation_id="c3", question="What is FOSSIL?"))
    types = [event.type for event in events]
    assert "answer.delta" not in types
    assert "answer.grounded" not in types
    assert "turn.complete" not in types
    assert events[-1].type == "turn.cancelled"
    assert events[-1].payload["reason"] == "grounding_verification_failed"


def test_catalog_failure_after_retrieval_fails_closed() -> None:
    catalog = BrokenCatalog()
    retriever = PublicClaimRetriever(catalog, load_retrieval_policy(POLICY))
    events = list(make_kernel(catalog=catalog, retriever=retriever).stream_turn(conversation_id="c4", question="What is FOSSIL?"))
    assert "answer.delta" not in [event.type for event in events]
    assert events[-1].type == "turn.cancelled"
    assert events[-1].payload["reason"].startswith("planning_failed:")


def test_new_generation_fences_old_turn_after_blocked_retrieval() -> None:
    catalog = FixtureCatalog()
    delegate = PublicClaimRetriever(catalog, load_retrieval_policy(POLICY))
    blocking = BlockingFirstRetriever(delegate)
    sessions = InMemoryConversationSessions()
    kernel = make_kernel(catalog=catalog, retriever=blocking, sessions=sessions)

    old = kernel.stream_turn(conversation_id="race", question="What is FOSSIL?")
    prefix = [next(old), next(old)]
    assert [event.type for event in prefix] == ["turn.accepted", "retrieval.started"]

    old_tail: list = []
    worker = threading.Thread(target=lambda: old_tail.extend(list(old)))
    worker.start()
    assert blocking.started.wait(timeout=5)

    newer = list(kernel.stream_turn(conversation_id="race", question="Why not just use Neo4j?"))
    blocking.release.set()
    worker.join(timeout=5)
    assert not worker.is_alive()

    assert newer[-1].type == "turn.complete"
    assert newer[-1].generation == 2
    old_types = [event.type for event in old_tail]
    assert "answer.delta" not in old_types
    assert "answer.grounded" not in old_types
    assert "turn.complete" not in old_types
    assert old_tail[-1].type == "turn.cancelled"
    assert old_tail[-1].payload["reason"] == "superseded_during_retrieval"
    assert sessions.get("race").active_generation == 2
    assert sessions.get("race").status == "complete"


@given(turn_count=st.integers(min_value=1, max_value=30))
def test_generations_are_monotonic_and_only_latest_state_survives(turn_count: int) -> None:
    sessions = InMemoryConversationSessions()
    kernel = make_kernel(sessions=sessions)
    seen: list[int] = []
    for _ in range(turn_count):
        events = list(kernel.stream_turn(conversation_id="property", question="What is FOSSIL?"))
        assert events[-1].type == "turn.complete"
        assert sum(event.type == "turn.complete" for event in events) == 1
        assert sum(event.type == "answer.delta" for event in events) == 1
        assert event_of(events, "answer.delta").generation == events[-1].generation
        seen.append(events[-1].generation)
    assert seen == list(range(1, turn_count + 1))
    assert sessions.get("property").active_generation == turn_count
    assert sessions.get("property").status == "complete"
