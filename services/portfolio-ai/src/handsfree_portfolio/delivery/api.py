from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from handsfree_portfolio.adapters.fakes import FakeKnowledge, FakePlanner, FakeRenderer, FakeVerifier
from handsfree_portfolio.application.answer_turn import AnswerTurn, GroundingFailure

app = FastAPI(title="Handsfree Portfolio AI", version="0.1.0")
use_case = AnswerTurn(
    knowledge=FakeKnowledge(),
    planner=FakePlanner(),
    renderer=FakeRenderer(),
    verifier=FakeVerifier(),
)


class TurnRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    generation: int = Field(ge=0)


class EvidenceResponse(BaseModel):
    evidenceId: str
    label: str
    sourceRef: str


class TurnResponse(BaseModel):
    turnId: str
    generation: int
    text: str
    evidence: list[EvidenceResponse]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/turns", response_model=TurnResponse)
def answer_turn(request: TurnRequest) -> TurnResponse:
    try:
        answer = use_case.execute(question=request.question, generation=request.generation)
    except GroundingFailure as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TurnResponse(
        turnId=answer.turn_id,
        generation=answer.generation,
        text=answer.text,
        evidence=[
            EvidenceResponse(evidenceId=item.evidence_id, label=item.label, sourceRef=item.source_ref)
            for item in answer.evidence
        ],
    )
