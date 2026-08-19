from __future__ import annotations

import json
from collections.abc import Callable, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from handsfree_portfolio.application.conversation_kernel import ConversationKernel
from handsfree_portfolio.delivery.composition import RuntimeConfigurationError, runtime_kernel


class TurnRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def encode_sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}\n\n"


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
    def stream_turn(conversation_id: str, request: TurnRequest) -> StreamingResponse:
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=422, detail="question must not be blank")
        kernel = configured_kernel()

        def event_stream() -> Iterator[str]:
            for event in kernel.stream_turn(conversation_id=conversation_id, question=question):
                yield encode_sse(event.type, event.to_contract())

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
