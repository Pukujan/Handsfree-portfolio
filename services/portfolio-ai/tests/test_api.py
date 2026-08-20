import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from handsfree_portfolio.adapters.clock import SystemClock
from handsfree_portfolio.adapters.retrieval_policy import load_retrieval_policy
from handsfree_portfolio.adapters.session_memory import InMemoryConversationSessions
from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.application.grounded_rendering import ClaimBoundTemplateRenderer, DeterministicGroundingVerifier
from handsfree_portfolio.application.retrieval import PublicClaimRetriever
from handsfree_portfolio.delivery.api import create_app
from handsfree_portfolio.delivery.composition import RuntimeConfigurationError
from handsfree_portfolio.domain.knowledge import PublicClaimRecord

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE = ROOT / "knowledge" / "portfolio-public"


class ApiFixtureCatalog:
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


def fixture_kernel() -> ConversationKernel:
    catalog = ApiFixtureCatalog()
    return ConversationKernel(
        catalog=catalog,
        retriever=PublicClaimRetriever(catalog, load_retrieval_policy(KNOWLEDGE / "retrieval-v1.json")),
        sessions=InMemoryConversationSessions(),
        renderer=ClaimBoundTemplateRenderer(),
        verifier=DeterministicGroundingVerifier(),
        clock=SystemClock(),
    )


def test_health_and_sse_turn_stream() -> None:
    kernel = fixture_kernel()
    client = TestClient(create_app(lambda: kernel))
    assert client.get("/health").json() == {"status": "ok"}

    with client.stream(
        "POST",
        "/v1/conversations/api-test/turns",
        json={"question": "What is FOSSIL?"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "event: turn.accepted" in body
    assert "event: retrieval.started" in body
    assert "event: answer.grounded" in body
    assert "event: turn.complete" in body
    assert "fixture:" in body

    state = client.get("/v1/conversations/api-test/state")
    assert state.status_code == 200
    assert state.json()["activeGeneration"] == 1
    assert state.json()["state"] == "complete"
    assert state.json()["activeSubject"] == "FOSSIL"


def test_turn_observability_is_bounded_and_omits_raw_conversation_content(caplog) -> None:
    conversation_id = "raw-conversation-id-must-not-be-logged"
    question = "What is FOSSIL?"
    request_id = "req-observability-1"
    kernel = fixture_kernel()
    client = TestClient(create_app(lambda: kernel))
    caplog.set_level(logging.INFO, logger="handsfree_portfolio.turn")

    with client.stream(
        "POST",
        f"/v1/conversations/{conversation_id}/turns",
        headers={"X-Request-ID": request_id},
        json={"question": question},
    ) as response:
        assert response.status_code == 200
        assert response.headers["x-request-id"] == request_id
        "".join(response.iter_text())

    records = [record for record in caplog.records if record.name == "handsfree_portfolio.turn"]
    assert len(records) == 1
    encoded = records[0].getMessage()
    summary = json.loads(encoded)
    assert summary["event"] == "portfolio.turn.summary"
    assert summary["requestId"] == request_id
    assert summary["outcome"] == "complete"
    assert summary["retrievalLane"] == "retrieval"
    assert summary["cacheHit"] is False
    assert summary["cacheRevalidation"] == "not_applicable"
    assert summary["answerContractVersion"] == "1.0.0"
    assert summary["turnId"]
    assert summary["generation"] == 1
    assert summary["claimIds"]
    assert summary["evidenceIds"]
    assert len(summary["conversationHash"]) == 24
    assert conversation_id not in encoded
    assert question not in encoded
    assert "question" not in summary
    assert "audio" not in summary
    assert "voice" not in summary


def test_blank_question_rejected_before_streaming() -> None:
    client = TestClient(create_app(fixture_kernel))
    response = client.post("/v1/conversations/c/turns", json={"question": "   "})
    assert response.status_code == 422


def test_unconfigured_runtime_fails_closed_instead_of_using_fake_answers() -> None:
    def unavailable():
        raise RuntimeConfigurationError("real public pack not configured")

    client = TestClient(create_app(unavailable))
    response = client.post("/v1/conversations/c/turns", json={"question": "What is FOSSIL?"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
