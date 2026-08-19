from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ConversationStatus = Literal["idle", "retrieving", "rendering", "complete", "cancelled", "error"]
TurnEventType = Literal[
    "turn.accepted",
    "retrieval.started",
    "evidence.found",
    "answer.planned",
    "answer.delta",
    "answer.grounded",
    "turn.complete",
    "turn.cancelled",
]


@dataclass(frozen=True)
class ConversationState:
    conversation_id: str
    active_generation: int = 0
    status: ConversationStatus = "idle"
    active_subject: str | None = None
    referents: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TurnEvent:
    turn_id: str
    generation: int
    type: TurnEventType
    occurred_at: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_contract(self) -> dict[str, Any]:
        return {
            "contractVersion": "1.0.0",
            "turnId": self.turn_id,
            "generation": self.generation,
            "type": self.type,
            "occurredAt": self.occurred_at,
            "payload": self.payload,
        }


__all__ = ["ConversationState", "ConversationStatus", "TurnEvent", "TurnEventType"]
