from __future__ import annotations

import json
from dataclasses import asdict

import httpx
import pytest

from scripts.run_g6_human_baseline import (
    FROZEN_CANDIDATE_REVISION,
    BaselineProtocolError,
    collect_grounded_answer,
    iter_sse_events,
    run_baseline_turn,
)


def event(event_type: str, payload: dict | None = None) -> dict:
    return {
        "contractVersion": "1.0.0",
        "turnId": "turn-1",
        "generation": 1,
        "type": event_type,
        "occurredAt": "2026-08-19T00:00:00Z",
        "payload": payload or {},
    }


def sse_body(events: list[dict]) -> str:
    return "".join(
        f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in events
    )


def grounded_stream(text: str = "Grounded answer.") -> list[dict]:
    return [
        event("turn.accepted"),
        event("retrieval.started"),
        event("answer.delta", {"text": text}),
        event("answer.grounded", {"claimIds": ["c1"], "evidenceIds": ["e1"]}),
        event("turn.complete", {"claimIds": ["c1"], "evidenceIds": ["e1"]}),
    ]


def test_sse_parser_and_grounding_gate_release_only_complete_answer() -> None:
    lines = sse_body(grounded_stream()).splitlines()
    events = list(iter_sse_events(lines))
    assert [item["type"] for item in events][-3:] == [
        "answer.delta",
        "answer.grounded",
        "turn.complete",
    ]
    assert collect_grounded_answer(events) == "Grounded answer."


def test_grounding_gate_rejects_partial_or_cancelled_language() -> None:
    with pytest.raises(BaselineProtocolError, match="never emitted answer.grounded"):
        collect_grounded_answer([event("answer.delta", {"text": "partial"}), event("turn.complete")])

    with pytest.raises(BaselineProtocolError, match="cancelled"):
        collect_grounded_answer(
            [
                event("answer.delta", {"text": "partial"}),
                event("turn.cancelled", {"reason": "superseded"}),
            ]
        )


def test_baseline_uses_fresh_conversation_each_turn_and_same_frozen_authority() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert json.loads(request.content) == {"question": "Why FOSSIL?"}
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse_body(grounded_stream("Same-authority answer.")),
        )

    baseline_revision = "c" * 40
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = run_baseline_turn(
            client=client,
            api_url="https://candidate.invalid",
            item_id="item-1",
            question="Why FOSSIL?",
            baseline_revision=baseline_revision,
        )
        second = run_baseline_turn(
            client=client,
            api_url="https://candidate.invalid",
            item_id="item-2",
            question="Why FOSSIL?",
            baseline_revision=baseline_revision,
        )

    assert first.conversationId != second.conversationId
    assert requests[0].url.path != requests[1].url.path
    assert first.candidateRevision == FROZEN_CANDIDATE_REVISION
    assert first.baselineRevision == baseline_revision
    assert first.answer == "Same-authority answer."
    assert "question" not in asdict(first)
    assert len(first.questionSha256) == 64


def test_baseline_rejects_nonimmutable_revision_marker() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500))) as client:
        with pytest.raises(BaselineProtocolError, match="40-character git SHA"):
            run_baseline_turn(
                client=client,
                api_url="https://candidate.invalid",
                item_id="item-1",
                question="Why FOSSIL?",
                baseline_revision="moving-branch",
            )
