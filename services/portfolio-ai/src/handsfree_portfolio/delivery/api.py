from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable, Iterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.delivery.composition import RuntimeConfigurationError, runtime_kernel


LOGGER = logging.getLogger("handsfree_portfolio.turn")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class TurnRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def encode_sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}\n\n"


def _safe_request_id(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate and _REQUEST_ID.fullmatch(candidate):
        return candidate
    return uuid4().hex


def _conversation_hash(conversation_id: str) -> str:
    return hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:24]


def _log_turn_summary(
    *,
    request_id: str,
    conversation_id: str,
    started_at: float,
    turn_id: str | None,
    generation: int | None,
    outcome: str,
    retrieval_started: bool,
    claim_ids: list[str],
    evidence_ids: list[str],
) -> None:
    cache_hit = outcome == "complete" and not retrieval_started
    payload = {
        "event": "portfolio.turn.summary",
        "requestId": request_id,
        "conversationHash": _conversation_hash(conversation_id),
        "turnId": turn_id,
        "generation": generation,
        "outcome": outcome,
        "durationMs": round((time.monotonic() - started_at) * 1000, 3),
        "retrievalLane": "retrieval" if retrieval_started else ("cache" if cache_hit else "none"),
        "cacheHit": cache_hit,
        "cacheRevalidation": "passed" if cache_hit else "not_applicable",
        "answerContractVersion": "1.0.0",
        "claimIds": claim_ids,
        "evidenceIds": evidence_ids,
    }
    LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def create_app(kernel_provider: Callable[[], ConversationKernel] = runtime_kernel) -> FastAPI:
    app = FastAPI(title="Handsfree Portfolio AI", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    def configured_kernel() -> ConversationKernel:
        try:
            return kernel_provider()
        except RuntimeConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/v1/conversations/{conversation_id}/state")
    def conversation_state(conversation_id: str) -> dict:
        kernel = configured_kernel()
        return kernel.sessions.get(conversation_id).to_contract()

    @app.post("/v1/conversations/{conversation_id}/turns")
    def stream_turn(
        conversation_id: str,
        turn_request: TurnRequest,
        http_request: Request,
    ) -> StreamingResponse:
        question = turn_request.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="question must not be blank")
        kernel = configured_kernel()
        request_id = _safe_request_id(http_request.headers.get("x-request-id"))
        started_at = time.monotonic()

        def event_stream() -> Iterator[str]:
            retrieval_started = False
            turn_id: str | None = None
            generation: int | None = None
            claim_ids: list[str] = []
            evidence_ids: list[str] = []
            terminal_logged = False
            try:
                for event in kernel.stream_turn(conversation_id=conversation_id, question=question):
                    turn_id = event.turn_id
                    generation = event.generation
                    if event.type == "retrieval.started":
                        retrieval_started = True
                    if event.type in {"answer.grounded", "turn.complete"}:
                        claim_ids = [str(value) for value in event.payload.get("claimIds", claim_ids)]
                        evidence_ids = [str(value) for value in event.payload.get("evidenceIds", evidence_ids)]
                    if event.type in {"turn.complete", "turn.cancelled"}:
                        outcome = "complete" if event.type == "turn.complete" else "cancelled"
                        _log_turn_summary(
                            request_id=request_id,
                            conversation_id=conversation_id,
                            started_at=started_at,
                            turn_id=turn_id,
                            generation=generation,
                            outcome=outcome,
                            retrieval_started=retrieval_started,
                            claim_ids=claim_ids,
                            evidence_ids=evidence_ids,
                        )
                        terminal_logged = True
                    yield encode_sse(event.type, event.to_contract())
            finally:
                if not terminal_logged:
                    _log_turn_summary(
                        request_id=request_id,
                        conversation_id=conversation_id,
                        started_at=started_at,
                        turn_id=turn_id,
                        generation=generation,
                        outcome="stream_ended_without_terminal_event",
                        retrieval_started=retrieval_started,
                        claim_ids=claim_ids,
                        evidence_ids=evidence_ids,
                    )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Request-ID": request_id,
            },
        )

    return app


app = create_app()
